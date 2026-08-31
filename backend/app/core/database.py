import asyncpg
import aiomysql
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_DATABASE")

# Global connection pools
db_pool = None
hris_pool = None
peraturan_pool = None

async def init_db_pool():
    """Inisialisasi dual-database connection pools saat startup"""
    global db_pool, hris_pool, peraturan_pool
    try:
        # 1. Main Database Pool (ragdb)
        db_pool = await asyncpg.create_pool(
            host=settings.DB_HOST,
            database=settings.DB_DATABASE,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            min_size=5,
            max_size=20,
            command_timeout=60.0,
        )

        # 2. HRIS Database Pool (Login DB)
        hris_pool = await asyncpg.create_pool(
            host=settings.DB_LOGIN_HOST,
            database=settings.DB_LOGIN_DATABASE,
            user=settings.DB_LOGIN_USER,
            password=settings.DB_LOGIN_PASSWORD,
            min_size=3,
            max_size=10,
            command_timeout=60.0,
        )

        # 3. Peraturan Database Pool (MySQL)
        try:
            peraturan_pool = await aiomysql.create_pool(
                host=settings.DB_PERATURAN_HOST,
                db=settings.DB_PERATURAN_DATABASE,
                user=settings.DB_PERATURAN_USER,
                password=settings.DB_PERATURAN_PASSWORD,
                minsize=3,
                maxsize=10,
                autocommit=True
            )
        except Exception as e:
            logger.error(f"[DB_CONNECTION_POOL_ERROR] Failed to initialize Peraturan DB pool: {e}")
            peraturan_pool = None

        async with db_pool.acquire() as conn:
            try:
                await _create_llm_thinking_audit_table(conn)
                await _update_chat_sessions_continuation_column(conn)
                await _update_chat_messages_sources_column(conn)
                await _update_chat_sessions_settings_column(conn)
                await _update_chat_messages_feedback_column(conn)
                await _update_chat_messages_metadata_column(conn)
                await _create_security_logs_table(conn)
                await _create_system_prompts_table(conn)
                await _create_api_keys_table(conn)
                await _create_training_jobs_table(conn)
                await _create_user_settings_table(conn)
                await _create_user_integrations_table(conn)
            except asyncpg.exceptions.InsufficientPrivilegeError as e:
                logger.warning(f"⚠️ [DB_MIGRATION] Izin ditolak untuk memodifikasi schema public. Minta admin untuk jalankan DDL secara manual: {e}")
            except Exception as e:
                logger.warning(f"⚠️ [DB_MIGRATION] Gagal menjalankan migrasi schema otomatis: {e}")

        logger.info("[DB_CONNECTION_POOL_INIT] Triple-database pools (ragdb, hris, peraturan) initialized successfully.")
    except Exception as e:
        logger.error(f"[DB_CONNECTION_POOL_ERROR] Failed to initialize database pools: {e}")
        raise e

async def close_db_pool():
    """Menutup pool koneksi saat aplikasi shutdown"""
    global db_pool, hris_pool, peraturan_pool
    if db_pool:
        await db_pool.close()
    if hris_pool:
        await hris_pool.close()
    if peraturan_pool:
        peraturan_pool.close()
        await peraturan_pool.wait_closed()
    logger.info("🛑 [DATABASE] All database connection pools closed clean.")

@asynccontextmanager
async def get_db():
    """Get main database (ragdb) connection context manager"""
    global db_pool
    if db_pool is None:
        logging.error("Database pool (db_pool) is None. Pastikan init_db_pool() sudah jalan.")
        raise RuntimeError("Main database pool not initialized")
    
    async with db_pool.acquire() as connection:
        yield connection

@asynccontextmanager
async def get_hris_db():
    """Get HRIS database connection context manager"""
    global hris_pool
    if hris_pool is None:
        logging.error("HRIS pool (hris_pool) is None. Pastikan init_db_pool() sudah jalan.")
        raise RuntimeError("HRIS database pool not initialized")
    
    async with hris_pool.acquire() as connection:
        yield connection

