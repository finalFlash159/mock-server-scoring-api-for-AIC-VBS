"""
Health check and system status endpoints
"""
from fastapi import APIRouter
from app import state


router = APIRouter(tags=["health"])


@router.get("/")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "AIC 2025 Scoring Server - Competition Mode",
        "version": "2.0.0",
        "total_questions": len(state.GT_TABLE) if state.GT_TABLE else 0
    }
