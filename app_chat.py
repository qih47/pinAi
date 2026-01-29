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
from quart import Quart, request, jsonify, send_file
from quart_cors import cors
from PIL import Image
from werkzeug.utils import secure_filename
from psycopg2.extras import RealDictCursor
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urljoin
from backend.app.services.ocr.ocr_processor import process_pdf_attachment_to_ocr

# Konstanta
SIMILARITY_THRESHOLD = 0.7
LIMIT = 10
EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")

app = Quart(__name__)

# ========== KONFIGURASI ==========
UPLOAD_FOLDER = "./uploads"
DB_DOC_FOLDER = "./db_doc"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt", "docx", "pptx", "xlsx"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["DB_DOC_FOLDER"] = DB_DOC_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# CORS
app = cors(app, allow_origin=["http://192.168.11.80:5173", "http://localhost:5173"])

# ========== KONFIGURASI DATABASE ==========
DB_CONFIG = {
    "host": "localhost",
    "database": "ragdb",
    "user": "pindadai",
    "password": "Pindad123!",
}

DB_LOGIN_CONFIG = {
    "host": "192.168.11.55",
    "database": "qa_payroll_db",
    "user": "qisthi",
    "password": "q1sthi",
}

# ========== KONFIGURASI OLLAMA ==========
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

PRIMARY_MODEL = "qwen3:8b"
VISION_MODEL = "qwen3-vl:8b"

MODE_NORMAL = "normal"
MODE_DOCUMENT = "document"
MODE_SEARCH = "search"


# ========== HELPER FUNCTIONS ==========
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    """Membuat koneksi database menggunakan DB_CONFIG"""
    return psycopg2.connect(**DB_CONFIG)


def embedding_to_pgvector_str(embedding):
    """Konversi embedding numpy ke string format vector PostgreSQL"""
    emb_array = np.array(embedding)
    return f"[{','.join(f'{val:.8f}' for val in emb_array)}]"


def get_embedding(text):
    """Generate embedding menggunakan SentenceTransformer"""
    if not text:
        return None
    try:
        embedding = EMBEDDING_MODEL.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logging.error(f"Embedding Error: {e}")
        return None


def get_chat_history_from_db(session_uuid, limit=5):
    """Mengambil history percakapan terakhir"""
    history = []
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT d.user_text, d.assistant_text 
            FROM ai_dialogue_corpus d
            JOIN chat_sessions s ON d.session_id = s.id
            WHERE s.session_uuid = %s
            ORDER BY d.created_at DESC, d.id DESC 
            LIMIT %s
        """
        cur.execute(query, (session_uuid, limit))
        rows = cur.fetchall()

        for row in reversed(rows):
            history.append({"role": "user", "content": row["user_text"]})
            history.append({"role": "assistant", "content": row["assistant_text"]})

        return history
    except Exception as e:
        logging.error(f"❌ Error fetch history: {e}")
        return []
    finally:
        if conn:
            conn.close()


# ========== WEB SCRAPING FUNCTIONS ==========
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
            await page.set_extra_http_headers(
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
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


# ========== AI FUNCTIONS ==========
async def ask_qwen3_vl(
    prompt, images=None, stream=False, file_type=None, override_model=None
):
    """Helper untuk bertanya ke model yang sesuai"""
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


async def search_documents(query, limit=LIMIT):
    """Search documents in the database using Hybrid Search"""
    logging.info(f"🔍 [search_documents] Mencari (Hybrid): '{query}'")
    try:
        query_embedding = EMBEDDING_MODEL.encode([query], normalize_embeddings=True)[
            0
        ].tolist()
        query_vector_str = embedding_to_pgvector_str(query_embedding)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Full-Text Search
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
            ts_rank_cd(to_tsvector('indonesian', dc.content), plainto_tsquery('indonesian', %s), 1) as fts_score
        FROM dokumen_chunk dc
        JOIN dokumen d ON dc.dokumen_id = d.id
        WHERE to_tsvector('indonesian', dc.content) @@ plainto_tsquery('indonesian', %s)
          AND d.status_ocr = 'rag_ready'
        ORDER BY fts_score DESC
        LIMIT %s;
        """
        cur.execute(fts_sql, (query, query, limit))
        fts_chunks = cur.fetchall()
        logging.info(f"✅ FTS menemukan {len(fts_chunks)} chunk.")

        # Vector Search
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
        logging.info(f"✅ Vector Search menemukan {len(vector_chunks)} chunk.")

        # Gabungkan Hasil (Hybrid)
        combined_scores = {}
        id_to_chunk = {}

        for chunk in fts_chunks:
            chunk_id = chunk["id"]
            combined_scores[chunk_id] = {
                "fts_score": chunk["fts_score"],
                "vector_score": 0.0,
                "similarity": 0.0,
                "chunk_data": chunk,
            }
            id_to_chunk[chunk_id] = chunk
            del combined_scores[chunk_id]["chunk_data"]["fts_score"]

        for chunk in vector_chunks:
            chunk_id = chunk["id"]
            cosine_distance = chunk["cosine_distance"]
            cosine_similarity = 1.0 - cosine_distance

            if chunk_id in combined_scores:
                combined_scores[chunk_id]["vector_score"] = cosine_similarity
                combined_scores[chunk_id]["similarity"] = cosine_similarity
            else:
                combined_scores[chunk_id] = {
                    "fts_score": 0.0,
                    "vector_score": cosine_similarity,
                    "similarity": cosine_similarity,
                    "chunk_data": chunk,
                }
                id_to_chunk[chunk_id] = chunk

        # Bobot untuk hybrid search
        WEIGHT_FTS = 0.4
        WEIGHT_VECTOR = 0.6

        def calculate_hybrid_score(scores):
            fts_norm = scores["fts_score"]
            vector_norm = scores["vector_score"]
            return (WEIGHT_FTS * fts_norm) + (WEIGHT_VECTOR * vector_norm)

        scored_chunks = [
            (cid, calculate_hybrid_score(scores))
            for cid, scores in combined_scores.items()
        ]
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        sorted_chunk_ids = [cid for cid, score in scored_chunks]
        sorted_chunks = [
            id_to_chunk[cid] for cid in sorted_chunk_ids if cid in id_to_chunk
        ]

        # Filter berdasarkan threshold
        filtered_chunks = []
        for chunk in sorted_chunks:
            vector_similarity = combined_scores[chunk["id"]]["vector_score"]
            if vector_similarity >= SIMILARITY_THRESHOLD:
                chunk["similarity"] = vector_similarity
                filtered_chunks.append(chunk)

        final_chunks = filtered_chunks[:limit]

        # Ambil info dokumen
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
            f"✅ Ditemukan {len(final_chunks)} chunk yang melewati filter Hybrid Search."
        )
        cur.close()
        conn.close()

        for i, chunk in enumerate(final_chunks):
            logging.info(
                f"[Hybrid] Chunk-{i} dokumen_id={chunk['dokumen_id']} judul={chunk['judul']} similarity: {chunk['similarity']:.4f}"
            )

        return {
            "documents": [dict(row) for row in documents],
            "chunks": [dict(row) for row in final_chunks],
        }

    except Exception as e:
        logging.error(f"Error searching documents (Hybrid): {e}")
        # Fallback ke vector search
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

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

            filtered_chunks = []
            for chunk in chunks:
                cosine_similarity = 1.0 - chunk["cosine_distance"]
                if cosine_similarity >= SIMILARITY_THRESHOLD:
                    chunk["similarity"] = cosine_similarity
                    filtered_chunks.append(chunk)
                del chunk["cosine_distance"]

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
                f"✅ Fallback Vector Search menemukan {len(final_chunks)} chunk."
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


