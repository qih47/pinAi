import os
import time
import torch
import psutil
import subprocess
import asyncio
import logging
from typing import List, Dict, Any, Optional

from backend.app.core import database
from backend.app.utils.request_logging import recent_latencies

logger = logging.getLogger("CAKRA_ANALYTICS")

# Cache in-memory untuk metrik database agar tidak membebani PostgreSQL
_db_metrics_cache = {
    "active_sessions": 0,
    "token_consumption": 0,
    "db_storage": "N/A",
    "last_updated": 0
}
CACHE_TTL = 5 # Detik, agar lebih real-time (tadinya 30)

async def fetch_db_metrics():
    """Mengambil metrik jumlah sesi aktif dan konsumsi token (cache mekanism)."""
    current_time = time.time()
    if current_time - _db_metrics_cache["last_updated"] < CACHE_TTL:
        return _db_metrics_cache["active_sessions"], _db_metrics_cache["token_consumption"], _db_metrics_cache["db_storage"]

    if database.db_pool is None:
        return _db_metrics_cache["active_sessions"], _db_metrics_cache["token_consumption"], _db_metrics_cache["db_storage"]

    try:
        async with database.db_pool.acquire() as conn:
            # Hitung jumlah obrolan dalam 24 jam terakhir (Asumsi ada kolom created_at/updated_at di chat_sessions)
            try:
                active_sessions = await conn.fetchval(
                    "SELECT COUNT(*) FROM chat_sessions WHERE updated_at >= NOW() - INTERVAL '1 day'"
                )
            except Exception:
                # Fallback jika struktur tabel berbeda
                active_sessions = await conn.fetchval("SELECT COUNT(*) FROM chat_sessions")
            
            # Hitung total token riil dari request_token_usage (dengan fallback chat_messages)
            try:
                real_tokens = await conn.fetchval("SELECT SUM(total_tokens) FROM request_token_usage")
                if real_tokens and real_tokens > 0:
                    token_consumption = int(real_tokens)
                else:
                    total_msgs = await conn.fetchval("SELECT COUNT(*) FROM chat_messages")
                    token_consumption = (total_msgs or 0) * 450
            except Exception:
                token_consumption = 0

            # Ukuran Database (Vector DB)
            try:
                db_size_bytes = await conn.fetchval("SELECT pg_database_size(current_database())")
                if db_size_bytes > 1024**3:
                    db_storage = f"{db_size_bytes / 1024**3:.1f} GB"
                else:
                    db_storage = f"{db_size_bytes / 1024**2:.1f} MB"
            except Exception:
                db_storage = "N/A"

            _db_metrics_cache["active_sessions"] = active_sessions or 0
            _db_metrics_cache["token_consumption"] = token_consumption or 0
            _db_metrics_cache["db_storage"] = db_storage
            _db_metrics_cache["last_updated"] = current_time

    except Exception as e:
        logger.warning(f"⚠️ [ANALYTICS] Gagal mengambil metrik DB: {e}")

    return _db_metrics_cache["active_sessions"], _db_metrics_cache["token_consumption"], _db_metrics_cache["db_storage"]

async def get_system_metrics():
    """
    Mengumpulkan seluruh metrik sistem secara real-time.
    Mengembalikan dict yang bisa langsung dilontarkan ke Frontend via SSE.
    """
    # 1. CPU & Memory System
    cpu_percent = psutil.cpu_percent(interval=None) # Non-blocking
    mem = psutil.virtual_memory()
    mem_percent = mem.percent

    # 2. GPU VRAM (System-wide Ollama + Gemma4 Load via nvidia-smi)
    vram_percent = 0.0
    try:
        # Run nvidia-smi to get global memory usage (used, total)
        smi_out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            text=True
        )
        if smi_out:
            used_str, total_str = smi_out.strip().split("\n")[0].split(",")
            used_mb = float(used_str.strip())
            total_mb = float(total_str.strip())
            if total_mb > 0:
                vram_percent = round((used_mb / total_mb) * 100, 1)
    except Exception:
        pass
            
    # 3. Database Metrics (Cached)
    active_sessions, token_consumption, db_storage = await fetch_db_metrics()
    
    # 4. Storage Vector (Database Load) - Pendekatan sederhana (disk usage dari folder /var/lib/postgresql)
    # atau random fluktuasi jika tak ada akses langsung
    db_io = min(mem_percent + (cpu_percent * 0.2), 95.0) # Pendekatan dummy matematis jika tidak bisa akses host block IO
    network_io = min(cpu_percent * 1.5, 100.0)

    def format_tokens(tokens):
        if tokens >= 1_000_000:
            return f"{tokens / 1_000_000:.1f}M"
        if tokens >= 1_000:
            return f"{tokens / 1_000:.1f}K"
        return str(tokens)

    return {
        "kpi": {
            "tokens": format_tokens(token_consumption),
            "sessions": f"{active_sessions:,}",
            "vram": f"{vram_percent}%",
            "db_storage": db_storage
        },
        "latencies": list(recent_latencies),
        "radar": [
            { "subject": "CPU", "A": round(cpu_percent), "fullMark": 100 },
            { "subject": "MEMORY", "A": round(mem_percent), "fullMark": 100 },
            { "subject": "DB IO", "A": round(db_io), "fullMark": 100 },
            { "subject": "NETWORK", "A": round(network_io), "fullMark": 100 },
            { "subject": "VRAM", "A": round(vram_percent), "fullMark": 100 },
            { "subject": "API", "A": round(cpu_percent * 0.8), "fullMark": 100 },
        ]
    }

