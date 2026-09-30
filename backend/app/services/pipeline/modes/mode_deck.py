import json
import asyncio
import logging
import time
from typing import AsyncGenerator, Dict, Any, Optional

from backend.app.services.pipeline.sse_validation import (
    SSEEventType,
    format_sse
)
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings
from backend.app.services.integrations.deck_service import DeckService
from backend.app.services.pipeline.prompts.deck_prompts import build_deck_system_prompt
from backend.app.services.pipeline.modes.mode_utils import resolve_history_messages

logger = logging.getLogger("CAKRA_MODE_DECK")

class ModeDeck:
    """
    Mode eksekusi untuk Nextcloud Deck (Pincloud).
    Mengambil data board, stack, dan card yang di-assign ke user, merangkumnya,
    serta menyertakan blok ```deck_tasks ... ``` untuk widget interaktif di Frontend.
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
        full_name: Optional[str] = None,
        current_user_npp: str = None,
        session_uuid: str = None
    ) -> AsyncGenerator[str, None]:
        logger.info(f"[MODE_DECK] Executing Deck Mode for NPP: {current_user_npp}")
        start_time = time.time()

        yield format_sse(
            status="🗂️ Mengambil data Nextcloud Deck...", 
            status_key="DECK_FETCHING", 
            event_type=SSEEventType.STATUS
        )

        resolved_full_name = full_name or (routing_data.get("full_name") if routing_data else None) or employee_name
        pronoun = routing_data.get("pronoun", "informal_gue_lo") if routing_data else "informal_gue_lo"

        # 1. Ambil data dari Pincloud Deck
        deck_res = await DeckService.get_user_assigned_cards(
            npp=current_user_npp,
            board_id=None,
            include_all_boards_if_none=True
        )

        if deck_res.get("code") == "NOT_CONNECTED":
            yield format_sse(
                chunk=(
                    f"Halo {employee_name}, akun Nextcloud/Pincloud Anda belum terhubung di sistem Cakra AI. "
                    "Silakan hubungkan kredensial akun Nextcloud Anda terlebih dahulu melalui menu **Settings** -> **Integrasi Akun** "
                    "agar saya dapat membaca tugas dan proyek yang di-assign ke Anda di Pincloud Deck."
                ),
                event_type=SSEEventType.CHUNK
            )
            yield format_sse(done=True, event_type=SSEEventType.DONE)
            return

        # 2. Susun ringkasan tekstual untuk LLM Persona
        total_assigned = deck_res.get("total_assigned", 0)
        active_count = deck_res.get("active_count", 0)
        done_count = deck_res.get("done_count", 0)
        boards = deck_res.get("boards", [])

        summary_lines = [
            f"Total Tugas/Proyek yang Di-assign: {total_assigned} (Aktif: {active_count}, Selesai: {done_count})",
            ""
        ]

        for b in boards:
            summary_lines.append(f"### Board: {b.get('title')} (Total: {b.get('total_cards')} kartu)")
            for card in b.get("cards", []):
                status_str = "SELESAI (Done)" if card.get("is_done") else f"AKTIF - Kolom: {card.get('stack_title')}"
                team_names = [t.get("name") for t in card.get("team", []) if t.get("name")]
                team_str = ", ".join(team_names) if team_names else "Hanya Anda"
                due_str = f" | Deadline: {card.get('duedate')}" if card.get("duedate") else ""
                summary_lines.append(
                    f"- **{card.get('title')}** [{status_str}]{due_str}\n"
                    f"  Anggota Tim: {team_str}"
                )
            summary_lines.append("")

        deck_summary_str = "\n".join(summary_lines)
        deck_json_str = json.dumps(deck_res, ensure_ascii=False)

        yield format_sse(
            status="📋 Menyusun ringkasan tugas & proyek...", 
            status_key="DECK_PROCESSING", 
            event_type=SSEEventType.STATUS
        )

        # 3. Bangun system prompt
        system_prompt = build_deck_system_prompt(
            employee_name=employee_name,
            full_name=resolved_full_name,
            current_user_npp=current_user_npp or "",
            deck_data_summary=deck_summary_str,
            deck_json_str=deck_json_str,
            pronoun=pronoun
        )

        needs_history = bool(routing_data.get("needs_history", False)) if routing_data else False
        trimmed_messages = resolve_history_messages(
            chat_history=chat_history,
            user_message=user_message,
            needs_history=needs_history,
            max_turns=6,
            max_assistant_chars=600,
            active_pronoun=pronoun,
            strip_system=True,
        )

        current_messages = [{"role": "system", "content": system_prompt}] + trimmed_messages

        # 4. Stream response
        response_stream = stream_ollama_chat(
            messages=current_messages,
            model_name=settings.MODEL_PERSONA,
            is_thinking=is_thinking,
            temperature=0.3,
            request=request
        )

        started_streaming = False
        try:
            async for chunk_line in response_stream:
                if not started_streaming:
                    started_streaming = True
                    yield format_sse(status="", event_type=SSEEventType.STATUS)

                try:
                    chunk = json.loads(chunk_line.strip())
                except json.JSONDecodeError:
                    continue

                event_type = chunk.get("event_type", "chunk")
                if event_type == "chunk":
                    thought = chunk.get("thinking", "")
                    content = chunk.get("chunk", "")

                    if thought:
                        yield format_sse(thinking=thought, event_type=SSEEventType.THINKING)
                    if content:
                        yield format_sse(chunk=content, event_type=SSEEventType.CHUNK)
                elif event_type == "done":
                    break
        except asyncio.CancelledError:
            logger.warning("[MODE_DECK] Stream cancelled by client.")
            raise
        except Exception as e:
            logger.error(f"[MODE_DECK] Error during streaming: {e}", exc_info=True)
            yield format_sse(error=str(e), event_type=SSEEventType.ERROR)
        # Emit widget block directly to guarantee fast streaming and valid JSON structure
        yield format_sse(
            chunk=f"\n\n```deck_tasks\n{deck_json_str}\n```\n",
            event_type=SSEEventType.CHUNK
        )

        # Save step observation to chat history (non-blocking)
        if session_uuid:
            try:
                from backend.app.services.chat.chat_history_service import chat_history_service
                obs_dict = {
                    "msg": "Nextcloud Deck tasks fetched and summarized.",
                    "total_assigned": total_assigned,
                    "active": active_count,
                    "done": done_count
                }
                asyncio.create_task(chat_history_service.save_agent_step(
                    session_id=session_uuid,
                    step_number=3,
                    tool_called="NEXTCLOUD_DECK_ENGINE",
                    tool_input=user_message[:200],
                    observation=json.dumps(obs_dict)
                ))
            except Exception as e:
                logger.warning(f"[MODE_DECK] Failed to save agent step: {e}")

        logger.info(f"[MODE_DECK] Completed in {time.time() - start_time:.2f}s")
        yield format_sse(done=True, event_type=SSEEventType.DONE)
