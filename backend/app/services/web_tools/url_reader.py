import re
import asyncio
import logging
from typing import List, Optional, Dict, Any, AsyncGenerator, Tuple
from urllib.parse import urlparse, urljoin
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


_STATIC_FILE_EXTENSIONS = (
    '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', 
    '.pdf', '.zip', '.tar', '.gz', '.mp4', '.mp3', '.css', '.js', '.woff', '.woff2'
)

def _extract_internal_candidate_links(html_text: str, base_url: str) -> List[Dict[str, str]]:
    """
    Ekstrak daftar link internal dari HTML sebelum tag nav/a dibersihkan.
    """
    if not html_text:
        return []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_text, 'html.parser')
        base_domain = urlparse(base_url).netloc.replace("www.", "")
        candidates = []
        seen = set()
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            if parsed.netloc.replace("www.", "") != base_domain:
                continue
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in _STATIC_FILE_EXTENSIONS):
                continue
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if clean_url in seen or clean_url.rstrip('/') == base_url.rstrip('/'):
                continue
            seen.add(clean_url)
            text = a.get_text(strip=True) or a.get('title', '')
            candidates.append({"url": clean_url, "path": parsed.path, "text": text})
        return candidates
    except Exception as e:
        logger.debug(f"[URL Reader] Error extracting internal links: {e}")
        return []


async def fetch_webpage_with_discovery(
    url: str,
    user_query: str = ""
) -> Tuple[Optional[str], List[Dict[str, str]]]:
    """
    Mengambil konten halaman web dengan penelusuran tautan anak (Sub-Link Discovery).
    Jika URL berupa root domain dan query pengguna mencari topik/spesifikasi tertentu,
    sistem secara otomatis mencari dan menelusuri sub-halaman relevan (misal: /weapon -> /ss3).
    """
    display_info = extract_url_display_info(url)
    primary_node = {
        "title": display_info["title"],
        "domain": display_info["domain"],
        "url": url
    }
    
    parsed = urlparse(url)
    is_root = (parsed.path.strip("/") == "" and not parsed.query)
    
    # Ambil konten halaman awal (Tier 1 fast HTTP dengan timeout aman 8s)
    raw_html = ""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0), follow_redirects=True, headers=_HTTP_HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.text:
                raw_html = resp.text
    except Exception as e:
        logger.debug(f"[URL Reader] Fast HTTP initial fetch failed for '{url}': {e}")

    if not raw_html:
        base_content = await fetch_webpage_content(url)
        return base_content, [primary_node]
        
    main_markdown = _clean_html_to_markdown(raw_html)
    
    # Jika bukan root domain atau query kosong, kembalikan halaman ini saja
    if not is_root or not user_query.strip():
        return main_markdown, [primary_node]
        
    # Ekstrak kata kunci topik dari user_query (buang stopword umum)
    user_words = [w.lower() for w in re.sub(r'[^a-zA-Z0-9\s-]', ' ', user_query).split() if len(w) >= 2]
    stopwords = {
        "cari", "carikan", "cek", "spesifikasi", "spek", "fitur", "detail", "rincian",
        "pindad", "com", "co", "id", "dan", "yang", "ini", "itu", "link", "web", "website",
        "situs", "tautan", "halaman", "tentang", "baca", "apa", "ada", "di", "ke", "dari",
        "pada", "untuk", "info", "informasi", "tolong", "coba", "gimana", "bagaimana"
    }
    topic_keywords = [w for w in user_words if w not in stopwords]
    if not topic_keywords:
        return main_markdown, [primary_node]
        
    logger.info(f"[URL Reader] 🔍 Sub-link discovery active for '{url}' with topic keywords: {topic_keywords}")
    
    CATEGORY_KEYWORDS = ["weapon", "senjata", "product", "produk", "vehicle", "kendaraan", "munition", "munisi", "berita", "news", "press-release", "artikel"]
    
    candidate_links = _extract_internal_candidate_links(raw_html, url)
    if not candidate_links:
        return main_markdown, [primary_node]
        
    def _score(link: Dict[str, str]) -> int:
        p_low = link["path"].lower()
        t_low = link["text"].lower()
        if any(ign in p_low for ign in ["/set-language", "/privacy", "/terms", "/kontak", "/contact", "/karir", "/career", "/login", "/sitemap"]):
            return -100
        score = 0
        for kw in topic_keywords:
            if kw in p_low:
                score += 100
            if kw in t_low:
                score += 80
        for ckw in CATEGORY_KEYWORDS:
            if ckw in p_low:
                score += 25
            if ckw in t_low:
                score += 20
        return score

    scored_links = [(_score(l), l) for l in candidate_links]
    scored_links.sort(key=lambda x: x[0], reverse=True)
    
    discovered_nodes = [primary_node]
    target_sub_link = None
    
    # 1. Cek kecocokan langsung pada halaman utama
    top_direct = [l for s, l in scored_links if s >= 80]
    if top_direct:
        target_sub_link = top_direct[0]
        logger.info(f"[URL Reader] 🎯 Direct sub-link match found on homepage: {target_sub_link['url']}")
    else:
        # 2. 1-Hop traversal melalui halaman kategori terkait
        category_candidates = [l for s, l in scored_links if s >= 20][:2]
        if category_candidates:
            logger.info(f"[URL Reader] 🧭 Traversing category link(s): {[c['url'] for c in category_candidates]}")
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(6.0, connect=3.0), follow_redirects=True, headers=_HTTP_HEADERS) as client:
                    for cat in category_candidates:
                        cat_resp = await client.get(cat["url"])
                        if cat_resp.status_code == 200 and cat_resp.text:
                            cat_links = _extract_internal_candidate_links(cat_resp.text, cat["url"])
                            cat_scored = [(_score(l), l) for l in cat_links]
                            cat_scored.sort(key=lambda x: x[0], reverse=True)
                            cat_direct = [l for s, l in cat_scored if s >= 80]
                            if cat_direct:
                                target_sub_link = cat_direct[0]
                                logger.info(f"[URL Reader] 🎯 Direct sub-link match found via category '{cat['url']}': {target_sub_link['url']}")
                                break
            except Exception as e:
                logger.warning(f"[URL Reader] Category traversal error: {e}")

    # Jika menemukan sub-link spesifik yang cocok dengan query
    if target_sub_link:
        sub_url = target_sub_link["url"]
        sub_info = extract_url_display_info(sub_url)
        sub_content = await fetch_webpage_content(sub_url)
        if sub_content and len(sub_content.strip()) > 100:
            raw_title = target_sub_link.get("text") or sub_info["title"]
            clean_title = raw_title.strip() if raw_title.strip() else sub_info["title"]
            discovered_nodes.append({
                "title": clean_title,
                "domain": sub_info["domain"],
                "url": sub_url
            })
            combined_content = (
                f"{main_markdown}\n\n"
                f"==== ISI SUB-HALAMAN SPESIFIK: {sub_url} ({clean_title}) ====\n\n"
                f"{sub_content}\n\n"
                f"===========================================================\n"
            )
            logger.info(f"[URL Reader] ✅ Successfully discovered & injected sub-page {sub_url} ({len(sub_content)} chars)")
            return combined_content, discovered_nodes

    return main_markdown, discovered_nodes
