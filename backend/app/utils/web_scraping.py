import aiohttp
import requests
from bs4 import BeautifulSoup
import logging
from playwright.async_api import async_playwright
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from ..config import settings

def create_news_session():
    """Membuat session untuk web scraping"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

news_session = create_news_session()

async def get_article_content_playwright(url):
    """Ambil konten artikel menggunakan Playwright (fallback)"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            await page.set_default_timeout(15000)
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            content_html = await page.content()
            await browser.close()

            soup = BeautifulSoup(content_html, "html.parser")
            content_div = soup.select_one("div.blog-detail-article")
            if content_div:
                return content_div.get_text(separator="\n\n", strip=True)
    except Exception as e:
        logging.warning(f"Playwright fallback failed for {url}: {e}")
    return ""

async def scrape_pindad_news():
    """Scrape berita dari website Pindad"""
    url = "https://www.pindad.com/news"
    results = []
    page_number = 1
    max_pages = 1

    logging.info(f"🔍 [scrape_pindad_news] Mulai scraping berita dari {url}")

    while page_number <= max_pages:
        current_url = url if page_number == 1 else f"{url}/{page_number}"
        logging.info(f"🔍 Memproses halaman: {current_url}")

        try:
            response = news_session.get(current_url, timeout=20)
            if response.status_code != 200:
                logging.warning(
                    f"Status {response.status_code} saat mengakses {current_url}"
                )
                break

            soup = BeautifulSoup(response.content, "html.parser")
            news_items = soup.select("div.blog-post.style-3")

            if not news_items:
                logging.info(f"Tidak ada berita ditemukan di halaman {current_url}")
                break

            logging.info(
                f"🔍 Ditemukan {len(news_items)} artikel di halaman {page_number}."
            )

            for item in news_items:
                try:
                    title_tag = item.select_one("a.title")
                    title = (
                        title_tag.get_text(strip=True)
                        if title_tag
                        else "Tidak ada judul"
                    )
                    link = title_tag["href"] if title_tag else ""
                    if link and not link.startswith("http"):
                        link = "https://www.pindad.com" + link

                    date_div = item.select_one("div.date")
                    date_str = (
                        " ".join(date_div.stripped_strings)
                        if date_div
                        else "Tanggal tidak ditemukan"
                    )

                    img_tag = item.select_one("a.thumbnail-entry img")
                    img_src = ""
                    if img_tag:
                        img_src = img_tag.get("src", "")
                        if img_src and not img_src.startswith("http"):
                            img_src = "https://www.pindad.com" + img_src

                    konten_lengkap = ""
                    if link:
                        try:
                            detail_response = news_session.get(link, timeout=15)
                            if detail_response.status_code == 200:
                                detail_soup = BeautifulSoup(
                                    detail_response.content, "html.parser"
                                )
                                content_div = detail_soup.select_one(
                                    "div.blog-detail-article"
                                )
                                if content_div:
                                    konten_lengkap = content_div.get_text(
                                        separator="\n\n", strip=True
                                    )
                                else:
                                    konten_lengkap = (
                                        await get_article_content_playwright(link)
                                    )
                            else:
                                konten_lengkap = await get_article_content_playwright(
                                    link
                                )
                        except Exception as req_e:
                            konten_lengkap = await get_article_content_playwright(link)

                    news_object = {
                        "judul": title,
                        "tanggal": date_str,
                        "gambar": img_src,
                        "link": link,
                        "konten": konten_lengkap,
                    }
                    results.append(news_object)

                except Exception as e_item:
                    logging.warning(f"Error memproses item berita: {e_item}")
                    continue

            page_number += 1

        except Exception as e_page:
            logging.error(f"Error memproses halaman {current_url}: {e_page}")
            break

    logging.info(f"✅ Selesai scraping. Ditemukan {len(results)} artikel.")
    return results

async def get_all_pindad_links():
    """Dapatkan semua link dari homepage Pindad"""
    try:
        BASE_URL = "https://www.pindad.com"
        TARGET_URL = "https://www.pindad.com"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)

            links = await page.evaluate(
                """(baseUrl) => {
                const allLinks = new Set();
                const anchors = document.querySelectorAll('a[href]');
                
                anchors.forEach(a => {
                    let href = a.getAttribute('href').trim();
                    if (!href || href.startsWith('#') || href.startsWith('javascript:')) {
                        return;
                    }
                    
                    try {
                        const absoluteUrl = new URL(href, baseUrl).href;
                        if (absoluteUrl.includes('pindad.com')) {
                            allLinks.add(absoluteUrl);
                        }
                    } catch (e) {
                        console.log('Invalid URL:', href);
                    }
                });
                
                return Array.from(allLinks);
            }""",
                BASE_URL,
            )

            await browser.close()

            unique_links = list(set(links))[:50]
            logging.info(f"Found {len(unique_links)} unique links from homepage")
            return unique_links

    except Exception as e:
        logging.error(f"Error getting links: {e}")
        return []

