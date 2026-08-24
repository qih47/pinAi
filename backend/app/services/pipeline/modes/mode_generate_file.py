"""
Mode Generate File — Interceptor-Analyst Pipeline (REFACTOR ANTI-BOCOR)
=======================================================================
Arsitektur: Dual-Call + Live XML Parser + SSE Meta-Signals + Hard Break Enforcement
"""

import re
import json
import asyncio
import logging
import os
from pathlib import Path
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import (
    format_sse,
    format_sse_file_status,
    SSEEventType,
)
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.paths import get_account_dir
from backend.app.core.config import settings

logger = logging.getLogger("MODE_GENERATE_FILE")

_RE_OPEN_TAG   = re.compile(r'<(create_file|edit_file)\s+filename=["\']?([^"\'>\s]+)["\']?\s*>', re.IGNORECASE)
_RE_CLOSE_TAGS = re.compile(r'</(create_file|edit_file)\s*>', re.IGNORECASE)


def _sanitize_filename(filename: str) -> str:
    basename = os.path.basename(filename)
    safe = re.sub(r"[^\w.\-]", "_", basename)
    if not safe or safe.startswith("."):
        safe = f"generated_{safe}"
    return safe[:128]


async def _write_file_to_disk(filename: str, content: str, current_user_npp: str, session_id: str) -> Path:
    from backend.app.core.paths import get_account_session_dir
    account_artifacts_dir = get_account_session_dir(current_user_npp, session_id, "artifacts")
    safe_name = _sanitize_filename(filename)
    target_path = account_artifacts_dir / safe_name

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: target_path.write_text(content, encoding="utf-8")
    )
    logger.info(f"[GENERATE_FILE] File written to disk: {target_path}")
    return target_path