async def upsert_ai_memory(mem_key, mem_value, npp, category="public"):
    """Upsert data ke AI memory"""
    print(f"[DEBUG] 🧠 Memproses memori untuk NPP {npp}: {mem_key}")

    content_to_embed = f"Informasi {category} untuk {mem_key}: {mem_value}"
    conn = None

    try:
        embedding = get_embedding(content_to_embed)
        conn = get_db_connection()
        cur = conn.cursor()

        sql = """
            INSERT INTO ai_memory (mem_key, mem_value, npp, category, embedding, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (mem_key, npp) 
            DO UPDATE SET 
                mem_value = EXCLUDED.mem_value,
                embedding = EXCLUDED.embedding,
                category = EXCLUDED.category,
                updated_at = NOW();
        """

        cur.execute(sql, (mem_key, mem_value, npp, category, embedding))
        conn.commit()

        print(f"✅ [MEMORY] Tersimpan di Hard Disk untuk NPP {npp}")
        return True

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ [ERROR] Gagal simpan memori: {str(e)}")
        return False
    finally:
        if conn:
            cur.close()
            conn.close()


async def search_universal_knowledge(query, npp, role, limit=4):
    """Universal search across chat, documents, and memory"""
    logging.info(f"🧠 [Universal Search] NPP: {npp} | Role: {role} | Query: '{query}'")
    try:
        query_embedding = EMBEDDING_MODEL.encode([query], normalize_embeddings=True)[
            0
        ].tolist()
        query_vector_str = embedding_to_pgvector_str(query_embedding)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        is_trainer = (role.upper() == "TRAINER") if role else False

        sql = """
        WITH combined_knowledge AS (
            -- Sumber A: History Chat
            SELECT 
                'CHAT' as source,
                adc.user_text as primary_content,
                adc.assistant_text as secondary_content,
                (adc.embedding_user <=> %s::vector) as distance,
                cs.npp as owner_npp
            FROM ai_dialogue_corpus adc
            JOIN chat_sessions cs ON adc.session_id = cs.id
            LEFT JOIN users u ON cs.npp = u.npp
            WHERE (
                %s = TRUE OR 
                cs.npp = %s OR 
                cs.npp IS NULL OR cs.npp = '' OR 
                u.role = 'TRAINER'
            )

            UNION ALL

            -- Sumber B: Isi Dokumen OCR
            SELECT 
                'DOCUMENT' as source,
                content as primary_content,
                metadata->>'filename' as secondary_content,
                (embedding <=> %s::vector) as distance,
                adc_chunks.npp as owner_npp
            FROM ai_document_chunks adc_chunks
            LEFT JOIN users u ON adc_chunks.npp = u.npp
            WHERE (
                %s = TRUE OR 
                adc_chunks.npp = %s OR 
                adc_chunks.npp IS NULL OR adc_chunks.npp = '' OR 
                u.role = 'TRAINER'
            )

            UNION ALL

            -- Sumber C: MEMORI PERMANEN (AI MEMORY)
            SELECT 
                'PERMANENT' as source,
                mem_key as primary_content,
                mem_value as secondary_content,
                (embedding <=> %s::vector) as distance,
                npp as owner_npp
            FROM ai_memory
            WHERE (
                category = 'public' OR
                npp = %s OR
                %s = TRUE
            )
        )
        SELECT * FROM combined_knowledge
        WHERE (1 - distance) >= 0.55
        ORDER BY 
            (CASE WHEN source = 'PERMANENT' THEN 0 ELSE 1 END), 
            distance ASC
        LIMIT %s;
        """

        cur.execute(
            sql,
            (
                query_vector_str,
                is_trainer,
                npp,
                query_vector_str,
                is_trainer,
                npp,
                query_vector_str,
                npp,
                is_trainer,
                limit,
            ),
        )

        results = cur.fetchall()
        cur.close()
        conn.close()

        return results

    except Exception as e:
        logging.error(f"Error in universal search: {e}")
        return []


