"""
CAKRA AI — Security Firewall Hub
=================================

Multi-layer defense-in-depth security module.

Layer 1  — Rate Limiting        : Per-IP sliding window, burst protection
Layer 2  — Input Validation     : Size, encoding, null byte, control char
Layer 3  — Injection Detection  : SQLi, XSS, SSTI, Path Traversal, Command Injection
Layer 4  — Content Safety       : Prohibited content (NSFW, violence, SARA)
Layer 5  — Attachment Security  : MIME sniffing, magic bytes, filename sanitization
Layer 6  — Semantic Anomaly     : Prompt injection, jailbreak pattern detection

Design principles:
  - Fail-closed: unknown errors → reject, not allow
  - Silent logging: never expose detection logic in error messages
  - Layered: each layer independent, no single point of failure
  - Performance: fast-path short-circuit before expensive checks
"""

import re
import json
import time
import hashlib
import logging
import unicodedata
from collections import defaultdict, deque
from threading import Lock
from typing import Any, Optional
from fastapi import HTTPException, Request, UploadFile

logger = logging.getLogger("CAKRA_SECURITY")


# ==============================================================================
# LAYER 1: RATE LIMITING — Sliding Window per IP
# ==============================================================================

class SlidingWindowRateLimiter:
    """
    Thread-safe sliding window rate limiter.
    Tracks request timestamps per key (IP or NPP) in a fixed-size deque.
    """
    def __init__(self):
        self._windows: dict[str, deque] = defaultdict(lambda: deque())
        self._lock = Lock()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            dq = self._windows[key]
            # Evict expired timestamps
            while dq and dq[0] < cutoff:
                dq.popleft()

            if len(dq) >= max_requests:
                logger.warning(
                    f"[RATE_LIMIT] Key '{key}' exceeded {max_requests} req/{window_seconds}s"
                )
                return False

            dq.append(now)
            return True

    def get_remaining(self, key: str, max_requests: int, window_seconds: int) -> int:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            dq = self._windows[key]
            active = sum(1 for t in dq if t >= cutoff)
            return max(0, max_requests - active)


# Global singleton
_rate_limiter = SlidingWindowRateLimiter()

# Rate limit policies (tunable)
_POLICY_CHAT     = (60, 60)    # 60 req per 60s per IP (chat endpoints)
_POLICY_UPLOAD   = (10, 300)   # 10 uploads per 5 min per IP
_POLICY_AUTH     = (10, 60)    # 10 auth attempts per 60s (brute-force guard)
_POLICY_GLOBAL   = (200, 60)   # 200 total req per 60s per IP (DDoS floor)


def check_rate_limit(client_ip: str, policy: str = "chat") -> bool:
    """
    Check rate limit for a given IP and policy.
    Returns True if allowed, False if throttled.
    """
    policies = {
        "chat":   _POLICY_CHAT,
        "upload": _POLICY_UPLOAD,
        "auth":   _POLICY_AUTH,
        "global": _POLICY_GLOBAL,
    }
    max_req, window = policies.get(policy, _POLICY_GLOBAL)
    key = f"{policy}:{client_ip}"
    return _rate_limiter.is_allowed(key, max_req, window)


# ==============================================================================
# LAYER 2: INPUT VALIDATION
# ==============================================================================

_MAX_BODY_SIZE    = 512 * 1024          # 512 KB JSON body hard cap
_MAX_STRING_LEN   = 32_768             # 32 KB per string field
_MAX_ARRAY_ITEMS  = 200                # Max items in any array
_MAX_NESTING      = 10                 # Max JSON nesting depth