class InterceptorParser:
    def __init__(self):
        self.reset()
        self.completed_files: list = []

    def reset(self):
        self._buffer       = ""         
        self._transition_buffer = ""
        self._code_buffer  = []         
        self._state        = "STREAMING_PREAMBLE"
        self._filename     = None
        self._tag_type     = "create_file"   

    def reset_for_next_file(self):
        self._buffer       = ""
        self._transition_buffer = ""
        self._code_buffer  = []
        self._state        = "WAITING_FOR_NEXT_FILE"
        self._filename     = None
        self._tag_type     = "create_file"

    @property
    def filename(self) -> Optional[str]:
        return self._filename

    @property
    def tag_type(self) -> str:
        return self._tag_type

    @property
    def captured_code(self) -> str:
        return "".join(self._code_buffer)

    @property
    def state(self) -> str:
        return self._state

    def process_chunk(self, chunk: str):
        self._buffer += chunk
        results = []        
        if self._state in ("STREAMING_PREAMBLE", "WAITING_FOR_NEXT_FILE"):
            m = _RE_OPEN_TAG.search(self._buffer)
            if m:
                pre_tag_text = self._buffer[:m.start()]
                full_preamble = pre_tag_text
                if self._state == "WAITING_FOR_NEXT_FILE":
                    full_preamble = self._transition_buffer + pre_tag_text
                    self._transition_buffer = ""
                
                if full_preamble.strip():
                    results.append(("preamble", full_preamble))
                    if self._state == "WAITING_FOR_NEXT_FILE":
                        results.append(("batch_break", {}))
                
                self._tag_type = m.group(1).lower()      
                self._filename = _sanitize_filename(m.group(2))
                self._state    = "CAPTURING_CODE"
                
                tag_text = self._buffer[m.start():m.end()]
                results.append(("preamble", tag_text))
                
                rest = self._buffer[m.end():]
                self._buffer = ""

                results.append(("tag_open", { "filename": self._filename, "tag_type": self._tag_type }))
                results.extend(self._capture_code(rest))
            else:
                last_lt = self._buffer.rfind('<')
                if last_lt > 0:
                    safe_to_stream = self._buffer[:last_lt]
                    self._buffer   = self._buffer[last_lt:]
                    if safe_to_stream:
                        results.append(("preamble", safe_to_stream))
                elif last_lt == -1 and len(self._buffer) > 60:
                    safe_to_stream = self._buffer[:-10]
                    self._buffer   = self._buffer[-10:]
                    if safe_to_stream:
                        results.append(("preamble", safe_to_stream))

        elif self._state == "CAPTURING_CODE":
            rest = self._buffer
            self._buffer = ""
            results.extend(self._capture_code(rest))

        return results

    def _capture_code(self, text: str):
        results = []
        m = _RE_CLOSE_TAGS.search(text)
        open_m = _RE_OPEN_TAG.search(text)

        if open_m and (not m or open_m.start() < m.start()):
            # A new open tag appeared BEFORE a close tag! Auto-close the current file!
            code_part = text[:open_m.start()]
            if code_part:
                self._code_buffer.append(code_part)
                results.append(("code_chunk", code_part))
                results.append(("preamble", code_part))

            completed = {
                "filename": self._filename,
                "tag_type": self._tag_type,
                "code": self.captured_code,
            }
            self.completed_files.append(completed)

            done_filename = self._filename
            done_tag_type = self._tag_type
            done_code = self.captured_code
            self.reset_for_next_file()

            results.append(("file_ready", { "filename": done_filename, "tag_type": done_tag_type, "code": done_code }))
            
            # Kembalikan teks mulai dari tag buka baru ke buffer dan proses ulang
            self._buffer = text[open_m.start():]
            results.extend(self.process_chunk(""))
            return results

        if m:
            code_part = text[:m.start()]
            if code_part:
                self._code_buffer.append(code_part)
                results.append(("code_chunk", code_part))
                results.append(("preamble", code_part))
                
            close_tag_text = text[m.start():m.end()]
            results.append(("preamble", close_tag_text))

            completed = {
                "filename": self._filename,
                "tag_type": self._tag_type,
                "code": self.captured_code,
            }
            self.completed_files.append(completed)

            done_filename = self._filename
            done_tag_type = self._tag_type
            done_code = self.captured_code
            self.reset_for_next_file()

            results.append(("file_ready", { "filename": done_filename, "tag_type": done_tag_type, "code": done_code }))

            rest_after_close = text[m.end():]
            if rest_after_close:
                self._buffer = rest_after_close
                results.extend(self.process_chunk(""))  
        else:
            TAG_PREFIXES = ["</create_file", "</edit_file", "<create_file", "<edit_file"]
            partial_pos = -1
            for prefix_str in TAG_PREFIXES:
                for prefix_len in range(len(prefix_str), 1, -1):
                    prefix = prefix_str[:prefix_len]
                    if text.endswith(prefix):
                        pos = len(text) - prefix_len
                        if pos > partial_pos:
                            partial_pos = pos
                        break

            if partial_pos != -1:
                safe = text[:partial_pos]
                self._buffer = text[partial_pos:]
                if safe:
                    self._code_buffer.append(safe)
                    results.append(("code_chunk", safe))
                    results.append(("preamble", safe))
            else:
                safe = text[:-5] if len(text) > 5 else ""
                self._buffer = text[-5:] if len(text) > 5 else text
                if safe:
                    self._code_buffer.append(safe)
                    results.append(("code_chunk", safe))
                    results.append(("preamble", safe))

        return results

    def flush(self):
        results = []
        if self._state == "CAPTURING_CODE":
            if self._buffer:
                clean_content = _RE_CLOSE_TAGS.sub("", self._buffer)
                self._code_buffer.append(clean_content)
                results.append(("code_chunk", clean_content))
                results.append(("preamble", clean_content))
                self._buffer = ""
            completed = {
                "filename": self._filename,
                "tag_type": self._tag_type,
                "code": self.captured_code,
            }
            self.completed_files.append(completed)
            results.append(("file_ready", { "filename": self._filename, "tag_type": self._tag_type, "code": self.captured_code }))
            self.reset_for_next_file()
        elif self._buffer:
            results.append(("preamble", self._buffer))
            self._buffer = ""
            
        return results


