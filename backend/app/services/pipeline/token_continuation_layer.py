import json
import re
from typing import List, Dict, Any, AsyncGenerator

def build_raw_prompt_string(
    system_prompt: str,
    messages: List[Dict[str, str]],  
    prefill_thinking: str = ""  
) -> str:
    """
    Build exact raw prompt string with Gemma4 token markers.
    
    Returns format:
        <start_of_turn>system\n{system_prompt}<end_of_turn>
        <start_of_turn>user\n{message}<end_of_turn>
        <start_of_turn>assistant\n<think>{prefill_thinking}
    
    Key requirements:
    - NO spaces around markers
    - Newline after <start_of_turn>system/user
    - NO newline after <start_of_turn>assistant before <think>
    - If prefill_thinking: place immediately after <think> (no newline)
    """
    prompt = f"<start_of_turn>system\n{system_prompt}<end_of_turn>\n"
    
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            prompt += f"<start_of_turn>user\n{content}<end_of_turn>\n"
        elif role == "assistant":
            prompt += f"<start_of_turn>assistant\n{content}<end_of_turn>\n"
            
    prompt += "<start_of_turn>assistant\n<think>"
    if prefill_thinking:
        prompt += prefill_thinking
        
    return prompt

class RawPromptBuilder:
    """Builder pattern for complex raw prompts."""
    
    def __init__(self):
        self._system_prompt = ""
        self._messages = []
        self._prefill_thinking = ""
        self._rag_injection = ""
    
    def set_system(self, prompt: str) -> "RawPromptBuilder":
        """Set system prompt."""
        self._system_prompt = prompt
        return self
    
    def add_message(self, role: str, content: str) -> "RawPromptBuilder":
        """Add user/assistant message."""
        self._messages.append({"role": role, "content": content})
        return self
    
    def set_prefill_thinking(self, thinking: str) -> "RawPromptBuilder":
        """Set thinking block prefill (for continuation)."""
        self._prefill_thinking = thinking
        return self
    
    def inject_rag_context(self, context_text: str) -> "RawPromptBuilder":
        """Inject RAG data into thinking."""
        self._rag_injection = context_text
        return self
    
    def build(self) -> str:
        """Generate final raw prompt."""
        prompt = build_raw_prompt_string(self._system_prompt, self._messages, self._prefill_thinking)
        if self._rag_injection:
            prompt += f"\n{self._rag_injection}\n"
        return prompt

def parse_channel_marker(accumulated_text: str) -> Dict[str, Any]:
    """
    Extract sub-queries from <channel|>{...json...} marker.
    
    Returns:
        {
            "found": bool,
            "queries": List[str],
            "raw_json": str
        }
    """
    match = re.search(r"<channel\|>(\{.*?\})", accumulated_text, re.DOTALL)
    if not match:
        return {"found": False, "queries": [], "raw_json": ""}
        
    raw_json = match.group(1)
    queries = []
    try:
        data = json.loads(raw_json)
        queries = data.get("queries", [])
    except json.JSONDecodeError:
        pass
        
    return {
        "found": True,
        "queries": queries,
        "raw_json": raw_json
    }

class TokenStreamParser:
    """Async parser for streaming token response from /api/generate."""
    
    def __init__(self):
        self.accumulated_text = ""
        self.thinking_content = ""
        self.in_thinking_block = True  # Assuming start inside <think> from prompt prefill
        self.marker_found = False
    
    async def parse_chunk(self, json_line: str) -> Dict[str, Any]:
        """
        Parse single chunk from /api/generate stream.
        
        Args:
            json_line: Line from streaming response (JSON string)
        
        Returns:
            {
                "token": str,
                "thinking_updated": bool,
                "marker_detected": bool,
                "status": "streaming" | "done" | "interrupted"
            }
        """
        try:
            data = json.loads(json_line)
            token = data.get("response", "")
            is_done = data.get("done", False)
        except json.JSONDecodeError:
            return {"token": "", "thinking_updated": False, "marker_detected": False, "status": "streaming"}
            
        self.accumulated_text += token
        thinking_updated = False
        
        if "</think>" in self.accumulated_text and self.in_thinking_block:
            self.in_thinking_block = False
            # Extract thinking up to </think>
            parts = self.accumulated_text.split("</think>")
            self.thinking_content = parts[0]
            thinking_updated = True
            
        if self.in_thinking_block:
            self.thinking_content = self.accumulated_text
            thinking_updated = True
            
        if "<channel|>" in self.accumulated_text:
            self.marker_found = True
            
        status = "streaming"
        if is_done:
            status = "done"
        if self.marker_found:
            status = "interrupted"
            
        return {
            "token": token,
            "thinking_updated": thinking_updated,
            "marker_detected": self.marker_found,
            "status": status
        }
    
    def get_accumulated_thinking(self) -> str:
        """Return all thinking content collected so far."""
        cleaned = re.sub(r"<channel\|>(\{.*?\})?", "", self.thinking_content, flags=re.DOTALL)
        cleaned = cleaned.replace("<|channel>thought", "")
        return cleaned.strip()
    
    def get_accumulated_text(self) -> str:
        """Return full accumulated response."""
        return self.accumulated_text
    
    async def wait_for_marker_or_done(self):
        """Generator that yields until <channel|> or done."""
        pass

def stitch_raw_prompt_with_rag(
    previous_raw_prompt: str,
    accumulated_thinking: str,
    rag_context: str,
    rag_sources: List[Dict[str, Any]]
) -> str:
    """
    Stitch thinking + RAG data into new continuation prompt.
    """
    injection = format_rag_injection_block(rag_sources, rag_context)
    
    # We reconstruct the prompt by adding the accumulated thinking so far
    # and the RAG injection, and closing the think block
    # Actually, if we already have the previous raw prompt with <think>,
    # we just append the generated thinking and the injection.
    stitched_prompt = f"{previous_raw_prompt}{accumulated_thinking}\n{injection}\n"
    
    return stitched_prompt

def format_rag_injection_block(
    rag_sources: List[Dict[str, Any]],
    rag_context: str
) -> str:
    """
    Format RAG data as natural-language injection into thinking block.
    """
    injection = "[SISTEM INTERUPSI: Pencarian dokumen selesai. Ditemukan rujukan:\n\n"
    
    for i, src in enumerate(rag_sources, 1):
        title = src.get("title", "Dokumen")
        doc_id = src.get("doc_id", "")
        injection += f"({i}) {title} (ID: {doc_id})\n"
    
    injection += "\nIsi ringkas:\n"
    injection += rag_context[:5000]  
    injection += "\n\nBerdasarkan rujukan di atas, lanjutkan analisis sebelumnya.]"
    
    return injection
