from flask import Flask, render_template, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer
import subprocess
import uuid
import datetime
import re
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# ====================================================
# CONFIGURATION
# ====================================================
class Config:
    DB_CONFIG = {
        "host": os.getenv('DB_HOST', 'localhost'),
        "database": os.getenv('DB_NAME', 'ragdb'),
        "user": os.getenv('DB_USER', 'pindadai'),
        "password": os.getenv('DB_PASSWORD', 'Pindad123!')
    }
    
    EMBEDDING_MODEL = "intfloat/multilingual-e5-base"
    DEFAULT_MODELS = ["qwen2.5:7b", "qwen3:8b", "deepseek-coder:6.7b"]
    OLLAMA_TIMEOUT = 120
    SEARCH_TOP_K = 5

# ====================================================
# DATABASE MANAGER
# ====================================================
class DatabaseManager:
    @staticmethod
    def get_connection():
        return psycopg2.connect(**Config.DB_CONFIG)
    
    @staticmethod
    def execute_query(query, params=None, fetch=False):
        conn = DatabaseManager.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params or ())
                if fetch:
                    return cur.fetchall()
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

# ====================================================
# EMBEDDING SERVICE
# ====================================================
class EmbeddingService:
    _instance = None
    
    def __init__(self):
        if EmbeddingService._instance is None:
            self.embedder = SentenceTransformer(Config.EMBEDDING_MODEL, device="cuda")
            EmbeddingService._instance = self
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def encode_text(self, text):
        return self.embedder.encode([text], convert_to_numpy=True)[0].tolist()