_NULL_BYTE_PATTERN    = re.compile(r"\x00")
_CONTROL_CHAR_PATTERN = re.compile(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _check_string_safety(text: str, field_name: str = "field") -> None:
    """Validate a single string: length, null bytes, control chars, encoding."""
    if len(text) > _MAX_STRING_LEN:
        logger.warning(f"[INPUT_VALIDATION] Field '{field_name}' exceeds max length ({len(text)} chars)")
        raise HTTPException(status_code=400, detail="Input terlalu panjang.")

    if _NULL_BYTE_PATTERN.search(text):
        logger.warning(f"[INPUT_VALIDATION] Null byte detected in '{field_name}'")
        raise HTTPException(status_code=400, detail="Input tidak valid.")

    if _CONTROL_CHAR_PATTERN.search(text):
        logger.warning(f"[INPUT_VALIDATION] Control characters detected in '{field_name}'")
        raise HTTPException(status_code=400, detail="Input mengandung karakter tidak valid.")

    # Unicode normalization check — catch homoglyph attacks
    try:
        normalized = unicodedata.normalize("NFKC", text)
        # If normalization changes the string significantly, flag it
        if len(normalized) != len(text) and abs(len(normalized) - len(text)) > 10:
            logger.info(f"[INPUT_VALIDATION] Unicode normalization delta in '{field_name}': {len(text)}→{len(normalized)}")
    except Exception:
        pass  # Non-fatal


def _check_depth(data: Any, depth: int = 0) -> None:
    if depth > _MAX_NESTING:
        logger.warning(f"[INPUT_VALIDATION] JSON nesting exceeds max depth {_MAX_NESTING}")
        raise HTTPException(status_code=400, detail="Struktur data terlalu dalam.")
    if isinstance(data, dict):
        for v in data.values():
            _check_depth(v, depth + 1)
    elif isinstance(data, list):
        if len(data) > _MAX_ARRAY_ITEMS:
            raise HTTPException(status_code=400, detail="Array terlalu banyak elemen.")
        for item in data:
            _check_depth(item, depth + 1)


# ==============================================================================
# LAYER 3: INJECTION DETECTION
# ==============================================================================

# SQL Injection — covers UNION, stacked queries, comment injection, blind SQLi
_SQLI_PATTERNS = [
    re.compile(r"(?i)\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|CAST|CONVERT)\b\s+\w"),
    re.compile(r"(?i)\bUNION\b.{0,30}\bSELECT\b"),
    re.compile(r"(?i)\bOR\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?"),   # OR 1=1
    re.compile(r"(?i)\bAND\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?"),  # AND 1=1
    re.compile(r"--\s"),                                                    # SQL comment
    re.compile(r";\s*(DROP|DELETE|INSERT|UPDATE)", re.IGNORECASE),          # Stacked
    re.compile(r"(?i)\bWAITFOR\b\s+DELAY"),                               # Time-based blind
    re.compile(r"(?i)\bSLEEP\s*\("),                                       # MySQL blind
    re.compile(r"(?i)'\s*OR\s*'[^']*'\s*=\s*'"),                         # Classic ' OR 'x'='x
    re.compile(r"(?i)xp_cmdshell"),                                        # MSSQL RCE
]

# XSS — covers reflected, stored, DOM, polyglot
_XSS_PATTERNS = [
    re.compile(r"(?i)<\s*script[^>]*>"),
    re.compile(r"(?i)</\s*script\s*>"),
    re.compile(r"(?i)javascript\s*:"),
    re.compile(r"(?i)vbscript\s*:"),
    re.compile(r"(?i)on\w+\s*=\s*['\"]?[^'\"]{0,200}(alert|eval|document|window|location)", re.IGNORECASE),
    re.compile(r"(?i)<\s*iframe[^>]*>"),
    re.compile(r"(?i)<\s*img[^>]*onerror\s*="),
    re.compile(r"(?i)expression\s*\("),                 # IE CSS expression
    re.compile(r"(?i)data\s*:\s*text/html"),            # data: URI XSS
    re.compile(r"(?i)<\s*svg[^>]*onload\s*="),
]

# Server-Side Template Injection (SSTI)
_SSTI_PATTERNS = [
    re.compile(r"\{\{.*?\}\}"),            # Jinja2 / Vue
    re.compile(r"\{%.*?%\}"),             # Jinja2 block
    re.compile(r"\$\{.*?\}"),             # JS template / FreeMarker
    re.compile(r"#\{.*?\}"),              # Ruby / Thymeleaf
    re.compile(r"<%.*?%>"),               # JSP / ASP
    re.compile(r"(?i)\{\{7\s*\*\s*7\}\}"),  # Classic SSTI detection payload
]

# Path Traversal
_PATH_TRAVERSAL_PATTERNS = [
    re.compile(r"\.\./"),
    re.compile(r"\.\.\\"),
    re.compile(r"%2e%2e%2f", re.IGNORECASE),   # URL encoded ../
    re.compile(r"%2e%2e/", re.IGNORECASE),
    re.compile(r"\.\.%2f", re.IGNORECASE),
    re.compile(r"(?i)/etc/passwd"),
    re.compile(r"(?i)/etc/shadow"),
    re.compile(r"(?i)c:\\\\windows"),
    re.compile(r"(?i)/proc/self"),
]

# Command Injection
_CMDI_PATTERNS = [
    re.compile(r"(?:;|\||&&|\$\(|\`)\s*(?:ls|cat|pwd|whoami|id|uname|curl|wget|nc|bash|sh|python|perl|ruby|php)", re.IGNORECASE),
    re.compile(r"\$\(.*?\)"),             # $(command)
    re.compile(r"`[^`]{2,100}`"),         # backtick execution
    re.compile(r"(?i)\|\s*bash"),
    re.compile(r"(?i)&&\s*rm\s+-rf"),
]

# Prompt Injection / Jailbreak — protect LLM from manipulation
_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context)"),
    re.compile(r"(?i)you\s+are\s+now\s+(a\s+)?(DAN|jailbreak|unrestricted|free|uncensored)"),
    re.compile(r"(?i)(pretend|act|roleplay|imagine|simulate)\s+(you\s+)?(are|as)\s+(a\s+)?(different|new|other|evil|bad)"),
    re.compile(r"(?i)system\s*prompt\s*[:=]"),
    re.compile(r"(?i)(reveal|show|print|output|display|expose)\s+(your\s+)?(system\s+)?(prompt|instruction|secret|rule)"),
    re.compile(r"(?i)bypass\s+(safety|filter|content|restriction|policy|guideline)"),
    re.compile(r"(?i)do\s+anything\s+now"),          # DAN pattern
    re.compile(r"(?i)jailbreak"),
    re.compile(r"(?i)override\s+(your\s+)?(programming|training|instruction)"),
    re.compile(r"(?i)<\s*/?system\s*>"),              # Fake system tags
    re.compile(r"(?i)\[INST\]"),                      # LLaMA instruction injection
    re.compile(r"(?i)###\s*instruction"),             # Alpaca-style injection
]

