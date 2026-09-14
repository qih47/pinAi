import re
import asyncio
import logging
from typing import List, Optional, Dict, Any, AsyncGenerator
from urllib.parse import urlparse
import httpx

logger = logging.getLogger("cakra.web_tools")

# Attempt to import crawl4ai
try:
    from crawl4ai import AsyncWebCrawler
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    logger.warning("crawl4ai is not installed. URL Reader will fallback to fast HTTP.")

_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}


_IGNORED_DOMAINS = {
    "registry.npmjs.org", "pypi.org", "files.pythonhosted.org",
    "repo.maven.apache.org", "rubygems.org", "crates.io",
    "localhost", "127.0.0.1", "0.0.0.0", "example.com"
}

_PACKAGE_EXTENSIONS = (".tgz", ".whl", ".tar.gz", ".zip", ".bin", ".iso", ".gz", ".exe", ".dmg", ".pkg")

_ERROR_LOG_SIGNALS = (
    "npm err", "yarn error", "pnpm err", "pip error", "traceback (most recent call last)",
    "stacktrace", "exception in thread", "fatal error", "failed to fetch",
    "404 not found", "connection refused", "econnrefused", "etimedout", "err_connection",
    "status code: 4", "status code: 5", "error:", "exception:", "stderr:", "failed on",
    "failed to", "download failed", "wget ", "curl -", "git clone", "docker run",
    "log:", "logs:", "warning:", "warn:"
)

_EXPLICIT_READ_SIGNALS = (
    "baca link", "baca url", "baca tautan", "baca web", "baca artikel", "baca halaman",
    "baca ini", "buka link", "buka url", "buka web", "buka tautan", "isi tautan",
    "isi link", "isi web", "isi url", "apa isi", "ringkas link", "ringkas url",
    "ringkas tautan", "ringkasan dari", "rangkum link", "rangkum url", "rangkum web",
    "cek link", "cek url", "kunjungi", "analisis web", "analisis url", "analisis link",
    "simpulkan link", "telaah link", "bedah link"
)

_SEARCH_INTENT_SIGNALS = (
    "cari", "carikan", "search", "googling", "berita", "kabar", "terkini", "terbaru",
    "info", "informasi", "cek berita", "apa kabar", "kabar di", "berita di"
)


def is_incidental_url(url: str, full_text: str = "") -> bool:
    """
    Memeriksa apakah URL adalah URL insidental (bagian dari error log, package manager registry,
    snippet kode, atau sekadar penyebutan domain dalam konteks web search) yang TIDAK dimaksudkan
    untuk di-scrape langsung oleh URL Reader.
    """
    url_lower = url.lower()

    # 1. Cek domain terabaikan (registry, localhost, dll)
    for ign in _IGNORED_DOMAINS:
        if ign in url_lower:
            return True

    # 2. Cek ekstensi file arsip/package
    if any(url_lower.endswith(ext) for ext in _PACKAGE_EXTENSIONS):
        return True

    # 3. Jika ada full_text, periksa apakah berada di konteks error log atau search
    if full_text:
        text_lower = full_text.lower()
        has_explicit_read = any(sig in text_lower for sig in _EXPLICIT_READ_SIGNALS)
        has_error = any(sig in text_lower for sig in _ERROR_LOG_SIGNALS)
        
        # 3a. Berada di dalam pesan error / log instalasi tanpa instruksi eksplisit membaca link
        if has_error and not has_explicit_read:
            return True

        # 3b. Cek apakah URL hanya muncul di dalam blok kode (```...```)
        code_blocks = re.findall(r'```[\s\S]*?```', full_text)
        if code_blocks:
            url_in_code = any(url in cb or url.replace('https://', '') in cb or url.replace('http://', '') in cb for cb in code_blocks)
            text_without_code = re.sub(r'```[\s\S]*?```', '', full_text)
            url_outside_code = url in text_without_code or url.replace('https://', '') in text_without_code or url.replace('http://', '') in text_without_code
            if url_in_code and not url_outside_code and not has_explicit_read:
                return True

    return False


def extract_urls_from_text(text: str) -> List[str]:
    """
    Ekstrak semua URL yang ada di dalam teks, menyaring URL insidental dari log error/koding.
    """
    if not text:
        return []

    url_pattern = re.compile(
        r'(?:https?://)?(?:www\.)?[-a-zA-Z0-9@:%_\+~#=]{1,256}\s*\.\s*(?:com|co\.id|id|org|net|gov|edu|mil)\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)',
        re.IGNORECASE
    )

    matches = url_pattern.findall(text)

    valid_urls = []
    for match in matches:
        clean_match = match.replace(' ', '')
        if not clean_match.startswith('http://') and not clean_match.startswith('https://'):
            url_to_check = f'https://{clean_match}'
        else:
            url_to_check = clean_match

        if not is_incidental_url(url_to_check, text):
            valid_urls.append(url_to_check)

    return valid_urls