async def generate_judul_ai(message):
    """Generate judul untuk chat session"""
    try:
        prompt = (
            f"Buat judul singkat 3-6 kata untuk pesan ini: '{message}'\n"
            "Judul harus mewakili topik utama. Hanya kembalikan judulnya saja."
        )

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


# ========== SMART CHAT FUNCTION ==========
async def smart_chat_with_context(
    user_message, active_file, mode, model, session_uuid, npp, role, attachments
):
    # Load history dari DB
    history_context = ""
    if session_uuid:
        history_messages = get_chat_history_from_db(session_uuid, limit=3)
        if history_messages:
            history_context = "\n".join(
                [f"{m['role'].upper()}: {m['content']}" for m in history_messages]
            )

    # 1. JALUR DOKUMEN AKTIF (BYPASS PDF/OCR) - PRIORITAS UTAMA
    if active_file and active_file.get("text"):
        print(f"[DEBUG] BYPASS: Menggunakan Teks PaddleOCR untuk PDF")
        prompt_ocr = f"""Tugas: {user_message if user_message else "Rangkum dokumen ini"}

Gunakan teks hasil scan OCR di bawah ini untuk menjawab pertanyaan/tugas tersebut.
---
[ISI DOKUMEN]:
{active_file["text"][:15000]} 
---
[HISTORY PERCAKAPAN]:
{history_context[-3000:]}

INSTRUKSI KHUSUS:
- Analisis teks di atas dan jawab pertanyaan user dengan detail.
- Jika user minta rangkuman, buatkan poin-poin pentingnya.
- Jika jawaban tidak ada di dokumen, beri tahu user secara jujur.
"""
        reply = await ask_qwen3_vl(prompt_ocr, stream=True, override_model=model)
        return reply, None, False

    # 2. MULTIMODAL LAYER (Handle Images)
    has_images = attachments and any(
        a and "image" in a.get("type", "").lower() for a in attachments
    )
    if has_images:
        try:
            img_obj = next(
                a for a in attachments if "image" in a.get("type", "").lower()
            )
            img_data = img_obj.get("data", "")
            raw_base64 = img_data.split(",")[1] if "," in img_data else img_data

            vlm_intent_prompt = f"""Tugas: Analisis apakah pertanyaan user tentang gambar ini memerlukan referensi data internal perusahaan atau hanya ekstraksi gambar biasa.
            User Message: {user_message}
            Jawab dengan format JSON: {{"use_rag": true, "focus_instruction": "instruksi"}}"""

            intent_res = await ask_qwen3_vl(
                vlm_intent_prompt, stream=False, override_model="qwen2.5:14b-instruct"
            )

            try:
                clean_json = (
                    intent_res.replace("```json", "").replace("```", "").strip()
                )
                intent_data = json.loads(clean_json)
            except:
                intent_data = {
                    "use_rag": False,
                    "focus_instruction": "Ekstrak data secara objektif.",
                }

            vlm_final_prompt = (
                f"{intent_data.get('focus_instruction')}\n\nUser: {user_message}"
            )
            reply = await ask_qwen3_vl(
                prompt=vlm_final_prompt,
                images=[raw_base64],
                stream=True,
                override_model=VISION_MODEL,
            )
            return reply, None, False
        except Exception as e:
            print(f"[ERROR] Multimodal Layer Error: {e}")

    # MODE SEARCH (Pindad Website Scraper)
    if mode == MODE_SEARCH:
        refine_prompt = f"History:\n{history_context}\n\nUser: {user_message}\nBuat query search singkat untuk website."
        web_query = await ask_qwen3_vl(
            refine_prompt, stream=False, override_model=model
        )
        search_result = await scrape_pindad_website(
            web_query if web_query else user_message
        )

        search_prompt = f"""Kamu adalah asisten AI untuk PT Pindad. Berdasarkan informasi dari www.pindad.com:

{search_result}

KONTEKS PERCAKAPAN SEBELUMNYA:
{history_context}

Tolong jawab pertanyaan pengguna: 
    PERTANYAAN: "{user_message}"

    INSTRUKSI:
    1. Jika jawaban ada, berikan jawaban detail
    2. Jika tidak ada, JAWAB: "Tidak ditemukan informasi spesifik tentang hal ini dalam dokumen perusahaan"
    3. Gunakan Bahasa Indonesia yang baik dan benar dan jawab dengan natural
"""
        reply = await ask_qwen3_vl(search_prompt, stream=True, override_model=model)
        return reply, None, False

    # MODE DOCUMENT (RAG dengan Analisa & Verifikasi)
    elif mode == MODE_DOCUMENT:
        analysis_prompt = f"""Analisis pertanyaan pengguna.
HISTORY PERCAKAPAN:
{history_context}

PERTANYAAN BARU: "{user_message}"

Tugas:
1. Hubungkan dengan history jika masih relevan.
2. Berikan kata kunci pencarian (search query) yang efektif.

Jawaban format: ANALISIS | KATA_KUNCI
"""
        analysis_res = await ask_qwen3_vl(
            analysis_prompt, stream=False, override_model=model
        )
        parts = (
            analysis_res.split("|")
            if "|" in analysis_res
            else ["Tidak ada analisa", user_message]
        )
        reasoning = parts[0].strip()
        search_query = parts[1].strip()

        print("\n🔍 " + "─" * 40)
        print(f"🤖 AI ANALYSIS 1 (With Context)")
        print(f"🧠 Reasoning : {reasoning}")
        print(f"🔑 Query 1   : {search_query}")

        search_result = await search_documents(search_query)
        relevant_chunks = [
            c
            for c in search_result["chunks"]
            if c["similarity"] >= SIMILARITY_THRESHOLD
        ]

        is_truly_relevant = False
        if relevant_chunks:
            eval_prompt = f"""User bertanya tentang: "{user_message}"
Hasil pencarian database: "{relevant_chunks[0]["content"][:500]}..."

Tugas: Apakah hasil pencarian tersebut BENAR-BENAR relevan dan menjawab pertanyaan user?
Contoh: Jika user tanya 'efisiensi' tapi hasilnya 'mesin painting', maka JAWAB: TIDAK.
Jawaban: YA atau TIDAK"""

            eval_res = await ask_qwen3_vl(
                eval_prompt, stream=False, override_model=model
            )
            if "YA" in eval_res.upper():
                is_truly_relevant = True

        if not is_truly_relevant:
            print(
                f"⚠️  [VERIFIKASI 2] Hasil Tahap 1 tidak relevan. Melakukan Re-Analisa..."
            )
            re_analysis_prompt = f"""Pertanyaan user: "{user_message}"
Hasil pencarian sebelumnya tidak relevan karena tercampur konteks lama.
Tugas: Buat kata kunci pencarian baru yang murni hanya fokus pada pertanyaan user tersebut (abaikan topik sebelumnya).

Jawaban format: ANALISIS_ULANG | KATA_KUNCI_MURNI
"""
            re_analysis_res = await ask_qwen3_vl(
                re_analysis_prompt, stream=False, override_model=model
            )
            re_parts = (
                re_analysis_res.split("|")
                if "|" in re_analysis_res
                else ["Cari ulang", user_message]
            )
            search_query = re_parts[1].strip()
            print(f"🧠 Re-Analisa : {re_parts[0].strip()}")
            print(f"🔑 Query Baru : {search_query}")

            search_result = await search_documents(search_query)
            relevant_chunks = [
                c
                for c in search_result["chunks"]
                if c["similarity"] >= SIMILARITY_THRESHOLD
            ]

        if relevant_chunks:
            top_chunk = relevant_chunks[0]
            print(
                f"✅ HIT FINAL: {top_chunk.get('judul')} ({top_chunk.get('similarity'):.4f})"
            )
        else:
            print(f"❌ [LOG] Tetap tidak ada data relevan di database.")
        print("─" * 43 + "\n")

        # Deteksi Greeting
        user_message_lower = user_message.lower()
        greeting_keywords = ["hai", "halo", "selamat pagi", "thanks", "terima kasih"]
        if (
            any(kw in user_message_lower for kw in greeting_keywords)
            and not relevant_chunks
        ):
            reply = await ask_qwen3_vl(
                f"Sapa user dengan ramah: {user_message}", stream=True
            )
            return reply, None, False

        if not relevant_chunks:
            prompt = f"Beritahu user bahwa dokumen terkait '{user_message}' tidak ditemukan di database internal."
            reply = await ask_qwen3_vl(prompt, stream=True, override_model=model)
            return reply, None, False

        document_info = None
        target_doc_id = relevant_chunks[0]["dokumen_id"]
        if search_result.get("documents"):
            for doc in search_result["documents"]:
                if doc["id"] == target_doc_id:
                    document_info = doc
                    break

        referensi_doc = ""
        if document_info:
            jenis_map = {
                1: "SURAT KEPUTUSAN",
                2: "SURAT EDARAN",
                3: "INSTRUKSI KERJA",
                4: "PROSEDUR",
            }
            jenis = jenis_map.get(document_info.get("id_jenis"), "DOKUMEN")
            referensi_doc = f"{jenis} {document_info.get('judul')} Nomor {document_info.get('nomor')}"

        context_text = "\n".join(
            [f"DOKUMEN: {c.get('judul')}\n{c['content']}" for c in relevant_chunks[:3]]
        )
        doc_prompt = f"""Anda adalah AI internal PT Pindad.
DOKUMEN TERBARU:
{context_text}

PERTANYAAN USER: "{user_message}"

INSTRUKSI:
1. Gunakan informasi dari DOKUMEN TERBARU di atas untuk menjawab
2. JANGAN bahas topik lama (seperti mesin painting) jika dokumen ini membahas hal baru (seperti efisiensi).
3. Di akhir sebutkan: "Informasi ini berdasarkan dokumen {referensi_doc}"
4. Jawab dalam Bahasa Indonesia yang natural
"""
        reply = await ask_qwen3_vl(doc_prompt, stream=True, override_model=model)

        reply_lower = reply.lower()
        doc_match = False
        if document_info:
            nomor_doc = str(document_info.get("nomor", "")).lower()
            judul_doc = str(document_info.get("judul", "")).lower()
            if (nomor_doc != "" and nomor_doc in reply_lower) or (
                judul_doc != "" and judul_doc in reply_lower
            ):
                doc_match = True

        final_pdf_info = None
        if doc_match and document_info:
            final_pdf_info = {
                "filename": document_info["filename"],
                "title": document_info.get("judul", document_info["filename"]),
                "nomor": document_info.get("nomor", ""),
                "tanggal": document_info.get("tanggal", ""),
                "tempat": document_info.get("tempat", ""),
                "url": f"/db_doc/{document_info['filename']}",
                "download_url": f"/db_doc/{document_info['filename']}",
            }

        return reply, final_pdf_info, doc_match

    # MODE NORMAL
    elif mode == MODE_NORMAL:
        print(f"\n[DEBUG] === 🚀 MEMULAI ANALISIS PESAN (MODE NORMAL) ===")
        print(f"[DEBUG] User Message: {user_message}")

        analysis_prompt = f"""
                    Tugas: 
                    1. Analisis apakah pesan user memerlukan data perusahaan/history.
                    2. DETEKSI KOREKSI: Jika user mengoreksi data (contoh: "yang bener adalah...", "web pindad itu .com"), set 'is_update_memory': true.
                    3. BUAT NARASI TEGAS: Jika 'is_update_memory' true, buat 'extracted_value' berupa kalimat deklaratif yang sangat jelas untuk menindih info lama.
                    
                    History: {history_context[-3000:]}
                    User Message: "{user_message}"

                    Jawab hanya JSON:
                    {{
                    "perlu_cari": true/false, 
                    "is_update_memory": true/false,
                    "keyword_pencarian": "keyword baku",
                    "extracted_key": "snake_case_label",
                    "extracted_value": "isi_informasi_lengkap_dan_tegas"
                    }}
                """

        print(f"[DEBUG] --- [LOG LAYER 1: ANALISIS NIAT] ---")
        analysis_res = await ask_qwen3_vl(
            analysis_prompt, stream=False, override_model="qwen2.5:14b-instruct"
        )
        print(f"[DEBUG] Raw AI Result: {analysis_res.strip()}")

        try:
            clean_json = analysis_res.replace("```json", "").replace("```", "").strip()
            analysis_data = json.loads(clean_json)
            print(
                f"[DEBUG] Parsing Sukses: Perlu Cari={analysis_data.get('perlu_cari')}, Update Memory={analysis_data.get('is_update_memory')}"
            )
        except Exception as e:
            print(f"[DEBUG] ❌ Parsing Gagal: {str(e)}")
            analysis_data = {
                "perlu_cari": True,
                "keyword_pencarian": user_message,
                "is_update_memory": False,
            }

        if analysis_data.get("is_update_memory"):
            print(
                f"[DEBUG] 💾 KOREKSI TERDETEKSI! Key: {analysis_data.get('extracted_key')} | Val: {analysis_data.get('extracted_value')}"
            )
            success = await upsert_ai_memory(
                analysis_data.get("extracted_key"),
                analysis_data.get("extracted_value"),
                npp,
            )
            if success:
                print(
                    f"[DEBUG] ✅ Berhasil menyimpan ke Permanent Memory (Hard Disk) untuk NPP: {npp}"
                )
            else:
                print(f"[DEBUG] ❌ Gagal menyimpan ke Permanent Memory")

        corpus_context = ""
        if analysis_data.get("perlu_cari"):
            search_query = analysis_data.get("keyword_pencarian", user_message)
            print(f"[DEBUG] --- [LOG LAYER 2: RAG SEARCH] ---")
            print(f"[DEBUG] Searching for: '{search_query}'")

            universal_refs = await search_universal_knowledge(search_query, npp, role)

            if universal_refs:
                print(
                    f"[DEBUG] ✅ Berhasil menarik {len(universal_refs)} data referensi."
                )
                formatted_refs = []
                for ref in universal_refs:
                    source_type = ref.get("source")
                    if source_type == "PERMANENT":
                        print(
                            f"[DEBUG] -> [FOUND IN HARD DISK]: {ref['primary_content']}"
                        )
                        formatted_refs.append(
                            f"[DATA TERVERIFIKASI]: {ref['primary_content']} adalah {ref['secondary_content']}"
                        )
                    elif source_type == "CHAT":
                        print(
                            f"[DEBUG] -> [FOUND IN CHAT HISTORY]: {ref['primary_content'][:50]}..."
                        )
                        formatted_refs.append(
                            f"[MEMORI CHAT]: User tanya '{ref['primary_content']}' -> AI jawab '{ref['secondary_content']}'"
                        )
                    else:
                        print(
                            f"[DEBUG] -> [FOUND IN DOCUMENT]: {ref['secondary_content']}"
                        )
                        formatted_refs.append(
                            f"[DOKUMEN {ref['secondary_content']}]: {ref['primary_content']}"
                        )

                corpus_context = (
                    "REFERENSI DATA INTERNAL PERUSAHAAN (UTAMAKAN DATA TERVERIFIKASI):\n"
                    + "\n---\n".join(formatted_refs)
                    + "\n\n"
                )
            else:
                print(f"[DEBUG] ⚠️ Tidak ada referensi relevan ditemukan.")
                corpus_context = (
                    "INFO: Tidak ada referensi dokumen lama yang relevan.\n"
                )
        else:
            print(f"[DEBUG] ⏭️ Skip RAG Search: AI merasa tidak butuh data eksternal.")

        print(f"[DEBUG] --- [LOG LAYER 3: GENERATING FINAL RESPONSE] ---")

        base_instruction = """
        INSTRUKSI KHUSUS:
        1. Jika ada perbedaan antara 'REFERENSI DATA INTERNAL' dengan pengetahuan umummu, gunakan DATA INTERNAL.
        2. Jangan memberikan informasi domain atau data yang sudah dinyatakan TIDAK BERLAKU dalam referensi.
        """

        if active_file:
            print(f"[DEBUG] Priority: Active File ({active_file.get('name')})")
            context_text = active_file.get("text", "")[:7000]
            file_name = active_file.get("name", "Dokumen Terlampir")

            prompt = f"""Kamu adalah CAKRA (Cerdas Terpercaya), AI PT Pindad.
{base_instruction}
DOKUMEN YANG SEDANG DIBUKA (PRIORITAS UTAMA):
Nama File: {file_name}
Konten: {context_text}

{corpus_context}

HISTORY CHAT TERAKHIR:
{history_context}

User Message: "{user_message}"
"""
        else:
            print(f"[DEBUG] Priority: Universal RAG")
            prompt = f"""Kamu adalah CAKRA, AI PT Pindad.
{base_instruction}
{corpus_context}

HISTORY CHAT TERAKHIR:
{history_context}

User: {user_message}

Tugas: Jawab dengan jujur berdasarkan referensi data internal yang tersedia.
"""

        reply = await ask_qwen3_vl(prompt, stream=True, override_model=model)

        if reply is None:
            print(f"[DEBUG] ❌ Final Response is None")
            reply = "Maaf bro, sistem sedang sibuk. Coba ulangi lagi ya."

        print(f"[DEBUG] === ✅ ANALISIS SELESAI ===\n")
        return reply, None, False


