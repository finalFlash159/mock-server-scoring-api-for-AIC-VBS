"""
FastAPI main application
AIC 2025 - Scoring Server for Multiple Events with Competition Mode
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional
import logging

from app.config import load_config, update_active_question
from app.groundtruth_loader import load_groundtruth
from app.normalizer import normalize_kis, normalize_qa, normalize_tr
from app.scoring import score_submission
from app.models import ScoringParams
from app.session import (
    start_question, stop_question, get_question_session,
    is_question_active, get_elapsed_time, get_remaining_time,
    get_team_submission, record_submission, get_question_leaderboard,
    get_all_sessions_status, reset_all_questions
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables
GT_TABLE = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Load ground truth
    global GT_TABLE
    try:
        GT_TABLE = load_groundtruth("data/groundtruth.csv")
        logger.info(f"✅ Server started with {len(GT_TABLE)} ground truth entries")
    except Exception as e:
        logger.error(f"❌ Failed to load ground truth: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Server shutting down")


# Create FastAPI app
app = FastAPI(
    title="AIC 2025 - Scoring Server",
    description="Mock scoring server for KIS, QA, TR tasks with multiple events",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware (allow all origins for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "AIC 2025 Scoring Server - Competition Mode",
        "version": "2.0.0",
        "total_questions": len(GT_TABLE) if GT_TABLE else 0
    }


# ==================== ADMIN ENDPOINTS ====================

@app.post("/admin/start-question")
async def admin_start_question(request: dict):
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
    
    # Check if question exists
    if question_id not in GT_TABLE:
        raise HTTPException(status_code=404, detail=f"Question {question_id} not found in groundtruth")
    
    # Start question session
    session = start_question(question_id, time_limit, buffer_time)
    
    # Update config
    update_active_question(question_id)
    
    return {
        "success": True,
        "question_id": question_id,
        "start_time": session.start_time,
        "time_limit": time_limit,
        "buffer_time": buffer_time,
        "message": f"Question {question_id} started. Teams can now submit."
    }


@app.post("/admin/stop-question")
async def admin_stop_question(request: dict):
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


@app.post("/admin/reset-all")
async def admin_reset_all():
    """Admin: Reset all sessions (DANGEROUS - testing only)"""
    count = reset_all_questions()
    return {
        "success": True,
        "deleted_sessions": count,
        "message": f"All sessions cleared. Deleted {count} questions."
    }


@app.get("/admin/sessions")
async def admin_list_sessions():
    """Admin: List all active sessions"""
    status = get_all_sessions_status()
    return {
        "total": len(status),
        "sessions": status
    }


# ==================== PUBLIC ENDPOINTS ====================

@app.get("/question/{question_id}/status")
async def get_question_status(question_id: int):
    """
    Public: Get question status
    
    Response includes timing info and participation stats
    """
    session = get_question_session(question_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Question {question_id} not started")
    
    return {
        "question_id": question_id,
        "is_active": is_question_active(question_id),
        "elapsed_time": round(get_elapsed_time(question_id), 2),
        "remaining_time": round(get_remaining_time(question_id), 2),
        "time_limit": session.time_limit,
        "buffer_time": session.buffer_time,
        "total_teams_submitted": len(session.team_submissions),
        "completed_teams": sum(1 for ts in session.team_submissions.values() if ts.is_completed)
    }


@app.get("/leaderboard")
async def get_leaderboard(question_id: Optional[int] = None):
    """
    Get leaderboard
    
    Query params:
        question_id: Specific question (required for now)
    """
    if not question_id:
        raise HTTPException(status_code=400, detail="question_id required")
    
    rankings = get_question_leaderboard(question_id)
    
    return {
        "question_id": question_id,
        "total_ranked": len(rankings),
        "rankings": rankings
    }


@app.get("/config")
async def get_config():
    """Get current active question configuration"""
    try:
        cfg = load_config("config/current_task.yaml")
        
        if cfg.active_question_id not in GT_TABLE:
            raise HTTPException(
                status_code=404, 
                detail=f"Active question {cfg.active_question_id} not found in ground truth"
            )
        
        gt = GT_TABLE[cfg.active_question_id]
        
        return {
            "active_question_id": cfg.active_question_id,
            "type": gt.type,
            "video_id": gt.video_id,
            "scene_id": gt.scene_id,
            "num_events": len(gt.points) // 2,
            "fps": cfg.fps,
            "max_score": cfg.max_score,
            "frame_tolerance": cfg.frame_tolerance,
            "aggregation": cfg.aggregation
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/submit")
async def submit(request: Request):
    """
    Submit answer (Competition Mode - No session_id needed)
    
    Request:
        {
            "team_id": "team_01",
            "question_id": 1,  # optional, uses active if not specified
            "answerSets": [...]
        }
    
    Response (CORRECT):
        {
            "success": true,
            "correctness": "full|partial",
            "score": 85.5,
            "detail": {...}
        }
    
    Response (INCORRECT):
        {
            "success": false,
            "correctness": "incorrect",
            "score": 0,
            "detail": {...}
        }
    """
    try:
        # Parse request body
        body = await request.json()
        team_id = body.get("team_id")
        question_id = body.get("question_id")
        answer_sets = body.get("answerSets")
        
        if not team_id:
            raise HTTPException(status_code=400, detail="team_id required")
        
        if not answer_sets:
            raise HTTPException(status_code=400, detail="answerSets required")
        
        # Get active question if not specified
        if not question_id:
            cfg = load_config()
            question_id = cfg.active_question_id
        
        # Check if question is active (includes buffer time check)
        if not is_question_active(question_id):
            elapsed = get_elapsed_time(question_id)
            session = get_question_session(question_id)
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "time_limit_exceeded",
                    "elapsed_time": round(elapsed, 2),
                    "time_limit": session.time_limit if session else 300,
                    "buffer_time": session.buffer_time if session else 10,
                    "message": "Time limit exceeded (including buffer)"
                }
            )
        
        # Check if team already completed this question
        team_sub = get_team_submission(question_id, team_id)
        if team_sub and team_sub.is_completed:
            return {
                "success": False,
                "error": "already_completed",
                "detail": {
                    "score": team_sub.final_score,
                    "completed_at": round(team_sub.first_correct_time - get_question_session(question_id).start_time, 2)
                },
                "message": f"You already completed this question with score {team_sub.final_score}"
            }
        
        # Get ground truth
        gt = GT_TABLE.get(question_id)
        if not gt:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        
        # Normalize submission
        try:
            if gt.type == "KIS":
                normalized = normalize_kis(answer_sets, gt.video_id, question_id)
            elif gt.type == "QA":
                normalized = normalize_qa(answer_sets, gt.video_id, question_id)
            elif gt.type == "TR":
                normalized = normalize_tr(answer_sets, gt.video_id, question_id)
            else:
                raise HTTPException(status_code=400, detail=f"Unknown task type: {gt.type}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid submission format: {str(e)}")
        
        # Get elapsed time and wrong count
        elapsed_time = get_elapsed_time(question_id)
        k = team_sub.wrong_count if team_sub else 0
        
        # Load scoring params
        cfg = load_config()
        params = ScoringParams(
            p_max=cfg.p_max,
            p_base=cfg.p_base,
            p_penalty=cfg.p_penalty,
            time_limit=cfg.time_limit,
            buffer_time=cfg.buffer_time
        )
        
        # Score submission
        result = score_submission(normalized, gt, elapsed_time, k, params)
        
        # Determine if correct
        is_correct = result["correctness_factor"] > 0
        
        # Record submission
        record_submission(question_id, team_id, is_correct, result["score"] if is_correct else None)
        
        # Build response
        if is_correct:
            correctness = "full" if result["correctness_factor"] == 1.0 else "partial"
            logger.info(
                f"✅ Team {team_id} | Q{question_id} ({gt.type}) | "
                f"Score: {result['score']:.2f} | Time: {elapsed_time:.2f}s | Wrong: {k}"
            )
            return {
                "success": True,
                "correctness": correctness,
                "score": result["score"],
                "detail": {
                    "matched_events": result["matched_events"],
                    "total_events": result["total_events"],
                    "percentage": result["percentage"],
                    "elapsed_time": round(elapsed_time, 2),
                    "time_factor": result["time_factor"],
                    "penalty": result["penalty"],
                    "wrong_count": k
                },
                "message": f"Correct! Final score: {result['score']}"
            }
        else:
            logger.info(
                f"❌ Team {team_id} | Q{question_id} ({gt.type}) | "
                f"Incorrect | Matched: {result['matched_events']}/{result['total_events']} | Wrong: {k+1}"
            )
            return {
                "success": False,
                "correctness": "incorrect",
                "score": 0,
                "detail": {
                    "matched_events": result["matched_events"],
                    "total_events": result["total_events"],
                    "percentage": result["percentage"],
                    "elapsed_time": round(elapsed_time, 2),
                    "remaining_time": round(get_remaining_time(question_id), 2),
                    "wrong_count": k + 1
                },
                "message": "Incorrect. Try again!"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in submit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/questions")
async def list_questions():
    """List all available questions"""
    if not GT_TABLE:
        return {"questions": []}
    
    questions = []
    for qid, gt in sorted(GT_TABLE.items()):
        questions.append({
            "id": qid,
            "type": gt.type,
            "video_id": gt.video_id,
            "scene_id": gt.scene_id,
            "num_events": len(gt.points) // 2
        })
    
    return {"questions": questions}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
