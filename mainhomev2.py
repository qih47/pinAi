from flask import Flask, render_template, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer
import subprocess, uuid, datetime, re, os, json
import numpy as np
from typing import Dict, List, Tuple, Optional

app = Flask(__name__)
app.secret_key = "80769f0403534ef73f11092dd900d8ce8d8bad1ed4fbe81c634562258b36e1fd"

# ====================================================
# DATABASE CONFIG
# ====================================================
DB_CONFIG = {
    "host": "localhost",
    "database": "ragdb",
    "user": "pindadai",
    "password": "Pindad123!"
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

# ====================================================
# EMBEDDING MODEL
# ====================================================
embedder = SentenceTransformer("intfloat/multilingual-e5-base", device="cuda")

# ====================================================
# ENHANCED CONTEXT MANAGER WITH NLP
# ====================================================
class EnhancedConversationContext:
    def __init__(self):
        self.current_context = None
        self.last_question = None
        self.last_answer = None
        self.context_history = []
        self.entities = {}  # Track entities dalam conversation
        self.question_type = None
        self.sentiment = "neutral"
        self.conversation_topic = None
        
    def update_context(self, question: str, answer: str, rag_context: List):
        # Comprehensive NLP analysis sebelum update
        self._analyze_question(question)
        
        # Extract context dari RAG results dengan NLP enhancement
        self.current_context = self._extract_context_from_rag(rag_context)
        self.last_question = question
        self.last_answer = answer
        
        # Update conversation topic
        self._update_conversation_topic(question, answer)
        
        self.context_history.append({
            "question": question,
            "answer": answer, 
            "context": self.current_context,
            "entities": self.entities.copy(),
            "question_type": self.question_type,
            "sentiment": self.sentiment,
            "topic": self.conversation_topic,
            "timestamp": datetime.datetime.now()
        })
        
        # Keep only last 5 conversations untuk better context
        if len(self.context_history) > 5:
            self.context_history.pop(0)
    
    def _analyze_question(self, question: str):
        """Comprehensive NLP analysis untuk setiap question"""
        # Entity extraction
        self.entities = self._extract_entities(question)
        
        # Question type classification
        self.question_type = self._classify_question_type(question)
        
        # Sentiment analysis
        self.sentiment = self._detect_sentiment(question)
        
        print(f"🔍 NLP Analysis - Type: {self.question_type}, Sentiment: {self.sentiment}")
        if self.entities:
            print(f"   Entities: {self.entities}")
    
    def _extract_entities(self, text: str) -> Dict:
        """Extract entities dari text menggunakan rule-based + patterns"""
        entities = {
            'person': [],
            'department': [],
            'numbers': [],
            'dates': [],
            'documents': [],
            'topics': []
        }
        
        text_lower = text.lower()
        
        # Person names
        person_patterns = [
            r'(?:nama|panggil|saya|aku) (?:saya|aku)?\s*(\w+)',
            r'bilang (?:pada|ke) (\w+)',
            r'(\w+) (?:dari|di) departemen'
        ]
        for pattern in person_patterns:
            matches = re.findall(pattern, text_lower)
            entities['person'].extend(matches)
        
        # Departments
        dept_patterns = [
            r'departemen\s*(\w+)',
            r'divisi\s*(\w+)', 
            r'bagian\s*(\w+)',
            r'di\s*(?:departemen|divisi)\s*(\w+)'
        ]
        for pattern in dept_patterns:
            matches = re.findall(pattern, text_lower)
            entities['department'].extend(matches)
        
        # Document references
        doc_patterns = [
            r'dokumen\s*(\w+)',
            r'surat\s*(\w+)',
            r'peraturan\s*(\w+)',
            r'kebijakan\s*(\w+)'
        ]
        for pattern in doc_patterns:
            matches = re.findall(pattern, text_lower)
            entities['documents'].extend(matches)
        
        # Numbers and dates
        entities['numbers'] = re.findall(r'\b\d+\b', text)
        entities['dates'] = re.findall(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', text)
        
        # Clean empty entities
        return {k: v for k, v in entities.items() if v}
    
    def _classify_question_type(self, question: str) -> str:
        """Classify question type untuk better processing"""
        question_lower = question.lower()
        
        patterns = {
            'factual': [
                r'^(apa|berapa|kapan|dimana|siapa)\b',
                r'\b(apa itu|apa saja)\b'
            ],
            'procedural': [
                r'^(bagaimana|cara|langkah|proses|tahapan)\b',
                r'\b(cara|langkah|proses)\b'
            ],
            'comparative': [
                r'^(mana yang|perbedaan|lebih|bandingkan)\b',
                r'\b(perbedaan|perbandingan)\b'
            ],
            'confirmational': [
                r'^(apakah|benarkah|bisakah|bolehkah)\b',
                r'\b(apakah|benarkah)\b.*\?$'
            ],
            'instructional': [
                r'^(tolong|bantu|carikan|jelaskan)\b',
                r'\b(tolong|bantu)\b'
            ]
        }
        
        for q_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                if re.search(pattern, question_lower):
                    return q_type
        
        return 'general'
    
    def _detect_sentiment(self, text: str) -> str:
        """Simple sentiment analysis untuk personalize response"""
        positive_words = ['terima kasih', 'bagus', 'mantap', 'oke', 'sip', 'thanks', 'good', 'perfect']
        negative_words = ['error', 'gak bisa', 'salah', 'masalah', 'bug', 'jelek', 'buruk', 'susah']
        urgent_words = ['cepat', 'segera', 'urgent', 'penting', 'sekarang', 'cepatan']
        
        text_lower = text.lower()
        positive_score = sum(1 for word in positive_words if word in text_lower)
        negative_score = sum(1 for word in negative_words if word in text_lower)
        urgent_score = sum(1 for word in urgent_words if word in text_lower)
        
        if urgent_score > 0:
            return "urgent"
        elif positive_score > negative_score:
            return "positive"
        elif negative_score > positive_score:
            return "negative"
        else:
            return "neutral"
    
    def _update_conversation_topic(self, question: str, answer: str):
        """Update current conversation topic"""
        topic_keywords = {
            'benefit': ['benefit', 'tunjangan', 'kesehatan', 'asuransi', 'cuti'],
            'hr': ['hr', 'human resource', 'karyawan', 'gaji', 'kontrak'],
            'dokumen': ['dokumen', 'surat', 'peraturan', 'kebijakan', 'prosedur'],
            'technical': ['technical', 'teknisi', 'mesin', 'produksi', 'quality'],
            'training': ['training', 'pelatihan', 'workshop', 'sertifikasi']
        }
        
        combined_text = f"{question} {answer}".lower()
        topic_scores = {}
        
        for topic, keywords in topic_keywords.items():
            score = sum(1 for keyword in keywords if keyword in combined_text)
            if score > 0:
                topic_scores[topic] = score
        
        if topic_scores:
            self.conversation_topic = max(topic_scores.items(), key=lambda x: x[1])[0]
        else:
            self.conversation_topic = None
    
    def _extract_context_from_rag(self, rag_results: List) -> Optional[str]:
        """Enhanced context extraction dengan entity awareness"""
        if not rag_results:
            return None
            
        # Ambil content dari RAG results yang similarity tinggi
        high_similarity_content = []
        for result in rag_results[:3]:  # Ambil 3 hasil terbaik
            if result.get("similarity", 0) >= 0.7:
                content = result["content"]
                
                # Prioritize content yang mengandung entities yang relevan
                if self.entities:
                    entity_score = sum(1 for entity_list in self.entities.values() 
                                    for entity in entity_list if str(entity).lower() in content.lower())
                    if entity_score > 0:
                        # Add entity-relevant content dengan priority
                        words = content.split()[:15]
                        high_similarity_content.extend(words)
                else:
                    # Default: ambil 10 kata pertama
                    words = content.split()[:10]
                    high_similarity_content.extend(words)
        
        return " ".join(high_similarity_content) if high_similarity_content else None
    
    def should_maintain_context(self, new_question: str) -> bool:
        """Enhanced context maintenance dengan NLP features"""
        if not self.current_context or not self.last_question:
            return False
        
        # Analyze new question
        self._analyze_question(new_question)
        
        new_question_lower = new_question.lower()
        
        # Enhanced continuation patterns dengan NLP insights
        continuation_patterns = [
            # Basic continuation words
            r'^(kalau|lalu|selanjutnya|kemudian|terus|nah|trus)\b',
            # Question words yang biasanya lanjutan
            r'^(bagaimana|apa|berapa|kapan|dimana|siapa)\b.*\?$',
            # Procedural words
            r'^(proses|tahapan|langkah|syarat|persyaratan|kriteria)\b',
            # Continuation suffixes
            r'.*(lagi|lanjut|selanjutnya|berikutnya)$',
            # Short questions (likely follow-ups)
            r'^\s*\w{1,10}\s*\??$'
        ]
        
        # Pattern-based detection
        for pattern in continuation_patterns:
            if re.search(pattern, new_question_lower):
                return True
        
        # Entity-based context maintenance
        if self.entities and self.context_history:
            last_entities = self.context_history[-1].get("entities", {})
            current_entities = self.entities
            
            # Check jika ada entity overlap dengan previous question
            entity_overlap = False
            for entity_type in current_entities:
                if entity_type in last_entities:
                    common_entities = set(current_entities[entity_type]) & set(last_entities[entity_type])
                    if common_entities:
                        entity_overlap = True
                        break
            
            if entity_overlap:
                return True
        
        # Topic-based context maintenance
        if (self.conversation_topic and self.context_history and 
            self.conversation_topic == self.context_history[-1].get("topic")):
            return True
        
        # Jika pertanyaan sangat pendek (mungkin lanjutan)
        if len(new_question.split()) <= 4:
            return True
            
        return False
    
    def get_context_enhanced_prompt(self) -> str:
        """Get NLP-enhanced context untuk prompt engineering"""
        context_parts = []
        
        if self.entities:
            entity_str = ", ".join([f"{k}: {v}" for k, v in self.entities.items()])
            context_parts.append(f"Entities: {entity_str}")
        
        if self.question_type and self.question_type != 'general':
            context_parts.append(f"Question type: {self.question_type}")
        
        if self.sentiment != "neutral":
            context_parts.append(f"User sentiment: {self.sentiment}")
            
        if self.conversation_topic:
            context_parts.append(f"Conversation topic: {self.conversation_topic}")
        
        return " | ".join(context_parts) if context_parts else ""

# Global enhanced context manager
conversation_context = EnhancedConversationContext()

# ====================================================
# ENHANCED NLP INTENT DETECTION
# ====================================================
def is_memory_instruction(text: str) -> bool:
    """Enhanced memory instruction detection"""
    text = text.lower()
    patterns = [
        r"panggil saya", r"mulai sekarang", r"tolong ingat",
        r"saya ingin kamu", r"mulai hari ini", r"anggap bahwa",
        r"jika saya bilang", r"kalau aku bilang", r"preferensi saya",
        r"ingat ya", r"simpan ini", r"catat bahwa", r"ingatlah",
        r"selalu sebut", r"panggil aku", r"nama saya"
    ]
    return any(re.search(p, text) for p in patterns)

def is_correction(text: str) -> bool:
    """Enhanced correction detection"""
    text = text.lower()
    correction_patterns = [
        r"seharusnya", r"koreksi", r"yang benar", 
        r"bukan begitu", r"salah itu", r"perbaiki",
        r"sebenarnya", r"yang tepat", r"revisi",
        r"update informasi", r"info yang benar"
    ]
    return any(re.search(p, text) for p in correction_patterns)

def is_greeting(text: str) -> bool:
    """Detect greetings untuk personalized response"""
    text = text.lower()
    greetings = [
        r"hai|halo|hey|hi|hello",
        r"selamat (pagi|siang|sore|malam)",
        r"apa kabar", r"how are you",
        r"good (morning|afternoon|evening)"
    ]
    return any(re.search(g, text) for g in greetings)

def is_thanks(text: str) -> bool:
    """Detect thank you messages"""
    text = text.lower()
    thanks_patterns = [
        r"terima kasih", r"thanks", r"thank you",
        r"makasih", r"thx", r"terimakasih"
    ]
    return any(re.search(p, text) for p in thanks_patterns)

# ====================================================
# USER MEMORY (PREFERENSI) - ENHANCED
# ====================================================
def save_user_memory(key: str, value: str):
    """Enhanced memory saving dengan entity extraction"""
    # Extract entities dari key untuk better organization
    entities = conversation_context._extract_entities(key)
    
    emb = embedder.encode([key])[0].tolist()
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM ai_user_profile WHERE key=%s", (key,))
    exists = cur.fetchone()

    if exists:
        cur.execute("""
            UPDATE ai_user_profile 
            SET value=%s, embedding=%s, updated_at=NOW(), metadata=%s
            WHERE key=%s
        """, (value, emb, json.dumps({"entities": entities}), key))
    else:
        cur.execute("""
            INSERT INTO ai_user_profile (key, value, embedding, metadata)
            VALUES (%s, %s, %s, %s)
        """, (key, value, emb, json.dumps({"entities": entities})))

    conn.commit()
    conn.close()
    print(f"💾 Saved user memory: {key} -> {value}")

def get_relevant_user_memory(query: str, top_k: int = 10):
    """Enhanced memory retrieval dengan similarity threshold"""
    emb = embedder.encode([query])[0].tolist()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # FIX: Parameter match
    cur.execute("""
        SELECT key, value, metadata,
               1 - (embedding <=> %s::vector) AS similarity
        FROM ai_user_profile
        WHERE 1 - (embedding <=> %s::vector) > 0.7
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (emb, emb, emb, top_k))  # 4 parameters
    rows = cur.fetchall()
    conn.close()
    return rows

# ====================================================
# LEARNING (KOREKSI USER) - ENHANCED
# ====================================================
def save_correction(question: str, corrected: str):
    """Enhanced correction saving dengan context"""
    emb = embedder.encode([question])[0].tolist()
    conn = get_db()
    cur = conn.cursor()
    
    # Simpan context dari conversation
    metadata = {
        "context": conversation_context.current_context,
        "entities": conversation_context.entities,
        "question_type": conversation_context.question_type,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    cur.execute("""
        INSERT INTO ai_learning (question_text, corrected_answer, embedding, metadata)
        VALUES (%s, %s, %s, %s)
    """, (question, corrected, emb, json.dumps(metadata)))
    conn.commit()
    conn.close()
    print(f"📝 Saved correction: {question}")

def search_learning(query: str, top_k: int = 10):
    """Enhanced learning search dengan context awareness"""
    emb = embedder.encode([query])[0].tolist()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # FIX: Parameter match  
    cur.execute("""
        SELECT question_text, corrected_answer, metadata,
               1 - (embedding <=> %s::vector) AS similarity
        FROM ai_learning
        WHERE 1 - (embedding <=> %s::vector) > 0.6
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (emb, emb, emb, top_k))  # 4 parameters
    rows = cur.fetchall()
    conn.close()
    return rows

# ====================================================
# DIALOG CORPUS (Conversational Memory) - ENHANCED
# ====================================================
def save_dialogue(user_text: str, assistant_text: str):
    """Enhanced dialogue saving dengan NLP features"""
    emb_user = embedder.encode([user_text])[0].tolist()
    emb_ai = embedder.encode([assistant_text])[0].tolist()

    # Simpan NLP insights
    metadata = {
        "entities": conversation_context.entities,
        "question_type": conversation_context.question_type,
        "sentiment": conversation_context.sentiment,
        "topic": conversation_context.conversation_topic,
        "source": "live",
        "timestamp": datetime.datetime.now().isoformat()
    }

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ai_dialogue_corpus
        (user_text, assistant_text, embedding_user, embedding_assistant, metadata)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_text, assistant_text, emb_user, emb_ai, json.dumps(metadata)))
    conn.commit()
    conn.close()

