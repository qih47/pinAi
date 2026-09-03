"""
CAKRA AI — Web Reader
======================
URL fetcher dan content extractor bersih.
Mengambil konten halaman web dan mengubahnya menjadi teks bersih
untuk konteks AI tanpa noise navigasi/footer/iklan.
"""

import re
import logging
import asyncio
from typing import Dict, Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger("CAKRA_WEB_READER")

# Timeout dalam detik untuk HTTP request
HTTP_TIMEOUT = 15
# Max panjang konten yang dikembalikan (karakter)
MAX_CONTENT_LENGTH = 20_000


# ─── Main Fetcher ─────────────────────────────────────────────────────────────
async def fetch_url(url: str, timeout: int = HTTP_TIMEOUT) -> Dict[str, Any]:
    """
    Fetch konten URL dan kembalikan teks bersih.

    Args:
        url: URL yang ingin dibaca.
        timeout: Timeout HTTP dalam detik.

    Returns:
        {
            "url": str,
            "title": str,
            "content": str,       # Teks bersih, max MAX_CONTENT_LENGTH chars
            "status": "success" | "failed",
            "error": str | None,
        }
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return _error_result(url, f"Skema URL tidak didukung: {parsed.scheme}")

    def _do_fetch():
        try:
            import httpx
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(url, headers={
                    "User-Agent": "CakraAI/1.0 (Research Assistant)",
                    "Accept-Language": "id,en;q=0.9",
                })
                resp.raise_for_status()
                return resp.text, resp.headers.get("content-type", "")
        except ImportError:
            raise RuntimeError("httpx tidak terinstal — jalankan: pip install httpx")

    try:
        raw_html, content_type = await asyncio.to_thread(_do_fetch)
        text, title = _extract_clean_text(raw_html, content_type)
        content = text[:MAX_CONTENT_LENGTH]
        if len(text) > MAX_CONTENT_LENGTH:
            content += f"\n\n[... konten dipotong setelah {MAX_CONTENT_LENGTH} karakter]"

        logger.info(f"[WEB_READER] ✅ {url} — {len(content)} chars")
        return {
            "url": url,
            "title": title,
            "content": content,
            "status": "success",
            "error": None,
        }
    except Exception as e:
        logger.warning(f"[WEB_READER] ❌ Gagal fetch {url}: {e}")
        return _error_result(url, str(e))


async def fetch_multiple(urls: list, timeout: int = HTTP_TIMEOUT) -> list:
    """Fetch beberapa URL secara concurrent."""
    tasks = [fetch_url(u, timeout) for u in urls]
    return await asyncio.gather(*tasks, return_exceptions=False)


# ─── HTML → Text Extractor ────────────────────────────────────────────────────
def _extract_clean_text(html: str, content_type: str = "") -> tuple[str, str]:
    """
    Konversi HTML ke teks bersih, buang nav/footer/script/style.
    Returns (clean_text, page_title)
    """
    if "text/html" not in content_type and not html.strip().startswith("<"):
        return html.strip(), ""

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # Ekstrak judul
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Hapus elemen noise
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "noscript", "iframe", "form", "button",
                          "advertisement", "ads"]):
            tag.decompose()

        # Coba ambil konten utama dulu
        main = (
            soup.find("main") or
            soup.find("article") or
            soup.find(id=re.compile(r'content|main|article', re.I)) or
            soup.find(class_=re.compile(r'content|main|article|post', re.I)) or
            soup.find("body") or
            soup
        )

        text = main.get_text(separator="\n")
        # Bersihkan baris kosong berulang
        lines = [line.strip() for line in text.splitlines()]
        clean_lines = []
        prev_empty = False
        for line in lines:
            if not line:
                if not prev_empty:
                    clean_lines.append("")
                prev_empty = True
            else:
                clean_lines.append(line)
                prev_empty = False

        return "\n".join(clean_lines).strip(), title

    except ImportError:
        # Fallback tanpa bs4: strip tag manual dengan regex
        logger.warning("[WEB_READER] bs4 tidak terinstal, menggunakan regex fallback")
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        return text, title


def _error_result(url: str, error: str) -> Dict[str, Any]:
    return {
        "url": url,
        "title": "",
        "content": "",
        "status": "failed",
        "error": error,
    }
