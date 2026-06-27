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
        
        stream_messages = [
            {"role": "system", "content": system_prompt},
            *trimmed_messages,
        ]

        if attachments:
            images_base64 = []
            for att in attachments:
                if isinstance(att, dict) and "base64" in att:
                    images_base64.append(att["base64"])
                elif isinstance(att, str) and att.startswith("data:image"):
                    base64_data = att.split("base64,")[-1]
                    images_base64.append(base64_data)
            
            if images_base64:
                yield format_sse(status="🖼️ Memproses lampiran gambar...", event_type=SSEEventType.STATUS)
                try:
                    import base64
                    from io import BytesIO
                    from PIL import Image

                    processed_images = []
                    for b64_str in images_base64:
                        try:
                            image_data = base64.b64decode(b64_str)
                            img = Image.open(BytesIO(image_data))
                            
                            # Jika WEBP atau format lain yang mungkin bermasalah, konversi ke PNG
                            if img.format not in ["PNG", "JPEG"]:
                                if img.mode in ("RGBA", "P"):
                                    img = img.convert("RGB")
                                buffered = BytesIO()
                                img.save(buffered, format="PNG")
                                processed_images.append(base64.b64encode(buffered.getvalue()).decode("utf-8"))
                            else:
                                processed_images.append(b64_str)
                        except Exception as img_err:
                            logger.error(f"[VISION] Error processing image: {img_err}")
                            processed_images.append(b64_str)

                    # Append images to the last user message
                    for msg in reversed(stream_messages):
                        if msg["role"] == "user":
                            msg["images"] = processed_images
                            break
                except Exception as e:
                    logger.error(f"[VISION] Gagal memproses gambar: {e}")

        num_ctx = ATTACHMENT_MODE_CONFIG["num_ctx"]
        temperature = ATTACHMENT_MODE_CONFIG["temperature"]

        yield format_sse(status="👁️ Menganalisis lampiran dokumen/gambar", event_type=SSEEventType.STATUS)

        # Selalu gunakan MODEL_PERSONA (Gemma 4) karena memiliki kapabilitas multimodal native & 256K context
        target_model = getattr(settings, "MODEL_PERSONA", "gemma4:12b")

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
