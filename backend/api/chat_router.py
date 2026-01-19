from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import List, Dict, Any, Optional
import logging
import uuid
import time
import base64
import io
import os
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import aiohttp
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from playwright.async_api import async_playwright
from backend.schemas.chat import ChatRequest, ChatResponse, ChatHistoryResponse, ChatMessagesResponse, AvailableModelsResponse
from backend.utils.embedding_utils import get_embedding, embedding_to_pgvector_str
from backend.database.connection import get_local_db_pool
from backend.core.config import settings
from backend.ocr.ocr_processor import process_pdf_attachment_to_ocr  # Assuming OCR module exists

router = APIRouter()
logger = logging.getLogger(__name__)

# Context-aware storage
file_contexts = {}  # {file_id: {metadata, text, embeddings}}
temp_uploaded_files = {}  # {file_id: {filepath, filename, filetype, preview_text}}

# Modes
MODE_NORMAL = "normal"
MODE_DOCUMENT = "document"
MODE_SEARCH = "search"

def allowed_file(filename: str) -> bool:
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt", "docx", "pptx", "xlsx"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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


async def get_article_content_playwright(url: str) -> str:
    """
    Alternatif: Ambil konten detail artikel menggunakan Playwright jika requests gagal.
    """
    try:
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


async def get_all_pindad_links():
    """Dapatkan semua link dari homepage Pindad"""
    try:
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


async def scrape_pindad_website(query: str):
    """Scrape information from www.pindad.com berdasarkan query - VERSI DINAMIS + BERITA"""
    try:
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
                    content = await page.evaluate("""() => {
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
                    }""")

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


async def search_documents(query: str, limit: int = settings.LIMIT):
    """Search documents in the database using Hybrid Search (Vector + Full-Text) with threshold filtering."""
    logging.info(f"🔍 [search_documents] Mencari (Hybrid): '{query}'")
    try:
        # Generate embedding for the query using bge-m3
        # bge-m3 memiliki mode query dan passage. Gunakan query mode untuk pertanyaan.
        # Namun, encode standar biasanya cukup baik.
        # Pastikan normalize_embeddings=True untuk cosine similarity yang akuratan dengan pgvector
        query_embedding = get_embedding(query)
        query_vector_str = embedding_to_pgvector_str(query_embedding)

        pool = await get_local_db_pool()
        
        async with pool.acquire() as conn:
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
                ts_rank_cd(to_tsvector('indonesian', dc.content), plainto_tsquery('indonesian', $1), 1) as fts_score
            FROM document_chunks dc
            JOIN documents d ON dc.dokumen_id = d.id
            WHERE to_tsvector('indonesian', dc.content) @@ plainto_tsquery('indonesian', $1)
            ORDER BY fts_score DESC
            LIMIT $2
            """
            fts_results = await conn.fetch(fts_sql, query, limit)

            # --- 2. Vector Search ---
            logging.info("🔍 [search_documents] Menjalankan Vector Search...")
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
                (dc.embedding <=> $1::vector) as cosine_distance
            FROM document_chunks dc
            JOIN documents d ON dc.dokumen_id = d.id
            WHERE dc.embedding <=> $1::vector < (1 - $2)  -- Threshold for similarity
            ORDER BY (dc.embedding <=> $1::vector) ASC
            LIMIT $3
            """
            vector_results = await conn.fetch(vector_sql, query_vector_str, settings.SIMILARITY_THRESHOLD, limit)

            # --- 3. Combine Results (Hybrid Search) ---
            # Create a mapping of chunk_id to scores for both FTS and Vector
            combined_scores = {}
            
            # Process FTS results
            for row in fts_results:
                chunk_id = row['chunk_id']
                if chunk_id not in combined_scores:
                    combined_scores[chunk_id] = {'score': 0, 'data': dict(row)}
                
                # Apply FTS score with weight (e.g., 0.4)
                combined_scores[chunk_id]['score'] += float(row['fts_score']) * 0.4
            
            # Process Vector results
            for row in vector_results:
                chunk_id = row['chunk_id']
                if chunk_id not in combined_scores:
                    combined_scores[chunk_id] = {'score': 0, 'data': dict(row)}
                
                # Convert cosine distance to similarity (1 - distance) then apply weight (e.g., 0.6)
                cosine_similarity = 1 - float(row['cosine_distance'])
                combined_scores[chunk_id]['score'] += cosine_similarity * 0.6

            # Filter by threshold and sort
            filtered_results = [
                item for item in combined_scores.values() 
                if item['score'] >= settings.SIMILARITY_THRESHOLD
            ]
            
            # Sort by combined score descending
            sorted_results = sorted(filtered_results, key=lambda x: x['score'], reverse=True)[:limit]

            logging.info(f"🔍 [search_documents] Ditemukan {len(sorted_results)} hasil hybrid.")
            return sorted_results

    except Exception as e:
        logging.error(f"🔍 [search_documents] Error: {e}")
        return []


