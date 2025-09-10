from fastapi import APIRouter

from src.api.auth import router as auth_router
from src.api.chatbot import router as chatbot_router
from loguru import logger

api_router = APIRouter()

# Include routers
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(chatbot_router, prefix="/chatbot", tags=["chatbot"])
