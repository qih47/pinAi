"""
CAKRA AI - API Gateway
Runs on port 8000.
Acts as a single entry point, routing all requests to:
  - /api/chat, /api/health, /api/documents, /api/keys,
    /api/training, /api/synthetic, /api/corporate,
    /api/notifications, /api/nextcloud, /api/voice,
    /api/user  →  Chat Service (port 8001)
  - /api/analytics, /api/admin, /audit-logs  →  Analytics Service (port 8002)
  - /api/auth                               →  Auth Service (port 8003)
  - /db_doc, /uploads, /accounts, /file_peraturan  →  Chat Service (port 8001)
"""
import sys
import os
import logging

CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = CURRENT_FILE_DIR

for path in [ROOT_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

from backend.app.core.logging_setup import setup_root_logger
from backend.app.utils.request_logging import setup_request_id_logging

setup_root_logger()
setup_request_id_logging()
logger = logging.getLogger("CAKRA_GATEWAY")

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio

# ─── Service Registry ─────────────────────────────────────────────────────────
CHAT_SERVICE_URL    = os.getenv("CHAT_SERVICE_URL",      "http://localhost:8001")
ANALYTICS_SERVICE_URL = os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8002")
AUTH_SERVICE_URL    = os.getenv("AUTH_SERVICE_URL",      "http://localhost:8003")

# Prefix routing table (matched in ORDER — more specific first)
ROUTE_MAP = [
    # Auth Service
    ("/api/auth",        AUTH_SERVICE_URL),
    # Analytics Service
    ("/api/analytics",   ANALYTICS_SERVICE_URL),
    ("/api/admin",       ANALYTICS_SERVICE_URL),
    ("/api/audit-logs",  ANALYTICS_SERVICE_URL),
    # Chat Service — everything else under /api
    ("/api",             CHAT_SERVICE_URL),
    # Static files served by Chat Service
    ("/db_doc",          CHAT_SERVICE_URL),
    ("/uploads",         CHAT_SERVICE_URL),
    ("/accounts",        CHAT_SERVICE_URL),
    ("/file_peraturan",  CHAT_SERVICE_URL),
]

SSE_PATHS = [
    "/api/analytics/logs/stream",
    "/api/analytics/metrics/stream",
    "/api/chat/stream",
]

# ─── Shared httpx Client (persistent connection pool) ────────────────────────
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(180.0, connect=10.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=True,
        )
    return _http_client


def resolve_target(path: str) -> str:
    """Determine which backend service URL to route the request to."""
    for prefix, service_url in ROUTE_MAP:
        if path.startswith(prefix):
            return service_url
    # Fallback → Chat Service
    return CHAT_SERVICE_URL


def is_sse_path(path: str) -> bool:
    """Check if the path is a Server-Sent Events (SSE) endpoint."""
    return any(path.startswith(sse) for sse in SSE_PATHS)


app = FastAPI(
    title="CAKRA AI - API Gateway",
    description="Unified API Gateway — routes requests to microservices",
    version="1.0.0",
    docs_url="/gateway-docs",
    redoc_url=None,
)

# ─── CORS (Gateway is the public face — FE talks only to :8000) ──────────────
origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://192.168.11.80:5173",
    "http://192.168.11.80:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Universal Proxy Handler ───────────────────────────────────────────────────
@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def gateway_proxy(full_path: str, request: Request):
    path = "/" + full_path
    target_base = resolve_target(path)
    target_url = f"{target_base}{path}"

    # Forward query params
    if request.query_params:
        target_url += "?" + str(request.query_params)

    # Build forwarded headers (strip host, add X-Forwarded-For)
    headers = dict(request.headers)
    headers.pop("host", None)
    headers["x-forwarded-for"] = request.client.host if request.client else "unknown"
    headers["x-forwarded-proto"] = "http"

    body = await request.body()

    logger.info(f"[GATEWAY] {request.method} {path}  →  {target_base}")

    # ── SSE / Streaming ───────────────────────────────────────────────────────
    if is_sse_path(path) or "text/event-stream" in request.headers.get("accept", ""):
        async def stream_generator():
            try:
                async with get_http_client().stream(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body,
                ) as upstream_response:
                    async for chunk in upstream_response.aiter_bytes():
                        yield chunk
            except Exception as e:
                logger.error(f"[GATEWAY] SSE stream error: {e}")
                yield b"data: {\"error\": \"Service unavailable\"}\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Regular Request ───────────────────────────────────────────────────────
    try:
        client = get_http_client()
        upstream_response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
        )
        # Filter hop-by-hop headers
        excluded = {"transfer-encoding", "connection", "keep-alive", "upgrade"}
        response_headers = {
            k: v for k, v in upstream_response.headers.items()
            if k.lower() not in excluded
        }
        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=response_headers,
            media_type=upstream_response.headers.get("content-type"),
        )
    except httpx.ConnectError:
        logger.error(f"[GATEWAY] Cannot connect to {target_base}")
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable. Backend service at {target_base} is not responding."
        )
    except httpx.TimeoutException:
        logger.error(f"[GATEWAY] Timeout proxying to {target_base}")
        raise HTTPException(status_code=504, detail="Gateway timeout.")
    except Exception as e:
        logger.error(f"[GATEWAY] Unexpected error: {e}")
        raise HTTPException(status_code=502, detail=f"Bad gateway: {str(e)}")


@app.on_event("startup")
async def startup():
    logger.info("=" * 60)
    logger.info("🚀 [GATEWAY] CAKRA AI API Gateway starting on port 8000")
    logger.info(f"   Chat Service    → {CHAT_SERVICE_URL}")
    logger.info(f"   Analytics Svc   → {ANALYTICS_SERVICE_URL}")
    logger.info(f"   Auth Service    → {AUTH_SERVICE_URL}")
    logger.info("=" * 60)
    get_http_client()  # warm up the client


@app.on_event("shutdown")
async def shutdown():
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
    logger.info("🛑 [GATEWAY] Shutdown complete.")


@app.get("/gateway-health", tags=["Gateway"])
async def gateway_health():
    """Check connectivity to all downstream services."""
    results = {}
    client = get_http_client()
    for name, url in [("chat", CHAT_SERVICE_URL), ("analytics", ANALYTICS_SERVICE_URL), ("auth", AUTH_SERVICE_URL)]:
        try:
            r = await client.get(f"{url}/", timeout=3.0)
            results[name] = {"status": "online", "code": r.status_code}
        except Exception as e:
            results[name] = {"status": "offline", "error": str(e)}
    return {"gateway": "online", "services": results}


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 [GATEWAY] Starting API Gateway on port 8000...")
    uvicorn.run("run_gateway:app", host="0.0.0.0", port=8000, reload=False)
