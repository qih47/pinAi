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
import psycopg2
import hashlib
import requests
import numpy as np
from quart import Quart, request, jsonify
from quart_cors import cors
from PIL import Image
from werkzeug.utils import secure_filename
from psycopg2.extras import RealDictCursor
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from quart import send_file

# Konstanta
# Gunakan SIMILARITY_THRESHOLD yang sesuai, misalnya 0.7
# Ini adalah ambang batas cosine similarity
SIMILARITY_THRESHOLD = 0.7  # Atur sesuai kebutuhan
LIMIT = 10  # Atur sesuai kebutuhan
# Initialize embedding model (same as in your upload route)
EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")

app = Quart(__name__)

# ========== KONFIGURASI ==========
UPLOAD_FOLDER = "./uploads"
DB_DOC_FOLDER = "./db_doc"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt", "docx", "pptx", "xlsx"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["DB_DOC_FOLDER"] = DB_DOC_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB

# CORS
app = cors(app, allow_origin=["http://192.168.11.80:5173", "http://localhost:5173"])

# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "ragdb",
    "user": "pindadai",
    "password": "Pindad123!",
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

# Context-aware storage
file_contexts = {}  # {file_id: {metadata, text, embeddings}}
temp_uploaded_files = {}  # {file_id: {filepath, filename, filetype, preview_text}}


# ========== HELPER FUNCTIONS ==========
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    return psycopg2.connect(
        host="localhost", database="ragdb", user="pindadai", password="Pindad123!"
    )


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
                                content: mainContent.innerText.replace(/\\s+/g, ' ').trim()
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

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

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
            ts_rank_cd(to_tsvector('indonesian', dc.content), plainto_tsquery('indonesian', %s), 1) as fts_score -- Gunakan ts_rank_cd untuk efisiensi
        FROM dokumen_chunk dc
        JOIN dokumen d ON dc.dokumen_id = d.id
        WHERE to_tsvector('indonesian', dc.content) @@ plainto_tsquery('indonesian', %s)
          AND d.status_ocr = 'rag_ready'
        ORDER BY fts_score DESC
        LIMIT %s;
        """
        cur.execute(fts_sql, (query, query, limit))
        fts_chunks = cur.fetchall()
        logging.info(f"✅ [search_documents] FTS menemukan {len(fts_chunks)} chunk.")

        # --- 2. Vector Search ---
        logging.info("🔍 [search_documents] Menjalankan Vector Search...")
        # Gunakan <#> untuk cosine distance (1 - cosine_similarity) di pgvector
        # Jadi, (dc.embedding <#> %s::vector) = 1 - cosine_similarity
        # cosine_similarity = 1 - (dc.embedding <#> %s::vector)
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
            (dc.embedding <#> %s::vector) as cosine_distance
        FROM dokumen_chunk dc
        JOIN dokumen d ON dc.dokumen_id = d.id
        WHERE d.status_ocr = 'rag_ready'
        ORDER BY (dc.embedding <#> %s::vector)
        LIMIT %s;
        """
        cur.execute(vector_sql, (query_vector_str, query_vector_str, limit))
        vector_chunks = cur.fetchall()
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
            WHERE id = ANY(%s)
            """
            cur.execute(doc_sql, (document_ids,))
            documents = cur.fetchall()

        logging.info(
            f"✅ [search_documents] Ditemukan {len(final_chunks)} chunk yang melewati filter Hybrid Search (threshold={SIMILARITY_THRESHOLD})."
        )
        cur.close()
        conn.close()

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
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Gunakan kode vector search original kamu di sini
            # Pastikan query_vector_str dan threshold sudah didefinisikan
            # Gunakan <#> untuk cosine similarity
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
                (dc.embedding <#> %s::vector) as cosine_distance
            FROM dokumen_chunk dc
            JOIN dokumen d ON dc.dokumen_id = d.id
            WHERE d.status_ocr = 'rag_ready'
            ORDER BY (dc.embedding <#> %s::vector)
            LIMIT %s;
            """

            cur.execute(chunk_sql, (query_vector_str, query_vector_str, limit))
            chunks = cur.fetchall()

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
                WHERE id = ANY(%s)
                """
                cur.execute(doc_sql, (document_ids,))
                documents = cur.fetchall()

            logging.info(
                f"✅ [search_documents] Fallback Vector Search menemukan {len(final_chunks)} chunk."
            )
            cur.close()
            conn.close()

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


async def ask_qwen3_vl(prompt, images=None, stream=False, file_type=None):
    """Helper untuk bertanya ke model yang sesuai berdasarkan konten"""
    # Pilih model berdasarkan apakah ada gambar atau file PDF
    selected_model = (
        VISION_MODEL
        if images or (file_type and file_type in ["pdf", "png", "jpg", "jpeg"])
        else PRIMARY_MODEL
    )

    messages = [{"role": "user", "content": prompt}]
    if images:
        messages[0]["images"] = images

    async with aiohttp.ClientSession() as session:
        async with session.post(
            OLLAMA_URL,
            json={
                "model": selected_model,
                "messages": messages,
                "stream": stream,
                "options": {"temperature": 0.1},
            },
        ) as resp:
            if stream:
                reply = ""
                async for line in resp.content:
                    if line:
                        try:
                            obj = json.loads(line.decode("utf-8"))
                            reply += obj.get("message", {}).get("content", "")
                        except:
                            continue
                return reply
            else:
                result = await resp.json()
                return result.get("message", {}).get("content", "")


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


# ========== SMART CHAT FUNCTION ==========
# ========== SMART CHAT FUNCTION ==========
async def smart_chat_with_context(user_message, active_file=None, mode=MODE_NORMAL):
    """Smart chat that can detect and handle different modes"""
    
    # Inisialisasi pdf_info sebagai None
    pdf_info = None
    should_include_pdf = False
    
    if mode == MODE_SEARCH:
        # Search mode: Get information from www.pindad.com
        search_result = await scrape_pindad_website(user_message)
        search_prompt = f"""Kamu adalah asisten AI untuk PT Pindad. Berdasarkan informasi dari www.pindad.com:

{search_result}

Tolong jawab pertanyaan pengguna: 

    PERTANYAAN: "{user_message}"

    INSTRUKSI:
    1. Jika jawaban ada, berikan jawaban detail
    2. Jika tidak ada, JAWAB: "Tidak ditemukan informasi spesifik tentang hal ini dalam dokumen perusahaan" (bisa improvisasi tapi jangan memberikan informasi dokumen apapun)
    3. Gunakan Bahasa Indonesia yang baik dan benar dan jawab dengan natural

"""
        reply = await ask_qwen3_vl(search_prompt, stream=True)
        return reply, None, False

    elif mode == MODE_DOCUMENT:
        # Document mode: Hybrid search through database
        search_result = await search_documents(user_message)
        
        # --- LOGIKA FALLBACK LEBIH CERDAS ---
        MIN_RELEVANT_CHUNKS = 1
        relevant_chunks = [
            c for c in search_result["chunks"] 
            if c["similarity"] >= SIMILARITY_THRESHOLD
        ]

        # --- DETEKSI JENIS PERTANYAAN USER ---
        # Jika user hanya menyapa atau bertanya umum, jangan tampilkan PDF
        user_message_lower = user_message.lower()
        greeting_keywords = [
            'hai', 'hello', 'halo', 'hi', 'hey', 'selamat', 'pagi', 'siang', 'sore', 'malam',
            'apa kabar', 'how are you', 'bisa bantu', 'help', 'tolong',
            'terima kasih', 'thanks', 'makasih',
            'bye', 'sampai jumpa', 'goodbye'
        ]
        
        is_greeting = any(keyword in user_message_lower for keyword in greeting_keywords)
        
        if is_greeting:
            # User hanya menyapa, berikan respons biasa tanpa dokumen
            logging.info("🔍 User hanya menyapa, berikan respons normal")
            prompt = f"""Kamu adalah asisten AI untuk PT Pindad. 
            User berkata: "{user_message}"
            
            Berikan respons yang ramah dan sopan dalam Bahasa Indonesia.
            Jangan menyebutkan dokumen apapun karena user hanya menyapa."""
            
            reply = await ask_qwen3_vl(prompt, stream=True)
            return reply, None, False

        # --- AMBIL INFORMASI DOKUMEN UNTUK PDF ---
        document_info = None
        if relevant_chunks and search_result.get("documents"):
            # Ambil dokumen pertama yang relevan
            first_chunk = relevant_chunks[0]
            for doc in search_result["documents"]:
                if doc["id"] == first_chunk["dokumen_id"]:
                    document_info = doc
                    break
            
            # --- BUAT PDF_INFO UNTUK RESPONSE ---
            if document_info and relevant_chunks:
                filename = document_info.get("filename", "")
                if filename.lower().endswith('.pdf'):
                    filepath = os.path.join(app.config.get("DB_DOC_FOLDER", "./db_doc"), filename)
                    if os.path.exists(filepath):
                        pdf_info = {
                            "filename": filename,
                            "title": document_info.get("judul", filename),
                            "nomor": document_info.get("nomor", ""),
                            "tanggal": document_info.get("tanggal", ""),
                            "tempat": document_info.get("tempat", ""),
                            "url": f"/db_doc/{filename}",
                            "download_url": f"/db_doc/{filename}"
                        }
                        
                        # TANDAI BAHWA PDF HARUS DITAMPILKAN
                        should_include_pdf = True
                        logging.info(f"✅ PDF akan ditampilkan: {filename}")

        if not relevant_chunks or len(relevant_chunks) < MIN_RELEVANT_CHUNKS:
            # Tidak ada dokumen relevan
            logging.info("🔍 Tidak ada dokumen relevan yang ditemukan")
            if not active_file:
                reply = await ask_qwen3_vl(user_message, stream=True)
                return reply, None, False
            context_text = active_file["text"][:2500]
            prompt = f"""Tugas: Jawab pertanyaan pengguna dengan cerdas.
                INFORMASI FILE TERSEDIA (gunakan JIKA PERTANYAAN TENTANG FILE INI):
                📁 File: {active_file["filename"]}
                📄 Konten: {context_text}
                PERTANYAAN PENGGUNA: "{user_message}"
                INSTRUKSI:
                1. Analisis: Apakah pertanyaan ini tentang file di atas?
                2. Jika YA: Jawab berdasarkan konten file
                3. Jika TIDAK: Abaikan file, jawab sebagai AI assistant biasa
                4. Gunakan Bahasa Indonesia
                5. Jangan sebut "berdasarkan file" kecuali pertanyaan tentang file
                """
            reply = await ask_qwen3_vl(prompt, stream=True)
            return reply, None, False

        # --- BANGUN PROMPT DENGAN DOKUMEN ---
        context_parts = []
        for chunk in relevant_chunks[:3]:
            doc_title = chunk.get("judul") or "Dokumen Tanpa Judul"
            context_parts.append(f"""=== DOKUMEN: {doc_title} ===
                Isi:
                {chunk["content"]}
                Relevansi (Vector): {chunk["similarity"]:.4f} ---""")

        context_text = "\n".join(context_parts)
        
        # Ambil info sumber dari dokumen pertama
        source_info = ""
        doc_metadata = {}
        if relevant_chunks:
            first_doc_id = relevant_chunks[0]["dokumen_id"]
            source_doc = next(
                (d for d in search_result["documents"] if d["id"] == first_doc_id), None
            )
            if source_doc:
                # Simpan metadata dokumen untuk deteksi nanti
                doc_metadata = {
                    "judul": source_doc.get("judul", ""),
                    "nomor": source_doc.get("nomor", ""),
                    "tanggal": source_doc.get("tanggal", "")
                }
                
                jenis_dokumen_map = {
                    1: "SURAT KEPUTUSAN",
                    2: "SURAT EDARAN",
                    3: "INSTRUKSI KERJA",
                    4: "PROSEDUR",
                }
                jenis_dokumen = "DOKUMEN"
                if source_doc.get("id_jenis"):
                    jenis_dokumen = jenis_dokumen_map.get(
                        source_doc["id_jenis"], "DOKUMEN"
                    )
                source_info = f"""Sumber Informasi:
                    - Dokumen: {jenis_dokumen}
                    - Judul Dokumen: {source_doc.get("judul", "Tidak tersedia")}
                    - Nomor: {source_doc.get("nomor", "Tidak tersedia")}
                    - Tanggal: {source_doc.get("tanggal", "Tidak tersedia")}
                    - Tempat: {source_doc.get("tempat", "Tidak tersedia")}
                    - File: {source_doc.get("filename", "Tidak tersedia")}"""
                    
                referensi_doc = f"""Sumber Informasi:
                    - Dokumen: {jenis_dokumen}{source_doc.get("judul", "Tidak tersedia")}
                    - Nomor: {source_doc.get("nomor", "Tidak tersedia")}"""

        # Bangun prompt yang MEMAKSA AI untuk menyebut referensi
        doc_prompt = f"""
            Anda adalah AI internal PT Pindad.

            INFORMASI DOKUMEN:
            ====================================================
            {context_text}         
            {source_info}         
            ====================================================

            PERTANYAAN PENGGUNA: "{user_message}"

            INSTRUKSI SANGAT PENTING:
            1. Gunakan informasi dari dokumen di atas untuk menjawab
            2. Jangan mengubah makna konten dari dokumen 
            3. Di AKHIR jawaban, SEBUTKAN referensi dokumen dengan format:
               "Informasi ini berdasarkan dokumen {referensi_doc}"
            4. Jangan lupa menyebutkan nomor dokumen dan judulnya
            5. Jawab dalam Bahasa Indonesia yang natural
        """
        
        reply = await ask_qwen3_vl(doc_prompt, stream=True)
        
        # --- DETEKSI YANG LEBIH CERDAS ---
        # 1. Cek apakah AI menyebut referensi dokumen
        reply_lower = reply.lower()
        
        # Kata kunci yang menunjukkan AI menggunakan dokumen
        doc_references = [
            'berdasarkan dokumen', 'sesuai dokumen', 'dalam dokumen', 
            'menurut dokumen', 'dokumen menyebutkan', 'disebutkan dalam',
            'nomor', 'tanggal', 'surat keputusan', 'instruksi kerja',
            'prosedur', 'sumber:', 'mengacu pada', 'referensi',
            'informasi ini berdasarkan', 'berdasarkan instruksi',
            'dokumen i-', 'dokumen no.', 'dokumen nomor'
        ]
        
        # 2. Cek apakah AI menyebut nomor dokumen spesifik
        ai_used_document = False
        
        # Cek kata kunci umum
        for ref in doc_references:
            if ref in reply_lower:
                ai_used_document = True
                break
        
        # 3. Cek apakah AI menyebut metadata dokumen (judul/nomor)
        if doc_metadata.get("nomor") and doc_metadata["nomor"].lower() in reply_lower:
            ai_used_document = True
            logging.info(f"✅ AI menyebut nomor dokumen: {doc_metadata['nomor']}")
        
        if doc_metadata.get("judul") and any(word in reply_lower for word in doc_metadata["judul"].lower().split()[:3]):
            ai_used_document = True
            logging.info(f"✅ AI menyebut judul dokumen: {doc_metadata['judul']}")
        
        # 4. Cek apakah jawaban mengandung informasi spesifik (bukan general)
        # Kata kunci yang menunjukkan informasi spesifik
        specific_info_keywords = [
            'langkah-langkah', 'prosedur', 'instruksi', 'tahapan',
            'cara', 'teknis', 'operasional', 'suhu', 'saklar',
            'tombol', 'panel', 'mesin', 'alat'
        ]
        
        has_specific_info = any(keyword in reply_lower for keyword in specific_info_keywords)
        
        # Logika akhir: Tampilkan PDF jika:
        # 1. Ada PDF info yang valid
        # 2. DAN (AI menyebut dokumen ATAU jawaban mengandung info spesifik)
        final_should_include = False
        if pdf_info and should_include_pdf:
            if ai_used_document or has_specific_info:
                final_should_include = True
                logging.info(f"✅ Final: PDF akan ditampilkan. AI used doc: {ai_used_document}, Has specific info: {has_specific_info}")
            else:
                logging.info(f"⚠️ Final: PDF TIDAK ditampilkan. AI used doc: {ai_used_document}, Has specific info: {has_specific_info}")
        
        if final_should_include:
            return reply, pdf_info, True
        else:
            return reply, None, False

    elif mode == MODE_NORMAL:
        # Normal mode: Direct chat without special context
        if not active_file:
            reply = await ask_qwen3_vl(user_message, stream=True)
            return reply, None, False

        context_text = active_file["text"][:2500]
        prompt = f"""Tugas: Jawab pertanyaan pengguna dengan cerdas.