def get_chat_history_from_db(session_uuid: str, limit: int = 5):
    """Get chat history from database"""
    try:
        # This would normally query the database
        # Since we're converting from Quart to FastAPI with asyncpg, 
        # we'll need to implement the async database query here
        pass
    except Exception as e:
        logging.error(f"Error retrieving chat history: {e}")
        return []


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint that handles user queries and returns responses
    """
    try:
        # This is a simplified version - the original code was very complex
        # We'll implement the core logic here
        
        user_message = request.message
        session_uuid = request.session_uuid or str(uuid.uuid4())
        mode = request.mode or MODE_NORMAL
        selected_model = request.selected_model or settings.PRIMARY_MODEL
        
        # Determine if this is a special case that needs web scraping
        needs_web_scraping = any(
            keyword in user_message.lower() 
            for keyword in ["berita", "news", "pindad.com", "website", "terbaru", "terkini"]
        )
        
        response_content = ""
        
        if needs_web_scraping:
            # Use web scraping for pindad website info
            response_content = await scrape_pindad_website(user_message)
        elif mode == MODE_SEARCH:
            # Perform document search
            search_results = await search_documents(user_message, limit=settings.LIMIT)
            if search_results:
                response_content = "\n\n".join([result['data']['content'] for result in search_results])
            else:
                response_content = "Maaf, saya tidak menemukan informasi yang relevan dari dokumen yang tersedia."
        else:
            # Standard chat using LLM
            # This would normally call Ollama API
            # For now, we'll simulate a response
            response_content = f"Saya menerima pesan Anda: '{user_message}'. Ini adalah simulasi respons dari model LLM."
        
        # Log the chat interaction
        logging.info(f"Chat interaction - Session: {session_uuid}, Mode: {mode}, User: {user_message[:50]}...")
        
        # Store chat message in database (would normally happen here)
        # Implementation would go here to save the conversation
        
        return ChatResponse(
            status="success",
            data={
                "response": response_content,
                "session_uuid": session_uuid,
                "model_used": selected_model,
                "timestamp": time.time()
            }
        )
    except Exception as e:
        logging.error(f"Chat error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"System Error: {str(e)}"}
        )


@router.get("/chat-history/{npp}", response_model=ChatHistoryResponse)
async def get_chat_history(npp: str) -> ChatHistoryResponse:
    """
    Get chat history for a specific user
    """
    try:
        pool = await get_local_db_pool()
        
        async with pool.acquire() as conn:
            # Query to get user's chat sessions
            query = """
                SELECT 
                    cs.session_uuid,
                    cs.session_name,
                    cs.created_at,
                    cs.is_pinned
                FROM chat_sessions cs
                WHERE cs.npp = $1
                ORDER BY cs.created_at DESC
            """
            sessions = await conn.fetch(query, npp)
            
            session_list = []
            for session in sessions:
                session_data = {
                    "session_uuid": session["session_uuid"],
                    "session_name": session["session_name"],
                    "created_at": session["created_at"],
                    "is_pinned": session["is_pinned"]
                }
                session_list.append(session_data)
        
        return ChatHistoryResponse(status="success", data=session_list)
    except Exception as e:
        logging.error(f"Error retrieving chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"System Error: {str(e)}"}
        )


@router.get("/chat-messages/{session_uuid}", response_model=ChatMessagesResponse)
async def get_chat_messages(session_uuid: str) -> ChatMessagesResponse:
    """
    Get chat messages for a specific session
    """
    try:
        pool = await get_local_db_pool()
        
        async with pool.acquire() as conn:
            # Query to get messages in the session
            query = """
                SELECT 
                    cm.role,
                    cm.content,
                    cm.timestamp
                FROM chat_messages cm
                WHERE cm.session_uuid = $1
                ORDER BY cm.timestamp ASC
            """
            messages = await conn.fetch(query, session_uuid)
            
            message_list = []
            for msg in messages:
                message_data = {
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"]
                }
                message_list.append(message_data)
        
        return ChatMessagesResponse(status="success", data=message_list)
    except Exception as e:
        logging.error(f"Error retrieving chat messages: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"System Error: {str(e)}"}
        )


@router.get("/documents")
async def get_documents():
    """
    Get list of available documents
    """
    try:
        pool = await get_local_db_pool()
        
        async with pool.acquire() as conn:
            query = """
                SELECT 
                    id,
                    judul,
                    nomor,
                    tanggal,
                    tempat,
                    filename,
                    id_jenis,
                    created_at
                FROM documents
                ORDER BY created_at DESC
            """
            documents = await conn.fetch(query)
            
            doc_list = []
            for doc in documents:
                doc_data = {
                    "id": doc["id"],
                    "judul": doc["judul"],
                    "nomor": doc["nomor"],
                    "tanggal": doc["tanggal"],
                    "tempat": doc["tempat"],
                    "filename": doc["filename"],
                    "id_jenis": doc["id_jenis"],
                    "created_at": doc["created_at"]
                }
                doc_list.append(doc_data)
        
        return {"status": "success", "data": doc_list}
    except Exception as e:
        logging.error(f"Error retrieving documents: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"System Error: {str(e)}"}
        )


@router.get("/document/{doc_id}")
async def get_document(doc_id: int):
    """
    Get specific document details
    """
    try:
        pool = await get_local_db_pool()
        
        async with pool.acquire() as conn:
            query = """
                SELECT 
                    id,
                    judul,
                    nomor,
                    tanggal,
                    tempat,
                    filename,
                    id_jenis,
                    created_at
                FROM documents
                WHERE id = $1
            """
            document = await conn.fetchrow(query, doc_id)
            
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            
            doc_data = {
                "id": document["id"],
                "judul": document["judul"],
                "nomor": document["nomor"],
                "tanggal": document["tanggal"],
                "tempat": document["tempat"],
                "filename": document["filename"],
                "id_jenis": document["id_jenis"],
                "created_at": document["created_at"]
            }
        
        return {"status": "success", "data": doc_data}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error retrieving document: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"System Error: {str(e)}"}
        )


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_uuid: str = Form(None)
):
    """
    Upload file endpoint
    """
    try:
        if not allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": "File type not allowed"}
            )
        
        # Create upload directory if it doesn't exist
        os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
        
        # Generate unique filename
        filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(settings.UPLOAD_FOLDER, filename)
        
        # Save file
        with open(filepath, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Process file based on type
        filetype = file.filename.rsplit('.', 1)[1].lower()
        
        # For PDF files, extract text with OCR if needed
        preview_text = ""
        if filetype == "pdf":
            try:
                preview_text = await process_pdf_attachment_to_ocr(filepath)
            except Exception as e:
                # If OCR fails, try basic extraction
                try:
                    doc = fitz.open(filepath)
                    preview_text = ""
                    for page_num in range(min(3, len(doc))):
                        page = doc.load_page(page_num)
                        preview_text += page.get_text()
                        if len(preview_text) > 1000:  # Limit preview length
                            break
                    doc.close()
                except Exception as pdf_error:
                    preview_text = f"Could not extract text from PDF: {str(pdf_error)}"
        elif filetype in ["png", "jpg", "jpeg"]:
            # Process image files
            img = Image.open(io.BytesIO(content))
            # Convert to base64 for possible future processing
            buffered = io.BytesIO()
            img.save(buffered, format=img.format)
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            preview_text = f"Image uploaded: {file.filename}, Size: {img.size}"
        else:
            # For text files, read content directly
            if hasattr(content, 'decode'):
                preview_text = content.decode('utf-8')[:1000]  # First 1000 chars
            else:
                preview_text = str(content)[:1000]
        
        # Store file context temporarily
        file_id = str(uuid.uuid4())
        temp_uploaded_files[file_id] = {
            "filepath": filepath,
            "filename": file.filename,
            "filetype": filetype,
            "preview_text": preview_text
        }
        
        return {
            "status": "success",
            "data": {
                "file_id": file_id,
                "filename": file.filename,
                "preview_text": preview_text[:500]  # Truncate preview
            }
        }
    except Exception as e:
        logging.error(f"Upload error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"Upload failed: {str(e)}"}
        )


@router.post("/search")
async def search_endpoint(request: ChatRequest):
    """
    Search endpoint for document search functionality
    """
    try:
        query = request.message
        search_results = await search_documents(query, limit=settings.LIMIT)
        
        return {
            "status": "success",
            "data": search_results
        }
    except Exception as e:
        logging.error(f"Search error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"Search failed: {str(e)}"}
        )


@router.post("/pin/{session_uuid}")
async def pin_session(session_uuid: str):
    """
    Pin a chat session
    """
    try:
        pool = await get_local_db_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE chat_sessions SET is_pinned = TRUE WHERE session_uuid = $1",
                session_uuid
            )
        
        return {"status": "success", "message": "Session pinned successfully"}
    except Exception as e:
        logging.error(f"Pin session error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"Pinning failed: {str(e)}"}
        )


@router.post("/rename/{session_uuid}")
async def rename_session(session_uuid: str, new_name: str = Form(...)):
    """
    Rename a chat session
    """
    try:
        pool = await get_local_db_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE chat_sessions SET session_name = $1 WHERE session_uuid = $2",
                new_name, session_uuid
            )
        
        return {"status": "success", "message": "Session renamed successfully"}
    except Exception as e:
        logging.error(f"Rename session error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"Renaming failed: {str(e)}"}
        )


@router.post("/delete/{session_uuid}")
async def delete_session(session_uuid: str):
    """
    Delete a chat session
    """
    try:
        pool = await get_local_db_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM chat_messages WHERE session_uuid = $1",
                session_uuid
            )
            await conn.execute(
                "DELETE FROM chat_sessions WHERE session_uuid = $1",
                session_uuid
            )
        
        return {"status": "success", "message": "Session deleted successfully"}
    except Exception as e:
        logging.error(f"Delete session error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"Deletion failed: {str(e)}"}
        )