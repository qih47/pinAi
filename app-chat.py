from quart import Quart, request, jsonify
from quart_cors import cors
import aiohttp
import json
import os
import fitz  # PyMuPDF
from PIL import Image
from werkzeug.utils import secure_filename
import logging
import base64
import io
import asyncio
import uuid
import time
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import requests
from bs4 import BeautifulSoup

app = Quart(__name__)

# ========== KONFIGURASI ==========
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'txt', 'docx', 'pptx', 'xlsx'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# CORS
app = cors(app, allow_origin=["http://192.168.11.80:5173", "http://localhost:5173"])

# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "ragdb",
    "user": "pindadai",
    "password": "Pindad123!"
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
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    return psycopg2.connect(
        host="localhost", database="ragdb", user="pindadai", password="Pindad123!"
    )

async def scrape_pindad_website(query):
    """Scrape information from www.pindad.com based on the query"""
    try:
        # First, we'll try to search for relevant URLs based on the query
        search_url = f"https://www.pindad.com/?s={query.replace(' ', '+')}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Get search results page
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find relevant links from search results
        links = []
        for link in soup.find_all('a', href=True)[:5]:  # Limit to top 5 results
            href = link['href']
            if 'pindad.com' in href and not href.endswith(('.pdf', '.jpg', '.png', '.zip')):
                links.append(href)
        
        # Scrape content from found pages
        scraped_content = ""
        for url in links[:3]:  # Process top 3 links
            try:
                page_response = requests.get(url, headers=headers, timeout=10)
                page_soup = BeautifulSoup(page_response.content, 'html.parser')
                
                # Remove script and style elements
                for script in page_soup(["script", "style"]):
                    script.decompose()
                
                # Extract main content
                main_content = page_soup.find('main') or page_soup.find('article') or page_soup.find('div', class_='content') or page_soup.body
                if main_content:
                    text = main_content.get_text()
                    # Clean up text
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = ' '.join(chunk for chunk in chunks if chunk)
                    
                    scraped_content += f"\n\nFrom {url}:\n{text[:1000]}"  # Limit content per page
                
                if len(scraped_content) > 2000:  # Don't exceed 2000 chars total
                    break
            except Exception as e:
                logging.error(f"Error scraping {url}: {e}")
                continue
        
        return scraped_content if scraped_content else f"No specific information found about '{query}' on www.pindad.com"
        
    except Exception as e:
        logging.error(f"Error during web scraping: {e}")
        return f"Unable to retrieve information from www.pindad.com: {str(e)}"

