import aiohttp
import json
import os
import fitz  # PyMuPDF
import logging
import base64
import io
import asyncio
import uuid
import time
import hashlib
import requests
import numpy as np
from fastapi import FastAPI, Request, File, UploadFile, Form, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from werkzeug.utils import secure_filename
from asyncpg import create_pool
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from webui.backend.ocr.ocr_processor import process_pdf_attachment_to_ocr

# Konstanta
# Gunakan SIMILARITY_THRESHOLD yang sesuai, misalnya 0.7
# Ini adalah ambang batas cosine similarity
SIMILARITY_THRESHOLD = 0.7  # Atur sesuai kebutuhan
LIMIT = 10  # Atur sesuai kebutuhan
# Initialize embedding model (same as in your upload route)
EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")

app = FastAPI()

# ========== KONFIGURASI ==========
UPLOAD_FOLDER = "./uploads"
DB_DOC_FOLDER = "./db_doc"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt", "docx", "pptx", "xlsx"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DB_DOC_FOLDER, exist_ok=True)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.11.80:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== KONFIGURASI DB RAG (PostgreSQL Lokal) ==========
DB_CONFIG = {
    "host": "localhost",
    "database": "ragdb",
    "user": "pindadai",
    "password": "Pindad123!",
}

# ========== KONFIGURASI DB LOGIN (PostgreSQL Server 11.55) ==========
DB_LOGIN_CONFIG = {
    "host": "192.168.11.55",
    "database": "qa_payroll_db",
    "user": "qisthi",
    "password": "q1sthi",
}

# Ollama endpoints
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

# PRIMARY MODEL - HANYA SATU
PRIMARY_MODEL = "qwen3:8b"  # 🎯 MODEL UTAMA
# FALLBACK MODEL for images and PDFs
VISION_MODEL = "qwen3-vl:8b"  # 🎯 MODEL VISUAL

# MODES
MODE_NORMAL = "normal"
MODE_DOCUMENT = "document"
MODE_SEARCH = "search"

# Database connection pools
rag_pool = None
login_pool = None

async def init_db_pools():
    global rag_pool, login_pool
    rag_pool = await create_pool(
        host=DB_CONFIG["host"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"]
    )
    login_pool = await create_pool(
        host=DB_LOGIN_CONFIG["host"],
        database=DB_LOGIN_CONFIG["database"],
        user=DB_LOGIN_CONFIG["user"],
        password=DB_LOGIN_CONFIG["password"]
    )

@app.on_event("startup")
async def startup_event():
    await init_db_pools()

# ========== ROUTES ==========

@app.post("/api/login")
async def login(request: Request):
    data = await request.json()
    npp = data.get("username")
    password_input = data.get("password")

    if not npp or not password_input:
        return JSONResponse(
            {"status": "error", "message": "NPP dan Password wajib diisi"},
            status_code=400
        )

    password_md5 = hashlib.md5(password_input.encode()).hexdigest()

    try:
        user_hris = None
        current_role = "USER"

        # --- LANGKAH 0: HANDLE SPECIAL ACCOUNT (LEARN DATA AI) ---
        if str(npp) == "99999" and str(password_input) == "123456":
            user_hris = {
                "npp": "99999",
                "nama": "Learn Data AI",
                "username_alias": "LearnDataAI",
                "divisi": "PINDAD",
                "password": password_input,  # bypass check md5 nanti
            }
            current_role = "TRAINER"
            logging.info("Login via Special Account: Learn Data AI")

        else:
            # --- LANGKAH 1: CEK KE DB HRIS (User Reguler) ---
            async with login_pool.acquire() as conn:
                async with conn.transaction():
                    query_hris = """
                        SELECT 
                            mp.nama_lengkap as nama, tu.npp, tu.password, 
                            split_part(ref_unit.unit_path::text, '->'::text, 2) AS divisi
                        FROM master_unit unit
                        JOIN temp_ref_unit ref_unit ON ref_unit.kode_unit = unit.kode_unit
                        LEFT JOIN master_personil mp ON mp.kode_unit = unit.kode_unit
                        LEFT JOIN tabel_user tu ON tu.npp = mp.npp
                        WHERE tu.npp = $1
                    """
                    user_hris = await conn.fetchrow(query_hris, npp)

            if not user_hris:
                return JSONResponse(
                    {"status": "error", "message": "NPP tidak terdaftar"},
                    status_code=404
                )

            # Validasi Password Reguler (MD5)
            if user_hris["password"] != password_md5:
                return JSONResponse({"status": "error", "message": "Password salah"}, status_code=401)

        # --- LANGKAH 2: SIMPAN SESSION & SYNC KE DB LOKAL ---
        session_token = str(uuid.uuid4())
        user_ip = request.client.host
        u_agent = request.headers.get("User-Agent")

        async with rag_pool.acquire() as conn:
            async with conn.transaction():
                # Jika bukan akun spesial, ambil role dari DB lokal (siapa tahu sudah di-set TRAINER sebelumnya)
                if npp != "99999":
                    existing = await conn.fetchrow(
                        "SELECT role FROM users WHERE npp = $1", user_hris["npp"]
                    )
                    current_role = existing["role"] if existing else "USER"

                # Sinkronisasi Data ke Tabel Users Lokal
                await conn.execute(
                    """
                    INSERT INTO users (npp, fullname, divisi, role) 
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (npp) DO UPDATE SET 
                        fullname = EXCLUDED.fullname, 
                        divisi = EXCLUDED.divisi,
                        role = EXCLUDED.role; 
                    """,
                    user_hris["npp"],
                    user_hris["nama"],
                    user_hris["divisi"],
                    current_role,
                )

                # Insert Session
                await conn.execute(
                    """
                    INSERT INTO session_login (npp, session_token, ip_address, is_login, last_activity)
                    VALUES ($1, $2, $3, TRUE, CURRENT_TIMESTAMP)
                    ON CONFLICT (npp) DO UPDATE SET 
                        session_token = EXCLUDED.session_token, 
                        is_login = TRUE, 
                        last_activity = CURRENT_TIMESTAMP;
                    """,
                    user_hris["npp"], session_token, user_ip,
                )

                # History
                await conn.execute(
                    "INSERT INTO history_login (npp, action, ip_address, user_agent) VALUES ($1, 'LOGIN', $2, $3)",
                    user_hris["npp"], user_ip, u_agent,
                )

        return JSONResponse(
            {
                "status": "success",
                "data": {
                    "token": session_token,
                    "username": user_hris.get("username_alias", user_hris["npp"]),
                    "npp": user_hris["npp"],
                    "fullname": user_hris["nama"],
                    "divisi": user_hris["divisi"],
                    "role": current_role,
                },
            }
        )

    except Exception as e:
        logging.error(f"Login Error: {e}")
        return JSONResponse({"status": "error", "message": f"System Error: {str(e)}"}, status_code=500)


@app.post("/api/logout")
async def logout(request: Request):
    try:
        data = await request.json()
        token = data.get("token")

        async with rag_pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT npp FROM session_login WHERE session_token = $1", token,
                )

                if row:
                    npp = row["npp"]
                    # GANTI NULL MENJADI '' (String Kosong) agar tidak melanggar constraint
                    await conn.execute(
                        "UPDATE session_login SET is_login = FALSE, session_token = '' WHERE npp = $1",
                        npp,
                    )

                    await conn.execute(
                        """
                        INSERT INTO history_login (npp, action, ip_address)
                        VALUES ($1, 'LOGOUT', $2);
                        """,
                        npp, request.client.host,
                    )

                    return JSONResponse({"status": "success", "message": "Logged out"}, status_code=200)

                # Jika token tidak ditemukan, anggap saja sudah logout
                return JSONResponse({"status": "success", "message": "Token already gone"}, status_code=200)

    except Exception as e:
        print(f"❌ LOGOUT ERROR: {str(e)}")  # Ini yang tadi muncul di log lu
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/verify-session")
async def verify_session(token: str = Query(...)):
    if not token:
        return JSONResponse({"status": "error", "message": "Token missing"}, status_code=401)

    try:
        async with rag_pool.acquire() as conn:
            async with conn.transaction():
                # Join ke tabel users untuk ambil data lengkap
                query = """
                    SELECT u.npp, u.fullname, u.divisi 
                    FROM session_login s
                    JOIN users u ON s.npp = u.npp
                    WHERE s.session_token = $1 AND s.is_login = TRUE
                """
                user = await conn.fetchrow(query, token)

                if user:
                    # Update last_activity setiap kali user akses
                    await conn.execute(
                        "UPDATE session_login SET last_activity = CURRENT_TIMESTAMP WHERE session_token = $1",
                        token,
                    )

                    return JSONResponse(
                        {
                            "status": "success",
                            "data": {
                                "username": user["npp"],
                                "fullname": user["fullname"],
                                "divisi": user["divisi"],
                            },
                        }
                    )
                else:
                    return JSONResponse(
                        {"status": "error", "message": "Session expired or invalid"}
                    , status_code=401)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/available-models")