@asynccontextmanager
async def get_peraturan_db():
    """Get Peraturan database connection context manager"""
    global peraturan_pool
    if peraturan_pool is None:
        logging.error("Peraturan pool (peraturan_pool) is None. Pastikan init_db_pool() sudah jalan.")
        raise RuntimeError("Peraturan database pool not initialized")
    
    async with peraturan_pool.acquire() as connection:
        yield connection

def embedding_to_pgvector_str(embedding) -> str:
    """Convert embedding list/numpy array to PostgreSQL vector format string"""
    import numpy as np
    if isinstance(embedding, list):
        embedding = np.array(embedding)
    return f"[{','.join(f'{val:.8f}' for val in embedding)}]"

async def _create_llm_thinking_audit_table(conn):
    """
    Create audit table for thinking content & RAG decisions (compliance).
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_thinking_audit (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_uuid UUID NOT NULL REFERENCES chat_sessions(session_uuid),
            message_id UUID,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
            
            -- Raw thinking content
            thinking_content TEXT,
            thinking_token_estimate INT,
            
            -- Phase 1 routing decision
            routing_decision JSONB,
            
            -- RAG execution
            rag_queries TEXT[],
            rag_results_count INT,
            rag_source_ids TEXT[],
            rag_fetch_duration_ms INT,
            
            -- Final response
            response_text TEXT,
            response_token_count INT,
            
            -- Continuation metadata
            continuation_attempts INT,
            
            CONSTRAINT session_audit_fk 
                FOREIGN KEY (session_uuid) REFERENCES chat_sessions(session_uuid)
        );
        
        CREATE INDEX IF NOT EXISTS idx_thinking_audit_session 
        ON llm_thinking_audit(session_uuid);
        
        CREATE INDEX IF NOT EXISTS idx_thinking_audit_timestamp 
        ON llm_thinking_audit(timestamp DESC);
    """)

async def _update_chat_sessions_continuation_column(conn):
    """
    Memastikan kolom continuation_state (JSONB) tersedia pada chat_sessions
    untuk arsitektur Token-Level Continuation.
    """
    await conn.execute("""
        ALTER TABLE chat_sessions 
        ADD COLUMN IF NOT EXISTS continuation_state JSONB DEFAULT NULL;
        
        CREATE INDEX IF NOT EXISTS idx_continuation_state 
        ON chat_sessions USING GIN(continuation_state);
    """)

async def _update_chat_sessions_settings_column(conn):
    """
    Memastikan kolom settings (JSONB) tersedia pada chat_sessions
    untuk arsitektur Token-Level Continuation.
    """
    await conn.execute("""
        ALTER TABLE chat_sessions 
        ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT NULL;
    """)

async def _update_chat_messages_feedback_column(conn):
    """
    Memastikan kolom feedback (JSONB) tersedia pada chat_messages
    untuk menampung status good/bad response dan rating tambahan.
    """
    await conn.execute("""
        ALTER TABLE chat_messages 
        ADD COLUMN IF NOT EXISTS feedback JSONB DEFAULT NULL;
    """)


async def _update_chat_messages_sources_column(conn):
    """
    Memastikan kolom sources (JSONB) tersedia pada chat_messages
    untuk menampung RAG Metrics / Source Citations yang tahan reload.
    """
    await conn.execute("""
        ALTER TABLE chat_messages 
        ADD COLUMN IF NOT EXISTS sources JSONB;
    """)

async def _update_chat_messages_metadata_column(conn):
    """
    Memastikan kolom metadata (JSONB) tersedia pada chat_messages
    untuk menyimpan path dari file-file artifacts yang di-generate.
    """
    await conn.execute("""
        ALTER TABLE chat_messages 
        ADD COLUMN IF NOT EXISTS metadata JSONB;
    """)

