import pytest
from backend.app.services.pipeline.token_continuation_layer import (
    build_raw_prompt_string,
    RawPromptBuilder,
    TokenStreamParser,
    parse_channel_marker,
    format_rag_injection_block,
    stitch_raw_prompt_with_rag
)

def test_build_system_only():
    prompt = build_raw_prompt_string("system prompt", [])
    assert "<start_of_turn>system\nsystem prompt<end_of_turn>\n" in prompt
    assert "<start_of_turn>assistant\n<think>" in prompt

def test_build_with_messages():
    prompt = build_raw_prompt_string("system", [{"role": "user", "content": "hi"}])
    assert "<start_of_turn>user\nhi<end_of_turn>\n" in prompt

def test_build_with_prefill_thinking():
    prompt = build_raw_prompt_string("system", [], "thinking...")
    assert "<think>thinking..." in prompt

@pytest.mark.asyncio
async def test_parse_normal_chunk():
    parser = TokenStreamParser()
    res = await parser.parse_chunk('{"response": " hello", "done": false}')
    assert res["token"] == " hello"
    assert res["status"] == "streaming"

def test_parse_channel_marker():
    text = 'some text <channel|>{"queries": ["q1"]} </channel|>'
    res = parse_channel_marker(text)
    assert res["found"] is True
    assert res["queries"] == ["q1"]

def test_format_rag_injection_block():
    sources = [{"title": "Doc 1", "doc_id": "123"}]
    res = format_rag_injection_block(sources, "Context text")
    assert "[SISTEM INTERUPSI" in res
    assert "(1) Doc 1 (ID: 123)" in res
    assert "Context text" in res

def test_stitch_raw_prompt_with_rag():
    prev = "<start_of_turn>system\nsys<end_of_turn>\n<start_of_turn>user\nhi<end_of_turn>\n<start_of_turn>assistant\n<think>"
    thinking = "I need to search"
    res = stitch_raw_prompt_with_rag(prev, thinking, "context", [])
    assert res.startswith(prev)
    assert thinking in res
    assert "[SISTEM INTERUPSI" in res
