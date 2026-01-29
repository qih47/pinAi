import asyncio
import logging
import requests
import re
import json
import os
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from difflib import SequenceMatcher

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def create_news_session():
    """Membuat session requests dengan retry strategy dan headers manusiawi"""
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
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    return session


news_session = create_news_session()


async def get_article_content_playwright(url):
    """Fallback: Ambil konten artikel menggunakan Playwright jika requests gagal"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await page.route(
                "**/*.{png,jpg,jpeg,css,svg,woff2}", lambda route: route.abort()
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(1)
            content_html = await page.content()
            await browser.close()
            soup = BeautifulSoup(content_html, "html.parser")
            content_div = soup.select_one("div.blog-detail-article")
            if content_div:
                return content_div.get_text(separator="\n\n", strip=True)
    except Exception as e:
        logging.warning(f"⚠️ Playwright fallback failed for {url}: {e}")
    return ""


async def scrape_pindad_news():
    """Scrape daftar berita terbaru secara paralel dengan penyajian data favorit lo"""
    url = "https://www.pindad.com/news"
    logging.info(f"🔍 [scrape_pindad_news] Memulai penarikan berita terbaru...")
    try:
        response = news_session.get(url, timeout=20)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.content, "html.parser")
        news_items = soup.select("div.blog-post.style-3")
        if not news_items:
            return []

        async def fetch_item_detail(item):
            try:
                title_tag = item.select_one("a.title")
                title = title_tag.get_text(strip=True) if title_tag else "N/A"
                link = title_tag["href"] if title_tag else ""
                if link and not link.startswith("http"):
                    link = "https://www.pindad.com" + link
                date_div = item.select_one("div.date")
                date_str = " ".join(date_div.stripped_strings) if date_div else "N/A"
                img_tag = item.select_one("a.thumbnail-entry img")
                img_src = img_tag.get("src", "") if img_tag else ""
                if img_src and not img_src.startswith("http"):
                    img_src = "https://www.pindad.com" + img_src

                konten_lengkap = ""
                if link:
                    try:
                        res = news_session.get(link, timeout=10)
                        if res.status_code == 200:
                            d_soup = BeautifulSoup(res.content, "html.parser")
                            c_div = d_soup.select_one("div.blog-detail-article")
                            if c_div:
                                konten_lengkap = c_div.get_text(
                                    separator="\n\n", strip=True
                                )
                    except:
                        pass
                    if not konten_lengkap:
                        konten_lengkap = await get_article_content_playwright(link)

                return {
                    "judul": title,
                    "tanggal": date_str,
                    "gambar": img_src,
                    "link": link,
                    "konten": konten_lengkap,
                }
            except Exception as e:
                logging.error(f"Error detail item: {e}")
                return None

        tasks = [fetch_item_detail(item) for item in news_items[:6]]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r]
    except Exception as e:
        logging.error(f"Error scrape_pindad_news: {e}")
        return []


async def get_homepage_map():
    """Stage 1: Ambil semua link dan teks navigasi dari homepage"""
    BASE_URL = "https://www.pindad.com"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
            map_data = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href]')).map(a => {
                // Ambil teks dari innerText, atau alt image kalau di dalamnya ada gambar, atau title
                let linkText = a.innerText || a.getAttribute('title') || "";
                
                // Jika teks kosong, coba cari image di dalamnya (misal ikon kontak)
                if (!linkText.trim()) {
                    const img = a.querySelector('img');
                    if (img) linkText = img.getAttribute('alt') || img.getAttribute('title') || "";
                }

                return {
                    text: linkText.toLowerCase().trim(),
                    href: a.href
                };
            }).filter(item => item.text.length > 2 && item.href.includes('pindad.com'));
        }""")
            await browser.close()
            return map_data
    except Exception as e:
        logging.error(f"Error Mapping Homepage: {e}")
        return []


# ==========================================
# GLOBAL CACHE & DB LOADER
# ==========================================
_DB_CACHE = None


def load_pindad_db():
    global _DB_CACHE
    if _DB_CACHE is None:
        json_path = "backend/app/nosql/pindad_scrap_website.json"
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                # Cache hanya field "data" supaya pencarian cepat
                _DB_CACHE = json.load(f).get("data", [])
                logging.info(
                    f"📂 [CACHE] Database loaded to memory. Total: {len(_DB_CACHE)} entries."
                )
        except Exception as e:
            logging.error(f"❌ [DB ERROR] Gagal load JSON: {e}")
            _DB_CACHE = []
    return _DB_CACHE