async def search_documents(query, limit=5):
    """Search documents in the database based on the query"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Search in dokumen table
        sql = """
        SELECT d.id, d.judul, d.nomor, d.tanggal, d.filename, d.status,
               ts_rank(to_tsvector('indonesian', coalesce(d.judul, '') || ' ' || coalesce(d.nomor, '')), plainto_tsquery(%s)) as rank
        FROM dokumen d
        WHERE to_tsvector('indonesian', coalesce(d.judul, '') || ' ' || coalesce(d.nomor, '')) @@ plainto_tsquery(%s)
        ORDER BY rank DESC
        LIMIT %s;
        """
        
        cur.execute(sql, (query, query, limit))
        documents = cur.fetchall()
        
        # Also search in dokumen_chunk table
        chunk_sql = """
        SELECT dc.dokumen_id, d.judul, d.filename, dc.content,
               ts_rank(dc.embedding <=> (SELECT array_agg(s) FROM unnest(string_to_array(%s, ' ')) s)) as similarity
        FROM dokumen_chunk dc
        JOIN dokumen d ON dc.dokumen_id = d.id
        WHERE d.status = 'draft' OR d.status = 'published'
        ORDER BY similarity ASC
        LIMIT %s;
        """
        
        # For now, use a simpler search since vector search might need proper setup
        simple_chunk_sql = """
        SELECT dc.dokumen_id, d.judul, d.filename, dc.content,
               ts_rank(to_tsvector('indonesian', dc.content), plainto_tsquery(%s)) as rank
        FROM dokumen_chunk dc
        JOIN dokumen d ON dc.dokumen_id = d.id
        WHERE to_tsvector('indonesian', dc.content) @@ plainto_tsquery(%s)
          AND (d.status = 'draft' OR d.status = 'published')
        ORDER BY rank DESC
        LIMIT %s;
        """
        
        cur.execute(simple_chunk_sql, (query, query, limit))
        chunks = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "documents": [dict(row) for row in documents],
            "chunks": [dict(row) for row in chunks]
        }
        
    except Exception as e:
        logging.error(f"Error searching documents: {e}")
        return {"documents": [], "chunks": []}

async def extract_with_qwen3_vl(filepath, filetype):
    """Ekstrak teks menggunakan qwen3-vl:8b"""
    try:
        if filetype == 'pdf':
            doc = fitz.open(filepath)
            images = []
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                images.append(base64.b64encode(img_bytes).decode('utf-8'))
            doc.close()
            
            all_text = []
            for i, img_b64 in enumerate(images):
                text = await ask_qwen3_vl(
                    f"Ekstrak semua teks dari halaman {i+1} dokumen ini:",
                    images=[img_b64],
                    file_type=filetype
                )
                all_text.append(text)
            
            return "\n\n".join(all_text)
            
        elif filetype in ['png', 'jpg', 'jpeg']:
            with open(filepath, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode('utf-8')
            
            return await ask_qwen3_vl(
                "Ekstrak semua teks dari gambar ini:",
                images=[img_b64],
                file_type=filetype
            )
            
        elif filetype == 'txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
                
        else:
            return await extract_fallback(filepath, filetype)
            
    except Exception as e:
        logging.error(f"Qwen3-VL extraction error: {e}")
        return await extract_fallback(filepath, filetype)

async def ask_qwen3_vl(prompt, images=None, stream=False, file_type=None):
    """Helper untuk bertanya ke model yang sesuai berdasarkan konten"""
    # Pilih model berdasarkan apakah ada gambar atau file PDF
    selected_model = VISION_MODEL if images or (file_type and file_type in ['pdf', 'png', 'jpg', 'jpeg']) else PRIMARY_MODEL
    
    messages = [{"role": "user", "content": prompt}]
    if images:
        messages[0]["images"] = images
    
    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json={
            "model": selected_model,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": 0.1}
        }) as resp:
            
            if stream:
                reply = ""
                async for line in resp.content:
                    if line:
                        try:
                            obj = json.loads(line.decode('utf-8'))
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
        if filetype == 'pdf':
            doc = fitz.open(filepath)
            text = "\n".join([page.get_text() for page in doc])
            doc.close()
            return text.strip() if text.strip() else "[PDF tidak mengandung teks]"
            
        elif filetype in ['png', 'jpg', 'jpeg']:
            try:
                import pytesseract
                image = Image.open(filepath)
                text = pytesseract.image_to_string(image, lang='eng+ind')
                return text.strip() if text.strip() else "[Gambar tidak mengandung teks]"
            except ImportError:
                return "[OCR tidak tersedia]"
                
        elif filetype == 'txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
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
async def smart_chat_with_context(user_message, active_file=None, mode=MODE_NORMAL):
    """Smart chat that can detect and handle different modes"""
    
    if mode == MODE_SEARCH:
        # Search mode: Get information from www.pindad.com
        search_result = await scrape_pindad_website(user_message)
        search_prompt = f"""Based on the information from www.pindad.com:

{search_result}

Please answer the user's question: {user_message}

Provide a helpful and accurate response in Indonesian."""
        
        return await ask_qwen3_vl(search_prompt, stream=True)
    
    elif mode == MODE_DOCUMENT:
        # Document mode: Search through database documents
        search_result = await search_documents(user_message)
        
        if search_result["documents"] or search_result["chunks"]:
            # Combine document information
            context_parts = []
            
            # Add document summaries
            for doc in search_result["documents"][:3]:
                context_parts.append(f"Document: {doc['judul'] or 'Untitled'}")
                if doc['nomor']:
                    context_parts.append(f"Number: {doc['nomor']}")
                if doc['tanggal']:
                    context_parts.append(f"Date: {doc['tanggal']}")
                context_parts.append("---")
            
            # Add relevant chunks
            for chunk in search_result["chunks"][:3]:
                context_parts.append(f"Relevant section from '{chunk['judul']}':")
                context_parts.append(chunk['content'][:500])
                context_parts.append("---")
            
            context_text = "\n".join(context_parts)
            
            doc_prompt = f"""Using the following document information, please answer the user's question:

{context_text}

User question: {user_message}

Provide a helpful response in Indonesian based on the document information."""
            
            return await ask_qwen3_vl(doc_prompt, stream=True)
        else:
            # No relevant documents found, fall back to general search
            fallback_search = await scrape_pindad_website(user_message)
            fallback_prompt = f"""I couldn't find specific documents related to your query. However, here's some general information from www.pindad.com:

