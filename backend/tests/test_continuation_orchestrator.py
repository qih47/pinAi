import pytest
from backend.app.services.pipeline.continuation_orchestrator import ContinuationState

def test_state_initialization():
    state = ContinuationState(session_uuid="123")
    assert state.session_uuid == "123"
    assert state.phase == "analysis"

def test_set_thinking_content():
    state = ContinuationState(session_uuid="123")
    state.append_thinking("think")
    assert state.accumulated_thinking == "think"

def test_mark_phase_complete():
    state = ContinuationState(session_uuid="123")
    state.mark_rag_complete()
    assert state.phase == "response"
    assert state.rag_data_injected is True