def search_dialogue(query: str, top_k: int = 10):
    """Enhanced dialogue search dengan similarity threshold"""
    emb = embedder.encode([query])[0].tolist()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # FIX: Parameter match
    cur.execute("""
        SELECT user_text, assistant_text, metadata,
               1 - (embedding_user <=> %s::vector) AS similarity
        FROM ai_dialogue_corpus
        WHERE 1 - (embedding_user <=> %s::vector) > 0.65
        ORDER BY embedding_user <=> %s::vector
        LIMIT %s
    """, (emb, emb, emb, top_k))  # 4 parameters
    rows = cur.fetchall()
    conn.close()
    return rows

# ====================================================
# ENHANCED RAG SEARCH WITH NLP AWARENESS
# ====================================================
def search_rag(query: str, top_k: int = 8) -> List:
    """Enhanced RAG search dengan complete dokumen reference data"""
    
    search_query = query
    
    # Context awareness
    if conversation_context.should_maintain_context(query):
        if conversation_context.current_context:
            search_query = f"{query} {conversation_context.current_context}"
            print(f"🔍 Maintaining context: {search_query}")
    
    emb = embedder.encode([search_query])[0].tolist()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # QUERY YANG BENAR - Ambil semua data yang dibutuhkan untuk reference
    cur.execute("""
        SELECT 
            c.content, 
            c.dokumen_id,
            d.judul, 
            d.nomor,
            d.tanggal,
            d.filename,
            jd.nama AS jenis_dokumen,
            1 - (c.embedding <=> %s::vector) AS similarity
        FROM dokumen_chunk c
        JOIN dokumen d ON d.id = c.dokumen_id
        LEFT JOIN jenis_dokumen jd ON jd.id = d.id_jenis
        ORDER BY c.embedding <=> %s::vector
        LIMIT 15
    """, (emb, emb))
    chunks = cur.fetchall()
    conn.close()
    
    # Filtering based on quality
    high_quality = [r for r in chunks if r["similarity"] >= 0.7]
    medium_quality = [r for r in chunks if 0.6 <= r["similarity"] < 0.7]
    
    if high_quality:
        return sorted(high_quality, key=lambda x: x["similarity"], reverse=True)[:top_k]
    elif medium_quality:
        return sorted(medium_quality, key=lambda x: x["similarity"], reverse=True)[:top_k]
    else:
        return chunks[:3]