{fallback_search}

User question: {user_message}

Please provide a helpful response in Indonesian."""
            
            return await ask_qwen3_vl(fallback_prompt, stream=True)
    
    elif mode == MODE_NORMAL:
        # Normal mode: Direct chat without special context
        if not active_file:
            # General chat without file
            return await ask_qwen3_vl(user_message, stream=True)
        
        context_text = active_file['text'][:2500]  # Limit context
        
        # PROMPT ENGINEERING YANG OPTIMAL
        prompt = f"""Tugas: Jawab pertanyaan pengguna dengan cerdas.

INFORMASI FILE TERSEDIA (gunakan JIKA PERTANYANYA TENTANG FILE INI):
📁 File: {active_file['filename']}
📄 Konten: {context_text}

PERTANYAAN PENGGUNA: "{user_message}"

INSTRUKSI:
1. Analisis: Apakah pertanyaan ini tentang file di atas?
2. Jika YA: Jawab berdasarkan konten file
3. Jika TIDAK: Abaikan file, jawab sebagai AI assistant biasa
4. Gunakan Bahasa Indonesia
5. Jangan sebut "berdasarkan file" kecuali pertanyaan tentang file

JAWABAN:"""
        
        return await ask_qwen3_vl(prompt, stream=True)

# ========== ROUTES ==========
@app.route("/api/chat", methods=["POST"])
async def chat():
    """Endpoint chat utama dengan SMART context handling"""
    try:
        data = await request.get_json()
        user_message = data.get("message", "")
        file_id = data.get("file_id", None)
        mode = data.get("mode", MODE_NORMAL)  # Default to normal mode
        
        # Cek file context
        active_file = None
        if file_id and file_id in file_contexts:
            active_file = file_contexts[file_id]
        elif file_contexts and mode == MODE_NORMAL:  # Only use last file in normal mode
            last_file_id = list(file_contexts.keys())[-1]
            active_file = file_contexts[last_file_id]
        
        # Panggil SMART chat function
        reply = await smart_chat_with_context(user_message, active_file, mode)
        
        # Format response
        response = {"reply": reply, "mode": mode}
        if active_file:
            response["file_info"] = {
                "id": active_file['id'],
                "name": active_file['filename']
            }
        
        return jsonify(response)
        
    except Exception as e:
        logging.error(f"Chat error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload", methods=["POST"])
async def upload():
    """Upload dan analisis file dengan qwen3-vl"""
    try:
        if 'file' not in (await request.files):
            return jsonify({"error": "Tidak ada file"}), 400
        
        files = await request.files
        file = files['file']
        
        if not allowed_file(file.filename):
            return jsonify({"error": "Tipe file tidak didukung"}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        await file.save(filepath)
        
        filetype = filename.rsplit('.', 1)[1].lower()
        
        # Generate unique ID
        file_id = str(uuid.uuid4())[:8]
        
        # Simpan metadata awal
        file_contexts[file_id] = {
            "id": file_id,
            "filename": filename,
            "type": filetype,
            "path": filepath,
            "text": "[Sedang mengekstrak...]"
        }
        
        # Ekstrak konten
        extracted_text = await extract_with_qwen3_vl(filepath, filetype)
        
        # Update dengan hasil ekstraksi
        file_contexts[file_id]['text'] = extracted_text[:8000]
        
        # Generate ringkasan
        summary = await generate_summary(extracted_text[:2000])
        
        return jsonify({
            "success": True,
            "file_id": file_id,
            "filename": filename,
            "file_type": filetype,
            "text_length": len(extracted_text),
            "summary": summary,
            "message": f"✅ File '{filename}' berhasil diupload dan dianalisis."
        })
        
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
        if context['type'] in ['png', 'jpg', 'jpeg']:
            with open(context['path'], "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode('utf-8')
            
            reply = await ask_qwen3_vl(question, images=[img_b64], file_type=context['type'])
            
        else:
            # Untuk file lain
            prompt = f"""File: {context['filename']}

Konten File:
{context['text'][:4000]}

Pertanyaan: {question}