def _clean_html_to_markdown(html_text: str) -> str:
    """
    Fast-path HTML to clean Markdown text extractor (0ms execution).
    Menghilangkan tag script/style/nav dan mengekstrak struktur teks utama.
    """
    if not html_text:
        return ""
    
    # 1. Hapus scripts, styles, metadata, comments
    text = re.sub(r'<!--.*?-->', '', html_text, flags=re.DOTALL)
    text = re.sub(r'<(script|style|nav|footer|header|aside|noscript|svg|iframe)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # 2. Tangkap Judul Halaman
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html_text, flags=re.IGNORECASE | re.DOTALL)
    page_title = title_match.group(1).strip() if title_match else ""
    
    # 3. Format heading & list
    text = re.sub(r'<h[1-3][^>]*>(.*?)</h[1-3]>', r'\n\n### \1\n', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<h[4-6][^>]*>(.*?)</h[4-6]>', r'\n\n#### \1\n', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'\n• \1', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\n\1', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<br\s*/?>', r'\n', text, flags=re.IGNORECASE)
    
    # 4. Hapus sisa HTML tag
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # 5. Decode HTML entities umum
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
    
    # 6. Bersihkan spasi & newline berlebihan
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    cleaned_body = '\n\n'.join(lines)
    
    if page_title and not cleaned_body.startswith(f"### {page_title}"):
        return f"# {page_title}\n\n{cleaned_body}"
    return cleaned_body


async def _fetch_fast_http(url: str) -> Optional[str]:
    """
    Tier 1: Fast-Path Scraping menggunakan async HTTPX (~150-300ms).
    """
    try:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True, headers=_HTTP_HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.text:
                markdown = _clean_html_to_markdown(resp.text)
                if len(markdown) >= 150:
                    logger.info(f"[URL Reader] ⚡ Fast-Path HTTP success for '{url}' ({len(markdown)} chars)")
                    return markdown
    except Exception as e:
        logger.debug(f"[URL Reader] Fast-Path HTTP skipped/failed for '{url}': {e}")
    return None


async def _fetch_crawl4ai(url: str) -> Optional[str]:
    """
    Tier 2: Fallback Headless Chromium (Crawl4AI) untuk SPA / JS-heavy websites.
    """
    if not CRAWL4AI_AVAILABLE:
        return None
    try:
        logger.info(f"[URL Reader] 🌐 Tier 2 Headless Browser fallback for: {url}")
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
            markdown_content = result.markdown
            if markdown_content and len(markdown_content) > 40000:
                markdown_content = markdown_content[:40000] + "\n\n...[CONTENT TRUNCATED]..."
            return markdown_content
    except Exception as e:
        logger.error(f"[URL Reader] Tier 2 Crawl4AI failed for {url}: {e}")
        return None


async def fetch_webpage_content(url: str) -> Optional[str]:
    """
    Tiered Web Scraper:
    1. Coba Fast-Path HTTP (~200ms)
    2. Fallback ke Headless Chromium jika halaman butuh JS rendering
    """
    logger.info(f"[URL Reader] Fetching content for: {url}")
    
    # Tier 1: Fast-Path HTTP
    fast_content = await _fetch_fast_http(url)
    if fast_content:
        return fast_content
    
    # Tier 2: Headless Browser Fallback
    return await _fetch_crawl4ai(url)


def extract_url_display_info(url: str) -> Dict[str, str]:
    """
    Ekstrak metadata tampilan URL untuk widget timeline (domain, title/path, clean url).
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        
        if path_parts:
            raw_title = path_parts[-1]
            raw_title = re.sub(r'\.(html|php|asp|htm)$', '', raw_title)
            title = raw_title.replace("-", " ").replace("_", " ")
        else:
            title = domain
            
        return {
            "url": url,
            "title": title,
            "domain": domain
        }
    except Exception:
        return {
            "url": url,
            "title": url,
            "domain": url
        }


async def fetch_urls_progressive(urls: List[str]) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Generator asinkron yang melakukan fetch paralel untuk semua URL
    namun tetap memancarkan progress event secara progresif.
    """
    async def _fetch_single(u: str) -> Dict[str, Any]:
        display_info = extract_url_display_info(u)
        content = await fetch_webpage_content(u)
        return {
            "url": u,
            "title": display_info["title"],
            "domain": display_info["domain"],
            "content": content,
            "success": bool(content)
        }

    # Jalankan fetch secara paralel menggunakan asyncio.as_completed
    tasks = [_fetch_single(url) for url in urls]
    for fut in asyncio.as_completed(tasks):
        result = await fut
        yield result


async def fetch_multiple_urls(urls: List[str]) -> str:
    """
    Mengambil banyak URL secara paralel dan merangkai menjadi satu teks context.
    """
    tasks = [fetch_webpage_content(url) for url in urls]
    results = await asyncio.gather(*tasks)
    
    combined_text = ""
    for url, content in zip(urls, results):
        if content:
            combined_text += f"\n\n==== ISI WEB: {url} ====\n\n{content}\n\n========================\n"
        else:
            combined_text += f"\n\n[Gagal membaca isi web dari {url}]\n"
            
    return combined_text
