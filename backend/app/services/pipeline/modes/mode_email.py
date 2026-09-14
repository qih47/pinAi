import json
import asyncio
import logging
import time
from typing import AsyncGenerator

from backend.app.services.pipeline.sse_validation import (
    SSEEventType,
    format_sse
)
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings
from backend.app.services.pipeline.prompts.email_prompts import build_email_system_prompt

logger = logging.getLogger("CAKRA_MODE_EMAIL")

class ModeEmail:
    """
    Mode eksekusi untuk Generate Email.
    Sistem akan membuat draf email formal dan membalutnya dalam markdown block `smartmail`.
    """
    async def execute(
        self,
        user_message: str,
        chat_history: list,
        is_thinking: bool,
        attachments: list = None,
        context_isolation: dict = None,
        routing_data: dict = None,
        request = None,
        employee_name: str = "Pegawai",
        current_user_npp: str = None,
        session_uuid: str = None
    ) -> AsyncGenerator[str, None]:
        logger.info(f"[MODE_EMAIL] Executing Email Draft Mode. Precheck data: {routing_data}")
        start_time = time.time()
        
        yield format_sse(status="📧 Menulis email", status_key="MAIL_INIT", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

        system_prompt = build_email_system_prompt(
            employee_name=employee_name,
            precheck=routing_data,
            is_thinking=is_thinking
        )

        # Convert chat history to dict list (Maks 5 putaran dialog / 10 pesan)
        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history if getattr(m, "role", None) != "system"]
        if not messages_dict or messages_dict[-1].get("role") != "user" or messages_dict[-1].get("content") != user_message:
            messages_dict.append({"role": "user", "content": user_message})
        trimmed_messages = messages_dict[-10:] if len(messages_dict) > 10 else messages_dict
        
        current_messages = [{"role": "system", "content": system_prompt}] + trimmed_messages
        
        response_stream = stream_ollama_chat(
            messages=current_messages,
            model_name=settings.MODEL_PERSONA,
            is_thinking=is_thinking,
            temperature=0.3, # Render JSON harus presisi
            request=request
        )
        
        final_thinking = ""
        final_answer = ""
        
        try:
            async for chunk_line in response_stream:
                try:
                    chunk = json.loads(chunk_line.strip())
                except json.JSONDecodeError:
                    continue

                event_type = chunk.get("event_type", "chunk")
                
                if event_type == "chunk":
                    char = chunk.get("chunk", "")
                    thought = chunk.get("thinking", "")
                    
                    if thought:
                        final_thinking += thought
                        yield format_sse(thinking=thought, event_type=SSEEventType.THINKING)
                    
                    if char:
                        final_answer += char
                        yield format_sse(chunk=char, event_type=SSEEventType.CHUNK)
        except asyncio.CancelledError:
            logger.warning("[MODE_EMAIL] Stream cancelled by client.")
            raise
            
        # Log to DB
        session_uuid = routing_data.get("_session_uuid") if routing_data else None
        if session_uuid:
            from backend.app.services.chat.chat_history_service import chat_history_service
            obs_dict = {
                "msg": f"Email Draft generated.",
                "radar": {"dokumen": 10, "coding": 10, "chitchat": 10, "analitik": 10, "ambigu": 10}
            }
            await chat_history_service.save_agent_step(
                session_id=session_uuid,
                step_number=3,
                tool_called="LLM_EMAIL_ENGINE",
                tool_input=user_message[:200],
                observation=json.dumps(obs_dict)
            )

        duration = time.time() - start_time
        logger.info(f"[MODE_EMAIL] Completed in {duration:.2f}s")
        yield format_sse(status=f"✨ Email siap ({duration:.1f}s)", status_key="EMAIL_READY", event_type=SSEEventType.STATUS)