# ====================================================
# ENHANCED CLEANING & RESPONSE PROCESSING
# ====================================================
def clean_response(text: str) -> str:
    """Enhanced response cleaning"""
    # Remove thinking patterns
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'Thinking\..*?\.\.\.done thinking\.', '', text, flags=re.DOTALL)
    text = re.sub(r'【.*?】', '', text)
    text = re.sub(r'^.*?Based on.*?(?=\n\n)', '', text, flags=re.DOTALL)
    text = re.sub(r'^.*?According to.*?(?=\n\n)', '', text, flags=re.DOTALL)
    
    # Remove excessive newlines
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()

# ====================================================
# ENHANCED ANTI-HALLUCINATION FILTER
# ====================================================
def is_corporate_answer_possible(rag: List, learning: List, memory: List, question: str) -> Tuple[bool, str]:
    """Enhanced anti-hallucination dengan NLP awareness"""
    
    # Strict RAG filtering
    if rag and isinstance(rag, list) and len(rag) > 0:
        # Different thresholds berdasarkan question type
        if conversation_context.question_type == 'factual':
            threshold = 0.7
        elif conversation_context.question_type == 'procedural':
            threshold = 0.65
        else:
            threshold = 0.6
            
        high_similarity_results = [r for r in rag if r.get("similarity", 0) >= threshold]
        
        if high_similarity_results:
            return True, "dokumen"
    
    # Untuk non-factual questions, consider learning dengan strict filter
    if (conversation_context.question_type != 'factual' and 
        learning and isinstance(learning, list) and len(learning) > 0):
        high_similarity_learning = [l for l in learning if l.get("similarity", 0) >= 0.8]
        if high_similarity_learning:
            return True, "learning"
    
    return False, "none"