# ========== ROUTES ==========
@app.route("/api/login", methods=["POST"])
async def login():
    data = await request.get_json()
    npp = data.get("username")
    password_input = data.get("password")

    if not npp or not password_input:
        return jsonify(
            {"status": "error", "message": "NPP dan Password wajib diisi"}
        ), 400

    password_md5 = hashlib.md5(password_input.encode()).hexdigest()
    conn_hris = None
    conn_local = None

    try:
        user_hris = None
        current_role = "USER"

        if str(npp) == "99999" and str(password_input) == "123456":
            user_hris = {
                "npp": "99999",
                "nama": "Learn Data AI",
                "username_alias": "LearnDataAI",
                "divisi": "PINDAD",
                "password": password_input,
            }
            current_role = "TRAINER"
            logging.info("Login via Special Account: Learn Data AI")
        else:
            conn_hris = psycopg2.connect(**DB_LOGIN_CONFIG)
            with conn_hris.cursor(cursor_factory=RealDictCursor) as cur:
                query_hris = """
                    SELECT 
                        mp.nama_lengkap as nama, tu.npp, tu.password, 
                        split_part(ref_unit.unit_path::text, '->'::text, 2) AS divisi
                    FROM master_unit unit
                    JOIN temp_ref_unit ref_unit ON ref_unit.kode_unit = unit.kode_unit
                    LEFT JOIN master_personil mp ON mp.kode_unit = unit.kode_unit
                    LEFT JOIN tabel_user tu ON tu.npp = mp.npp
                    WHERE tu.npp = %s
                """
                cur.execute(query_hris, (npp,))
                user_hris = cur.fetchone()

            if not user_hris:
                return jsonify(
                    {"status": "error", "message": "NPP tidak terdaftar"}
                ), 404

            if user_hris["password"] != password_md5:
                return jsonify({"status": "error", "message": "Password salah"}), 401

        conn_local = get_db_connection()
        session_token = str(uuid.uuid4())
        user_ip = request.remote_addr
        u_agent = request.headers.get("User-Agent")

        with conn_local.cursor(cursor_factory=RealDictCursor) as cur_local:
            if npp != "99999":
                cur_local.execute(
                    "SELECT role FROM users WHERE npp = %s", (user_hris["npp"],)
                )
                existing = cur_local.fetchone()
                current_role = existing["role"] if existing else "USER"

            cur_local.execute(
                """
                INSERT INTO users (npp, fullname, divisi, role) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (npp) DO UPDATE SET 
                    fullname = EXCLUDED.fullname, 
                    divisi = EXCLUDED.divisi,
                    role = EXCLUDED.role; 
                """,
                (
                    user_hris["npp"],
                    user_hris["nama"],
                    user_hris["divisi"],
                    current_role,
                ),
            )

            cur_local.execute(
                """
                INSERT INTO session_login (npp, session_token, ip_address, is_login, last_activity)
                VALUES (%s, %s, %s, TRUE, CURRENT_TIMESTAMP)
                ON CONFLICT (npp) DO UPDATE SET 
                    session_token = EXCLUDED.session_token, 
                    is_login = TRUE, 
                    last_activity = CURRENT_TIMESTAMP;
                """,
                (user_hris["npp"], session_token, user_ip),
            )

            cur_local.execute(
                "INSERT INTO history_login (npp, action, ip_address, user_agent) VALUES (%s, 'LOGIN', %s, %s)",
                (user_hris["npp"], user_ip, u_agent),
            )
            conn_local.commit()

        return jsonify(
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
        ), 200

    except Exception as e:
        if conn_local:
            conn_local.rollback()
        logging.error(f"Login Error: {e}")
        return jsonify({"status": "error", "message": f"System Error: {str(e)}"}), 500
    finally:
        if conn_hris:
            conn_hris.close()
        if conn_local:
            conn_local.close()