_ALL_INJECTION_CHECKS = [
    ("SQLi",             _SQLI_PATTERNS),
    ("XSS",              _XSS_PATTERNS),
    ("SSTI",             _SSTI_PATTERNS),
    ("PathTraversal",    _PATH_TRAVERSAL_PATTERNS),
    ("CommandInjection", _CMDI_PATTERNS),
    ("PromptInjection",  _PROMPT_INJECTION_PATTERNS),
]


def _scan_for_injections(text: str, field_name: str = "input") -> None:
    """Run all injection pattern checks on a string. Raises 403 on detection."""
    for attack_type, patterns in _ALL_INJECTION_CHECKS:
        for pattern in patterns:
            if pattern.search(text):
                logger.warning(
                    f"[INJECTION] {attack_type} detected in '{field_name}' "
                    f"from hash={hashlib.sha256(text.encode()).hexdigest()[:12]}"
                )
                # Generic error — never reveal what was detected
                raise HTTPException(status_code=403, detail="Permintaan tidak valid.")


def _scan_dict_recursive(data: Any, path: str = "root") -> None:
    """Recursively scan all string values in nested dicts/lists."""
    if isinstance(data, str):
        _check_string_safety(data, path)
        _scan_for_injections(data, path)
    elif isinstance(data, dict):
        for k, v in data.items():
            _scan_for_injections(str(k), f"{path}.key")
            _scan_dict_recursive(v, f"{path}.{k}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            _scan_dict_recursive(item, f"{path}[{i}]")


# ==============================================================================
# LAYER 4: CONTENT SAFETY
# ==============================================================================

# Exact banned phrases (word boundary match, case-insensitive)
_BANNED_EXACT = {
    # NSFW ID
    "bokep", "ngentot", "memek", "kontol", "jembut", "bugil",
    "telanjang", "colmek", "coli", "toket", "pepek", "ngewe",
    # NSFW EN
    "porn", "porno", "xxx", "nsfw", "nude",
    "blowjob", "handjob", "cumshot", "creampie",
    "milf", "onlyfans", "deepfake", "upskirt",
    # Violence / threat ID
    "bunuh diri", "ngebom", "meledakkan", "membunuh semua",
    # Violence / threat EN
    "mass murder", "school shooting", "suicide method", "how to bomb",
    # SARA / Hate
    "kafir bajingan", "dasar babi",
}

# Regex for contextual patterns (not whole-word, broader match)
_BANNED_PATTERNS = [
    re.compile(r"(?i)\bperkosa\b"),
    re.compile(r"(?i)\brape\b"),
    re.compile(r"(?i)\bpedoph[il]+e?\b"),
    re.compile(r"(?i)\bpedofil\b"),
    re.compile(r"(?i)\bterori[s]+(me|t)?\b"),
    re.compile(r"(?i)\bjihadis[m]?\b"),
    re.compile(r"(?i)\bchild\s+(porn|sex|abuse)\b"),
    re.compile(r"(?i)\bcp\s+link\b"),
    re.compile(r"(?i)cara\s+(membuat\s+)?(bom|racun|senjata\s+api)"),
    re.compile(r"(?i)how\s+to\s+(make\s+)?(bomb|poison|weapon)"),
]


def contains_prohibited_content(text: str) -> bool:
    """
    Returns True if text contains prohibited content.
    Checks exact banned words (word-boundary) and regex patterns.
    """
    if not text:
        return False

    text_lower = text.lower()

    # Exact word match with boundary
    for word in _BANNED_EXACT:
        pattern = r"(?<!\w)" + re.escape(word) + r"(?!\w)"
        if re.search(pattern, text_lower):
            logger.warning(f"[CONTENT_FILTER] Prohibited term matched (hash={hashlib.sha256(word.encode()).hexdigest()[:8]})")
            return True

    # Contextual regex patterns
    for pat in _BANNED_PATTERNS:
        if pat.search(text):
            logger.warning(f"[CONTENT_FILTER] Prohibited pattern matched")
            return True

    return False


def assert_safe_content(text: str) -> None:
    """Raises HTTPException 400 if prohibited content detected."""
    if contains_prohibited_content(text):
        raise HTTPException(
            status_code=400,
            detail="Pesan Anda melanggar Kebijakan Penggunaan Cakra AI."
        )


# ==============================================================================
# LAYER 5: ATTACHMENT SECURITY
# ==============================================================================

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_FILE_SIZE = 20 * 1024 * 1024   # 20 MB

# Magic bytes map: mime → (allowed_signatures, description)
_MAGIC_BYTES: dict[str, list[bytes]] = {
    "application/pdf":       [b"%PDF-"],
    "image/jpeg":            [b"\xff\xd8\xff"],
    "image/png":             [b"\x89PNG\r\n\x1a\n"],
    "image/webp":            [b"RIFF"],
    # DOCX / XLSX / PPTX are all ZIP-based
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [b"PK\x03\x04"],
}

# Filename: only alphanumeric, dash, underscore, dot — no traversal characters
_SAFE_FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,255}$")
_DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".ps1", ".msi", ".dll", ".so",
    ".php", ".py", ".rb", ".js", ".vbs", ".jar", ".class",
    ".scr", ".com", ".pif", ".gadget", ".hta", ".wsf", ".lnk",
}