INFORMASI FILE TERSEDIA (gunakan JIKA PERTANYAAN TENTANG FILE INI):
📁 File: {active_file["filename"]}
📄 Konten: {context_text}

PERTANYAAN PENGGUNA: "{user_message}"

INSTRUKSI:
1. Analisis: Apakah pertanyaan ini tentang file di atas?
2. Jika YA: Jawab berdasarkan konten file
3. Jika TIDAK: Abaikan file, jawab sebagai AI assistant biasa
4. Gunakan Bahasa Indonesia
5. Jangan sebut "berdasarkan file" kecuali pertanyaan tentang file

"""
        reply = await ask_qwen3_vl(prompt, stream=True)
        return reply, None, False


# ========== ROUTES ==========
@app.route("/api/chat", methods=["POST"])
async def chat():
    """Endpoint chat utama dengan SMART context handling"""
    try:
        data = await request.get_json()
        user_message = data.get("message", "")
        file_id = data.get("file_id", None)
        mode = data.get("mode", MODE_NORMAL)

        # Cek file context
        active_file = None
        if file_id and file_id in file_contexts:
            active_file = file_contexts[file_id]
        elif file_contexts and mode == MODE_NORMAL:
            last_file_id = list(file_contexts.keys())[-1]
            active_file = file_contexts[last_file_id]

        # Panggil SMART chat function (sekarang mengembalikan 3 values)
        reply, pdf_info, should_include_pdf = await smart_chat_with_context(user_message, active_file, mode)

        # Format response - HANYA sertakan pdf_info jika should_include_pdf True
        response = {
            "reply": reply, 
            "mode": mode,
            "pdf_info": pdf_info if should_include_pdf else None,  # <-- KUNCI UTAMA
            "is_from_document": should_include_pdf  # <-- Gunakan should_include_pdf
        }
        
        if active_file:
            response["file_info"] = {
                "id": active_file["id"],
                "name": active_file["filename"],
            }

        # Debug log
        logging.info(f"📤 Response - Mode: {mode}, Should Include PDF: {should_include_pdf}, PDF Info: {pdf_info is not None}")

        return jsonify(response)

    except Exception as e:
        logging.error(f"Chat error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/db_doc/<filename>", methods=["GET"])
async def serve_db_doc(filename):
    """Serve files from db_doc folder for preview"""
    try:
        db_doc_folder = app.config.get("DB_DOC_FOLDER", "./db_doc")
        filepath = os.path.join(db_doc_folder, filename)

        if not os.path.exists(filepath):
            return jsonify({"error": f"File {filename} not found"}), 404

        # Untuk PDF, set headers yang tepat
        if filename.lower().endswith(".pdf"):
            response = await send_file(
                filepath,
                mimetype="application/pdf",
                as_attachment=False,  # Ini penting untuk preview di browser
            )
            # Tambahkan header untuk mencegah caching issues
            response.headers["Content-Type"] = "application/pdf"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        else:
            return await send_file(filepath)

    except Exception as e:
        logging.error(f"Error serving db_doc file: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/db_doc/<filename>", methods=["GET"])
async def download_file(filename):
    """Download file with attachment header - akan di-download, bukan dibuka"""
    try:
        # Cari file di db_doc folder dulu
        db_doc_folder = app.config.get("DB_DOC_FOLDER", "./db_doc")
        filepath = os.path.join(db_doc_folder, filename)

        # Jika tidak ada di db_doc, coba di uploads
        if not os.path.exists(filepath):
            upload_folder = app.config.get("UPLOAD_FOLDER", "./uploads")
            filepath = os.path.join(upload_folder, filename)

        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404

        # Set header untuk force download (bukan preview)
        response = await send_file(filepath, as_attachment=True)
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# seacrh
@app.route("/api/search", methods=["POST"])
async def search_pindad():
    try:
        data = await request.get_json()
        query = data.get("query", "").strip()

        if not query:
            return jsonify({"error": "Query tidak boleh kosong"}), 400

        # Gunakan fungsi scrape yang baru
        search_result = await scrape_pindad_website(query)

        return jsonify(
            {
                "status": "success",
                "query": query,
                "result": search_result,  # PERBAIKAN: Pastikan ini string, bukan objek
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# upload
@app.route("/api/upload", methods=["POST"])
async def upload():
    """Upload dan analisis file dengan qwen3-vl"""
    try:
        if "file" not in (await request.files):
            return jsonify({"error": "Tidak ada file"}), 400

        files = await request.files
        file = files["file"]

        if not allowed_file(file.filename):
            return jsonify({"error": "Tipe file tidak didukung"}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        await file.save(filepath)

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

        return jsonify(
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
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze", methods=["POST"])
async def analyze():
    """Endpoint khusus untuk analisis file"""
    try:
        data = await request.get_json()
        file_id = data.get("file_id")
        question = data.get("question", "Apa isi file ini?")

        if not file_id or file_id not in file_contexts:
            return jsonify({"error": "File tidak ditemukan"}), 404

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

        return jsonify({"reply": reply, "file": context["filename"]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/files", methods=["GET"])
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

    return jsonify({"files": files_list, "count": len(files_list)})


@app.route("/api/upload-preview", methods=["POST"])
async def upload_preview():
    """Preview file before full upload and processing"""
    try:
        if "file" not in (await request.files):
            return jsonify({"error": "Tidak ada file"}), 400

        files = await request.files
        file = files["file"]

        if not allowed_file(file.filename):
            return jsonify({"error": "Tipe file tidak didukung"}), 400

        filename = secure_filename(file.filename)
        filetype = filename.rsplit(".", 1)[1].lower()

        # Generate unique ID
        file_id = str(uuid.uuid4())

        # Create temp upload path
        temp_filename = f"temp_{file_id}_{filename}"
        temp_filepath = os.path.join(app.config["UPLOAD_FOLDER"], temp_filename)
        await file.save(temp_filepath)

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

        return jsonify(
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
        return jsonify({"error": str(e)}), 500


@app.route("/api/confirm-upload", methods=["POST"])
async def confirm_upload():
    """Confirm and process uploaded file after preview"""
    try:
        data = await request.get_json()
        file_id = data.get("file_id")

        if not file_id or file_id not in temp_uploaded_files:
            return jsonify({"error": "File tidak ditemukan"}), 404

        temp_file_info = temp_uploaded_files[file_id]
        filepath = temp_file_info["filepath"]
        filename = temp_file_info["filename"]
        filetype = temp_file_info["filetype"]

        # Move file to permanent location
        final_filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        # If filename already exists, add timestamp
        if os.path.exists(final_filepath):
            name, ext = os.path.splitext(filename)
            timestamp = str(int(time.time()))
            final_filename = f"{name}_{timestamp}{ext}"
            final_filepath = os.path.join(app.config["UPLOAD_FOLDER"], final_filename)
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

        return jsonify(
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
        return jsonify({"error": str(e)}), 500


@app.route("/api/cancel-upload", methods=["POST"])
async def cancel_upload():
    """Cancel upload and remove temp file"""
    try:
        data = await request.get_json()
        file_id = data.get("file_id")

        if not file_id or file_id not in temp_uploaded_files:
            return jsonify(
                {"success": True, "message": "File tidak ditemukan di temp storage"}
            )

        temp_file_info = temp_uploaded_files[file_id]
        filepath = temp_file_info["filepath"]

        # Remove temp file
        if os.path.exists(filepath):
            os.remove(filepath)

        # Remove from temp storage
        del temp_uploaded_files[file_id]

        return jsonify(
            {"success": True, "message": "Upload dibatalkan dan file dihapus"}
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mode-switch", methods=["POST"])
async def mode_switch():
    """Endpoint to switch between different modes"""
    try:
        data = await request.get_json()
        mode = data.get("mode", MODE_NORMAL)

        # Validate mode
        if mode not in [MODE_NORMAL, MODE_DOCUMENT, MODE_SEARCH]:
            return jsonify({"error": "Invalid mode"}), 400

        return jsonify(
            {"success": True, "mode": mode, "message": f"Mode changed to {mode}"}
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/documents", methods=["GET"])
async def list_documents():
    """Get list of documents from database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get all documents
        sql = """
        SELECT d.id, d.judul, d.nomor, d.tanggal, d.filename, d.status, d.created_at
        FROM dokumen d
        ORDER BY d.created_at DESC
        LIMIT 20;
        """

        cur.execute(sql)
        documents = cur.fetchall()

        cur.close()
        conn.close()

        return jsonify(
            {"documents": [dict(row) for row in documents], "count": len(documents)}
        )

    except Exception as e:
        logging.error(f"Error listing documents: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/document/<int:doc_id>", methods=["GET"])
