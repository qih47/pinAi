import pytest
from backend.app.services.pipeline.ollama_raw_client import _build_ollama_request_payload, RawGenerateClient

def test_build_payload():
    payload = _build_ollama_request_payload("gemma4", "prompt", 0.5, 100, 200)
    assert payload["model"] == "gemma4"
    assert payload["raw"] is True
    assert payload["prompt"] == "prompt"
    assert payload["options"]["temperature"] == 0.5

@pytest.mark.asyncio
async def test_client_init():
    client = RawGenerateClient("http://localhost", 5)
    async_client = await client.get_client()
    assert async_client is not None
    await client.close()