def is_factual_question(question: str) -> bool:
    """Enhanced factual question detection"""
    factual_keywords = ["apa", "berapa", "kapan", "dimana", "bagaimana", "siapa", 
                       "prosedur", "kebijakan", "peraturan", "ketentuan", "syarat"]
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in factual_keywords)

# ====================================================
# ENHANCED ANSWER BUILDER WITH NLP
# ====================================================
def ask_ollama(model: str, memory: List, learning: List, dialog: List, rag: List, 
               question: str, source_type: str) -> str:
    """AI response generation dengan SATU dokumen reference paling relevan + PDF link"""
    
    # Build context
    rag_context = "\n".join([f"📄 {r['content']}" for r in rag if isinstance(r, dict) and 'content' in r]) if rag else "Tidak ada data dokumen yang relevan."
    
    # Extract SATU dokumen paling relevan (highest similarity)
    most_relevant_doc = None
    if rag and isinstance(rag, list) and len(rag) > 0:
        # Urutkan berdasarkan similarity tertinggi
        sorted_rag = sorted(rag, key=lambda x: x.get("similarity", 0), reverse=True)
        best_result = sorted_rag[0]  # Ambil yang paling relevan
        
        # AMBIL DATA REAL DARI HASIL TERBAIK
        judul = best_result.get('judul', '')
        nomor = best_result.get('nomor', '')
        jenis_dokumen = best_result.get('jenis_dokumen', '')
        tanggal = best_result.get('tanggal', '')
        filename = best_result.get('filename', '')
        
        # FORMAT TANGGAL BAHASA INDONESIA
        tanggal_text = ''
        if tanggal:
            if isinstance(tanggal, datetime.date):
                # Format: 01 Juli 2025
                bulan_indonesia = {
                    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
                    7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
                }
                tanggal_text = f"{tanggal.day} {bulan_indonesia[tanggal.month]} {tanggal.year}"
            elif isinstance(tanggal, str):
                # Jika tanggal sudah dalam format string Indonesia, pakai langsung
                if any(bulan in tanggal for bulan in ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']):
                    tanggal_text = tanggal
                else:
                    # Convert dari format database
                    try:
                        if '-' in tanggal:
                            date_obj = datetime.datetime.strptime(tanggal, '%Y-%m-%d')
                            bulan_indonesia = {
                                1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
                                7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
                            }
                            tanggal_text = f"{date_obj.day} {bulan_indonesia[date_obj.month]} {date_obj.year}"
                    except:
                        tanggal_text = tanggal  # Fallback ke string asli
        
        # Format tahun
        tahun = ''
        if tanggal:
            if isinstance(tanggal, datetime.date):
                tahun = tanggal.year
            elif isinstance(tanggal, str):
                try:
                    if '-' in tanggal:
                        tahun = datetime.datetime.strptime(tanggal, '%Y-%m-%d').year
                    elif '/' in tanggal:
                        tahun = datetime.datetime.strptime(tanggal, '%Y/%m/%d').year
                    else:
                        # Coba extract tahun dari string
                        tahun_match = re.search(r'\b(20\d{2})\b', tanggal)
                        if tahun_match:
                            tahun = tahun_match.group(1)
                except:
                    tahun = ''
        
        # Only create reference if we have sufficient data
        if judul and nomor and jenis_dokumen:
            most_relevant_doc = {
                'jenis_dokumen': jenis_dokumen,
                'nomor': nomor,
                'judul': judul,
                'tahun': tahun,
                'tanggal': tanggal_text,
                'filename': filename
            }
            
            print(f"🎯 Dokumen paling relevan: {jenis_dokumen} {nomor} - Similarity: {best_result.get('similarity', 0):.3f}")
            print(f"   File: {filename}")
    
    # Personality based on sentiment
    personality = ""
    if conversation_context.sentiment == "positive":
        personality = "Jawab dengan ramah dan antusias."
    elif conversation_context.sentiment == "negative":
        personality = "Jawab dengan empati dan berusaha membantu menyelesaikan masalah."
    elif conversation_context.sentiment == "urgent":
        personality = "Berikan jawaban yang jelas, langsung, dan to the point."
    
    # Prompt engineering
    full_context = f"""
INFORMASI RESMI DARI DOKUMEN PERUSAHAAN:
{rag_context}

PERTANYAAN: {question}

INSTRUKSI WAJIB:
1. JAWAB HANYA BERDASARKAN INFORMASI DI ATAS
2. {personality}
3. Jika informasi tersedia, berikan jawaban detail
4. Jika informasi tidak lengkap, jelaskan sebatas yang ada
5. Jika benar-benar tidak ada informasi, katakan: "Tidak ditemukan informasi spesifik tentang hal ini dalam dokumen perusahaan"
6. JANGAN menyarankan untuk menghubungi HRD atau sumber lain
7. Jawab dalam bahasa Indonesia yang jelas dan profesional

JAWABAN:
"""
    
    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=full_context.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120
        )
        
        output = result.stdout.decode("utf-8")
        cleaned_output = clean_response(output)
        
        # TAMBAHKAN SATU REFERENSI DOKUMEN PALING RELEVAN + PDF LINK
        if most_relevant_doc and "tidak ditemukan" not in cleaned_output.lower():
            reference_section = "\n\n**📋 Untuk informasi lebih jelasnya, Anda bisa membacanya pada dokumen:**\n"
            
            # Format: SKEP Nomor : SKEP/18/P/BD/I/2018 tentang "PERATURAN URUSAN DALAM DI LINGKUNGAN PERUSAHAAN" tahun 2018 Tanggal 15 Januari 2018
            doc_ref = most_relevant_doc
            tahun_text = f" tahun {doc_ref['tahun']}" if doc_ref['tahun'] else ""
            tanggal_text = f" Tanggal {doc_ref['tanggal']}" if doc_ref['tanggal'] else ""
            
            reference_section += f"**{doc_ref['jenis_dokumen']} Nomor : {doc_ref['nomor']}** tentang \"{doc_ref['judul']}\"{tahun_text}{tanggal_text}\n"
            
            # Tambahkan PDF link jika ada filename
            if doc_ref['filename']:
                # Path ke PDF di folder static/documents
                pdf_path = f"/static/documents/{doc_ref['filename']}"
                # reference_section += f"\n\n**📎 Download dokumen 📄:** <a href='{pdf_path}' target='_blank' class='pdf-link'>{doc_ref['filename']}</a>"
                reference_section += f"\n\n<div class='pdf-reference'>"
                reference_section += f"<span class='pdf-icon'>📄</span>"
                reference_section += f"<a href='{pdf_path}' target='_blank' class='pdf-link'>{doc_ref['filename']}</a>"
                reference_section += f"</div>"
            
            cleaned_output += reference_section
            
            print(f"📄 Referensi dokumen + PDF link ditambahkan: {doc_ref['jenis_dokumen']} {doc_ref['nomor']}")
            print(f"   PDF Path: {pdf_path if doc_ref['filename'] else 'No file'}")
        
        return cleaned_output
        
    except subprocess.TimeoutExpired:
        return "❌ Timeout: Model mengambil waktu terlalu lama untuk merespons."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ====================================================