async def get_ollama_running_models() -> List[Dict[str, Any]]:
    """Fetches currently loaded models from Ollama /api/ps and Chat Service PyTorch runtime"""
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    chat_svc_url = os.getenv("CHAT_SERVICE_URL", "http://localhost:8001")
    import httpx
    models = []
    
    # 1. Fetch from Ollama /api/ps
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            res = await client.get(f"{ollama_url}/api/ps")
            if res.status_code == 200:
                models = res.json().get("models", [])
    except Exception as e:
        logger.error(f"Failed to fetch Ollama PS: {e}")

    # 2. Fetch PyTorch CUDA models status from Chat Service (BGE-Reranker & F5-TTS)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.get(f"{chat_svc_url}/api/system/models-status")
            if res.status_code == 200:
                data = res.json()
                if data.get("reranker", {}).get("loaded"):
                    models.append({
                        "name": "bge-reranker-v2-m3",
                        "model": "bge-reranker-v2-m3",
                        "size": data["reranker"]["size"],
                        "size_vram": data["reranker"]["size_vram"],
                        "expires_at": "2318-12-12T00:00:00.000000+07:00",
                        "context_length": 512,
                        "is_pytorch": True
                    })
                if data.get("f5_tts", {}).get("loaded"):
                    models.append({
                        "name": "f5-tts-indo",
                        "model": "f5-tts-indo",
                        "size": data["f5_tts"]["size"],
                        "size_vram": data["f5_tts"]["size_vram"],
                        "expires_at": "2318-12-12T00:00:00.000000+07:00",
                        "context_length": 1024,
                        "is_pytorch": True
                    })
    except Exception as e:
        logger.debug(f"Chat service PyTorch models check: {e}")

    return models

async def get_top_users() -> List[Dict[str, Any]]:
    """Fetches top 10 token consumers in the last 7-30 days based on real token usage or message count"""
    if database.db_pool is None:
        return []

    try:
        async with database.db_pool.acquire() as conn:
            # 1. Coba ambil dari data riil request_token_usage
            try:
                real_rows = await conn.fetch("""
                    SELECT user_npp as npp, SUM(total_tokens) as tokens, COUNT(*) as msgs, MAX(created_at) as last_active
                    FROM request_token_usage
                    WHERE user_npp != 'GUEST' AND user_npp IS NOT NULL AND created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY user_npp
                    ORDER BY tokens DESC
                    LIMIT 10
                """)
                if real_rows and len(real_rows) > 0:
                    return [
                        {
                            "npp": r["npp"],
                            "tokens": int(r["tokens"] or 0),
                            "msgs": int(r["msgs"] or 0),
                            "last_active": r["last_active"].isoformat() if r["last_active"] else None,
                        }
                        for r in real_rows
                    ]
            except Exception:
                pass

            # 2. Fallback ke chat_messages (estimasi 450 token/msg) jika tabel token belum banyak data
            base_query = """
                SELECT s.npp, COUNT(m.id) as msgs, MAX(m.timestamp) as last_active
                FROM chat_messages m
                JOIN chat_sessions s ON m.session_id = s.id
                WHERE m.timestamp >= NOW() - INTERVAL '{interval}'
                AND s.npp != 'GUEST'
                GROUP BY s.npp
                ORDER BY msgs DESC
                LIMIT 10
            """
            rows = await conn.fetch(base_query.format(interval='7 days'))
            if not rows:
                rows = await conn.fetch(base_query.format(interval='30 days'))
            return [
                {
                    "npp": r["npp"],
                    "tokens": r["msgs"] * 450,
                    "msgs": r["msgs"],
                    "last_active": r["last_active"].isoformat() if r["last_active"] else None,
                }
                for r in rows
            ]
    except Exception as e:
        logger.warning(f"Failed to fetch top users: {e}")
        return []

async def get_rag_stats() -> int:
    """Fetch total document chunks stored in PostgreSQL vector database"""
    if database.db_pool is None:
        return 0
    try:
        async with database.db_pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM dokumen_chunk")
    except Exception as e:
        logger.warning(f"Failed to fetch RAG stats: {e}")
        return 0