@app.route("/api/logout", methods=["POST"])
async def logout():
    conn_local = None
    try:
        data = await request.get_json()
        token = data.get("token")

        conn_local = get_db_connection()
        with conn_local.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT npp FROM session_login WHERE session_token = %s", (token,)
            )
            row = cur.fetchone()

            if row:
                npp = row["npp"]
                cur.execute(
                    "UPDATE session_login SET is_login = FALSE, session_token = '' WHERE npp = %s",
                    (npp,),
                )

                cur.execute(
                    "INSERT INTO history_login (npp, action, ip_address) VALUES (%s, 'LOGOUT', %s);",
                    (npp, request.remote_addr),
                )

                conn_local.commit()
                return jsonify({"status": "success", "message": "Logged out"}), 200

            return jsonify({"status": "success", "message": "Token already gone"}), 200

    except Exception as e:
        if conn_local:
            conn_local.rollback()
        print(f"❌ LOGOUT ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn_local:
            conn_local.close()


@app.route("/api/verify-session", methods=["GET"])
async def verify_session():
    token = request.args.get("token")
    if not token:
        return jsonify({"status": "error", "message": "Token missing"}), 401

    conn_local = None
    try:
        conn_local = get_db_connection()
        with conn_local.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT u.npp, u.fullname, u.divisi 
                FROM session_login s
                JOIN users u ON s.npp = u.npp
                WHERE s.session_token = %s AND s.is_login = TRUE
            """
            cur.execute(query, (token,))
            user = cur.fetchone()

            if user:
                cur.execute(
                    "UPDATE session_login SET last_activity = CURRENT_TIMESTAMP WHERE session_token = %s",
                    (token,),
                )
                conn_local.commit()

                return jsonify(
                    {
                        "status": "success",
                        "data": {
                            "username": user["npp"],
                            "fullname": user["fullname"],
                            "divisi": user["divisi"],
                        },
                    }
                ), 200
            else:
                return jsonify(
                    {"status": "error", "message": "Session expired or invalid"}
                ), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn_local:
            conn_local.close()


@app.route("/api/available-models", methods=["GET"])
def get_available_models():
    models = [
        {"id": "qwen3:8b", "name": "Qwen 3 (8B)"},
        {"id": "qwen2.5:14b-instruct", "name": "Qwen 2.5-Instruct (14b)"},
        {"id": "qwen3-vl:8b", "name": "qwen 3 vl (8b)"},
        {"id": "llama3.1:8b", "name": "Llama 3.1 (8b)"},
    ]
    return jsonify({"status": "success", "data": models})


@app.route("/api/chat", methods=["POST"])
async def chat():
    global PRIMARY_MODEL
    conn_local = None
    role = "GUEST"
    npp = None
    username = "Guest"
    try:
        data = await request.get_json()
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

        conn_local = get_db_connection()
        cur = conn_local.cursor(cursor_factory=RealDictCursor)

        current_session_id = None
        judul_baru = None

        if session_uuid:
            cur.execute(
                "SELECT id FROM chat_sessions WHERE session_uuid = %s", (session_uuid,)
            )
            sess = cur.fetchone()
            if sess:
                current_session_id = sess["id"]

        if not current_session_id:
            if not session_uuid:
                session_uuid = str(uuid.uuid4())
            judul_baru = await generate_judul_ai(user_message)
            cur.execute(
                """
                INSERT INTO chat_sessions (session_uuid, user_name, npp, judul, model_name, is_active)
                VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING id
            """,
                (session_uuid, username, npp, judul_baru, selected_model),
            )
            current_session_id = cur.fetchone()["id"]

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

        active_file = None
        final_message_to_ai = user_message

        if ocr_context and len(ocr_context.strip()) > 10:
            print(f"[*] OCR SUKSES: {len(ocr_context)} karakter ditemukan.")
            active_file = {"text": ocr_context, "name": "Dokumen Terlampir"}

            final_message_to_ai = f"""
INSTRUKSI USER: {user_message if user_message else "Rangkum dokumen ini"}

DATA DOKUMEN HASIL SCAN:
{ocr_context}

Tolong jawab instruksi di atas berdasarkan data dokumen tersebut secara detail.
"""

        reply, pdf_info, should_include_pdf = await smart_chat_with_context(
            user_message=final_message_to_ai,
            active_file=active_file,
            mode=mode,
            model=selected_model,
            session_uuid=session_uuid,
            npp=npp,
            role=role,
            attachments=attachments,
        )

        try:
            vector_user = get_embedding(user_message)
            vector_assistant = get_embedding(reply)

            if vector_user is None:
                vector_user = [0.0] * 768
            if vector_assistant is None:
                vector_assistant = [0.0] * 768

        except Exception as emb_e:
            print(f"[WARNING] Gagal generate embedding: {emb_e}")
            vector_user = [0.0] * 768
            vector_assistant = [0.0] * 768

        cur.execute(
            """
            INSERT INTO ai_dialogue_corpus (
                session_id, user_text, assistant_text, 
                embedding_user, embedding_assistant, metadata, files
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
            (
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
            ),
        )

        conn_local.commit()

        return jsonify(
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
        if conn_local:
            conn_local.rollback()
        logging.error(f"Chat Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn_local:
            conn_local.close()


@app.route("/api/chat-history/<npp>", methods=["GET"])
async def get_chat_history(npp):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT session_uuid, judul, started_at, is_pinned  
                FROM chat_sessions 
                WHERE npp = %s AND is_active = TRUE
                AND is_deleted = false  
                ORDER BY is_pinned DESC, started_at DESC 
            """,
                (npp,),
            )
            sessions = cur.fetchall()
            return jsonify({"status": "success", "data": sessions})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/chat-messages/<session_uuid>", methods=["GET"])
async def get_session_messages(session_uuid):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id FROM chat_sessions WHERE session_uuid = %s", (session_uuid,)
            )
            sess = cur.fetchone()
            if not sess:
                return jsonify(
                    {"status": "error", "message": "Sesi tidak ditemukan"}
                ), 404

            cur.execute(
                """
                SELECT user_text, assistant_text, created_at, files
                FROM ai_dialogue_corpus 
                WHERE session_id = %s 
                ORDER BY created_at ASC
            """,
                (sess["id"],),
            )

            rows = cur.fetchall()
            formatted_messages = []

            for row in rows:
                attachments = row.get("files") if row.get("files") else []

                formatted_messages.append(
                    {
                        "id": f"u-{row['created_at'].timestamp()}",
                        "sender": "user",
                        "text": row["user_text"],
                        "attachments": attachments,
                        "timestamp": row["created_at"].strftime("%H:%M"),
                    }
                )

                formatted_messages.append(
                    {
                        "id": f"a-{row['created_at'].timestamp()}",
                        "sender": "ai",
                        "text": row["assistant_text"],
                        "timestamp": row["created_at"].strftime("%H:%M"),
                    }
                )

            return jsonify({"status": "success", "data": formatted_messages})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/db_doc/<filename>", methods=["GET"])
async def serve_db_doc(filename):
    """Serve files from db_doc folder for preview or download"""
    try:
        db_doc_folder = app.config.get("DB_DOC_FOLDER", "./db_doc")
        filepath = os.path.join(db_doc_folder, filename)

        if not os.path.exists(filepath):
            upload_folder = app.config.get("UPLOAD_FOLDER", "./uploads")
            filepath = os.path.join(upload_folder, filename)

        if not os.path.exists(filepath):
            return jsonify({"error": f"File {filename} not found"}), 404

        download = request.args.get("download", "false").lower() == "true"

        if filename.lower().endswith(".pdf") and not download:
            response = await send_file(
                filepath,
                mimetype="application/pdf",
                as_attachment=False,
            )
            response.headers["Content-Type"] = "application/pdf"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        else:
            response = await send_file(filepath, as_attachment=True)
            response.headers["Content-Disposition"] = (
                f'attachment; filename="{filename}"'
            )
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

    except Exception as e:
        logging.error(f"Error serving db_doc file: {e}")
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
                "ollama_connected": ollama_status,
            }
        )
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route("/api/documents", methods=["GET"])
async def list_documents():
    """Get list of documents from database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

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


@app.route("/api/chat/pin/<uuid:session_uuid>", methods=["POST"])
def toggle_pin_chat(session_uuid):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        sql = """
            UPDATE chat_sessions 
            SET is_pinned = NOT is_pinned 
            WHERE session_uuid = %s 
            RETURNING is_pinned
        """
        cur.execute(sql, (str(session_uuid),))
        result = cur.fetchone()

        if result:
            conn.commit()
            new_status = result[0]
            cur.close()
            conn.close()
            return jsonify(
                {
                    "status": "success",
                    "message": f"Chat {'disematkan' if new_status else 'dilepas'}",
                    "is_pinned": new_status,
                }
            )
        else:
            return jsonify(
                {"status": "error", "message": "Session tidak ditemukan"}
            ), 404

    except Exception as e:
        print(f"Error toggle pin: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/chat/rename/<session_uuid>", methods=["POST"])
async def rename_chat(session_uuid):
    try:
        data = await request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Data tidak ditemukan"}), 400

        new_judul = data.get("judul")
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "UPDATE chat_sessions SET judul = %s WHERE session_uuid = %s",
            (new_judul, str(session_uuid)),
        )
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"status": "success", "message": "Judul berhasil diubah"})
    except Exception as e:
        print(f"Error Rename: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/chat/delete/<session_uuid>", methods=["POST"])
async def delete_chat(session_uuid):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        sql = "UPDATE chat_sessions SET is_deleted = true WHERE session_uuid = %s"
        cur.execute(sql, (str(session_uuid),))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {"status": "success", "message": "Chat berhasil dihapus (soft delete)"}
        )
    except Exception as e:
        print(f"Error Delete: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print(f"🚀 CAKRA AI starting...")
    print(f"🤖 Primary Model: {PRIMARY_MODEL}")
    print(f"📁 Upload folder: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"🌐 API running on http://0.0.0.0:5000")

    app.run(host="0.0.0.0", port=5000, debug=True)