class ModeGenerateFile:
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
        session_uuid: Optional[str] = None,
    ):
        logger.info(f"[MODE_GENERATE_FILE] Starting Unified Single-Stream Generation for: {employee_name} (NPP: {current_user_npp})")

        routing_data = routing_data or {}
        pronoun = routing_data.get("pronoun", "unknown")
        tone_hint = routing_data.get("tone_hint", "casual")

        # Prepare RAG / existing files text
        existing_artifacts_content = ""
        try:
            from backend.app.core.paths import get_account_session_dir, ACCOUNTS_DIR
            from pathlib import Path
            account_artifacts_dir = get_account_session_dir(current_user_npp, session_uuid or "default_session", "artifacts")
            if account_artifacts_dir.exists():
                artifact_files = sorted(
                    [f for f in account_artifacts_dir.glob("*") if f.is_file()],
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )[:5]
                for art_file in artifact_files:
                    try:
                        content = art_file.read_text(encoding="utf-8")
                        existing_artifacts_content += f"\n<existing_file filename=\"{art_file.name}\">\n{content}\n</existing_file>\n"
                    except Exception as fe:
                        logger.warning(f"[MODE_GENERATE_FILE] Gagal membaca artifact {art_file.name}: {fe}")

            if attachments:
                for att in attachments:
                    try:
                        file_path = att.get("file_path")
                        if file_path:
                            att_path = Path(file_path)
                            if not att_path.is_absolute():
                                att_path = account_artifacts_dir.parent / "attachments" / att_path.name
                            if att_path.exists():
                                content = att_path.read_text(encoding="utf-8")
                                filename = att.get("file_name", att_path.name)
                                existing_artifacts_content += f"\n<existing_file filename=\"{filename}\" type=\"user_attachment\">\n{content}\n</existing_file>\n"
                    except Exception as e:
                        logger.warning(f"[MODE_GENERATE_FILE] Gagal membaca attachment {att.get('file_path')}: {e}")
        except Exception as e:
            logger.warning(f"[MODE_GENERATE_FILE] Gagal membaca existing artifacts/attachments: {e}")

        from backend.app.services.pipeline.system_prompts import build_generate_file_call1_prompt
        system_prompt = build_generate_file_call1_prompt(
            employee_name=employee_name,
            pronoun=pronoun,
            tone_hint=tone_hint,
            existing_files_text=existing_artifacts_content,
        )

        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        trimmed_messages = messages_dict[-6:] if len(messages_dict) > 6 else messages_dict

        stream_messages = [
            {"role": "system", "content": system_prompt},
            *trimmed_messages,
        ]

        yield format_sse(status="💻 Merancang arsitektur file", event_type=SSEEventType.STATUS)

        parser = InterceptorParser()
        current_streaming_filename = None
        written_files = []

        # ── SINGLE UNIFIED STREAM (gemma4:31b) ──────────────────────────────────────
        try:
            async for chunk_line in stream_ollama_chat(
                model_name=getattr(settings, "MODEL_PERSONA", "gemma4:12b"),
                messages=stream_messages,
                request=request,
                temperature=0.6,
                keep_alive=-1,
                num_ctx=32768,
                num_predict=-1,
                is_thinking=is_thinking
            ):
                try:
                    chunk_data    = json.loads(chunk_line)
                    chunk_text    = chunk_data.get("chunk", "")
                    native_thought = chunk_data.get("thinking", "")
                    eval_count    = chunk_data.get("eval_count", 0)
                    eval_dur      = chunk_data.get("eval_duration", 0)
                except (json.JSONDecodeError, AttributeError):
                    chunk_text = chunk_line if isinstance(chunk_line, str) else ""
                    native_thought = ""
                    eval_count = eval_dur = 0

                if native_thought and is_thinking:
                    yield format_sse("", native_thought, False, event_type=SSEEventType.THINKING)

                if not chunk_text:
                    if eval_count > 0:
                        yield format_sse("", "", False, event_type=SSEEventType.CHUNK, eval_count=eval_count, eval_duration=eval_dur)
                    continue

                parser_results = parser.process_chunk(chunk_text)

                for action, payload in parser_results:
                    if action == "preamble":
                        yield format_sse(payload, "", False, event_type=SSEEventType.CHUNK)
                        
                    elif action == "batch_break":
                        yield format_sse_file_status(stage="batch_break", filename="SYSTEM")

                    elif action == "tag_open":
                        fn = payload["filename"]
                        tag_type = payload.get("tag_type", "create_file")
                        current_streaming_filename = fn
                        logger.info(f"[MODE_GENERATE_FILE] Detected <{tag_type}> for: {fn}")
                        yield format_sse(status=f"📁 Menyiapkan {fn}", event_type=SSEEventType.STATUS)
                        yield format_sse_file_status(stage="creating", filename=fn, tag_type=tag_type)

                    elif action == "code_chunk":
                        fn = current_streaming_filename or parser.filename or "unknown"
                        yield format_sse_file_status(stage="code_chunk", filename=fn, code_chunk=payload, tag_type=parser.tag_type)

                    elif action == "file_ready":
                        fn = payload["filename"]
                        code = payload.get("code", "")
                        tag_type = payload.get("tag_type", "create_file")
                        logger.info(f"[MODE_GENERATE_FILE] </{tag_type}> completed for: {fn} ({len(code)} chars)")
                        current_streaming_filename = None

                        # Tulis langsung ke disk secara asinkron
                        try:
                            file_path = await _write_file_to_disk(filename=fn, content=code, current_user_npp=current_user_npp, session_id=session_uuid or "default_session")
                            from backend.app.core.paths import get_account_session_dir, ACCOUNTS_DIR
                            from pathlib import Path
                            
                            relative_path = str(file_path.relative_to(Path(ACCOUNTS_DIR).parent)) 
                            lines_count = len(code.splitlines()) if code else 1
                            written_files.append({ "filename": fn, "file_path": relative_path, "lines_count": lines_count })
                            yield format_sse(status=f"✨ Berkas {fn} siap", event_type=SSEEventType.STATUS)
                            yield format_sse_file_status(stage="done", filename=fn, file_path=relative_path, lines_count=lines_count)
                        except Exception as write_err:
                            logger.error(f"[MODE_GENERATE_FILE] File write error for {fn}: {write_err}")
                            yield format_sse_file_status(stage="error", filename=fn)

            # ── FLUSH sisa buffer jika ada yang tertahan ────────────────────
            for action, payload in parser.flush():
                if action == "preamble":
                    yield format_sse(payload, "", False, event_type=SSEEventType.CHUNK)
                elif action == "code_chunk":
                    fn = current_streaming_filename or parser.filename or "unknown"
                    yield format_sse_file_status(stage="code_chunk", filename=fn, code_chunk=payload, tag_type=parser.tag_type)
                elif action == "file_ready":
                    fn = payload["filename"]
                    code = payload.get("code", "")
                    tag_type = payload.get("tag_type", "create_file")
                    current_streaming_filename = None
                    try:
                        file_path = await _write_file_to_disk(filename=fn, content=code, current_user_npp=current_user_npp, session_id=session_uuid or "default_session")
                        from backend.app.core.paths import get_account_session_dir, ACCOUNTS_DIR
                        from pathlib import Path
                        
                        relative_path = str(file_path.relative_to(Path(ACCOUNTS_DIR).parent)) 
                        lines_count = len(code.splitlines()) if code else 1
                        written_files.append({ "filename": fn, "file_path": relative_path, "lines_count": lines_count })
                        yield format_sse_file_status(stage="done", filename=fn, file_path=relative_path, lines_count=lines_count)
                    except Exception as write_err:
                        logger.error(f"[MODE_GENERATE_FILE] Flushed file write error for {fn}: {write_err}")
                        yield format_sse_file_status(stage="error", filename=fn)

        except Exception as e:
            logger.error(f"[MODE_GENERATE_FILE] Single stream error: {e}")
            yield format_sse(f"Maaf, terjadi kendala: {str(e)}", "", False, event_type=SSEEventType.CHUNK)
            return