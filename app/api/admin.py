"""
Admin endpoints for question management
"""
from fastapi import APIRouter, HTTPException
import logging

from app import state
from app.core.session import (
    start_question, stop_question, get_question_session,
    get_all_sessions_status, reset_all_questions
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/start-question")
async def start_question_endpoint(request: dict):
    """
    Admin: Start a question with timer
    
    Request:
        {
            "question_id": 1,
            "time_limit": 300,  # optional, default 300
            "buffer_time": 10   # optional, default 10
        }
    """
    question_id = request.get("question_id")
    time_limit = request.get("time_limit", 300)
    buffer_time = request.get("buffer_time", 10)
    
    if not question_id:
        raise HTTPException(status_code=400, detail="question_id required")
    
    # Check if question exists in GT_TABLE
    if state.GT_TABLE is None or question_id not in state.GT_TABLE:
        raise HTTPException(status_code=404, detail=f"Question {question_id} not found in groundtruth")
    
    # Start question session
    session = start_question(question_id, time_limit, buffer_time)
    
    return {
        "success": True,
        "question_id": question_id,
        "start_time": session.start_time,
        "time_limit": time_limit,
        "buffer_time": buffer_time,
        "message": f"Question {question_id} started. Teams can now submit."
    }


@router.post("/stop-question")
async def stop_question_endpoint(request: dict):
    """
    Admin: Stop a question immediately
    
    Request:
        {"question_id": 1}
    """
    question_id = request.get("question_id")
    
    if not question_id:
        raise HTTPException(status_code=400, detail="question_id required")
    
    session = get_question_session(question_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Question {question_id} not active")
    
    stop_question(question_id)
    
    completed = sum(1 for ts in session.team_submissions.values() if ts.is_completed)
    total_subs = sum(len(ts.submit_times) for ts in session.team_submissions.values())
    
    return {
        "success": True,
        "question_id": question_id,
        "total_submissions": total_subs,
        "completed_teams": completed,
        "message": f"Question {question_id} stopped."
    }


@router.get("/sessions")
async def get_sessions():
    """Get status of all question sessions"""
    sessions = get_all_sessions_status()
    
    return {
        "sessions": sessions,
        "total_active": len([s for s in sessions if s["is_active"]])
    }


@router.post("/reset")
async def reset_sessions():
    """Reset all question sessions"""
    reset_all_questions()
    
    return {
        "success": True,
        "message": "All question sessions reset"
    }
