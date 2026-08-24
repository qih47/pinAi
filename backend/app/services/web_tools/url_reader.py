import re
import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger("cakra.web_tools")

# Attempt to import crawl4ai
try:
    from crawl4ai import AsyncWebCrawler
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    logger.warning("crawl4ai is not installed. URL Reader will not work properly.")

def extract_urls_from_text(text: str) -> List[str]:
    """
    Ekstrak semua URL yang ada di dalam teks, termasuk domain tanpa http:// (misal pindad.com).
    """
    url_pattern = re.compile(r'(?:https?://)?(?:www\.)?[-a-zA-Z0-9@:%_\+~#=]{1,256}\s*\.\s*(?:com|co\.id|id|org|net|gov|edu|mil)\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)', re.IGNORECASE)
    
    matches = url_pattern.findall(text)
    
    valid_urls = []
    for match in matches:
        clean_match = match.replace(' ', '')
        if not clean_match.startswith('http://') and not clean_match.startswith('https://'):
            valid_urls.append(f'https://{clean_match}')
        else:
            valid_urls.append(clean_match)
            
    return valid_urls

async def fetch_webpage_content(url: str) -> Optional[str]:
    """
    Mengambil konten Markdown dari URL menggunakan Crawl4AI.
    """
    if not CRAWL4AI_AVAILABLE:
        logger.error("Crawl4AI not available, cannot fetch URL.")
        return None

    logger.info(f"[URL Reader] Fetching content for: {url}")
    try:
        async with AsyncWebCrawler(verbose=True) as crawler:
            result = await crawler.arun(url=url)
            
            # Kita menggunakan raw markdown yang sudah dibersihkan oleh Crawl4AI
            markdown_content = result.markdown
            
            # Batasi teks jika terlalu panjang (misal > 30000 karakter) agar context LLM tidak kepenuhan
            if markdown_content and len(markdown_content) > 40000:
                logger.info(f"[URL Reader] Content truncated from {len(markdown_content)} to 40000 chars.")
                markdown_content = markdown_content[:40000] + "\n\n...[CONTENT TRUNCATED]..."
                
            return markdown_content
    except Exception as e:
        logger.error(f"[URL Reader] Failed to fetch {url}: {str(e)}")
        return None

from urllib.parse import urlparse
from typing import List, Optional, Dict, Any, AsyncGenerator

def extract_url_display_info(url: str) -> Dict[str, str]:
    """
    Ekstrak metadata tampilan URL untuk widget timeline (domain, title/path, clean url).
    Contoh: https://ollama.com/library/ornith-1.5 -> title: 'ornith-1.5', domain: 'ollama.com'
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        
        if path_parts:
            # Ambil segmen path terakhir sebagai judul model/halaman
            raw_title = path_parts[-1]
            # Bersihkan ekstensi file jika ada (.html, .php)
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
    Generator asinkron yang melakukan fetch URL satu per satu secara berurutan/progresif
    dan memancarkan event tiap kali satu URL selesai dibaca.
    """
    for url in urls:
        display_info = extract_url_display_info(url)
        content = await fetch_webpage_content(url)
        yield {
            "url": url,
            "title": display_info["title"],
            "domain": display_info["domain"],
            "content": content,
            "success": bool(content)
        }

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
