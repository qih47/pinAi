import os
import time
import torch
import psutil
import subprocess
import asyncio
import logging
from typing import List, Dict, Any

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
            
            # Hitung total token (Simulasi atau Real jika ada kolom prompt_tokens dll)
            try:
                # Cek jika tabel audit / metrics ada, atau total pesan
                total_msgs = await conn.fetchval("SELECT COUNT(*) FROM chat_messages")
                # Simulasi: 1 pesan rata-rata konsumsi 450 tokens (karena kita ga nyimpen token exact per baris saat ini)
                token_consumption = total_msgs * 450
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
    """Fetches top 5 token consumers in the last 7 days based on message count"""
    if database.db_pool is None:
        return []

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

    try:
        async with database.db_pool.acquire() as conn:
            # Coba 7 hari dulu
            rows = await conn.fetch(base_query.format(interval='7 days'))
            # Fallback ke 30 hari kalau kosong
            if not rows:
                rows = await conn.fetch(base_query.format(interval='30 days'))
            # Estimasi token: 450 token per message
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