async def scrape_pindad_website(query):
    """Scrape informasi dari www.pindad.com berdasarkan query"""
    try:
        query_lower = query.lower()

        news_keywords = [
            "berita",
            "news",
            "artikel",
            "publikasi",
            "terbaru",
            "terkini",
            "update",
            "informasi terbaru",
            "artikel terbaru",
        ]
        is_news_query = any(keyword in query_lower for keyword in news_keywords)

        if is_news_query:
            logging.info(f"🔍 Query '{query}' terdeteksi sebagai pencarian berita.")
            news_results = await scrape_pindad_news()
            if news_results:
                formatted_news = ""
                for i, item in enumerate(news_results[:3]):
                    formatted_news += f"\n{'=' * 50}\n"
                    formatted_news += f"📰 Berita {i + 1}: {item['judul']}\n"
                    formatted_news += f"📎 URL: {item['link']}\n"
                    formatted_news += f"📅 Tanggal: {item['tanggal']}\n"
                    formatted_news += f"📝 Deskripsi: {item['konten'][:150]}...\n"
                    if item.get("gambar"):
                        formatted_news += f"🖼️ Gambar: {item['gambar']}\n"
                    formatted_news += f"{'-' * 30}\n"
                return f"""**BERITA TERBARU DARI PT PINDAD**
                
🔍 Query: "{query}"

📊 **Hasil Pencarian Berita**:
Sistem telah mengambil {len(news_results)} artikel berita terbaru.

{formatted_news}

**CATATAN**: Informasi diambil secara otomatis dari halaman berita resmi PT Pindad."""
            else:
                return f"""**TIDAK DITEMUKAN BERITA RELEVAN**
                
Sistem telah mencari berita terbaru di PT Pindad, 
namun tidak menemukan artikel yang sesuai dengan "{query}" atau tidak ada berita baru."""

        logging.info(f"🔍 Query '{query}' terdeteksi sebagai pencarian umum.")
        all_links = await get_all_pindad_links()

        if not all_links:
            return "Tidak dapat menemukan link dari website Pindad."

        relevant_links = []
        for link in all_links:
            link_lower = link.lower()
            if (
                query_lower in link_lower
                or any(
                    keyword in link_lower
                    for keyword in ["produk", "product", "senjata"]
                    if "produk" in query_lower
                )
                or any(
                    keyword in link_lower
                    for keyword in ["tentang", "about", "profil"]
                    if "tentang" in query_lower or "profil" in query_lower
                )
                or any(
                    keyword in link_lower
                    for keyword in ["karir", "career", "rekrutmen"]
                    if "karir" in query_lower
                )
            ):
                relevant_links.append(link)

        if not relevant_links:
            relevant_links = all_links[:10]

        scraped_content = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for url in relevant_links[:5]:
                try:
                    page = await browser.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)

                    content = await page.evaluate("""
                        () => {
                            const elementsToRemove = document.querySelectorAll(
                                'script, style, nav, header, footer, aside, iframe, noscript, button'
                            );
                            elementsToRemove.forEach(el => el.remove());
                            
                            const mainSelectors = [
                                'main', 'article', 'div.content', 
                                'div.post-content', 'section', 'div.container'
                            ];
                            
                            let mainContent = document.body;
                            for (const selector of mainSelectors) {
                                const element = document.querySelector(selector);
                                if (element && element.textContent.length > 200) {
                                    mainContent = element;
                                    break;
                                }
                            }
                            
                            return {
                                title: document.title,
                                url: window.location.href,
                                content: mainContent.innerText.replace(/\\s+/g, ' ').trim()
                            };
                        }
                    """)

                    content_lower = content["content"].lower()
                    relevance_score = 0

                    for word in query_lower.split():
                        if word in content_lower:
                            relevance_score += content_lower.count(word) * 2

                    if relevance_score > 0 or len(content["content"]) > 300:
                        scraped_content.append(
                            {
                                "url": content["url"],
                                "title": content["title"],
                                "content": content["content"][:2500],
                                "relevance": relevance_score,
                            }
                        )

                    await page.close()
                except Exception as e:
                    continue

            await browser.close()

        scraped_content.sort(key=lambda x: x["relevance"], reverse=True)

        if scraped_content:
            formatted_content = ""
            for i, item in enumerate(scraped_content[:3]):
                highlighted = item["content"]
                for word in query_lower.split():
                    if word in highlighted.lower() and len(word) > 3:
                        highlighted = highlighted.replace(word, f"**{word}**")

                formatted_content += f"\n{'=' * 50}\n"
                formatted_content += f"🔗 Sumber {i + 1}: {item['title']}\n"
                formatted_content += f"📎 URL: {item['url']}\n"
                formatted_content += f"📊 Relevansi: {item['relevance']} poin\n"
                formatted_content += f"{'-' * 30}\n"
                formatted_content += f"{highlighted[:1000]}...\n"
                if len(item["content"]) > 1000:
                    formatted_content += (
                        f"[... dan {len(item['content']) - 1000} karakter lainnya]\n"
                    )

            return f"""**INFORMASI DARI PT PINDAD WEBSITE**
            
🔍 Query: "{query}"

📊 **Hasil Pencarian Dinamis**:
Sistem telah menelusuri {len(relevant_links)} halaman dan menemukan {len(scraped_content)} halaman relevan.

{formatted_content}

**CATATAN**: Informasi diambil secara dinamis dari website resmi PT Pindad."""

        else:
            return f"""**TIDAK DITEMUKAN INFORMASI RELEVAN**
            
Sistem telah menelusuri {len(relevant_links)} halaman dari website Pindad, 
namun tidak menemukan konten yang cukup relevan dengan "{query}"."""

    except Exception as e:
        logging.error(f"Error during dynamic scraping: {e}")
        return f"**ERROR**: Terjadi kesalahan: {str(e)}"