async def get_available_models():
    models = [
        {"id": "qwen3:8b", "name": "Qwen 3 (8B)"},
        {"id": "qwen2.5:14b-instruct", "name": "Qwen 2.5-Instruct (14b)"},
        {"id": "qwen3-vl:8b", "name": "qwen 3 vl (8b)"},
        {"id": "llama3.1:8b", "name": "Llama 3.1 (8b)"},
    ]
    return JSONResponse({"status": "success", "data": models})


# Context-aware storage
file_contexts = {}  # {file_id: {metadata, text, embeddings}}
temp_uploaded_files = {}  # {file_id: {filepath, filename, filetype, preview_text}}


# ========== HELPER FUNCTIONS ==========
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


async def get_db_connection():
    return rag_pool


async def scrape_pindad_website(query):
    """Scrape information from www.pindad.com berdasarkan query - VERSI DINAMIS + BERITA"""
    try:
        from playwright.async_api import async_playwright
        from urllib.parse import urljoin
        import asyncio

        query_lower = query.lower()

        # --- DETEKSI QUERY BERITA ---
        # Kata kunci yang menunjukkan pencarian berita
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
            logging.info(
                f"🔍 [scrape_pindad_website] Query '{query}' terdeteksi sebagai pencarian berita. Menggunakan scraper spesifik."
            )
            # Jalankan scraper berita
            news_results = await scrape_pindad_news()
            if news_results:
                formatted_news = ""
                for i, item in enumerate(news_results[:3]):  # Ambil 3 berita teratas
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
namun tidak menemukan artikel yang sesuai dengan "{query}" atau tidak ada berita baru.

**Saran**:
1. Coba kata kunci yang lebih umum seperti "berita" atau "news"
2. Kunjungi langsung halaman berita: https://www.pindad.com/news"""

        # --- JIKA BUKAN QUERY BERITA, GUNAKAN PENCARIAN DINAMIS ---
        logging.info(
            f"🔍 [scrape_pindad_website] Query '{query}' terdeteksi sebagai pencarian umum. Menggunakan pencarian dinamis."
        )

        # 1. Pertama, dapatkan SEMUA link dari homepage
        all_links = await get_all_pindad_links()

        if not all_links:
            return "Tidak dapat menemukan link dari website Pindad."

        # 2. Filter link yang mungkin relevan berdasarkan kata kunci dalam URL
        relevant_links = []
        for link in all_links:
            link_lower = link.lower()
            # Cari kecocokan kata kunci di URL
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

        # Jika tidak ada link yang cocok berdasarkan URL, gunakan semua link
        if not relevant_links:
            relevant_links = all_links[:10]  # Batasi ke 10 link pertama untuk efisiensi

        # 3. Scrape konten dari link yang relevan
        scraped_content = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for url in relevant_links[:5]:  # Batasi 5 link untuk efisiensi
                try:
                    page = await browser.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)

                    # Ambil konten teks
                    content = await page.evaluate("""
                        () => {
                            // Hapus elemen yang tidak perlu
                            const elementsToRemove = document.querySelectorAll(
                                'script, style, nav, header, footer, aside, iframe, noscript, button'
                            );
                            elementsToRemove.forEach(el => el.remove());
                            
                            // Ambil teks dari elemen konten utama
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
                                content: mainContent.innerText.replace(/\s+/g, ' ').trim()
                            };
                        }
                    """)

                    # Hitung relevansi dengan query
                    content_lower = content["content"].lower()
                    relevance_score = 0

                    # Hitung berdasarkan kemunculan kata kunci
                    for word in query_lower.split():
                        if word in content_lower:
                            relevance_score += content_lower.count(word) * 2

                    # Tambahkan jika ada kemiripan
                    if relevance_score > 0 or len(content["content"]) > 300:
                        scraped_content.append(
                            {
                                "url": content["url"],
                                "title": content["title"],
                                "content": content["content"][:2500],  # Batasi panjang
                                "relevance": relevance_score,
                            }
                        )

                    await page.close()

                except Exception as e:
                    continue

            await browser.close()

        # 4. Urutkan berdasarkan relevansi
        scraped_content.sort(key=lambda x: x["relevance"], reverse=True)

        # 5. Format hasil
        if scraped_content:
            formatted_content = ""
            for i, item in enumerate(scraped_content[:3]):  # Ambil 3 terbaik
                # Sorot bagian yang mengandung kata kunci query
                highlighted = item["content"]
                for word in query_lower.split():
                    if word in highlighted.lower() and len(word) > 3:
                        # Simple highlighting
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
namun tidak menemukan konten yang cukup relevan dengan "{query}".

