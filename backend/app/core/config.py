import os
import logging
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CURRENT_DIR)
BACKEND_DIR = os.path.dirname(APP_DIR)
ROOT_DIR = os.path.dirname(BACKEND_DIR)

ENV_PATH = os.path.join(BACKEND_DIR, ".env")
if not os.path.exists(ENV_PATH):
    ENV_PATH = os.path.join(ROOT_DIR, ".env")


class Settings(BaseSettings):
    APP_NAME: str = "CAKRA_AI"
    DEBUG: bool = True

    DB_HOST: str = "localhost"
    DB_DATABASE: str = "ragdb"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    DB_LOGIN_HOST: str = "localhost"
    DB_LOGIN_DATABASE: str = "hris_db"
    DB_LOGIN_USER: str = "postgres"
    DB_LOGIN_PASSWORD: str = "postgres"

    OLLAMA_BASE_URL: str = "http://localhost:11434"

    MODEL_PERSONA: str = "gemma4:12b"       # Satu-satunya LLM — Gemma4 Agentic Engine
    MODEL_VISION: str = "minicpm-v:latest"   # Vision/OCR untuk attachment PDF & image
    MODEL_EMBEDDING: str = "mxbai-embed-large:latest"  # Embedding untuk RAG

    SIMILARITY_THRESHOLD: float = 0.75
    SEARCH_LIMIT: int = 5
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024

    BYPASS_ACCOUNT_ENABLED: bool = False
    BYPASS_ACCOUNT_NPP: str = "99999"
    BYPASS_ACCOUNT_PASSWORD_HASH: str = ""

    # ============================================================================
    # GEMMA4 TOKEN-LEVEL CONTINUATION FEATURE
    # ============================================================================

    ENABLE_TOKEN_CONTINUATION: bool = True
    ENABLE_MULTI_HOP_RAG: bool = True
    ENABLE_CHITCHAT_FAST_PATH: bool = True

    RAW_PROMPT_MAX_TOKENS: int = 32000
    THINKING_DEPTH_THRESHOLD: int = 500
    CHANNEL_MARKER_TOKEN: str = "<channel|>"
    CHANNEL_MARKER_STOP_SEQUENCES: list = ["<channel|>", "\n\n"]

    RAG_FETCH_TIMEOUT_MS: int = 15000
    CONTINUATION_CALL_TIMEOUT_MS: int = 60000
    OLLAMA_GENERATE_TIMEOUT_S: float = 180.0

    OLLAMA_GENERATE_POOL_SIZE: int = 10
    OLLAMA_GENERATE_MAX_LIFETIME_S: int = 300

    AUDIT_THINKING_CONTENT: bool = True
    AUDIT_RAG_DECISIONS: bool = True

    LOG_RAW_PROMPTS: bool = False

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
ENABLE_TOKEN_CONTINUATION = settings.ENABLE_TOKEN_CONTINUATION

logger = logging.getLogger("CAKRA_CONFIG")

print("==================================================================", flush=True)
print(f"📁 [DEBUG_ENV] Target file path lookup: {ENV_PATH}", flush=True)

if os.path.exists(ENV_PATH):
    print("✅ [DEBUG_ENV] Physical status: File .env successfully detected!", flush=True)
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            active_lines = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
        print(f"📝 [DEBUG_ENV] Loaded {len(active_lines)} active configuration lines from file.", flush=True)
    except Exception as e:
        print(f"❌ [DEBUG_ENV] Failed reading raw .env data contents: {e}", flush=True)
else:
    print("❌ [DEBUG_ENV] Physical status: File .env NOT found! Running completely on built-in fallback values.", flush=True)

print("------------------------------------------------------------------", flush=True)
print("📊 [ACTIVE RUNTIME OLLAMA MODELS]:", flush=True)
print(f"   • GEMMA4 AGENTIC  : {settings.MODEL_PERSONA}", flush=True)
print(f"   • VISION (MiniCPM): {settings.MODEL_VISION}", flush=True)
print(f"   • EMBEDDING       : {settings.MODEL_EMBEDDING}", flush=True)
print("   (Layer 0 Gateway & Layer 1 Router deprecated — unified Gemma4 engine)", flush=True)
print("------------------------------------------------------------------", flush=True)
print(f"🔌 [CONFIG] Database User: {settings.DB_USER} | Target Database: {settings.DB_DATABASE}", flush=True)
print("==================================================================", flush=True)