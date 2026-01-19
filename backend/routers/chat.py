from fastapi import APIRouter, HTTPException
from typing import Optional
import logging
from backend.models.chat import ChatRequest, ChatResponse, SearchRequest, SearchResponse
from backend.services.chat_service import ChatService
from backend.config.settings import settings


router = APIRouter(prefix="/api", tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint"""
    try:
        # Determine the model to use
        selected_model = request.model if request.npp else settings.PRIMARY_MODEL
        
        print(
            f"\n🚀 CHAT INCOMING | NPP: {request.npp} | Role: {request.role} | Attachments: {len(request.attachments)}"
        )

        # Initialize active file variable
        active_file = None
        final_message_to_ai = request.message  # Default to original message

        # --- 4. PANGGIL SMART CHAT ---
        reply, pdf_info, should_include_pdf = await ChatService.smart_chat_with_context(
            user_message=final_message_to_ai,
            active_file=active_file,
            mode=request.mode,
            model=selected_model,
            session_uuid=request.session_uuid,
            npp=request.npp,
            role=request.role or "GUEST"
        )

        # Generate initial session UUID if not provided
        session_uuid = request.session_uuid or str(request.npp or "temp") + str(hash(request.message))

        # Generate title for the conversation
        judul_baru = await ChatService.generate_judul_ai(request.message)

        # Return the response
        return ChatResponse(
            reply=reply,
            session_uuid=session_uuid,
            judul=judul_baru,
            pdf_info=pdf_info if (should_include_pdf and request.npp) else None,
            is_from_document=(should_include_pdf or active_file is not None),
            model_used=selected_model,
            attachments=request.attachments
        )

    except Exception as e:
        logging.error(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResponse)
async def search_pindad(request: SearchRequest):
    """Search endpoint for Pindad website"""
    try:
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query tidak boleh kosong")

        # In the converted version, we return a placeholder since the full implementation requires more components
        search_result = f"Fitur pencarian website untuk query '{request.query}' belum sepenuhnya diimplementasikan dalam versi FastAPI ini"

        return SearchResponse(
            status="success",
            query=request.query,
            result=search_result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available-models")
async def get_available_models():
    """Get list of available models"""
    models = [
        {"id": "qwen3:8b", "name": "Qwen 3 (8B)"},
        {"id": "qwen2.5:14b-instruct", "name": "Qwen 2.5-Instruct (14b)"},
        {"id": "qwen3-vl:8b", "name": "qwen 3 vl (8b)"},
        {"id": "llama3.1:8b", "name": "Llama 3.1 (8b)"},
    ]
    return {"status": "success", "data": models}


@router.get("/chat-history/{npp}")
async def get_chat_history(npp: str):
    """Get chat history for a specific user"""
    try:
        # Placeholder implementation - would connect to database in full implementation
        # For now, returning an empty list as this requires more complex database integration
        return {"status": "success", "data": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat-messages/{session_uuid}")
async def get_session_messages(session_uuid: str):
    """Get messages for a specific session"""
    try:
        # Placeholder implementation - would connect to database in full implementation
        # For now, returning an empty list as this requires more complex database integration
        return {"status": "success", "data": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))