# PERSONALIZED RESPONSE HANDLER
# ====================================================
def handle_special_cases(question: str) -> Optional[str]:
    """Handle special cases seperti greeting, thanks, dll."""
    if is_greeting(question):
        greetings = [
            "Halo! Ada yang bisa saya bantu?",
            "Hi! Senang berbicara dengan Anda. Ada pertanyaan tentang perusahaan?",
            "Halo! Silakan tanyakan apa saja tentang kebijakan perusahaan.",
            "Selamat datang! Siap membantu Anda dengan informasi perusahaan."
        ]
        return np.random.choice(greetings)
    
    elif is_thanks(question):
        thanks_responses = [
            "Sama-sama! Senang bisa membantu.",
            "Terima kasih kembali! Kalau ada pertanyaan lagi, saya siap membantu.",
            "Dengan senang hati! Jangan ragu untuk bertanya lagi.",
            "Sama-sama bro! Stay awesome! 😊"
        ]
        return np.random.choice(thanks_responses)
    
    return None

# ====================================================
# SAVE CHAT - ENHANCED
# ====================================================
def save_chat_message(session_id: int, role: str, text: str):
    """Enhanced chat saving dengan NLP metadata"""
    emb = embedder.encode([text])[0].tolist()
    
    # Simpan NLP insights
    metadata = {
        "entities": conversation_context.entities,
        "question_type": conversation_context.question_type,
        "sentiment": conversation_context.sentiment,
        "topic": conversation_context.conversation_topic
    }
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_messages(session_id, role, message_text, embedding, metadata, timestamp)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (session_id, role, text, emb, json.dumps(metadata)))
    conn.commit()
    conn.close()