# ====================================================
# OLLAMA CLIENT
# ====================================================
class OllamaClient:
    @staticmethod
    def clean_response(response):
        """Clean Ollama response from thinking process and markdown"""
        if not response:
            return "❌ Tidak ada jawaban yang dihasilkan."
        
        # Remove thinking patterns
        thinking_patterns = [
            r'Thinking\..*?\.\.\.done thinking\.',
            r'^.*[Tt]hinking.*$',
            r'^\.\.\.done thinking\.$',
            r'^Okay, so.*$',
            r'^Okay,.*?(?=\n\n)',
        ]
        
        cleaned = response
        for pattern in thinking_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.DOTALL)
        
        # Remove markdown
        markdown_cleaners = [
            (r'\*\*(.*?)\*\*', r'\1'),
            (r'\*(.*?)\*', r'\1'),
            (r'##\s*', ''),
            (r'#\s*', ''),
            (r'`(.*?)`', r'\1'),
        ]
        
        for pattern, replacement in markdown_cleaners:
            cleaned = re.sub(pattern, replacement, cleaned)
        
        # Clean whitespace
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned).strip()
        return cleaned
    
    @staticmethod
    def get_models():
        """Get available Ollama models"""
        try:
            result = subprocess.run(
                ["ollama", "list"], 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                models = [line.split()[0] for line in lines[1:] if line.strip()]
                return models or Config.DEFAULT_MODELS
        except Exception as e:
            logger.error(f"Failed to get Ollama models: {e}")
        
        return Config.DEFAULT_MODELS
    
    @staticmethod
    def ask_model(model, context, question):
        """Ask question to Ollama model with context"""
        if not question.strip():
            return "❌ Pertanyaan tidak boleh kosong."
        
        prompt = f"""
Konteks:
{context}

Pertanyaan:
{question}

Jawablah secara rinci dan senatural mungkin berdasarkan konteks di atas. 
Perbaiki kata yang tidak sesuai atau koreksi kalimat agar seperti semestinya bahasa Indonesia yang baik dan benar.
Langsung berikan jawaban tanpa proses thinking.
"""
        try:
            result = subprocess.run(
                ["ollama", "run", model],
                input=prompt.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=Config.OLLAMA_TIMEOUT
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.decode("utf-8", errors="ignore")
                return f"❌ Error dari Ollama: {error_msg}"
            
            raw_output = result.stdout.decode("utf-8", errors="ignore")
            return OllamaClient.clean_response(raw_output)
            
        except subprocess.TimeoutExpired:
            return "❌ Timeout: Model mengambil waktu terlalu lama untuk merespons."
        except Exception as e:
            return f"❌ Error: {str(e)}"

# ====================================================
# RAG SERVICE
# ====================================================
class RAGService:
    @staticmethod
    def search_similar(query_text, top_k=Config.SEARCH_TOP_K):
        """Search similar documents in database"""
        try:
            embedder = EmbeddingService.get_instance()
            emb = embedder.encode_text(query_text)
            
            results = DatabaseManager.execute_query(
                """
                SELECT id, dokumen_id, chunk_id, content,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM dokumen_chunk
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (emb, emb, top_k),
                fetch=True
            )
            return results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

# ====================================================
# CHAT MANAGER
# ====================================================
class ChatManager:
    @staticmethod
    def create_session(model_name, user_name="anonymous"):
        """Create new chat session"""
        result = DatabaseManager.execute_query(
            """
            INSERT INTO chat_sessions (session_uuid, user_name, model_name, started_at)
            VALUES (%s, %s, %s, NOW())
            RETURNING id, session_uuid;
            """,
            (str(uuid.uuid4()), user_name, model_name),
            fetch=True
        )
        return result[0]['id'], result[0]['session_uuid'] if result else (None, None)
    
    @staticmethod
    def save_message(session_id, role, message_text):
        """Save chat message to database"""
        DatabaseManager.execute_query(
            """
            INSERT INTO chat_messages (session_id, role, message_text, timestamp)
            VALUES (%s, %s, %s, NOW());
            """,
            (session_id, role, message_text)
        )
    
    @staticmethod
    def get_sessions():
        """Get all chat sessions"""
        return DatabaseManager.execute_query(
            """
            SELECT cs.id, cs.session_uuid, cs.model_name, cs.started_at,
                   COUNT(cm.id) as message_count
            FROM chat_sessions cs
            LEFT JOIN chat_messages cm ON cs.id = cm.session_id
            GROUP BY cs.id, cs.session_uuid, cs.model_name, cs.started_at
            ORDER BY cs.started_at DESC
            LIMIT 20;
            """,
            fetch=True
        ) or []
    
    @staticmethod
    def get_session_messages(session_id):
        """Get messages for specific session"""
        return DatabaseManager.execute_query(
            """
            SELECT role, message_text, timestamp
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY timestamp ASC;
            """,
            (session_id,),
            fetch=True
        ) or []
    
    @staticmethod
    def switch_model(session_id, new_model):
        """Switch model for chat session"""
        DatabaseManager.execute_query(
            """
            UPDATE chat_sessions 
            SET model_name = %s 
            WHERE id = %s;
            """,
            (new_model, session_id)
        )

# ====================================================
# FLASK ROUTES
# ====================================================
@app.route('/')
def index():
    sessions = ChatManager.get_sessions()
    models = OllamaClient.get_models()
    return render_template('askIndex.html', sessions=sessions, models=models)

@app.route('/chat/<int:session_id>')
def chat_session(session_id):
    sessions = ChatManager.get_sessions()
    models = OllamaClient.get_models()
    messages = ChatManager.get_session_messages(session_id)
    
    current_session = next((s for s in sessions if s['id'] == session_id), None)
    if not current_session:
        return "Session not found", 404
        
    return render_template('chat.html', 
                         sessions=sessions, 
                         models=models,
                         current_session=current_session,
                         messages=messages)

@app.route('/api/new_chat', methods=['POST'])
def new_chat():
    model_name = request.json.get('model', 'qwen2.5:7b')
    session_id, session_uuid = ChatManager.create_session(model_name)
    
    if session_id:
        return jsonify({
            'success': True,
            'session_id': session_id,
            'session_uuid': str(session_uuid),
            'redirect_url': f'/chat/{session_id}'
        })
    else:
        return jsonify({'success': False, 'error': 'Failed to create session'}), 500

@app.route('/api/send_message', methods=['POST'])
def send_message():
    data = request.json
    session_id = data.get('session_id')
    question = data.get('message', '').strip()
    model = data.get('model', 'qwen2.5:7b')
    
    if not session_id or not question:
        return jsonify({'error': 'Missing session_id or message'}), 400
    
    # Save user message
    ChatManager.save_message(session_id, 'user', question)
    
    # Search for context and get AI response
    results = RAGService.search_similar(question)
    context = "\n\n".join([r["content"] for r in results]) if results else ""
    answer = OllamaClient.ask_model(model, context, question)
    
    # Save AI response
    ChatManager.save_message(session_id, 'assistant', answer)
    
    return jsonify({
        'success': True,
        'answer': answer
    })

@app.route('/api/switch_model', methods=['POST'])
def switch_model():
    data = request.json
    session_id = data.get('session_id')
    new_model = data.get('model')
    
    if not session_id or not new_model:
        return jsonify({'error': 'Missing session_id or model'}), 400
    
    ChatManager.switch_model(session_id, new_model)
    return jsonify({'success': True, 'new_model': new_model})

# ====================================================
# ERROR HANDLERS
# ====================================================
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ====================================================
# INITIALIZATION
# ====================================================
def initialize_services():
    """Initialize required services on startup"""
    try:
        # Initialize embedding service
        EmbeddingService.get_instance()
        logger.info("✅ Services initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")

# Initialize on import
initialize_services()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)