from fastapi import APIRouter
from .sessions import router as sessions_router
from .stream import router as stream_router
from .attachments import router as attachments_router
from .feedback import router as feedback_router
from .artifacts import router as artifacts_router

router = APIRouter()

# Combine all sub-routers into the package router
router.include_router(sessions_router)
router.include_router(stream_router)
router.include_router(attachments_router)
router.include_router(feedback_router)
router.include_router(artifacts_router)
