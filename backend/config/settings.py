import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database configurations
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = os.getenv("DB_PORT", 5432)
    DB_NAME: str = os.getenv("DB_NAME", "ragdb")
    DB_USER: str = os.getenv("DB_USER", "pindadai")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "Pindad123!")
    
    # Login database configurations
    DB_LOGIN_HOST: str = os.getenv("DB_LOGIN_HOST", "192.168.11.55")
    DB_LOGIN_PORT: int = os.getenv("DB_LOGIN_PORT", 5432)
    DB_LOGIN_NAME: str = os.getenv("DB_LOGIN_NAME", "qa_payroll_db")
    DB_LOGIN_USER: str = os.getenv("DB_LOGIN_USER", "qisthi")
    DB_LOGIN_PASSWORD: str = os.getenv("DB_LOGIN_PASSWORD", "q1sthi")
    
    # Ollama configurations
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
    OLLAMA_GENERATE_URL: str = os.getenv("OLLAMA_GENERATE_URL", "http://localhost:11434/api/generate")
    PRIMARY_MODEL: str = os.getenv("PRIMARY_MODEL", "qwen3:8b")
    VISION_MODEL: str = os.getenv("VISION_MODEL", "qwen3-vl:8b")
    
    # Application settings
    UPLOAD_FOLDER: str = os.getenv("UPLOAD_FOLDER", "./uploads")
    DB_DOC_FOLDER: str = os.getenv("DB_DOC_FOLDER", "./db_doc")
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
    LIMIT: int = int(os.getenv("LIMIT", "10"))
    
    class Config:
        env_file = ".env"


settings = Settings()