async def validate_attachment_security(file: UploadFile) -> None:
    """
    Multi-layer attachment validation:
      1. Filename safety (anti path-traversal, dangerous extension)
      2. MIME type whitelist
      3. File size limit
      4. Magic bytes verification (anti-spoofing)
      5. Content scan for embedded scripts (basic)
    """
    filename = file.filename or "unknown"

    # 1. Filename sanitization
    if ".." in filename or "/" in filename or "\\" in filename:
        logger.warning(f"[ATTACHMENT] Path traversal attempt: '{filename}'")
        raise HTTPException(status_code=400, detail="Nama file tidak valid.")

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _DANGEROUS_EXTENSIONS:
        logger.warning(f"[ATTACHMENT] Dangerous extension blocked: '{ext}'")
        raise HTTPException(status_code=400, detail="Tipe file tidak diizinkan.")

    safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", filename)
    if not _SAFE_FILENAME_PATTERN.match(safe_name):
        logger.warning(f"[ATTACHMENT] Filename failed sanitization: '{filename}'")
        raise HTTPException(status_code=400, detail="Nama file mengandung karakter tidak valid.")

    # 2. MIME type whitelist
    if file.content_type not in ALLOWED_MIME_TYPES:
        logger.warning(f"[ATTACHMENT] Blocked MIME type: '{file.content_type}'")
        raise HTTPException(status_code=400, detail="Tipe file tidak diizinkan.")

    # 3. Read header for magic byte check + size estimation
    header_bytes = await file.read(4096)
    await file.seek(0)

    # 4. Magic byte verification
    expected_signatures = _MAGIC_BYTES.get(file.content_type)
    if expected_signatures:
        if not any(header_bytes.startswith(sig) for sig in expected_signatures):
            logger.warning(
                f"[ATTACHMENT] Magic byte mismatch for MIME '{file.content_type}' "
                f"in file '{filename}' — possible spoofing"
            )
            raise HTTPException(status_code=400, detail="File corrupt atau tipe tidak sesuai.")

    # 5. File size check
    try:
        file.file.seek(0, 2)
        file_size = file.file.tell()
        await file.seek(0)
    except Exception:
        file_size = len(header_bytes)

    if file_size > MAX_FILE_SIZE:
        logger.warning(f"[ATTACHMENT] File too large: {file_size} bytes from '{filename}'")
        raise HTTPException(status_code=413, detail="Ukuran file maksimal adalah 20MB.")

    # 6. Basic embedded script scan for text-based files (txt, csv)
    if file.content_type in ("text/plain", "text/csv"):
        try:
            sample = header_bytes.decode("utf-8", errors="replace")
            _scan_for_injections(sample, f"attachment:{filename}")
        except Exception:
            pass  # Non-fatal for binary-safe formats

    logger.info(f"✅ [ATTACHMENT] '{safe_name}' passed all security checks ({file_size} bytes)")


