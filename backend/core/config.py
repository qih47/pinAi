import os
from typing import Dict, Any

# Konstanta
SIMILARITY_THRESHOLD = 0.7  # Atur sesuai kebutuhan
LIMIT = 10  # Atur sesuai kebutuhan

# DB Configurations
DB_RAG_CONFIG = {
    "host": "localhost",
    "database": "ragdb",
    "user": "pindadai",
    "password": "Pindad123!",
    "port": 5432
}

DB_LOGIN_CONFIG = {
    "host": "192.168.11.55",
    "database": "qa_payroll_db",
    "user": "qisthi",
    "password": "q1sthi",
    "port": 5432
}

# Ollama endpoints
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

# Models
PRIMARY_MODEL = "qwen3:8b"  # 🎯 MODEL UTAMA
VISION_MODEL = "qwen3-vl:8b"  # 🎯 MODEL VISUAL

# Modes
MODE_NORMAL = "normal"
MODE_DOCUMENT = "document"
MODE_SEARCH = "search"

# Upload settings
UPLOAD_FOLDER = "./uploads"
DB_DOC_FOLDER = "./db_doc"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt", "docx", "pptx", "xlsx"}

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DB_DOC_FOLDER, exist_ok=True)