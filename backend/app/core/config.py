import os
from pydantic_settings import BaseSettings

# Cari posisi file .env di folder utama (/home/qisthi/pinAi/.env) secara dinamis
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # core
APP_DIR = os.path.dirname(CURRENT_DIR)                  # app
BACKEND_DIR = os.path.dirname(APP_DIR)                  # backend
ROOT_DIR = os.path.dirname(BACKEND_DIR)                  # pinAi
ENV_PATH = os.path.join(ROOT_DIR, ".env")

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "CAKRA_AI"
    DEBUG: bool = True
    
    # 📝 SEMUA DI BAWAH INI DIBACA DARI FILE .ENV (Nilai di kanan cuma fallback jika .env kosong)
    DB_HOST: str = "localhost"
    DB_DATABASE: str = "ragdb"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    
    DB_LOGIN_HOST: str = "localhost"
    DB_LOGIN_DATABASE: str = "hris_db"
    DB_LOGIN_USER: str = "postgres"
    DB_LOGIN_PASSWORD: str = "postgres"
    
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # Roster Tiga Engine Sesuai Tagging Spek Lo, Bolo!
# Ganti bagian roster model di config.py:
    MODEL_ROUTER: str = "qwen2.5:3b-instruct"      # Layer 1 Cognitive Analyzer
    MODEL_GATEWAY: str = "qwen2.5:0.5b"            # Layer 0 Gateway (ringan)
    MODEL_PERSONA: str = "gemma4:12b"              # Layer 2 Executor
    MODEL_VISION: str = "minicpm-v:latest"
    MODEL_EMBEDDING: str = "mxbai-embed-large:latest"
    
    SIMILARITY_THRESHOLD: float = 0.75
    SEARCH_LIMIT: int = 5
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024
    
    class Config:
        # Kunci file .env lo sebagai satu-satunya sumber kebenaran data
        env_file = ENV_PATH
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

print(f"⚙️  [CONFIG] Memuat file environment dari: {ENV_PATH}")
print(f"🔌 [CONFIG] User Terbaca: {settings.DB_USER} | Target DB: {settings.DB_DATABASE}")
print(f"👁️  [CONFIG] Engine Vision Terkunci: {settings.MODEL_VISION}")