async def simulate_rag_search(query: str) -> List[Dict[str, Any]]:
    """Simulate RAG retrieval without LLM processing to test vector accuracy"""
    try:
        from backend.app.services.rag.vector_service import vector_service
        # Dapatkan embedding untuk query
        query_embedding = await vector_service.get_query_embedding(query)
        if not query_embedding:
            return []
            
        query_vector_str = f"[{','.join(str(x) for x in query_embedding)}]"
        
        async with database.db_pool.acquire() as conn:
            # Lakukan pencarian Vektor murni
            sql = """
                SELECT 
                    dc.id AS chunk_id,
                    dc.content,
                    dc.dokumen_id,
                    d.judul,
                    1 - (dc.embedding <=> $1::vector) AS similarity
                FROM dokumen_chunk dc
                LEFT JOIN dokumen d ON dc.dokumen_id = d.id
                ORDER BY dc.embedding <=> $1::vector
                LIMIT 5
            """
            rows = await conn.fetch(sql, query_vector_str)
            
            simulated_results = []
            for r in rows:
                content = r["content"]
                simulated_results.append({
                    "document_id": str(r["chunk_id"]),
                    "judul": r["judul"] or "Unknown Document",
                    "content_preview": content[:200] + "..." if len(content) > 200 else content,
                    "similarity_score": round(r["similarity"], 4) if r["similarity"] else 0.0
                })
                
            return simulated_results
    except Exception as e:
        logger.error(f"Failed RAG simulation: {e}")
        return []

import json

async def get_user_sessions(npp: str) -> List[Dict[str, Any]]:
    """Fetch all chat sessions for a specific NPP"""
    if database.db_pool is None:
        return []
    try:
        async with database.db_pool.acquire() as conn:
            query = """
                SELECT session_uuid, judul, started_at, ended_at, is_deleted
                FROM chat_sessions
                WHERE npp = $1
                ORDER BY started_at DESC
                LIMIT 50
            """
            rows = await conn.fetch(query, npp)
            return [{
                "session_uuid": str(r["session_uuid"]),
                "title": r["judul"] or "Untitled Chat",
                "created_at": r["started_at"].isoformat() if r["started_at"] else None,
                "updated_at": r["ended_at"].isoformat() if r["ended_at"] else None,
                "is_deleted": r["is_deleted"]
            } for r in rows]
    except Exception as e:
        logger.error(f"Failed to fetch user sessions: {e}")
        return []