**Saran**:
1. Coba gunakan kata kunci yang lebih spesifik
2. Kunjungi langsung website www.pindad.com
3. Periksa bagian pencarian di website mereka"""

    except Exception as e:
        logging.error(f"Error during dynamic scraping: {e}")
        return f"**ERROR**: Terjadi kesalahan: {str(e)}"


async def get_all_pindad_links():
    """Dapatkan semua link dari homepage Pindad"""
    try:
        from playwright.async_api import async_playwright
        from urllib.parse import urljoin

        BASE_URL = "https://www.pindad.com"
        TARGET_URL = "https://www.pindad.com"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)

            # Ekstrak semua link
            links = await page.evaluate(
                """(baseUrl) => {
                const allLinks = new Set();
                const anchors = document.querySelectorAll('a[href]');
                
                anchors.forEach(a => {
                    let href = a.getAttribute('href').trim();
                    
                    // Skip anchor kosong atau javascript
                    if (!href || href.startsWith('#') || href.startsWith('javascript:')) {
                        return;
                    }
                    
                    // Buat URL absolut
                    try {
                        const absoluteUrl = new URL(href, baseUrl).href;
                        // Hanya simpan link dari domain pindad.com
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

            # Filter unik dan batasi jumlah
            unique_links = list(set(links))[:50]  # Batasi 50 link untuk efisiensi
            logging.info(f"Found {len(unique_links)} unique links from homepage")

            return unique_links

    except Exception as e:
        logging.error(f"Error getting links: {e}")
        return []


def create_news_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,  # Kurangi jumlah retry untuk scraping cepat
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
    """
    Alternatif: Ambil konten detail artikel menggunakan Playwright jika requests gagal.
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            # Tambahkan timeout dan user agent
            await page.set_extra_http_headers(
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            )
            await page.set_default_timeout(15000)  # 15 detik timeout
            await page.goto(url, wait_until="domcontentloaded")
            # Tunggu sedikit agar konten dinamis mungkin muncul
            await page.wait_for_timeout(2000)
            content_html = await page.content()
            await browser.close()

            # Parse dengan BeautifulSoup
            soup = BeautifulSoup(content_html, "html.parser")
            content_div = soup.select_one("div.blog-detail-article")
            if content_div:
                return content_div.get_text(separator="\n\n", strip=True)
    except Exception as e:
        logging.warning(f"Playwright fallback failed for {url}: {e}")
    return ""


async def scrape_pindad_news():
    """Scrape berita dari https://www.pindad.com/news - SPECIFIC NEWS SCRAPER - ROBUST VERSION (requests + fallback)"""
    url = "https://www.pindad.com/news"
    results = []
    page_number = 1
    max_pages = 1  # Batasi jumlah halaman yang di-scrape untuk efisiensi

    logging.info(f"🔍 [scrape_pindad_news] Mulai scraping berita dari {url}")

    while page_number <= max_pages:
        current_url = url if page_number == 1 else f"{url}/{page_number}"
        logging.info(f"🔍 [scrape_pindad_news] Memproses halaman: {current_url}")

        try:
            # 1. Gunakan requests + session robust untuk daftar berita
            response = news_session.get(current_url, timeout=20)
            if response.status_code != 200:
                logging.warning(
                    f"Status {response.status_code} saat mengakses {current_url}. Berhenti scraping."
                )
                break

            soup = BeautifulSoup(response.content, "html.parser")
            news_items = soup.select("div.blog-post.style-3")

            if not news_items:
                logging.info(
                    f"Tidak ada berita ditemukan di halaman {current_url}. Berhenti scraping."
                )
                break  # Tidak ada berita lagi, hentikan loop

            logging.info(
                f"🔍 [scrape_pindad_news] Ditemukan {len(news_items)} artikel di halaman {page_number}."
            )

            for item in news_items:
                try:
                    # 1. Judul & Link
                    title_tag = item.select_one("a.title")
                    title = (
                        title_tag.get_text(strip=True)
                        if title_tag
                        else "Tidak ada judul"
                    )
                    link = title_tag["href"] if title_tag else ""
                    if link and not link.startswith("http"):
                        link = "https://www.pindad.com" + link

                    # 2. Tanggal
                    date_div = item.select_one("div.date")
                    date_str = (
                        " ".join(date_div.stripped_strings)
                        if date_div
                        else "Tanggal tidak ditemukan"
                    )

                    # 3. Gambar (Thumbnail)
                    img_tag = item.select_one("a.thumbnail-entry img")
                    img_src = ""
                    if img_tag:
                        img_src = img_tag.get("src", "")
                        if img_src and not img_src.startswith("http"):
                            img_src = "https://www.pindad.com" + img_src

                    # 4. Konten Lengkap (Gunakan requests dulu, Playwright jika gagal)
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
                                    logging.info(
                                        f"Konten tidak ditemukan di {link} via requests, mencoba Playwright..."
                                    )
                                    konten_lengkap = (
                                        await get_article_content_playwright(link)
                                    )
                            else:
                                logging.warning(
                                    f"Status {detail_response.status_code} saat mengambil konten dari {link}, mencoba Playwright..."
                                )
                                konten_lengkap = await get_article_content_playwright(
                                    link
                                )
                        except Exception as req_e:
                            logging.warning(
                                f"requests gagal mengambil konten dari {link}: {req_e}. Mencoba Playwright..."
                            )
                            konten_lengkap = await get_article_content_playwright(link)

                    # 5. Simpan hasil
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
                    continue  # Lanjut ke item berikutnya

            page_number += 1  # Naik ke halaman berikutnya

        except Exception as e_page:
            logging.error(f"Error memproses halaman {current_url}: {e_page}")
            break  # Hentikan scraping jika ada error di level halaman

    logging.info(
        f"✅ [scrape_pindad_news] Selesai scraping. Ditemukan {len(results)} artikel."
    )
    return results


def embedding_to_pgvector_str(embedding):
    """Konversi embedding numpy ke string format vector PostgreSQL secara efisien."""
    emb_array = np.array(embedding)
    return f"[{','.join(f'{val:.8f}' for val in emb_array)}]"


async def search_documents(query, limit=LIMIT):
    """Search documents in the database using Hybrid Search (Vector + Full-Text) with threshold filtering."""
    logging.info(f"🔍 [search_documents] Mencari (Hybrid): '{query}'")
    try:
        # Generate embedding for the query using bge-m3
        # bge-m3 memiliki mode query dan passage. Gunakan query mode untuk pertanyaan.
        # Namun, encode standar biasanya cukup baik.
        # Pastikan normalize_embeddings=True untuk cosine similarity yang akurat dengan pgvector
        query_embedding = EMBEDDING_MODEL.encode([query], normalize_embeddings=True)[
            0
        ].tolist()
        query_vector_str = embedding_to_pgvector_str(query_embedding)

        async with rag_pool.acquire() as conn:
            # --- 1. Full-Text Search ---
            logging.info("🔍 [search_documents] Menjalankan Full-Text Search...")
            fts_sql = """
            SELECT
                dc.id,
                dc.dokumen_id,
                d.judul,
                d.nomor,
                d.tanggal,
                d.tempat,
                d.filename,
                d.id_jenis,
                dc.content,
                dc.chunk_id,
                ts_rank_cd(to_tsvector('indonesian', dc.content), plainto_tsquery('indonesian', $1), 1) as fts_score -- Gunakan ts_rank_cd untuk efisiensi
            FROM dokumen_chunk dc
            JOIN dokumen d ON dc.dokumen_id = d.id
            WHERE to_tsvector('indonesian', dc.content) @@ plainto_tsquery('indonesian', $1)
              AND d.status_ocr = 'rag_ready'
            ORDER BY fts_score DESC
            LIMIT $2;
            """
            fts_chunks = await conn.fetch(fts_sql, query, limit)
            logging.info(f"✅ [search_documents] FTS menemukan {len(fts_chunks)} chunk.")

            # --- 2. Vector Search ---
            logging.info("🔍 [search_documents] Menjalankan Vector Search...")
            # Gunakan <-> untuk cosine distance (1 - cosine_similarity) di pgvector
            # Jadi, (dc.embedding <-> $1::vector) = 1 - cosine_similarity
            # cosine_similarity = 1 - (dc.embedding <-> $1::vector)
            vector_sql = """
            SELECT
                dc.id,
                dc.dokumen_id,
                d.judul,
                d.nomor,
                d.tanggal,
                d.tempat,
                d.filename,
                d.id_jenis,
                dc.content,
                dc.chunk_id,
                (dc.embedding <-> $1::vector) as cosine_distance
            FROM dokumen_chunk dc
            JOIN dokumen d ON dc.dokumen_id = d.id
            WHERE d.status_ocr = 'rag_ready'
            ORDER BY (dc.embedding <-> $1::vector)
            LIMIT $2;
            """
            vector_chunks = await conn.fetch(vector_sql, query_vector_str, limit)
            logging.info(
                f"✅ [search_documents] Vector Search menemukan {len(vector_chunks)} chunk."
            )

            # --- 3. Gabungkan Hasil (Hybrid) ---
            combined_scores = {}
            id_to_chunk = {}

            # Tambahkan skor FTS
            for chunk in fts_chunks:
                chunk_id = chunk["id"]
                combined_scores[chunk_id] = {
                    "fts_score": chunk["fts_score"],
                    "vector_score": 0.0,
                    "similarity": 0.0,
                    "chunk_data": chunk,
                }
                id_to_chunk[chunk_id] = chunk
                # Hapus kolom sementara dari chunk_data
                del combined_scores[chunk_id]["chunk_data"]["fts_score"]

            # Tambahkan skor Vector dan perbarui similarity
            for chunk in vector_chunks:
                chunk_id = chunk["id"]
                cosine_distance = chunk["cosine_distance"]
                # cosine_similarity = 1 - cosine_distance
                cosine_similarity = 1.0 - cosine_distance

                if chunk_id in combined_scores:
                    # Jika chunk muncul di FTS, update skor vector-nya
                    combined_scores[chunk_id]["vector_score"] = cosine_similarity
                    combined_scores[chunk_id]["similarity"] = (
                        cosine_similarity  # Gunakan similarity vector untuk filtering
                    )
                else:
                    # Jika chunk hanya ada di Vector Search
                    combined_scores[chunk_id] = {
                        "fts_score": 0.0,
                        "vector_score": cosine_similarity,
                        "similarity": cosine_similarity,
                        "chunk_data": chunk,
                    }
                    id_to_chunk[chunk_id] = chunk

            # --- 4. Hitung Skor Gabungan dan Urutkan ---
            # Bobot untuk hybrid search (FTS vs Vector)
            WEIGHT_FTS = 0.4
            WEIGHT_VECTOR = 0.6

            def calculate_hybrid_score(scores):
                fts_norm = scores["fts_score"]  # Skor FTS biasanya 0-1
                vector_norm = scores["vector_score"]  # Sudah dalam bentuk similarity 0-1
                return (WEIGHT_FTS * fts_norm) + (WEIGHT_VECTOR * vector_norm)

            # Buat list tuple (chunk_id, hybrid_score) untuk diurutkan
            scored_chunks = [
                (cid, calculate_hybrid_score(scores))
                for cid, scores in combined_scores.items()
            ]

            # Urutkan berdasarkan skor gabungan, tertinggi dulu
            scored_chunks.sort(key=lambda x: x[1], reverse=True)

            # Ambil chunk yang sudah diurutkan
            sorted_chunk_ids = [cid for cid, score in scored_chunks]
            sorted_chunks = [
                id_to_chunk[cid] for cid in sorted_chunk_ids if cid in id_to_chunk
            ]

            # --- 5. Filter berdasarkan SIMILARITY_THRESHOLD ---
            # Gunakan similarity dari vector search (karena itu representasi semantik utama)
            filtered_chunks = []
            for chunk in sorted_chunks:
                vector_similarity = combined_scores[chunk["id"]]["vector_score"]
                if vector_similarity >= SIMILARITY_THRESHOLD:
                    chunk["similarity"] = (
                        vector_similarity  # Pastikan kolom similarity ada dan benar
                    )
                    filtered_chunks.append(chunk)

            # Ambil limit
            final_chunks = filtered_chunks[:limit]

            # Ambil info dokumen untuk hasil final
            document_ids = list(set(chunk["dokumen_id"] for chunk in final_chunks))
            documents = []
            if document_ids:
                doc_sql = """
                SELECT id, judul, nomor, tanggal, tempat, filename, status, id_jenis
                FROM dokumen
                WHERE id = ANY($1)
                """
                documents = await conn.fetch(doc_sql, document_ids)

            logging.info(
                f"✅ [search_documents] Ditemukan {len(final_chunks)} chunk yang melewati filter Hybrid Search (threshold={SIMILARITY_THRESHOLD})."
            )

            # Log hasil hybrid (opsional, untuk debugging)
            for i, chunk in enumerate(final_chunks):
                logging.info(
                    f"[search_documents][Hybrid] Chunk-{i} dokumen_id={chunk['dokumen_id']} judul={chunk['judul']} content: {chunk['content'][:100]}... similarity: {chunk['similarity']:.4f}"
                )

            return {
                "documents": [dict(row) for row in documents],
                "chunks": [dict(row) for row in final_chunks],
            }

    except Exception as e:
        logging.error(f"Error searching documents (Hybrid): {e}")
        # Fallback ke vector search original jika hybrid gagal
        try:
            async with rag_pool.acquire() as conn:
                # Gunakan kode vector search original kamu di sini
                # Pastikan query_vector_str dan threshold sudah didefinisikan
                # Gunakan <-> untuk cosine similarity
                chunk_sql = """
                SELECT
                    dc.id,
                    dc.dokumen_id,
                    d.judul,
                    d.nomor,
                    d.tanggal,
                    d.tempat,
                    d.filename,
                    d.id_jenis,
                    dc.content,
                    dc.chunk_id,
                    (dc.embedding <-> $1::vector) as cosine_distance
                FROM dokumen_chunk dc
                JOIN dokumen d ON dc.dokumen_id = d.id
                WHERE d.status_ocr = 'rag_ready'
                ORDER BY (dc.embedding <-> $1::vector)
                LIMIT $2;
                """

                chunks = await conn.fetch(chunk_sql, query_vector_str, limit)

                # Filter berdasarkan threshold setelah mengambil semua
                filtered_chunks = []
                for chunk in chunks:
                    cosine_similarity = 1.0 - chunk["cosine_distance"]
                    if cosine_similarity >= SIMILARITY_THRESHOLD:
                        chunk["similarity"] = cosine_similarity
                        filtered_chunks.append(chunk)
                    # Hapus kolom distance setelah digunakan
                    del chunk["cosine_distance"]

                # Ambil limit setelah filtering
                final_chunks = filtered_chunks[:limit]

                document_ids = list(set(chunk["dokumen_id"] for chunk in final_chunks))
                documents = []
                if document_ids:
                    doc_sql = """
                    SELECT id, judul, nomor, tanggal, tempat, filename, status, id_jenis
                    FROM dokumen
                    WHERE id = ANY($1)
                    """
                    documents = await conn.fetch(doc_sql, document_ids)

                logging.info(
                    f"✅ [search_documents] Fallback Vector Search menemukan {len(final_chunks)} chunk."
                )

                return {
                    "documents": [dict(row) for row in documents],
                    "chunks": [dict(row) for row in final_chunks],
                }
        except Exception as fallback_e:
            logging.error(f"Fallback search also failed: {fallback_e}")
            return {"documents": [], "chunks": []}


async def extract_with_qwen3_vl(filepath, filetype):
    """Ekstrak teks menggunakan qwen3-vl:8b"""
    try:
        if filetype == "pdf":
            doc = fitz.open(filepath)
            images = []
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                images.append(base64.b64encode(img_bytes).decode("utf-8"))
            doc.close()

            all_text = []
            for i, img_b64 in enumerate(images):
                text = await ask_qwen3_vl(
                    f"Ekstrak semua teks dari halaman {i + 1} dokumen ini:",
                    images=[img_b64],
                    file_type=filetype,
                )
                all_text.append(text)

            return "\n\n".join(all_text)

        elif filetype in ["png", "jpg", "jpeg"]:
            with open(filepath, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            return await ask_qwen3_vl(
                "Ekstrak semua teks dari gambar ini:",
                images=[img_b64],
                file_type=filetype,
            )

        elif filetype == "txt":
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        else:
            return await extract_fallback(filepath, filetype)

    except Exception as e:
        logging.error(f"Qwen3-VL extraction error: {e}")
        return await extract_fallback(filepath, filetype)


async def ask_qwen3_vl(
    prompt, images=None, stream=False, file_type=None, override_model=None
):
    """Helper untuk bertanya ke model yang sesuai dengan jaminan return string"""

    # 1. LOGIKA PEMILIHAN MODEL
    if images or (file_type and file_type in ["pdf", "png", "jpg", "jpeg"]):
        target_model = VISION_MODEL
    else:
        target_model = override_model if override_model else PRIMARY_MODEL

    messages = [{"role": "user", "content": prompt}]
    if images:
        messages[0]["images"] = images

    print(f"--- Ollama Request: Using model {target_model} ---")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OLLAMA_URL,
                json={
                    "model": target_model,
                    "messages": messages,
                    "stream": stream,
                    "options": {"temperature": 0.1},
                },
                timeout=120,
            ) as resp:
                if resp.status != 200:
                    err_msg = await resp.text()
                    print(f"Ollama Error ({resp.status}): {err_msg}")
                    return f"Error dari Ollama: {resp.status}"

                if stream:
                    full_reply = ""
                    async for line in resp.content:
                        if line:
                            try:
                                obj = json.loads(line.decode("utf-8"))
                                chunk = obj.get("message", {}).get("content", "")
                                full_reply += chunk
                                if obj.get("done"):
                                    break
                            except:
                                continue
                    return (
                        full_reply
                        if full_reply
                        else "Model memberikan respon kosong (stream)."
                    )
                else:
                    result = await resp.json()
                    return result.get("message", {}).get(
                        "content", "Model memberikan respon kosong."
                    )
    except Exception as e:
        print(f"Critical Error in ask_qwen3_vl: {str(e)}")
        return f"Sistem AI sedang sibuk atau error: {str(e)}"


async def extract_fallback(filepath, filetype):
    """Fallback extraction jika model gagal"""
    try:
        if filetype == "pdf":
            doc = fitz.open(filepath)
            text = "\n".join([page.get_text() for page in doc])
            doc.close()
            return text.strip() if text.strip() else "[PDF tidak mengandung teks]"

        elif filetype in ["png", "jpg", "jpeg"]:
            try:
                import pytesseract

                image = Image.open(filepath)
                text = pytesseract.image_to_string(image, lang="eng+ind")
                return (
                    text.strip() if text.strip() else "[Gambar tidak mengandung teks]"
                )
            except ImportError:
                return "[OCR tidak tersedia]"

        elif filetype == "txt":
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()

        else:
            return f"[File {filetype.upper()} diupload]"

    except Exception as e:
        return f"[Ekstraksi gagal: {str(e)}]"


async def generate_summary(text):
    """Generate ringkasan otomatis"""
    try:
        prompt = f"""Buat ringkasan 1-2 kalimat dari teks berikut:

{text[:1500]}

Ringkasan:"""

        return await ask_qwen3_vl(prompt)
    except:
        return "Ringkasan tidak tersedia."


# Fungsi Helper History (Pastikan ditaruh di luar smart_chat_with_context)
async def get_chat_history_from_db(session_uuid, limit=5):
    """Mengambil history percakapan terakhir menggunakan asyncpg"""
    history = []
    try:
        async with rag_pool.acquire() as conn:
            # Query join ke sessions untuk memastikan session_uuid yang dipakai
            query = """
                SELECT d.user_text, d.assistant_text 
                FROM ai_dialogue_corpus d
                JOIN chat_sessions s ON d.session_id = s.id
                WHERE s.session_uuid = $1
                ORDER BY d.created_at DESC 
                LIMIT $2
            """
            rows = await conn.fetch(query, session_uuid, limit)

            # Balik urutan agar kronologis: Lama -> Baru
            for row in reversed(rows):
                history.append({"role": "user", "content": row["user_text"]})
                history.append({"role": "assistant", "content": row["assistant_text"]})

            return history
    except Exception as e:
        logging.error(f"❌ Error fetch history: {e}")
        return []


# ========== SMART CHAT FUNCTION ==========
# Fungsi helper untuk memformat input ke Qwen2-VL
def format_vlm_payload(user_message, base64_image):
    # Gunakan parameter 'base64_image', bukan 'img_obj'
    raw_base64 = base64_image.split(",")[1] if "," in base64_image else base64_image

    return [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": raw_base64},
                {"type": "text", "text": user_message},
            ],
        }
    ]


async def smart_chat_with_context(
    user_message,
    active_file=None,
    mode=MODE_NORMAL,
    model=PRIMARY_MODEL,
    session_uuid=None,
    npp=None,
    role="GUEST",
    attachments=[],
):
    """Versi smart chat dengan konteks historis dan mode dinamis"""
    logging.info(f"🧠 [smart_chat_with_context] Mode: {mode} | User: {npp}")

    # --- ANALISIS PESAN (LOGIKA CERDAS) ---
    # 1. Cek apakah perlu pencarian
    analysis_prompt = f"""
    Analisis pesan user berikut dan tentukan:
    1. Apakah perlu pencarian data: [ya/tidak]
    2. Keyword pencarian yang relevan (jika ya)
    3. Apakah pesan berkaitan dengan file aktif: [ya/tidak]
    
    Pesan: "{user_message}"
    
    Format jawaban (JSON):
    {{
        "perlu_cari": true/false,
        "keyword_pencarian": "kata kunci untuk pencarian",
        "ada_file_aktif": true/false,
        "jenis_pertanyaan": "deskripsi jenis pertanyaan"
    }}
    """

    try:
        analysis_raw = await ask_qwen3_vl(analysis_prompt)
        # Parsing JSON dari response
        analysis_str = analysis_raw.replace("```json", "").replace("```", "").strip()
        analysis_data = json.loads(analysis_str)
    except:
        # Fallback parsing manual
        analysis_data = {
            "perlu_cari": "data" in user_message.lower() or "informasi" in user_message.lower(),
            "keyword_pencarian": user_message,
            "ada_file_aktif": bool(active_file),
            "jenis_pertanyaan": "Umum"
        }

    # --- LAYER 1: CONTEXT HISTORY ---
    history_context = ""
    if session_uuid:
        history = await get_chat_history_from_db(session_uuid, limit=5)
        if history:
            history_context = "HISTORY PERCAKAPAN SEBELUMNYA:\n" + "\n".join([
                f"- {item['role'].upper()}: {item['content'][:100]}..." for item in history
            ]) + "\n\n"

    # --- LAYER 2: UNIVERSAL SEARCH (SYNC CHUNKS & CORPUS) ---
    corpus_context = ""
    if analysis_data.get("perlu_cari"):
        search_query = analysis_data.get("keyword_pencarian", user_message)

        # Ini fungsi sakti yang kita buat tadi (UNION SQL)
        universal_refs = await search_universal_knowledge(search_query, npp, role)
        
        if universal_refs:
            formatted_refs = []
            for ref in universal_refs:
                # Bedakan cara menampilkan info Chunks vs History
                if ref["source"] == "CHAT":
                    formatted_refs.append(
                        f"[MEMORI CHAT]: User tanya '{ref['primary_content']}' -> AI jawab '{ref['secondary_content']}'"
                    )
                else:
                    formatted_refs.append(
                        f"[DOKUMEN {ref['secondary_content']}]: {ref['primary_content']}"
                    )

            corpus_context = (
                "REFERENSI DATA INTERNAL PERUSAHAAN:\n"
                + "---\n".join(formatted_refs)
                + "\n\n"
            )
        else:
            corpus_context = (
                "INFO: Tidak ada referensi dokumen lama yang relevan.\n"
            )

    # --- LAYER 3: GENERATE RESPON AKHIR ---
    # Jika ada file yang sedang di-upload (Active File), ia jadi prioritas #1
    if active_file:
        context_text = active_file.get("text", "")[
            :7000
        ]  # Gue naikin dikit limitnya karena A40 kuat
        file_name = active_file.get("name", "Dokumen Terlampir")

        prompt = f"""Kamu adalah CAKRA (Cerdas Terpercaya), AI PT Pindad.

DOKUMEN YANG SEDANG DIBUKA (PRIORITAS UTAMA):
Nama File: {file_name}
Konten: {context_text}

{corpus_context}

HISTORY CHAT TERAKHIR:
{history_context}

INSTRUKSI:
1. Jawab pertanyaan user: "{user_message}"
2. Berikan jawaban paling akurat berdasarkan 'DOKUMEN YANG SEDANG DIBUKA'.
3. Jika tidak ada di dokumen tersebut, gunakan 'REFERENSI DATA INTERNAL PERUSAHAAN'.
4. Gunakan gaya bahasa yang profesional namun membantu.
"""
    else:
        # Jika tidak ada file upload, murni pakai Universal RAG
        prompt = f"""Kamu adalah CAKRA, AI PT Pindad.
        
{corpus_context}

HISTORY CHAT TERAKHIR:
{history_context}

User: {user_message}

Tugas: Jawab dengan jujur berdasarkan referensi data internal yang tersedia.
"""

    # EKSEKUSI FINAL
    reply = await ask_qwen3_vl(prompt, stream=True, override_model=model)

    if reply is None:
        reply = "Maaf bro, sistem sedang sibuk. Coba ulangi lagi ya."

    return reply, None, False


async def search_universal_knowledge(query, npp, role, limit=4):
    """
    Hybrid Search dengan 3 Kondisi:
    1. USER: Data Sendiri + Data Publik (Tanpa NPP) + Data milik TRAINER.
    2. GUEST: Data Publik (Tanpa NPP) + Data milik TRAINER.
    3. TRAINER: Semua Data (Tanpa Filter).
    """
    logging.info(f"🧠 [Universal Search] NPP: {npp} | Role: {role} | Query: '{query}'")
    try:
        query_embedding = EMBEDDING_MODEL.encode([query], normalize_embeddings=True)[
            0
        ].tolist()
        query_vector_str = embedding_to_pgvector_str(query_embedding)

        async with rag_pool.acquire() as conn:

            # Flag apakah pencari adalah TRAINER
            is_trainer = (role.upper() == "TRAINER") if role else False

            sql = """
            WITH combined_knowledge AS (
                -- Sumber A: History Chat
                SELECT 
                    'CHAT' as source,
                    adc.user_text as primary_content,
                    adc.assistant_text as secondary_content,
                    (adc.embedding_user <-> $1::vector) as distance,
                    cs.npp as owner_npp
                FROM ai_dialogue_corpus adc
                JOIN chat_sessions cs ON adc.session_id = cs.id
                LEFT JOIN users u ON cs.npp = u.npp -- Join ke tabel user untuk cek role pemilik data
                WHERE (
                    $2 = TRUE OR                         -- Kondisi 3: Pencari adalah TRAINER (Akses Semua)
                    cs.npp = $3 OR                       -- Kondisi 1: Data milik sendiri
                    cs.npp IS NULL OR cs.npp = '' OR     -- Kondisi 1 & 2: Data Publik/Guest
                    u.role = 'TRAINER'                   -- Kondisi 1 & 2: Data milik user ber-role TRAINER
                )

                UNION ALL

                -- Sumber B: Isi Dokumen OCR
                SELECT 
                    'DOCUMENT' as source,
                    content as primary_content,
                    metadata->>'filename' as secondary_content,
                    (embedding <-> $4::vector) as distance,
                    adc_chunks.npp as owner_npp
                FROM ai_document_chunks adc_chunks
                LEFT JOIN users u ON adc_chunks.npp = u.npp
                WHERE (
                    $5 = TRUE OR                         -- Kondisi 3: Pencari adalah TRAINER (Akses Semua)
                    adc_chunks.npp = $6 OR               -- Kondisi 1: Data milik sendiri
                    adc_chunks.npp IS NULL OR adc_chunks.npp = '' OR 
                    u.role = 'TRAINER'                   -- Kondisi 1 & 2: Data milik TRAINER
                )
            )
            SELECT * FROM combined_knowledge
            WHERE (1 - distance) >= 0.7
            ORDER BY distance ASC
            LIMIT $7;
            """

            # Eksekusi dengan parameter yang sesuai
            results = await conn.fetch(
                sql,
                query_vector_str,
                is_trainer,
                npp,  # Params untuk Chat
                query_vector_str,
                is_trainer,
                npp,  # Params untuk Document
                limit,
            )

            return results

    except Exception as e:
        logging.error(f"Error in universal search: {e}")
        return []


async def generate_judul_ai(message):
    try:
        prompt = (
            f"Buat judul singkat 3-6 kata untuk pesan ini: '{message}'\n"
            "Judul harus mewakili topik utama. Hanya kembalikan judulnya saja."
        )

        # Menggunakan requests (Synchronous)
        response = requests.post(
            OLLAMA_GENERATE_URL,
            json={"model": PRIMARY_MODEL, "prompt": prompt, "stream": False},
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            return result.get("response", "").strip() or message[:30] + "..."
        return message[:30] + "..."

    except Exception as e:
        logging.error(f"Gagal generate judul via requests: {e}")
        return message[:30] + "..."


# --- HELPER EMBEDDING ---
def get_embedding(text):
    if not text:
        return None
    try:
        # Generate embedding menggunakan SentenceTransformer
        embedding = EMBEDDING_MODEL.encode(text, normalize_embeddings=True)
        # Convert dari numpy array ke list biasa agar bisa dibaca asyncpg
        return embedding.tolist()
    except Exception as e:
        logging.error(f"Embedding Error: {e}")
        return None


@app.post("/api/chat")
async def chat(request: Request):
    global PRIMARY_MODEL
    role = "GUEST"
    npp = None
    username = "Guest"
    try:
        data = await request.json()
        user_message = data.get("message", "")
        file_id = data.get("file_id", None)
        mode = data.get("mode", "normal")
        session_uuid = data.get("session_uuid")
        attachments = data.get("attachments", [])
        npp = data.get("npp")
        role = data.get("role", "GUEST")
        username = data.get("fullname", "Guest")
        selected_model = data.get("model", PRIMARY_MODEL) if npp else PRIMARY_MODEL

        print(
            f"\n🚀 CHAT INCOMING | User: {username} | NPP: {npp} | Role: {role} | Attachments: {len(attachments)}"
        )

        async with rag_pool.acquire() as conn:
            async with conn.transaction():
                # --- 1. LOGIKA MANAJEMEN SESI ---
                current_session_id = None
                judul_baru = None

                if session_uuid:
                    sess = await conn.fetchrow(
                        "SELECT id FROM chat_sessions WHERE session_uuid = $1", session_uuid,
                    )
                    if sess:
                        current_session_id = sess["id"]

                if not current_session_id:
                    if not session_uuid:
                        session_uuid = str(uuid.uuid4())
                    judul_baru = await generate_judul_ai(user_message)
                    result = await conn.fetchrow(
                        """
                        INSERT INTO chat_sessions (session_uuid, user_name, npp, judul, model_name, is_active)
                        VALUES ($1, $2, $3, $4, $5, TRUE) RETURNING id
                    """,
                        session_uuid, username, npp, judul_baru, selected_model,
                    )
                    current_session_id = result["id"]

                # --- 2. MULTIMODAL LAYER (OCR PROCESSOR) ---
                ocr_context = ""
                for att in attachments:
                    mime_type = att.get("type", "").lower()
                    if "application/pdf" in mime_type or att.get("name", "").endswith(".pdf"):
                        print(f"[*] Processing PDF with PaddleOCR: {att.get('name')}")
                        extracted_text = await process_pdf_attachment_to_ocr(
                            attachment=att,
                            npp=npp,
                            session_id=current_session_id,
                            get_embedding_func=get_embedding,
                        )
                        if extracted_text:
                            ocr_context += extracted_text

                # --- 3. LOGIKA GABUNG PROMPT (DI SINI KUNCINYA) ---
                active_file = None
                final_message_to_ai = user_message  # Default pakai pesan asli

                if ocr_context and len(ocr_context.strip()) > 10:
                    print(f"[*] OCR SUKSES: {len(ocr_context)} karakter ditemukan.")
                    active_file = {"text": ocr_context, "name": "Dokumen Terlampir"}

                    # Kita bungkus user_message asli lu dengan konteks OCR
                    # Agar AI langsung dapet perintah + datanya dalam satu tarikan napas
                    final_message_to_ai = f"""
INSTRUKSI USER: {user_message if user_message else "Rangkum dokumen ini"}

DATA DOKUMEN HASIL SCAN:
{ocr_context}

Tolong jawab instruksi di atas berdasarkan data dokumen tersebut secara detail.
"""

                # --- 4. PANGGIL SMART CHAT ---
                reply, pdf_info, should_include_pdf = await smart_chat_with_context(
                    user_message=final_message_to_ai,  # Masukin yang sudah digabung
                    active_file=active_file,  # Tetap dikirim buat cadangan di smart_chat
                    mode=mode,
                    model=selected_model,
                    session_uuid=session_uuid,
                    npp=npp,
                    role=role,
                    attachments=attachments,
                )

                # --- 4. GENERATE EMBEDDINGS & SAVE HISTORY ---
                try:
                    # Ambil embedding (pastikan get_embedding lu return list [0.1, 0.2, ...])
                    vector_user = get_embedding(user_message)
                    vector_assistant = get_embedding(reply)

                    # Jika return None (error dari model embedding), buat dummy
                    if vector_user is None:
                        vector_user = [0.0] * 768
                    if vector_assistant is None:
                        vector_assistant = [0.0] * 768

                except Exception as emb_e:
                    print(f"[WARNING] Gagal generate embedding: {emb_e}")
                    vector_user = [0.0] * 768
                    vector_assistant = [0.0] * 768

                await conn.execute(
                    """
                    INSERT INTO ai_dialogue_corpus (
                        session_id, user_text, assistant_text, 
                        embedding_user, embedding_assistant, metadata, files
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                    current_session_id,
                    user_message,
                    reply,
                    vector_user,
                    vector_assistant,
                    json.dumps(
                        {
                            "mode": mode,
                            "file_id": file_id,
                            "npp": npp,
                            "role": role,
                            "model": selected_model,
                            "has_ocr": ocr_context != "",
                        }
                    ),
                    json.dumps(attachments),
                )

        # --- 5. RESPONSE KE FRONTEND ---
        return JSONResponse(
            {
                "reply": reply,
                "session_uuid": session_uuid,
                "judul": judul_baru,
                "pdf_info": pdf_info if (should_include_pdf and npp) else None,
                "is_from_document": (should_include_pdf or ocr_context != ""),
                "model_used": selected_model,
                "attachments": attachments,
            }
        )

    except Exception as e:
        logging.error(f"Chat Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/chat-history/{npp}")
async def get_chat_history(npp: str):
    try:
        async with rag_pool.acquire() as conn:
            sessions = await conn.fetch(
                """
                SELECT session_uuid, judul, started_at, is_pinned  
                FROM chat_sessions 
                WHERE npp = $1 AND is_active = TRUE
                AND is_deleted = false  
                ORDER BY is_pinned DESC, started_at DESC 
            """,
                npp,
            )
            return JSONResponse({"status": "success", "data": [dict(row) for row in sessions]})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/chat-messages/{session_uuid}")
async def get_session_messages(session_uuid: str):
    try:
        async with rag_pool.acquire() as conn:
            # 1. Cari session_id berdasarkan UUID
            sess = await conn.fetchrow(
                "SELECT id FROM chat_sessions WHERE session_uuid = $1", session_uuid,
            )
            if not sess:
                return JSONResponse(
                    {"status": "error", "message": "Sesi tidak ditemukan"},
                    status_code=404
                )

            # 2. Ambil user_text, assistant_text, created_at, dan kolom FILES
            rows = await conn.fetch(
                """
                SELECT user_text, assistant_text, created_at, files
                FROM ai_dialogue_corpus 
                WHERE session_id = $1 
                ORDER BY created_at ASC
            """,
                sess["id"],
            )

            formatted_messages = []
            for row in rows:
                # Ambil data files (jika None, set jadi array kosong)
                attachments = row.get("files") if row.get("files") else []

                # --- Pesan User ---
                formatted_messages.append(
                    {
                        "id": f"u-{row['created_at'].timestamp()}",
                        "sender": "user",
                        "text": row["user_text"],
                        "attachments": attachments,  # MASUKKAN DATA FILE DI SINI
                        "timestamp": row["created_at"].strftime("%H:%M"),
                    }
                )

                # --- Pesan AI ---
                formatted_messages.append(
                    {
                        "id": f"a-{row['created_at'].timestamp()}",
                        "sender": "ai",  # Fix typo logic sender
                        "text": row["assistant_text"],
                        "timestamp": row["created_at"].strftime("%H:%M"),
                    }
                )

            return JSONResponse({"status": "success", "data": formatted_messages})

    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/db_doc/{filename}")
async def serve_db_doc(filename: str):
    """Serve files from db_doc folder for preview"""
    try:
        db_doc_folder = DB_DOC_FOLDER
        filepath = os.path.join(db_doc_folder, filename)

        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail=f"File {filename} not found")

        # Untuk PDF, set headers yang tepat
        if filename.lower().endswith(".pdf"):
            return FileResponse(
                filepath,
                media_type="application/pdf",
                headers={
                    "Content-Type": "application/pdf",
                    "X-Content-Type-Options": "nosniff"
                }
            )
        else:
            return FileResponse(filepath)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error serving db_doc file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download file with attachment header - akan di-download, bukan dibuka"""
    try:
        # Cari file di db_doc folder dulu
        db_doc_folder = DB_DOC_FOLDER
        filepath = os.path.join(db_doc_folder, filename)

        # Jika tidak ada di db_doc, coba di uploads
        if not os.path.exists(filepath):
            upload_folder = UPLOAD_FOLDER
            filepath = os.path.join(upload_folder, filename)

        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="File not found")

        # Set header untuk force download (bukan preview)
        return FileResponse(
            filepath,
            filename=filename,
            media_type='application/octet-stream',
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# seacrh
@app.post("/api/search")
async def search_pindad(request: Request):
    try:
        data = await request.json()
        query = data.get("query", "").strip()

        if not query:
            return JSONResponse({"error": "Query tidak boleh kosong"}, status_code=400)

        # Gunakan fungsi scrape yang baru
        search_result = await scrape_pindad_website(query)

        return JSONResponse(
            {
                "status": "success",
                "query": query,
                "result": search_result,  # PERBAIKAN: Pastikan ini string, bukan objek
            }
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# upload
@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """Upload dan analisis file dengan qwen3-vl"""
    try:
        if not file:
            return JSONResponse({"error": "Tidak ada file"}, status_code=400)

        filename = secure_filename(file.filename)
        
        if not allowed_file(filename):
            return JSONResponse({"error": "Tipe file tidak didukung"}, status_code=400)

        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        with open(filepath, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        filetype = filename.rsplit(".", 1)[1].lower()

        # Generate unique ID
        file_id = str(uuid.uuid4())[:8]

        # Simpan metadata awal
        file_contexts[file_id] = {
            "id": file_id,
            "filename": filename,
            "type": filetype,
            "path": filepath,
            "text": "[Sedang mengekstrak...]",
        }

        # Ekstrak konten
        extracted_text = await extract_with_qwen3_vl(filepath, filetype)

        # Update dengan hasil ekstraksi
        file_contexts[file_id]["text"] = extracted_text[:8000]

        # Generate ringkasan
        summary = await generate_summary(extracted_text[:2000])

        return JSONResponse(
            {
                "success": True,
                "file_id": file_id,
                "filename": filename,
                "file_type": filetype,
                "text_length": len(extracted_text),
                "summary": summary,
                "message": f"✅ File '{filename}' berhasil diupload dan dianalisis.",
            }
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/analyze")
async def analyze(request: Request):
    """Endpoint khusus untuk analisis file"""
    try:
        data = await request.json()
        file_id = data.get("file_id")
        question = data.get("question", "Apa isi file ini?")

        if not file_id or file_id not in file_contexts:
            return JSONResponse({"error": "File tidak ditemukan"}, status_code=404)

        context = file_contexts[file_id]

        # Untuk file gambar, kirim langsung ke model
        if context["type"] in ["png", "jpg", "jpeg"]:
            with open(context["path"], "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            reply = await ask_qwen3_vl(
                question, images=[img_b64], file_type=context["type"]
            )

        else:
            # Untuk file lain
            prompt = f"""File: {context["filename"]}

Konten File:
{context["text"][:4000]}

Pertanyaan: {question}

Jawab dalam Bahasa Indonesia:"""

            reply = await ask_qwen3_vl(prompt)

        return JSONResponse({"reply": reply, "file": context["filename"]})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/files")
async def list_files():
    """List semua file yang diupload"""
    files_list = []
    for fid, context in file_contexts.items():
        files_list.append(
            {
                "id": fid,
                "filename": context["filename"],
                "type": context["type"],
                "size": os.path.getsize(context["path"])
                if os.path.exists(context["path"])
                else 0,
                "summary": context["text"][:150] + "..."
                if len(context["text"]) > 150
                else context["text"],
            }
        )

    return JSONResponse({"files": files_list, "count": len(files_list)})


@app.post("/api/upload-preview")
async def upload_preview(file: UploadFile = File(...)):
    """Preview file before full upload and processing"""
    try:
        filename = secure_filename(file.filename)
        
        if not allowed_file(filename):
            return JSONResponse({"error": "Tipe file tidak didukung"}, status_code=400)

        filetype = filename.rsplit(".", 1)[1].lower()

        # Generate unique ID
        file_id = str(uuid.uuid4())

        # Create temp upload path
        temp_filename = f"temp_{file_id}_{filename}"
        temp_filepath = os.path.join(UPLOAD_FOLDER, temp_filename)
        
        with open(temp_filepath, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Extract preview text using qwen3-vl or fallback
        preview_text = await extract_with_qwen3_vl(temp_filepath, filetype)
        preview_text = preview_text[:1000]  # Limit preview text

        # Store in temp storage
        temp_uploaded_files[file_id] = {
            "filepath": temp_filepath,
            "filename": filename,
            "filetype": filetype,
            "preview_text": preview_text,
        }

        return JSONResponse(
            {
                "success": True,
                "file_id": file_id,
                "filename": filename,
                "file_type": filetype,
                "preview_text": preview_text,
                "size": os.path.getsize(temp_filepath),
            }
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/confirm-upload")
async def confirm_upload(request: Request):
    """Confirm and process uploaded file after preview"""
    try:
        data = await request.json()
        file_id = data.get("file_id")

        if not file_id or file_id not in temp_uploaded_files:
            return JSONResponse({"error": "File tidak ditemukan"}, status_code=404)

        temp_file_info = temp_uploaded_files[file_id]
        filepath = temp_file_info["filepath"]
        filename = temp_file_info["filename"]
        filetype = temp_file_info["filetype"]

        # Move file to permanent location
        final_filepath = os.path.join(UPLOAD_FOLDER, filename)
        # If filename already exists, add timestamp
        if os.path.exists(final_filepath):
            name, ext = os.path.splitext(filename)
            timestamp = str(int(time.time()))
            final_filename = f"{name}_{timestamp}{ext}"
            final_filepath = os.path.join(UPLOAD_FOLDER, final_filename)
        else:
            final_filename = filename

        import shutil

        shutil.move(filepath, final_filepath)

        # Generate unique ID for permanent storage
        final_file_id = str(uuid.uuid4())[:8]

        # Store in main context
        file_contexts[final_file_id] = {
            "id": final_file_id,
            "filename": final_filename,
            "type": filetype,
            "path": final_filepath,
            "text": temp_file_info["preview_text"],  # Use the preview text
        }

        # Remove from temp storage
        del temp_uploaded_files[file_id]

        # Generate summary
        summary = await generate_summary(temp_file_info["preview_text"][:2000])

        return JSONResponse(
            {
                "success": True,
                "file_id": final_file_id,
                "filename": final_filename,
                "file_type": filetype,
                "text_length": len(temp_file_info["preview_text"]),
                "summary": summary,
                "message": f"✅ File '{final_filename}' berhasil diproses.",
            }
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/cancel-upload")
async def cancel_upload(request: Request):
    """Cancel upload and remove temp file"""
    try:
        data = await request.json()
        file_id = data.get("file_id")

        if not file_id or file_id not in temp_uploaded_files:
            return JSONResponse(
                {"success": True, "message": "File tidak ditemukan di temp storage"}
            )

        temp_file_info = temp_uploaded_files[file_id]
        filepath = temp_file_info["filepath"]

        # Remove temp file
        if os.path.exists(filepath):
            os.remove(filepath)

        # Remove from temp storage
        del temp_uploaded_files[file_id]

        return JSONResponse(
            {"success": True, "message": "Upload dibatalkan dan file dihapus"}
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/mode-switch")
async def mode_switch(request: Request):
    """Endpoint to switch between different modes"""
    try:
        data = await request.json()
        mode = data.get("mode", MODE_NORMAL)

        # Validate mode
        if mode not in [MODE_NORMAL, MODE_DOCUMENT, MODE_SEARCH]:
            return JSONResponse({"error": "Invalid mode"}, status_code=400)

        return JSONResponse(
            {"success": True, "mode": mode, "message": f"Mode changed to {mode}"}
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/documents")
async def list_documents():
    """Get list of documents from database"""
    try:
        async with rag_pool.acquire() as conn:

            # Get all documents
            sql = """
            SELECT d.id, d.judul, d.nomor, d.tanggal, d.filename, d.status, d.created_at
            FROM dokumen d
            ORDER BY d.created_at DESC
            LIMIT 20;
            """

            documents = await conn.fetch(sql)

            return JSONResponse(
                {"documents": [dict(row) for row in documents], "count": len(documents)}
            )

    except Exception as e:
        logging.error(f"Error listing documents: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/document/{doc_id}")
async def get_document(doc_id: int):
    """Get specific document details from database"""
    try:
        async with rag_pool.acquire() as conn:

            # Get document details
            sql = """
            SELECT d.id, d.judul, d.nomor, d.tanggal, d.tempat, d.filename, d.status,
                   d.created_at, d.status_ocr, d.source_file_type
            FROM dokumen d
            WHERE d.id = $1;
            """

            document = await conn.fetchrow(sql, doc_id)

            if not document:
                return JSONResponse({"error": "Document not found"}, status_code=404)

            # Get related chunks
            chunk_sql = """
            SELECT id, content, created_at
            FROM dokumen_chunk
            WHERE dokumen_id = $1
            ORDER BY chunk_id;
            """

            chunks = await conn.fetch(chunk_sql, doc_id)

            return JSONResponse(
                {"document": dict(document), "chunks": [dict(row) for row in chunks]}
            )

    except Exception as e:
        logging.error(f"Error getting document: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OLLAMA_URL,
                json={
                    "model": PRIMARY_MODEL,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False,
                },
                timeout=5,
            ) as resp:
                ollama_status = resp.status == 200

        return JSONResponse(
            {
                "status": "healthy",
                "service": "CAKRA AI Pro",
                "model": PRIMARY_MODEL,
                "uploaded_files": len(file_contexts),
                "ollama_connected": ollama_status,
            }
        )
    except Exception as e:
        return JSONResponse({"status": "unhealthy", "error": str(e)}, status_code=500)


@app.post("/api/chat/pin/{session_uuid}")
async def toggle_pin_chat(session_uuid: str):
    try:
        async with rag_pool.acquire() as conn:
            # Logika TOGGLE: kalau true jadi false, kalau false jadi true
            sql = """
                UPDATE chat_sessions
                SET is_pinned = NOT is_pinned
                WHERE session_uuid = $1
                RETURNING is_pinned
            """
            result = await conn.fetchrow(sql, session_uuid)

            if result:
                new_status = result[0]
                return JSONResponse(
                    {
                        "status": "success",
                        "message": f"Chat {'disematkan' if new_status else 'dilepas'}",
                        "is_pinned": new_status,
                    }
                )
            else:
                return JSONResponse(
                    {"status": "error", "message": "Session tidak ditemukan"}
                , status_code=404)

    except Exception as e:
        print(f"Error toggle pin: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/chat/rename/{session_uuid}")
async def rename_chat(session_uuid: str, request: Request):
    try:
        # WAJIB pakai await di sini karena ini coroutine
        data = await request.json()

        if not data:
            return JSONResponse({"status": "error", "message": "Data tidak ditemukan"}, status_code=400)

        new_judul = data.get("judul")

        # Koneksi DB (Gunakan koneksi standar lu)
        async with rag_pool.acquire() as conn:
            await conn.execute(
                "UPDATE chat_sessions SET judul = $1 WHERE session_uuid = $2",
                new_judul, session_uuid,
            )

        return JSONResponse({"status": "success", "message": "Judul berhasil diubah"})
    except Exception as e:
        print(f"Error Rename: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/chat/delete/{session_uuid}")
async def delete_chat(session_uuid: str):
    try:
        async with rag_pool.acquire() as conn:
            # Soft delete: cuma ubah flag is_deleted
            sql = "UPDATE chat_sessions SET is_deleted = true WHERE session_uuid = $1"
            await conn.execute(sql, session_uuid)

        return JSONResponse(
            {"status": "success", "message": "Chat berhasil dihapus (soft delete)"}
        )
    except Exception as e:
        print(f"Error Delete: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)

    print(f"🚀 CAKRA AI Pro starting...")
    print(f"🤖 Primary Model: {PRIMARY_MODEL}")
    print(f"📁 Upload folder: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"🌐 API running on http://0.0.0.0:5000")

    uvicorn.run(app, host="0.0.0.0", port=5000, reload=True)