import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database Configuration
    db_host: str = "localhost"
    db_database: str = "ragdb"
    db_user: str = "pindadai"
    db_password: str = "Pindad123!"
    
    # HRIS Database
    db_login_host: str = "192.168.11.55"
    db_login_database: str = "qa_payroll_db"
    db_login_user: str = "qisthi"
    db_login_password: str = "q1sthi"
    
    # Ollama Configuration
    ollama_url: str = "http://localhost:11434/api/chat"
    ollama_generate_url: str = "http://localhost:11434/api/generate"
    
    # Model Configuration
    primary_model: str = "qwen3:8b"
    vision_model: str = "qwen3-vl:8b"
    
    # File Paths
    upload_folder: str = "./uploads"
    db_doc_folder: str = "./db_doc"
    
    # Application Settings
    allowed_extensions: set = {"pdf", "png", "jpg", "jpeg", "txt", "docx", "pptx", "xlsx"}
    max_content_length: int = 16 * 1024 * 1024
    similarity_threshold: float = 0.7
    search_limit: int = 10
    
    # CORS
    cors_origins: list = ["http://192.168.11.80:5173", "http://localhost:5173"]
    
    # Modes
    mode_normal: str = "normal"
    mode_document: str = "document"
    mode_search: str = "search"

settings = Settings()

# Ensure directories exist
os.makedirs(settings.upload_folder, exist_ok=True)
os.makedirs(settings.db_doc_folder, exist_ok=True)