Jawab dalam Bahasa Indonesia:"""
            
            reply = await ask_qwen3_vl(prompt)
        
        return jsonify({
            "reply": reply,
            "file": context['filename']
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/files", methods=["GET"])
async def list_files():
    """List semua file yang diupload"""
    files_list = []
    for fid, context in file_contexts.items():
        files_list.append({
            "id": fid,
            "filename": context['filename'],
            "type": context['type'],
            "size": os.path.getsize(context['path']) if os.path.exists(context['path']) else 0,
            "summary": context['text'][:150] + "..." if len(context['text']) > 150 else context['text']
        })
    
    return jsonify({"files": files_list, "count": len(files_list)})

@app.route("/api/upload-preview", methods=["POST"])
async def upload_preview():
    """Preview file before full upload and processing"""
    try:
        if 'file' not in (await request.files):
            return jsonify({"error": "Tidak ada file"}), 400
        
        files = await request.files
        file = files['file']
        
        if not allowed_file(file.filename):
            return jsonify({"error": "Tipe file tidak didukung"}), 400
        
        filename = secure_filename(file.filename)
        filetype = filename.rsplit('.', 1)[1].lower()
        
        # Generate unique ID
        file_id = str(uuid.uuid4())
        
        # Create temp upload path
        temp_filename = f"temp_{file_id}_{filename}"
        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
        await file.save(temp_filepath)
        
        # Extract preview text using qwen3-vl or fallback
        preview_text = await extract_with_qwen3_vl(temp_filepath, filetype)
        preview_text = preview_text[:1000]  # Limit preview text
        
        # Store in temp storage
        temp_uploaded_files[file_id] = {
            "filepath": temp_filepath,
            "filename": filename,
            "filetype": filetype,
            "preview_text": preview_text
        }
        
        return jsonify({
            "success": True,
            "file_id": file_id,
            "filename": filename,
            "file_type": filetype,
            "preview_text": preview_text,
            "size": os.path.getsize(temp_filepath)
        })
        
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
        final_filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        # If filename already exists, add timestamp
        if os.path.exists(final_filepath):
            name, ext = os.path.splitext(filename)
            timestamp = str(int(time.time()))
            final_filename = f"{name}_{timestamp}{ext}"
            final_filepath = os.path.join(app.config['UPLOAD_FOLDER'], final_filename)
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
            "text": temp_file_info["preview_text"]  # Use the preview text
        }
        
        # Remove from temp storage
        del temp_uploaded_files[file_id]
        
        # Generate summary
        summary = await generate_summary(temp_file_info["preview_text"][:2000])
        
        return jsonify({
            "success": True,
            "file_id": final_file_id,
            "filename": final_filename,
            "file_type": filetype,
            "text_length": len(temp_file_info["preview_text"]),
            "summary": summary,
            "message": f"✅ File '{final_filename}' berhasil diproses."
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cancel-upload", methods=["POST"])
async def cancel_upload():
    """Cancel upload and remove temp file"""
    try:
        data = await request.get_json()
        file_id = data.get("file_id")
        
        if not file_id or file_id not in temp_uploaded_files:
            return jsonify({"success": True, "message": "File tidak ditemukan di temp storage"})
        
        temp_file_info = temp_uploaded_files[file_id]
        filepath = temp_file_info["filepath"]
        
        # Remove temp file
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Remove from temp storage
        del temp_uploaded_files[file_id]
        
        return jsonify({
            "success": True,
            "message": "Upload dibatalkan dan file dihapus"
        })
        
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
        
        return jsonify({
            "success": True,
            "mode": mode,
            "message": f"Mode changed to {mode}"
        })
        
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
        
        return jsonify({
            "documents": [dict(row) for row in documents],
            "count": len(documents)
        })
        
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
        
        return jsonify({
            "document": dict(document),
            "chunks": [dict(row) for row in chunks]
        })
        
    except Exception as e:
        logging.error(f"Error getting document: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
async def health():
    """Health check endpoint"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OLLAMA_URL, json={
                "model": PRIMARY_MODEL,
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False
            }, timeout=5) as resp:
                ollama_status = resp.status == 200
                
        return jsonify({
            "status": "healthy",
            "service": "CAKRA AI Pro",
            "model": PRIMARY_MODEL,
            "uploaded_files": len(file_contexts),
            "ollama_connected": ollama_status
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print(f"🚀 CAKRA AI Pro starting...")
    print(f"🤖 Primary Model: {PRIMARY_MODEL}")
    print(f"📁 Upload folder: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"🌐 API running on http://0.0.0.0:5000")
    
    app.run(host="0.0.0.0", port=5000, debug=True)