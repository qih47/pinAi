import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Pindad AI Chat API"
    VERSION: str = "1.0.0"
    
    # Database configurations
    LOCAL_DB_HOST: str = os.getenv("LOCAL_DB_HOST", "localhost")
    LOCAL_DB_NAME: str = os.getenv("LOCAL_DB_NAME", "ragdb")
    LOCAL_DB_USER: str = os.getenv("LOCAL_DB_USER", "pindadai")
    LOCAL_DB_PASSWORD: str = os.getenv("LOCAL_DB_PASSWORD", "Pindad123!")
    
    LOGIN_DB_HOST: str = os.getenv("LOGIN_DB_HOST", "192.168.11.55")
    LOGIN_DB_NAME: str = os.getenv("LOGIN_DB_NAME", "qa_payroll_db")
    LOGIN_DB_USER: str = os.getenv("LOGIN_DB_USER", "qisthi")
    LOGIN_DB_PASSWORD: str = os.getenv("LOGIN_DB_PASSWORD", "q1sthi")
    
    # Ollama configurations
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
    OLLAMA_GENERATE_URL: str = os.getenv("OLLAMA_GENERATE_URL", "http://localhost:11434/api/generate")
    
    # Model configurations
    PRIMARY_MODEL: str = os.getenv("PRIMARY_MODEL", "qwen3:8b")
    VISION_MODEL: str = os.getenv("VISION_MODEL", "qwen3-vl:8b")
    
    # Similarity configurations
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
    LIMIT: int = int(os.getenv("LIMIT", "10"))
    
    # Upload configurations
    UPLOAD_FOLDER: str = os.getenv("UPLOAD_FOLDER", "./uploads")
    DB_DOC_FOLDER: str = os.getenv("DB_DOC_FOLDER", "./db_doc")
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", "16777216"))  # 16MB in bytes
    
    class Config:
        env_file = ".env"

settings = Settings()