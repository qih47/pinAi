"""
B9-B13 Integration Guide
Menunjukkan cara menggunakan semua optimization utilities di sistem.
"""

# ============================================================================

# B9 INTEGRATION: Query Embedding Caching

# ============================================================================

# Di vector_service.py atau rag_service.py, modify generate_embedding():

"""
from backend.app.utils.embedding_cache import get_embedding_cache

async def generate_embedding(query: str) -> List[float]:
'''Generate embedding dengan LRU cache.'''

    cache = get_embedding_cache()

    # Check cache first
    cached_embedding = cache.get(query)
    if cached_embedding:
        logger.debug(f"✅ Embedding hit from cache for: {query[:50]}")
        return cached_embedding

    # Generate if not cached
    embedding = await ollama_embed(query)

    # Store in cache
    cache.put(query, embedding)
    logger.debug(f"✅ Embedding cached for: {query[:50]}")

    return embedding

"""

# ============================================================================

# B10 INTEGRATION: Session Token Expiry

# ============================================================================

# Di auth.py, saat login atau create session:

"""
from backend.app.utils.token_expiry import get_token_expiry_time, extend_session_expiry

async def login_endpoint(npp: str, password: str, db_pool):
'''Login dengan auto-expiry token.'''

    # ... validate credentials ...

    # Create session dengan expiry
    expires_at = get_token_expiry_time(hours=8)

    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO session_login (npp, token, expires_at, is_active)
            VALUES ($1, $2, $3, TRUE)
        ''', npp, token, expires_at)

    return {"token": token, "expires_at": expires_at}

# Di chat.py atau sebelum processing request:

async def authenticate_user(npp: str, token: str, db_pool):
'''Validate token dan extend expiry jika valid.'''

    # Validate
    is_valid = await validate_token_expiry(npp, token)

    if is_valid:
        # Extend expiry (keep session alive jika user aktif)
        await extend_session_expiry(npp, extension_hours=8)

    return is_valid

"""

# ============================================================================

# B11 INTEGRATION: Request ID Tracing

# ============================================================================

# Di main.py, saat startup:

"""
from fastapi import FastAPI
from backend.app.utils.request_logging import RequestIDLoggingMiddleware, setup_request_id_logging

app = FastAPI()

# Setup logging dengan request ID

setup_request_id_logging()

# Add middleware

app.add_middleware(RequestIDLoggingMiddleware)

# Sekarang semua logger calls otomatis include request ID

# Log akan tampak seperti: [req-abc123] Processing user request

"""

# ============================================================================

# B12 INTEGRATION: Auto-Title Generation

# ============================================================================

# Di chat.py, setelah streaming selesai:

"""
from backend.app.utils.title_generator import enqueue_title_generation

async def chat_stream_endpoint(payload: ChatStreamRequest, db_pool):
'''Chat endpoint dengan async title generation.'''

    session_uuid = payload.session_uuid
    user_message = payload.messages[0].content

    # Stream response
    first_response_chunk = ""
    async for chunk in stream_pipeline(payload):
        first_response_chunk += chunk['chunk']
        yield chunk

    # Enqueue title generation (non-blocking, runs in background)
    await enqueue_title_generation(
        session_uuid=session_uuid,
        user_message=user_message,
        first_response=first_response_chunk[:200],
        db_pool=db_pool
    )

"""

# ============================================================================

# B13 INTEGRATION: HNSW Vector Index

# ============================================================================

# Di main.py, saat startup:

"""
from backend.app.utils.vector_index import setup_hnsw_index, optimize_vector_search

@app.on_event("startup")
async def startup_event():
'''Setup vector indexes saat startup.'''

    # Create HNSW index jika belum ada
    await setup_hnsw_index()

    # Run optimization
    stats = await optimize_vector_search()

    print(f"✅ Vector search optimization completed: {stats}")

"""

# ============================================================================

# COMPLETE STARTUP SEQUENCE (main.py)

# ============================================================================

"""
from fastapi import FastAPI
from backend.app.utils.request_logging import RequestIDLoggingMiddleware, setup_request_id_logging
from backend.app.utils.token_expiry import setup_token_expiry_migration, cleanup_expired_sessions
from backend.app.utils.vector_index import setup_hnsw_index, optimize_vector_search
import asyncio

app = FastAPI(title="CAKRA AI")

# ===== STARTUP =====

@app.on_event("startup")
async def startup():
'''Setup all B9-B13 optimizations.'''

    print("🚀 [STARTUP] Initializing CAKRA AI backend...")

    # B11: Request ID Logging
    setup_request_id_logging()
    app.add_middleware(RequestIDLoggingMiddleware)
    print("✅ [B11] Request ID logging initialized")

    # B10: Token Expiry
    await setup_token_expiry_migration()
    print("✅ [B10] Token expiry migration completed")

    # B13: HNSW Index
    await setup_hnsw_index()
    await optimize_vector_search()
    print("✅ [B13] Vector search optimization completed")

    # B9: Embedding Cache (no setup needed, lazy-loaded)
    print("✅ [B9] Embedding cache ready")

    # B12: Auto-Title (no setup needed, background task)
    print("✅ [B12] Title generation ready")

    print("✅ [STARTUP] All optimizations initialized successfully!")

# ===== PERIODIC CLEANUP =====

@app.on_event("startup")
async def start_cleanup_task():
'''Start background cleanup task untuk expired sessions.'''

    async def cleanup_loop():
        while True:
            try:
                await cleanup_expired_sessions()
                await asyncio.sleep(1800)  # 30 minutes
            except Exception as e:
                print(f"❌ [CLEANUP] Error: {e}")
                await asyncio.sleep(60)

    asyncio.create_task(cleanup_loop())

"""

print("✅ All B9-B13 integration patterns documented")
