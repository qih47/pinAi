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

app = Quart(__name__)

# ========== KONFIGURASI ==========
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'txt', 'docx', 'pptx', 'xlsx'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# CORS
app = cors(app, allow_origin=["http://192.168.11.80:5173"])

# Ollama endpoints
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

# PRIMARY MODEL - HANYA SATU
PRIMARY_MODEL = "qwen3-vl:8b"  # 🎯 MODEL UTAMA

# Context-aware storage
file_contexts = {}  # {file_id: {metadata, text, embeddings}}

# ========== HELPER FUNCTIONS ==========
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
                    images=[img_b64]
                )
                all_text.append(text)
            
            return "\n\n".join(all_text)
            
        elif filetype in ['png', 'jpg', 'jpeg']:
            with open(filepath, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode('utf-8')
            
            return await ask_qwen3_vl(
                "Ekstrak semua teks dari gambar ini:",
                images=[img_b64]
            )
            
        elif filetype == 'txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
                
        else:
            return await extract_fallback(filepath, filetype)
            
    except Exception as e:
        logging.error(f"Qwen3-VL extraction error: {e}")
        return await extract_fallback(filepath, filetype)

async def ask_qwen3_vl(prompt, images=None, stream=False):
    """Helper untuk bertanya ke qwen3-vl:8b"""
    messages = [{"role": "user", "content": prompt}]
    if images:
        messages[0]["images"] = images
    
    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json={
            "model": PRIMARY_MODEL,
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
async def smart_chat_with_context(user_message, active_file=None):
    """Smart chat yang bisa deteksi sendiri perlu context atau tidak"""
    
    if not active_file:
        # General chat tanpa file
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
        
        # Cek file context
        active_file = None
        if file_id and file_id in file_contexts:
            active_file = file_contexts[file_id]
        elif file_contexts:  # Ambil file terakhir jika tidak spesifik
            last_file_id = list(file_contexts.keys())[-1]
            active_file = file_contexts[last_file_id]
        
        # Panggil SMART chat function
        reply = await smart_chat_with_context(user_message, active_file)
        
        # Format response
        response = {"reply": reply}
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
            
            reply = await ask_qwen3_vl(question, images=[img_b64])
            
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