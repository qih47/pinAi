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


def extract_urls_from_text(text: str) -> List[str]:
    """
    Ekstrak semua URL yang ada di dalam teks, termasuk domain tanpa http:// (misal pindad.com).
    """
    url_pattern = re.compile(
        r'(?:https?://)?(?:www\.)?[-a-zA-Z0-9@:%_\+~#=]{1,256}\s*\.\s*(?:com|co\.id|id|org|net|gov|edu|mil)\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)',
        re.IGNORECASE
    )
    
    matches = url_pattern.findall(text)
    
    valid_urls = []
    for match in matches:
        clean_match = match.replace(' ', '')
        if not clean_match.startswith('http://') and not clean_match.startswith('https://'):
            valid_urls.append(f'https://{clean_match}')
        else:
            valid_urls.append(clean_match)
            
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