# ==========================================
# HELPERS
# ==========================================
def similarity_score(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def normalize(text):
    return re.sub(r"[^a-zA-Z0-9]", "", text).lower()


# ==========================================
# MAIN FUNCTION (SCRAPE PINDAD)
# ==========================================
async def scrape_pindad_website(query, is_retry=False):
    from .ai_helpers import ask_qwen3_vl

    # 1. CLEANING & PRE-PROCESS (REVISED)
    logging.info(f"📥 [RAW QUERY] Masuk ke fungsi (Retry={is_retry}): {repr(query)}")

    if is_retry:
        clean_text = query
    else:
        # STEP A: Hapus pengantar kaku dari AI (tapi jangan hapus konten di dalam bintang dulu)
        temp_query = re.sub(
            r"(?i)Query Search:|Maksimal.*?\.|Penjelasan:.*?\.", "", query
        )

        # STEP B: Hapus URL karena URL pasti bukan keyword pencarian label
        temp_query = re.sub(r"https?://\S+", "", temp_query)

        # STEP C: Buang karakter markdown sisa tapi pertahankan teksnya
        temp_query = (
            temp_query.replace("**", "")
            .replace("`", "")
            .replace("[", "")
            .replace("]", "")
        )

        # STEP D: Hapus kurung BESERTA isinya (karena biasanya itu narasi tambahan AI)
        temp_query = re.sub(r"\(.*?\)", "", temp_query).strip()

        # STEP E: Buang kata-kata sampah percakapan
        slang = ["ada bro", "kalau ga salah", "bro", "dong", "nih", "deh", "ya"]
        for s in slang:
            temp_query = re.sub(rf"(?i)\b{s}\b", "", temp_query)

        # Ambil baris pertama yang punya teks
        lines = [l.strip() for l in temp_query.split("\n") if l.strip()]
        clean_text = lines[0] if lines else temp_query

        # Ambil maksimal 4 kata kunci inti agar Pintu 2 & 3 bekerja
        words = [w for w in clean_text.split() if len(w) > 2]
        clean_text = " ".join(words[:4]).strip()

    query_upper = clean_text.upper()
    logging.info(f"🚀 [INIT] Fixed Clean Query: '{query_upper}'")

    # 2. LOAD DATA FROM CACHE (FAST)
    data_list = load_pindad_db()
    if not data_list:
        return "Database error atau file tidak ditemukan."

    # 3. INTERNAL WATERFALL LOGIC
    async def run_waterfall(target_query):
        target_upper = target_query.upper()

        # --- ✅ HARD-CODED ROUTING UNTUK TOPIK KRITIS ---
        if any(kw in target_upper for kw in ["DIREKTUR", "DIREKSI", "JAJARAN DIREKSI"]):
            logging.info("⚡ [HARD-CODED] Mengarahkan ke halaman 'direksi'")
            target_label = "DIREKSI"
        elif any(
            kw in target_upper
            for kw in ["KOMISARIS", "DEWAN KOMISARIS", "JAJARAN DEWAN KOMISARIS"]
        ):
            logging.info("⚡ [HARD-CODED] Mengarahkan ke halaman 'dewan-komisaris'")
            target_label = "DEWAN KOMISARIS"
        elif any(
            kw in target_upper
            for kw in [
                "ALAMAT",
                "KONTAK",
                "HUBUNGI",
                "LOKASI",
                "KANTOR",
                "TELEPON",
                "EMAIL",
            ]
        ):
            logging.info("⚡ [HARD-CODED] Mengarahkan ke halaman 'profil-perusahaan'")
            target_label = "PROFIL PERUSAHAAN"
        else:
            target_label = None

        if target_label:
            exact_match = next(
                (
                    d
                    for d in data_list
                    if d.get("label", "").upper() == target_label.upper()
                ),
                None,
            )
            if exact_match:
                return (
                    f"Berikut informasi resmi dari website PT Pindad:\n\n"
                    f"{exact_match['content']}\n\n"
                    f"🌐 Sumber: {exact_match.get('url', 'https://www.pindad.com')}"
                )

        # --- PINTU 1: GLOBAL ---
        keywords_umum = [
            "APA SAJA",
            "DAFTAR",
            "LIST",
            "KATALOG",
            "SEMUA",
            "PRODUK",
            "BERITA",
            "INFO",
        ]
        if any(kw in target_upper for kw in keywords_umum):
            logging.info(f"🔍 [PINTU 1] Checking Global Keywords")
            global_data = [d for d in data_list if d.get("isPrimary") == "Primary"]
            category_in_query = next(
                (d for d in global_data if d["label"].upper() in target_upper), None
            )

            if not category_in_query:
                logging.info("🚪 [PINTU 1] Jalur Umum Global Aktif")
                context = "\n".join([f"- {i['label']}" for i in global_data])
                return await ask_qwen3_vl(
                    f"Daftar kategori: {context}. Jawab permintaan: {target_query}",
                    stream=False,
                )
            else:
                logging.info(
                    f"⏭️ [PINTU 1] Kategori '{category_in_query['label']}' terdeteksi, skip ke Pintu 2"
                )

        # --- PINTU 2: KATEGORI UTAMA ---
        ignore = [
            "DAN",
            "DARI",
            "APA",
            "SAJA",
            "PINDAD",
            "PRODUK",
            "TERBARU",
            "TERKINI",
            "PERUSAHAAN",
        ]
        q_words = [w for w in target_upper.split() if w not in ignore and len(w) > 3]

        category_match = None
        logging.info(f"🔎 [PINTU 2] Scanning categories with: {q_words}")
        for d in data_list:
            if d.get("isPrimary") == "Primary":
                label_norm = d["label"].upper()
                if (
                    any(kw in label_norm for kw in q_words)
                    or label_norm in target_upper
                ):
                    category_match = d
                    break

        if category_match:
            logging.info(f"🚪 [PINTU 2] HIT Kategori: '{category_match['label']}'")
            return (
                f"Berikut informasi tentang {category_match['label']}:\n\n"
                f"{category_match['content']}\n\n"
                f"🌐 Sumber: {category_match.get('url', 'https://www.pindad.com')}"
            )

        # --- PINTU 3: DETAIL (DIPERLUAS KE SEMUA DATA) ---
        # Bersihkan karakter non-alphanumeric
        clean_kw = re.sub(r"[^A-Z0-9\s]", "", target_upper).strip()
        logging.info(f"🔎 [PINTU 3] Cleaned Keyword: '{clean_kw}'")

        # Cari di SEMUA entri (Primary + Sublink)
        all_entries = [d for d in data_list if "label" in d]
        potential = []
        for d in all_entries:
            label_upper = d["label"].upper()
            # Cek partial match
            if clean_kw in label_upper or any(
                w in label_upper for w in clean_kw.split()
            ):
                potential.append(d)

        if potential:
            # Urutkan berdasarkan similarity
            potential.sort(
                key=lambda x: similarity_score(clean_kw, x["label"].upper()),
                reverse=True,
            )
            top = potential[0]
            logging.info(f"🎁 [PINTU 3] MATCH FOUND: '{top['label']}'")
            return (
                f"Detail {top['label']}:\n\n{top['content']}\n\n"
                f"🌐 Sumber: {top.get('url', 'https://www.pindad.com')}"
            )

        return None

    # 4. EXECUTE WATERFALL
    result = await run_waterfall(clean_text)
    if result:
        return result

    # 5. RE-INJECTION (KONDISI NIHIL)
    if not is_retry:
        logging.warning(f"⚠️ [FAILED] Waterfall nihil. Mencoba analisa ulang...")
        available_labels = [
            d["label"] for d in data_list if d.get("isPrimary") == "Primary"
        ]

        analysis_prompt = f"User mencari: '{clean_text}'. Kategori tersedia: {available_labels}. Pilih satu label kategori yang paling relevan. Jawab HANYA labelnya saja."
        new_keyword = await ask_qwen3_vl(analysis_prompt, stream=False)
        new_keyword = re.sub(r'["\'.]', "", new_keyword).strip().upper()

        logging.info(f"🔄 [RE-INJECT] Keyword baru: '{new_keyword}'")
        return await scrape_pindad_website(new_keyword, is_retry=True)

    logging.error(f"💀 [TOTAL FAILED] Data '{clean_text}' tidak ditemukan.")
    return f"Maaf bro, setelah gue cek secara mendalam, informasi tentang '{clean_text}' emang nggak ada di database gue."