async def get_all_users_with_activity(
    search: str = "",
    filter_type: str = "all",  # "all" | "registered" | "guest"
    sort_by: str = "last_active",  # "last_active" | "total_sessions" | "name"
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Chat Explorer: Ambil daftar semua user (NPP + guest) beserta statistik aktivitas chat mereka.
    Dipakai di menu Chat Explorer pada admin dashboard.
    """
    if database.db_pool is None:
        return {"users": [], "total": 0}
    try:
        async with database.db_pool.acquire() as conn:
            # ── Registered Users ──────────────────────────────────────────────
            registered_query = """
                SELECT
                    cs.npp,
                    COALESCE(u.fullname, cs.npp)    AS display_name,
                    NULL::text                       AS jabatan,
                    COALESCE(u.divisi, '')           AS divisi,
                    COUNT(cs.id)                     AS total_sessions,
                    SUM(CASE WHEN cs.is_deleted = false THEN 1 ELSE 0 END) AS active_sessions,
                    MAX(cs.started_at)               AS last_active,
                    MIN(cs.started_at)               AS first_active,
                    false                            AS is_guest
                FROM chat_sessions cs
                LEFT JOIN users u ON cs.npp = u.npp
                WHERE cs.npp IS NOT NULL
                  AND cs.npp != ''
                  AND UPPER(cs.npp) != 'GUEST'
                GROUP BY cs.npp, u.fullname, u.divisi
            """

            # ── Guest Users ───────────────────────────────────────────────────
            guest_query = """
                SELECT
                    COALESCE(NULLIF(cs.npp, ''), 'GUEST') AS npp,
                    COALESCE(NULLIF(cs.npp, ''), 'Guest') AS display_name,
                    NULL::text                            AS jabatan,
                    NULL::text                            AS divisi,
                    COUNT(cs.id)                          AS total_sessions,
                    SUM(CASE WHEN cs.is_deleted = false THEN 1 ELSE 0 END) AS active_sessions,
                    MAX(cs.started_at)                    AS last_active,
                    MIN(cs.started_at)                    AS first_active,
                    true                                  AS is_guest
                FROM chat_sessions cs
                WHERE cs.npp IS NULL
                   OR cs.npp = ''
                   OR UPPER(cs.npp) = 'GUEST'
                   OR cs.npp ~* '^guest'
                GROUP BY cs.npp
            """

            # Gabungkan berdasarkan filter
            if filter_type == "registered":
                union_query = registered_query
            elif filter_type == "guest":
                union_query = guest_query
            else:
                union_query = f"({registered_query}) UNION ALL ({guest_query})"

            # Wrap untuk search + sort + pagination
            params = []
            param_idx = 1

            if search:
                search_val = f"%{search.lower()}%"
                search_clause = f"WHERE LOWER(display_name) LIKE ${param_idx} OR LOWER(npp) LIKE ${param_idx + 1}"
                params.extend([search_val, search_val])
                param_idx += 2
            else:
                search_clause = ""

            sort_map = {
                "last_active": "last_active DESC NULLS LAST",
                "total_sessions": "total_sessions DESC",
                "name": "display_name ASC NULLS LAST",
            }
            order_clause = sort_map.get(sort_by, "last_active DESC NULLS LAST")

            full_query = f"""
                WITH combined AS ({union_query})
                SELECT *, COUNT(*) OVER() AS total_count
                FROM combined
                {search_clause}
                ORDER BY {order_clause}
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            params.extend([limit, offset])

            rows = await conn.fetch(full_query, *params)
            total = rows[0]["total_count"] if rows else 0

            users = []
            for r in rows:
                users.append({
                    "npp": r["npp"] or "GUEST",
                    "display_name": r["display_name"] or r["npp"] or "Unknown",
                    "divisi": r["divisi"] or None,
                    "total_sessions": int(r["total_sessions"]),
                    "active_sessions": int(r["active_sessions"]),
                    "last_active": r["last_active"].isoformat() if r["last_active"] else None,
                    "first_active": r["first_active"].isoformat() if r["first_active"] else None,
                    "is_guest": r["is_guest"],
                })

            return {"users": users, "total": int(total)}
    except Exception as e:
        logger.error(f"Failed to fetch all users with activity: {e}")
        return {"users": [], "total": 0}



async def get_session_chat_history(session_uuid: str) -> List[Dict[str, Any]]:
    """Fetch chat messages for a specific session for God Mode audit"""
    if database.db_pool is None:
        return []
    try:
        async with database.db_pool.acquire() as conn:
            # Resolve session_id
            session_id = await conn.fetchval("SELECT id FROM chat_sessions WHERE session_uuid = $1", session_uuid)
            if not session_id:
                return []
                
            query = """
                SELECT role, message_text, timestamp, thought, sources, metadata
                FROM chat_messages
                WHERE session_id = $1
                ORDER BY timestamp ASC
            """
            rows = await conn.fetch(query, session_id)
            
            history = []
            for r in rows:
                try:
                    sources = json.loads(r["sources"]) if r["sources"] else []
                except:
                    sources = []
                    
                try:
                    metadata = json.loads(r["metadata"]) if r["metadata"] else {}
                except:
                    metadata = {}
                    
                history.append({
                    "role": r["role"],
                    "message_text": r["message_text"],
                    "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
                    "thought": r["thought"],
                    "sources": sources, 
                    "metadata": metadata,
                })
            return history
    except Exception as e:
        logger.error(f"Failed to fetch session chat history: {e}")
        return []

async def get_session_attachments(session_uuid: str) -> List[Dict[str, Any]]:
    """Fetch all attachments for a specific session"""
    if database.db_pool is None:
        return []
    try:
        async with database.db_pool.acquire() as conn:
            session_id = await conn.fetchval("SELECT id FROM chat_sessions WHERE session_uuid = $1", session_uuid)
            if not session_id:
                return []
                
            query = """
                SELECT id, file_name, file_size, mime_type, uploaded_at
                FROM chat_attachments
                WHERE session_id = $1
                ORDER BY uploaded_at ASC
            """
            rows = await conn.fetch(query, session_id)
            
            return [{
                "id": str(r["id"]),
                "filename": r["file_name"],
                "size": r["file_size"],
                "mime_type": r["mime_type"],
                "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None
            } for r in rows]
    except Exception as e:
        logger.error(f"Failed to fetch session attachments: {e}")
        return []

async def get_quality_metrics() -> Dict[str, Any]:
    """Fetch AI quality metrics based on user feedback"""
    if database.db_pool is None:
        return {"upvotes": 0, "downvotes": 0, "total_ratings": 0}
    try:
        async with database.db_pool.acquire() as conn:
            query = """
                SELECT 
                    SUM(CASE WHEN feedback->>'rating' = 'good' THEN 1 ELSE 0 END) as upvotes,
                    SUM(CASE WHEN feedback->>'rating' = 'bad' THEN 1 ELSE 0 END) as downvotes,
                    COUNT(feedback) as total_ratings
                FROM chat_messages
                WHERE feedback IS NOT NULL
            """
            row = await conn.fetchrow(query)
            
            upvotes = int(row["upvotes"] or 0)
            downvotes = int(row["downvotes"] or 0)
            total = int(row["total_ratings"] or 0)
            
            return {
                "upvotes": upvotes,
                "downvotes": downvotes,
                "total_ratings": total
            }
    except Exception as e:
        logger.error(f"Failed to fetch quality metrics: {e}")
        return {"upvotes": 0, "downvotes": 0, "total_ratings": 0}

async def get_agent_steps(limit: int = 20) -> List[Dict[str, Any]]:
    """Fetch recent AI agent steps for the Pipeline Visualizer"""
    if database.db_pool is None:
        return []
    try:
        async with database.db_pool.acquire() as conn:
            query = """
                WITH LatestMessage AS (
                    SELECT message_id 
                    FROM ai_agent_steps 
                    ORDER BY created_at DESC 
                    LIMIT 1
                )
                SELECT 
                    a.id, a.message_id, a.step_number, a.tool_called, 
                    a.tool_input, a.observation, a.created_at,
                    m.session_id, s.session_uuid, s.npp
                FROM ai_agent_steps a
                JOIN chat_messages m ON a.message_id = m.id
                JOIN chat_sessions s ON m.session_id = s.id
                WHERE a.message_id = (SELECT message_id FROM LatestMessage)
                ORDER BY a.step_number ASC, a.created_at ASC
            """
            rows = await conn.fetch(query)
            
            return [{
                "id": r["id"],
                "message_id": r["message_id"],
                "step_number": r["step_number"],
                "tool_called": r["tool_called"],
                "tool_input": r["tool_input"],
                "observation": r["observation"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "session_uuid": str(r["session_uuid"]),
                "npp": r["npp"]
            } for r in rows]
    except Exception as e:
        logger.error(f"Failed to fetch agent steps: {e}")
        return []



async def get_latest_rag_step() -> Dict[str, Any]:
    """Mengambil step RAG_SEARCH terakhir di seluruh sistem untuk divisualisasikan."""
    if database.db_pool is None:
        return {}
    try:
        async with database.db_pool.acquire() as conn:
            query = """
                SELECT 
                    a.id, a.message_id, a.step_number, a.tool_called, 
                    a.tool_input, a.observation, a.created_at,
                    m.session_id, s.session_uuid, s.npp
                FROM ai_agent_steps a
                JOIN chat_messages m ON a.message_id = m.id
                JOIN chat_sessions s ON m.session_id = s.id
                WHERE a.tool_called = 'RAG_SEARCH'
                ORDER BY a.created_at DESC
                LIMIT 1
            """
            r = await conn.fetchrow(query)
            if not r:
                return {}
            
            return {
                "id": r["id"],
                "message_id": r["message_id"],
                "step_number": r["step_number"],
                "tool_called": r["tool_called"],
                "tool_input": r["tool_input"],
                "observation": r["observation"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "session_uuid": str(r["session_uuid"]),
                "npp": r["npp"]
            }
    except Exception as e:
        import logging
        logging.error(f"Failed to fetch latest rag step: {e}")
        return {}


async def get_security_threat_score() -> Dict[str, Any]:
    """
    Hitung Threat Score (0-100) berdasarkan security_logs 24 jam terakhir.
    Severity weights: CRITICAL=10, HIGH=5, MEDIUM=2, LOW=1
    """
    if database.db_pool is None:
        return {"score": 0, "breakdown": {}, "total_events": 0, "recent_events": []}

    try:
        async with database.db_pool.acquire() as conn:
            # Count by severity in last 24h
            severity_query = """
                SELECT severity, COUNT(*) as cnt, event_type
                FROM security_logs
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
                GROUP BY severity, event_type
                ORDER BY cnt DESC
            """
            rows = await conn.fetch(severity_query)

            weights = {"CRITICAL": 10, "HIGH": 5, "MEDIUM": 2, "LOW": 1}
            total_score = 0
            breakdown = {}
            event_type_counts = {}

            for row in rows:
                sev = (row["severity"] or "LOW").upper()
                count = int(row["cnt"])
                etype = row["event_type"]

                total_score += weights.get(sev, 1) * count
                breakdown[sev] = breakdown.get(sev, 0) + count
                event_type_counts[etype] = event_type_counts.get(etype, 0) + count

            # Cap score at 100
            normalized_score = min(100, total_score)

            # Recent 10 events
            recent_query = """
                SELECT id, timestamp, event_type, npp, ip_address, description, severity
                FROM security_logs
                ORDER BY timestamp DESC
                LIMIT 10
            """
            recent_rows = await conn.fetch(recent_query)
            recent_events = [{
                "id": str(r["id"]),
                "timestamp": r["timestamp"].isoformat(),
                "event_type": r["event_type"],
                "npp": r["npp"],
                "ip_address": r["ip_address"],
                "description": r["description"],
                "severity": r["severity"]
            } for r in recent_rows]

            return {
                "score": normalized_score,
                "breakdown": breakdown,
                "event_type_counts": event_type_counts,
                "total_events": sum(breakdown.values()),
                "recent_events": recent_events
            }
    except Exception as e:
        logger.error(f"Failed to get security threat score: {e}")
        return {"score": 0, "breakdown": {}, "event_type_counts": {}, "total_events": 0, "recent_events": []}


async def get_query_clusters() -> List[Dict[str, Any]]:
    """
    Ambil distribusi routing intent dari ai_agent_steps (ROUTER_ENGINE steps).
    Return list of {mode, count, queries_sample} untuk scatter plot.
    """
    if database.db_pool is None:
        return []

    try:
        async with database.db_pool.acquire() as conn:
            # Ambil ROUTER_ENGINE steps & observasi-nya untuk mendapatkan mode routing
            query = """
                SELECT a.tool_called, a.observation, a.tool_input, a.created_at,
                       s.npp
                FROM ai_agent_steps a
                JOIN chat_messages m ON a.message_id = m.id
                JOIN chat_sessions s ON m.session_id = s.id
                WHERE a.tool_called = 'ROUTER_ENGINE'
                ORDER BY a.created_at DESC
                LIMIT 200
            """
            rows = await conn.fetch(query)

            clusters = {}
            for row in rows:
                obs = row["observation"] or ""
                tool_input = row["tool_input"] or ""
                npp = row["npp"] or "UNKNOWN"
                ts = row["created_at"].isoformat() if row["created_at"] else None

                # Parse mode from observation
                mode = "chitchat"
                obs_lower = obs.lower()
                if "dokumen" in obs_lower or "document" in obs_lower or "rag" in obs_lower:
                    mode = "dokumen"
                elif "coding" in obs_lower or "code" in obs_lower or "generate" in obs_lower:
                    mode = "coding"
                elif "chitchat" in obs_lower or "casual" in obs_lower:
                    mode = "chitchat"
                elif "analitik" in obs_lower or "insight" in obs_lower or "analytic" in obs_lower:
                    mode = "analitik"
                elif "ambigu" in obs_lower or "ambig" in obs_lower:
                    mode = "ambigu"

                if mode not in clusters:
                    clusters[mode] = {"mode": mode, "count": 0, "queries": [], "npps": set()}

                clusters[mode]["count"] += 1
                if len(clusters[mode]["queries"]) < 5:
                    clusters[mode]["queries"].append(tool_input[:80])
                clusters[mode]["npps"].add(npp)

            # Convert set to list for JSON serialization
            result = []
            for mode, data in clusters.items():
                result.append({
                    "mode": data["mode"],
                    "count": data["count"],
                    "queries_sample": data["queries"],
                    "unique_users": len(data["npps"])
                })

            return sorted(result, key=lambda x: x["count"], reverse=True)
    except Exception as e:
        logger.error(f"Failed to get query clusters: {e}")
        return []


async def record_request_tokens(
    request_id: str,
    session_uuid: Optional[str] = None,
    user_npp: Optional[str] = None,
    mode: str = "general",
    model_router: str = "gemma4:e4b",
    model_generator: str = "gemma4:31b",
    router_prompt_tokens: int = 0,
    router_completion_tokens: int = 0,
    gen_prompt_tokens: int = 0,
    gen_completion_tokens: int = 0,
    duration_ms: float = 0.0,
) -> bool:
    """
    Mencatat penggunaan token riil per request ke tabel request_token_usage.
    Dipanggil asinkron dari pipeline_orchestrator saat respons chat selesai.
    """
    if database.db_pool is None:
        return False

    tot_prompt = int(router_prompt_tokens or 0) + int(gen_prompt_tokens or 0)
    tot_completion = int(router_completion_tokens or 0) + int(gen_completion_tokens or 0)
    total_tokens = tot_prompt + tot_completion

    try:
        async with database.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO request_token_usage (
                    request_id, session_uuid, user_npp, mode,
                    model_router, model_generator,
                    router_prompt_tokens, router_completion_tokens,
                    gen_prompt_tokens, gen_completion_tokens,
                    total_prompt_tokens, total_completion_tokens,
                    total_tokens, duration_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                request_id,
                session_uuid,
                user_npp or "GUEST",
                mode or "general",
                model_router,
                model_generator,
                int(router_prompt_tokens or 0),
                int(router_completion_tokens or 0),
                int(gen_prompt_tokens or 0),
                int(gen_completion_tokens or 0),
                tot_prompt,
                tot_completion,
                total_tokens,
                float(duration_ms or 0.0),
            )
            logger.info(
                f"🪙 [TOKEN_TRACKER] Recorded request {request_id} | "
                f"prompt={tot_prompt} | completion={tot_completion} | total={total_tokens} tokens | mode={mode}"
            )
            return True
    except Exception as e:
        logger.warning(f"⚠️ [TOKEN_TRACKER] Failed to record token usage: {e}")
        return False


async def get_daily_token_usage(days: int = 7) -> Dict[str, Any]:
    """
    Agregasi metrik penggunaan token per hari untuk grafik time-series dan ringkasan KPI.
    Jika days <= 0 atau days >= 365, tampilkan Semua Waktu (All Time).
    """
    if database.db_pool is None:
        return {"status": "success", "days": days, "series": [], "models": [], "kpi": {}}

    is_all_time = (days <= 0 or days >= 365)
    days_clamped = 0 if is_all_time else max(1, min(days, 180))

    try:
        async with database.db_pool.acquire() as conn:
            # 1. Query runtun waktu per hari
            if is_all_time:
                query_series = """
                    SELECT 
                        TO_CHAR(created_at, 'YYYY-MM-DD') as date_str,
                        COUNT(*) as request_count,
                        COALESCE(SUM(total_tokens), 0) as total_tokens,
                        COALESCE(SUM(total_prompt_tokens), 0) as prompt_tokens,
                        COALESCE(SUM(total_completion_tokens), 0) as completion_tokens,
                        COALESCE(ROUND(AVG(total_tokens)), 0) as avg_tokens_per_req,
                        COALESCE(ROUND(AVG(duration_ms)), 0) as avg_latency_ms
                    FROM request_token_usage
                    GROUP BY TO_CHAR(created_at, 'YYYY-MM-DD')
                    ORDER BY date_str ASC;
                """
                rows = await conn.fetch(query_series)
            else:
                query_series = """
                    SELECT 
                        TO_CHAR(created_at, 'YYYY-MM-DD') as date_str,
                        COUNT(*) as request_count,
                        COALESCE(SUM(total_tokens), 0) as total_tokens,
                        COALESCE(SUM(total_prompt_tokens), 0) as prompt_tokens,
                        COALESCE(SUM(total_completion_tokens), 0) as completion_tokens,
                        COALESCE(ROUND(AVG(total_tokens)), 0) as avg_tokens_per_req,
                        COALESCE(ROUND(AVG(duration_ms)), 0) as avg_latency_ms
                    FROM request_token_usage
                    WHERE created_at >= CURRENT_DATE - ($1 || ' days')::INTERVAL
                    GROUP BY TO_CHAR(created_at, 'YYYY-MM-DD')
                    ORDER BY date_str ASC;
                """
                rows = await conn.fetch(query_series, str(days_clamped))

            # 2. Distribusi per Model
            if is_all_time:
                query_models = """
                    SELECT 
                        model_generator as model,
                        COUNT(*) as request_count,
                        COALESCE(SUM(total_tokens), 0) as total_tokens
                    FROM request_token_usage
                    GROUP BY model_generator
                    ORDER BY total_tokens DESC;
                """
                model_rows = await conn.fetch(query_models)
            else:
                query_models = """
                    SELECT 
                        model_generator as model,
                        COUNT(*) as request_count,
                        COALESCE(SUM(total_tokens), 0) as total_tokens
                    FROM request_token_usage
                    WHERE created_at >= CURRENT_DATE - ($1 || ' days')::INTERVAL
                    GROUP BY model_generator
                    ORDER BY total_tokens DESC;
                """
                model_rows = await conn.fetch(query_models, str(days_clamped))

            # 3. KPI Total All-Time, Hari ini & Kemarin
            all_time_tokens = await conn.fetchval(
                "SELECT COALESCE(SUM(total_tokens), 0) FROM request_token_usage"
            ) or 0
            all_time_requests = await conn.fetchval(
                "SELECT COUNT(*) FROM request_token_usage"
            ) or 0

            today_tokens = await conn.fetchval(
                "SELECT COALESCE(SUM(total_tokens), 0) FROM request_token_usage WHERE created_at >= CURRENT_DATE"
            ) or 0
            yesterday_tokens = await conn.fetchval(
                "SELECT COALESCE(SUM(total_tokens), 0) FROM request_token_usage WHERE created_at >= CURRENT_DATE - INTERVAL '1 day' AND created_at < CURRENT_DATE"
            ) or 0

            pct_change = 0.0
            if yesterday_tokens > 0:
                pct_change = round(((today_tokens - yesterday_tokens) / yesterday_tokens) * 100, 1)

            series_data = [
                {
                    "date": r["date_str"],
                    "requests": int(r["request_count"]),
                    "total_tokens": int(r["total_tokens"]),
                    "prompt_tokens": int(r["prompt_tokens"]),
                    "completion_tokens": int(r["completion_tokens"]),
                    "avg_tokens": int(r["avg_tokens_per_req"]),
                    "avg_latency_ms": int(r["avg_latency_ms"]),
                }
                for r in rows
            ]

            period_total = sum(s["total_tokens"] for s in series_data)
            period_requests = sum(s["requests"] for s in series_data)
            avg_per_req = round(period_total / period_requests) if period_requests > 0 else 0
            peak_day = max(series_data, key=lambda x: x["total_tokens"])["date"] if series_data else "-"

            models_data = [
                {
                    "model": m["model"] or "gemma4:31b",
                    "requests": int(m["request_count"]),
                    "tokens": int(m["total_tokens"]),
                }
                for m in model_rows
            ]

            return {
                "status": "success",
                "days": days_clamped,
                "is_all_time": is_all_time,
                "series": series_data,
                "models": models_data,
                "kpi": {
                    "all_time_tokens": int(all_time_tokens),
                    "all_time_requests": int(all_time_requests),
                    "today_tokens": int(today_tokens),
                    "yesterday_tokens": int(yesterday_tokens),
                    "pct_change": pct_change,
                    "period_total_tokens": period_total,
                    "period_requests": period_requests,
                    "avg_tokens_per_req": avg_per_req,
                    "peak_day": peak_day,
                }
            }
    except Exception as e:
        logger.error(f"Failed to fetch daily token usage: {e}")
        return {"status": "error", "error": str(e), "series": [], "models": [], "kpi": {}}


async def get_request_token_logs(
    limit: int = 25,
    offset: int = 0,
    search: str = "",
    mode: str = "",
    date: str = "",
) -> Dict[str, Any]:
    """
    Mengambil log per-request penggunaan token dengan pagination dan filter pencarian.
    """
    if database.db_pool is None:
        return {"status": "error", "total": 0, "logs": []}

    limit_clamped = max(1, min(limit, 100))
    offset_clamped = max(0, offset)

    conditions = ["1=1"]
    params = []
    idx = 1

    if search and search.strip():
        conditions.append(f"(request_id ILIKE ${idx} OR user_npp ILIKE ${idx} OR session_uuid ILIKE ${idx})")
        params.append(f"%{search.strip()}%")
        idx += 1

    if mode and mode.strip() and mode.lower() != "all":
        conditions.append(f"mode ILIKE ${idx}")
        params.append(mode.strip().lower())
        idx += 1

    if date and date.strip():
        conditions.append(f"TO_CHAR(created_at, 'YYYY-MM-DD') = ${idx}")
        params.append(date.strip())
        idx += 1

    where_clause = " AND ".join(conditions)

    try:
        async with database.db_pool.acquire() as conn:
            count_query = f"SELECT COUNT(*) FROM request_token_usage WHERE {where_clause}"
            total_records = await conn.fetchval(count_query, *params) or 0

            data_query = f"""
                SELECT 
                    id, request_id, session_uuid, user_npp, mode,
                    model_router, model_generator,
                    router_prompt_tokens, router_completion_tokens,
                    gen_prompt_tokens, gen_completion_tokens,
                    total_prompt_tokens, total_completion_tokens,
                    total_tokens, duration_ms, created_at
                FROM request_token_usage
                WHERE {where_clause}
                ORDER BY id DESC
                LIMIT ${idx} OFFSET ${idx + 1}
            """
            rows = await conn.fetch(data_query, *params, limit_clamped, offset_clamped)

            logs = [
                {
                    "id": r["id"],
                    "request_id": r["request_id"],
                    "session_uuid": r["session_uuid"],
                    "user_npp": r["user_npp"],
                    "mode": r["mode"],
                    "model_router": r["model_router"],
                    "model_generator": r["model_generator"],
                    "router_prompt_tokens": r["router_prompt_tokens"],
                    "router_completion_tokens": r["router_completion_tokens"],
                    "gen_prompt_tokens": r["gen_prompt_tokens"],
                    "gen_completion_tokens": r["gen_completion_tokens"],
                    "total_prompt_tokens": r["total_prompt_tokens"],
                    "total_completion_tokens": r["total_completion_tokens"],
                    "total_tokens": r["total_tokens"],
                    "duration_ms": round(r["duration_ms"] or 0, 1),
                    "timestamp": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]

            return {
                "status": "success",
                "total": total_records,
                "limit": limit_clamped,
                "offset": offset_clamped,
                "logs": logs,
            }
    except Exception as e:
        logger.error(f"Failed to fetch request token logs: {e}")
        return {"status": "error", "error": str(e), "total": 0, "logs": []}