async def get_document(doc_id):
    """Get specific document details from database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get document details
        sql = """
        SELECT d.id, d.judul, d.nomor, d.tanggal, d.tempat, d.filename, d.status, 
               d.created_at, d.status_ocr, d.source_file_type
        FROM dokumen d
        WHERE d.id = %s;
        """

        cur.execute(sql, (doc_id,))
        document = cur.fetchone()

        if not document:
            cur.close()
            conn.close()
            return jsonify({"error": "Document not found"}), 404

        # Get related chunks
        chunk_sql = """
        SELECT id, content, created_at
        FROM dokumen_chunk
        WHERE dokumen_id = %s
        ORDER BY chunk_id;
        """

        cur.execute(chunk_sql, (doc_id,))
        chunks = cur.fetchall()

        cur.close()
        conn.close()

        return jsonify(
            {"document": dict(document), "chunks": [dict(row) for row in chunks]}
        )

    except Exception as e:
        logging.error(f"Error getting document: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
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

        return jsonify(
            {
                "status": "healthy",
                "service": "CAKRA AI Pro",
                "model": PRIMARY_MODEL,
                "uploaded_files": len(file_contexts),
                "ollama_connected": ollama_status,
            }
        )
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print(f"🚀 CAKRA AI Pro starting...")
    print(f"🤖 Primary Model: {PRIMARY_MODEL}")
    print(f"📁 Upload folder: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"🌐 API running on http://0.0.0.0:5000")

    app.run(host="0.0.0.0", port=5000, debug=True)