async def _create_security_logs_table(conn):
    """
    Create audit table for security anomalies (SOC).
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS security_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
            event_type VARCHAR(50) NOT NULL,
            npp VARCHAR(50),
            ip_address VARCHAR(50),
            description TEXT,
            severity VARCHAR(20) DEFAULT 'MEDIUM'
        );
        CREATE INDEX IF NOT EXISTS idx_security_logs_timestamp ON security_logs(timestamp DESC);
    """)

async def _create_system_prompts_table(conn):
    """
    Create table for Dynamic Prompt Engineering Studio (Opsi 3).
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS system_prompts (
            name VARCHAR(100) PRIMARY KEY,
            template TEXT NOT NULL,
            description TEXT,
            version INT DEFAULT 1,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

async def _create_api_keys_table(conn):
    """
    Create table for API Key Management (Server-to-Server Auth).
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key_hash VARCHAR(255) NOT NULL UNIQUE,
            key_prefix VARCHAR(20) NOT NULL,
            app_name VARCHAR(100) NOT NULL,
            owner_npp VARCHAR(50) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            total_requests INT DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_used_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
    """)

async def _create_training_jobs_table(conn):
    """
    Create table for Deep Learning / Ingestion Background Jobs.
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS training_jobs (
            job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            dokumen_id INT NOT NULL,
            tipe_training VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
            progress INT DEFAULT 0,
            logs TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_training_jobs_status ON training_jobs(status);
        CREATE INDEX IF NOT EXISTS idx_training_jobs_dokumen ON training_jobs(dokumen_id);
    """)

async def _create_user_settings_table(conn):
    """
    Create table for storing user UI settings (like TTS Voice/Speed) persistently across devices.
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            npp VARCHAR(50) PRIMARY KEY REFERENCES users(npp) ON DELETE CASCADE,
            settings JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

async def _create_user_integrations_table(conn):
    """
    Create table for storing user integrations (Smart Mail & Nextcloud credentials).
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_integrations (
            npp VARCHAR(50) PRIMARY KEY REFERENCES users(npp) ON DELETE CASCADE,
            mail_username VARCHAR(255),
            mail_password VARCHAR(255),
            cloud_username VARCHAR(255),
            cloud_password VARCHAR(255),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

async def _update_users_onboarding_columns(conn):
    """
    Ensure users table has onboarding and preference columns.
    """
    await conn.execute("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS is_onboarded BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(10) DEFAULT 'id',
        ADD COLUMN IF NOT EXISTS theme_preference VARCHAR(20) DEFAULT 'dark',
        ADD COLUMN IF NOT EXISTS communication_style VARCHAR(30) DEFAULT 'formal_saya_anda',
        ADD COLUMN IF NOT EXISTS preferred_name VARCHAR(100);
    """)

async def get_continuation_state(session_uuid: str) -> dict:
    """Retrieve continuation state from chat_sessions."""
    pool = get_db_pool()
    if not pool: return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT continuation_state FROM chat_sessions WHERE session_uuid = $1", session_uuid)
            if row and row['continuation_state']:
                import json
                return json.loads(row['continuation_state']) if isinstance(row['continuation_state'], str) else row['continuation_state']
    except Exception as e:
        logger.warning(f"[DB] Failed to load continuation state: {e}")
    return None

async def save_continuation_state(session_uuid: str, state_data: dict) -> None:
    """Save or clear continuation state in chat_sessions."""
    pool = get_db_pool()
    if not pool: return
    try:
        import json
        state_json = json.dumps(state_data) if state_data else None
        async with pool.acquire() as conn:
            await conn.execute("UPDATE chat_sessions SET continuation_state = $1 WHERE session_uuid = $2", state_json, session_uuid)
    except Exception as e:
        logger.warning(f"[DB] Failed to save continuation state: {e}")

def get_db_pool():
    """
    🔥 JEMBATAN BERSAMA: Mengembalikan objek db_pool global 
    agar kompatibel dengan modul token_continuation_layer dkk.
    """
    global db_pool
    if db_pool is None:
        logger.warning("⚠️ [DB] db_pool diakses sebelum init_db_pool() selesai dijalankan.")
    return db_pool