# ====================================================
# CHAT SESSION - UI SUPPORT (SAME)
# ====================================================
def create_chat(model):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_sessions(session_uuid, user_name, model_name, started_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING id
    """, (str(uuid.uuid4()), "anonymous", model))
    row = cur.fetchone()
    conn.commit()
    return row[0]

def get_chat_sessions():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT cs.id, cs.session_uuid, cs.model_name, cs.started_at,
               COUNT(cm.id) AS message_count
        FROM chat_sessions cs
        LEFT JOIN chat_messages cm ON cm.session_id = cs.id
        GROUP BY cs.id
        ORDER BY cs.started_at DESC
        LIMIT 30
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def get_session_messages(session_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT role, message_text, timestamp, metadata
        FROM chat_messages
        WHERE session_id=%s
        ORDER BY timestamp ASC
    """, (session_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

# ====================================================
# ENHANCED ROUTES
# ====================================================
@app.route("/")
def index():
    sessions = get_chat_sessions()
    models = ["qwen3:8b", "deepseek-r1:8b", "qwen2.5:7b"]
    return render_template("askIndex.html", sessions=sessions, models=models)

@app.route("/chat/<int:session_id>")
def chat_session(session_id):
    sessions = get_chat_sessions()
    models = ["qwen3:8b", "deepseek-r1:8b", "qwen2.5:7b"]
    messages = get_session_messages(session_id)
    current = next((s for s in sessions if s["id"] == session_id), None)
    return render_template("chat.html", sessions=sessions, models=models,
                           current_session=current, messages=messages)

@app.route("/api/new_chat", methods=["POST"])
def new_chat():
    model = request.json["model"]
    session_id = create_chat(model)
    return jsonify({"success": True, "redirect_url": f"/chat/{session_id}"})

@app.route("/api/send_message", methods=["POST"])
def api_send_message():
    data = request.json
    session_id = data["session_id"]
    question = data["message"]
    model = data["model"]

    # Check untuk special cases terlebih dahulu
    special_response = handle_special_cases(question)
    if special_response:
        save_chat_message(session_id, "user", question)
        save_chat_message(session_id, "assistant", special_response)
        return jsonify({"success": True, "answer": special_response})

    save_chat_message(session_id, "user", question)

    # MEMORY INSTRUCTION
    if is_memory_instruction(question):
        save_user_memory(question, question)
        reply = "Siap bro, sudah aku ingat preferensimu!"
        save_chat_message(session_id, "assistant", reply)
        return jsonify({"success": True, "answer": reply})

    # USER CORRECTION
    if is_correction(question):
        save_correction(question, question)
        reply = "Oke bro, koreksi sudah aku simpan dan akan digunakan untuk improvement!"
        save_chat_message(session_id, "assistant", reply)
        return jsonify({"success": True, "answer": reply})

    # SMART CONTEXT DETECTION DENGAN NLP
    print(f"💬 Question: {question}")
    print(f"🔄 Use context: {conversation_context.should_maintain_context(question)}")
    print(f"🔍 NLP Analysis: {conversation_context.get_context_enhanced_prompt()}")

    # GATHER DATA SOURCES dengan enhanced context awareness
    rag = search_rag(question)
    print(f"🔍 RAG results: {len(rag) if rag else 0} results")
    
    # DEBUG: Print RAG content
    if rag:
        print("📄 TOP RAG RESULTS:")
        for i, result in enumerate(rag[:3]):
            print(f"  {i+1}. Similarity: {result.get('similarity', 0):.3f}")
            print(f"     Content: {result.get('content', '')[:150]}...")
    
    # Enhanced source selection berdasarkan question type
    if conversation_context.question_type == 'factual':
        # Untuk factual questions, hanya gunakan RAG
        learn = []
        mem = []
    else:
        # Untuk other questions, consider semua sources
        learn = search_learning(question) if not rag or len(rag) < 2 else []
        mem = get_relevant_user_memory(question) if not rag or len(rag) < 2 else []
    
    dialog = search_dialogue(question)

    # DEBUG: Print semua sources
    print(f"📊 SOURCES - RAG: {len(rag)}, Learning: {len(learn)}, Memory: {len(mem)}, Dialog: {len(dialog)}")

    # ENHANCED ANTI HALU FILTER
    is_possible, source_type = is_corporate_answer_possible(rag, learn, mem, question)
    print(f"🎯 Answer possible: {is_possible}, Source: {source_type}")
    
    if not is_possible:
        answer = "Maaf bro, tidak ada informasi spesifik tentang hal tersebut dalam dokumen perusahaan. Mungkin Anda bisa menanyakan hal lain yang terkait kebijakan atau prosedur perusahaan."
        save_chat_message(session_id, "assistant", answer)
        return jsonify({"success": True, "answer": answer})

    # FINAL ANSWER GENERATION
    mem_text = "\n".join([f"- {m['value']}" for m in mem]) if mem else ""
    learn_text = "\n".join([f"- {l['corrected_answer']}" for l in learn]) if learn else ""
    dialog_text = "\n".join([f"USER: {d['user_text']}\nAI: {d['assistant_text']}" for d in dialog]) if dialog else ""

    answer = ask_ollama(model, mem_text, learn_text, dialog_text, rag, question, source_type)

    # UPDATE CONVERSATION CONTEXT
    conversation_context.update_context(question, answer, rag)
    
    save_chat_message(session_id, "assistant", answer)
    save_dialogue(question, answer)

    return jsonify({"success": True, "answer": answer})

@app.route("/api/switch_model", methods=["POST"])
def switch_model():
    data = request.json
    session_id = data["session_id"]
    new_model = data["model"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE chat_sessions SET model_name=%s WHERE id=%s",
                (new_model, session_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ====================================================
# NEW NLP ENHANCEMENT ROUTES
# ====================================================
@app.route("/api/analyze_question", methods=["POST"])
def analyze_question():
    """API untuk analyze question dengan NLP"""
    data = request.json
    question = data["question"]
    
    # Analyze question
    conversation_context._analyze_question(question)
    
    return jsonify({
        "success": True,
        "analysis": {
            "question_type": conversation_context.question_type,
            "sentiment": conversation_context.sentiment,
            "entities": conversation_context.entities,
            "should_maintain_context": conversation_context.should_maintain_context(question)
        }
    })

@app.route("/api/conversation_insights", methods=["GET"])
def conversation_insights():
    """Get insights tentang current conversation"""
    return jsonify({
        "success": True,
        "insights": {
            "current_topic": conversation_context.conversation_topic,
            "context_history": [{
                "question": ctx["question"],
                "topic": ctx["topic"],
                "timestamp": ctx["timestamp"].isoformat()
            } for ctx in conversation_context.context_history[-3:]],
            "recent_entities": conversation_context.entities
        }
    })

# ====================================================
# RUN SERVER
# ====================================================
if __name__ == "__main__":
    print("🚀 Starting Enhanced RAG Chat System with Advanced NLP...")
    print("🔧 Features: Entity Recognition, Sentiment Analysis, Question Classification")
    print("🔧 Enhanced Context Management, Personalized Responses")
    app.run(host="0.0.0.0", port=5000, debug=True)