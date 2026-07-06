import logging
import json
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings
from backend.app.services.pipeline.system_prompts import build_attachment_system_prompt

logger = logging.getLogger("MODE_ATTACHMENT")

# Default config for Attachment Mode
ATTACHMENT_MODE_CONFIG = {
    "num_ctx": 16384,
    "temperature": 0.2,
}

class ModeAttachment:
    """
    Mode Attachment: Bypasses Call 1 and RAG, focuses purely on the provided attachment.
    It can handle text extraction directly from vision pipelines or multimodal base64.
    """
    async def execute(
        self,
        user_message: str,
        chat_history: List[ChatMessageSchema],
        is_thinking: bool,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_isolation: Optional[Dict[str, Any]] = None,
        routing_data: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        employee_name: str = "Pegawai",
        current_user_npp: Optional[str] = None,
        session_uuid: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        logger.info("[MODE_ATTACHMENT] Starting execution")
        
        system_prompt = build_attachment_system_prompt(employee_name=employee_name)

        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        # Mengambil 5 history + 1 current message = 6
        trimmed_messages = messages_dict[-6:] if len(messages_dict) > 6 else messages_dict
        
        # Inject attachments (base64 images if available) into the user's current message
        # For this, we assume that 'attachments' might contain base64 image strings 
        # that should be passed to the Ollama messages API.
        
        if is_thinking:
            system_prompt = "<|think|>\n" + system_prompt

        stream_messages = [
            {"role": "system", "content": system_prompt},
            *trimmed_messages,
        ]

        is_from_pdf = False
        if attachments:
            images_base64 = []
            for att in attachments:
                if isinstance(att, dict):
                    # Deteksi apakah gambar ini berasal dari dump PDF
                    if att.get("file_type") == "application/pdf" or "pdf" in att.get("file_path", "").lower():
                        is_from_pdf = True
                    
                    if "base64" in att:
                        images_base64.append(att["base64"])
                elif isinstance(att, str):
                    # Backward compatibility if it's already a base64 string
                    images_base64.append(att)
            
            if images_base64:
                import base64
                from io import BytesIO
                try:
                    from PIL import Image
                    processed_images = []
                    for b64_str in images_base64:
                        if len(b64_str) * 0.75 > 2 * 1024 * 1024:
                            image_data = base64.b64decode(b64_str)
                            image = Image.open(BytesIO(image_data))
                            max_size = (1024, 1024)
                            image.thumbnail(max_size, Image.Resampling.LANCZOS)
                            buffered = BytesIO()
                            image.save(buffered, format="JPEG", quality=85)
                            processed_images.append(base64.b64encode(buffered.getvalue()).decode("utf-8"))
                        else:
                            processed_images.append(b64_str)
                    
                    # Append images to the last user message
                    for msg in reversed(stream_messages):
                        if msg["role"] == "user":
                            msg["images"] = processed_images
                            break
                except Exception as e:
                    logger.error(f"[VISION] Gagal memproses gambar: {e}")

        # HYBRID TOKEN BUDGET UNTUK VISION GEMMA 4
        # Jika dari PDF -> Butuh high resolution token budget (misal 1120) & num_ctx besar
        # Jika gambar biasa -> Budget normal (280) & num_ctx standar
        num_ctx = 32000 if is_from_pdf else 16384
        temperature = 1.0 # Standard best practice Gemma 4
        # Parameter token budget jika didukung oleh Ollama via options
        token_budget = 1120 if is_from_pdf else 280

        yield format_sse(status="👁️ Menganalisis lampiran dokumen/gambar", event_type=SSEEventType.STATUS)

        # Selalu gunakan MODEL_PERSONA (Gemma 4) karena memiliki kapabilitas multimodal native & 256K context
        target_model = getattr(settings, "MODEL_PERSONA", "gemma4:12b")

        # Hitung estimasi token (1 token ~ 4 karakter)
        sys_tokens = len(system_prompt) // 4
        hist_tokens = sum(len(m.get("content", "")) for m in messages_dict) // 4
        rag_tokens = token_budget if token_budget else 1000 # Estimate attachment footprint
        total_used = sys_tokens + hist_tokens + rag_tokens

        session_uuid_to_use = session_uuid or (routing_data.get("_session_uuid") if routing_data else None)
        if session_uuid_to_use:
            from backend.app.services.chat_history_service import chat_history_service
            obs_dict = {
                "msg": "Generating response for attachment",
                "memory": {
                    "system_tokens": sys_tokens,
                    "history_tokens": hist_tokens,
                    "rag_tokens": rag_tokens,
                    "total_used": total_used,
                    "max_ctx": num_ctx
                }
            }
            await chat_history_service.save_agent_step(
                session_id=session_uuid_to_use,
                step_number=3,
                tool_called="CALL_2_ATTACHMENT",
                tool_input=f"Attachment analysis mode",
                observation=json.dumps(obs_dict)
            )

        try:
            async for chunk_line in stream_ollama_chat(
                model_name=target_model,
                messages=stream_messages,
                request=request,
                temperature=temperature,
                keep_alive=-1,
                num_ctx=num_ctx,
                num_predict=8192,
                is_thinking=is_thinking,
                token_budget=token_budget,
            ):
                try:
                    chunk_data = json.loads(chunk_line.strip())
                    yield chunk_line
                except json.JSONDecodeError:
                    yield chunk_line
        except Exception as e:
            logger.error(f"[MODE_ATTACHMENT] Execution error: {str(e)}", exc_info=True)
            yield format_sse(
                status=f"Terjadi kesalahan saat mengeksekusi Mode Attachment: {str(e)}",
                event_type=SSEEventType.STATUS
            )