# ==============================================================================
# LAYER 6 (integrated in Layer 3): PROMPT INJECTION detection
# Already embedded in _PROMPT_INJECTION_PATTERNS above.
# ==============================================================================


# ==============================================================================
# FASTAPI DEPENDENCY — Central Security Firewall
# ==============================================================================

async def security_firewall_dependency(request: Request) -> None:
    """
    FastAPI Depends() entry point.
    Runs on every request before the endpoint handler.

    Checks (in order):
      1. Global rate limit per IP
      2. URL path safety
      3. Query parameter injection scan
      4. JSON body: size cap, depth, injection scan
    """
    client_ip = request.client.host if request.client else "unknown"

    # 1. Global rate limit
    if not check_rate_limit(client_ip, "global"):
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak request. Silakan tunggu sebentar."
        )

    # 2. URL path scan
    raw_path = request.url.path
    try:
        _scan_for_injections(raw_path, "url_path")
    except HTTPException:
        logger.warning(f"[FIREWALL] Malicious URL path from {client_ip}: {raw_path[:100]}")
        raise

    # 3. Query params scan
    for param, value in request.query_params.items():
        try:
            _scan_for_injections(param, f"query_key:{param}")
            _scan_for_injections(value, f"query_val:{param}")
        except HTTPException:
            logger.warning(f"[FIREWALL] Malicious query param '{param}' from {client_ip}")
            raise

    # 4. JSON body — only for application/json requests
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body_bytes = await request.body()

            # Hard size cap before parsing
            if len(body_bytes) > _MAX_BODY_SIZE:
                logger.warning(
                    f"[FIREWALL] Body too large: {len(body_bytes)} bytes from {client_ip}"
                )
                raise HTTPException(status_code=413, detail="Request body terlalu besar.")

            if body_bytes:
                try:
                    body_json = json.loads(body_bytes)
                except json.JSONDecodeError:
                    # Malformed JSON — let Pydantic handle it downstream
                    return

                # Depth check first (fast)
                _check_depth(body_json)

                # Recursive injection + input validation scan
                _scan_dict_recursive(body_json)

        except HTTPException:
            raise
        except Exception as e:
            # Unexpected error in firewall — log but don't expose details
            logger.error(f"[FIREWALL] Unexpected error during body scan: {e}")
            # Fail-closed on unexpected errors
            raise HTTPException(status_code=400, detail="Request tidak dapat diproses.")