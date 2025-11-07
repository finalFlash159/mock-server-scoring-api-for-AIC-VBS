"""
FastAPI main application
AIC 2025 - Scoring Server for Multiple Events with Competition Mode
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from typing import Optional
import logging
import os

from app.config import load_config, update_active_question
from app.groundtruth_loader import load_groundtruth
from app.normalizer import normalize_kis, normalize_qa, normalize_tr
from app.scoring import score_submission
from app.models import ScoringParams
from app.session import (
    start_question, stop_question, get_question_session,
    is_question_active, get_elapsed_time, get_remaining_time,
    get_team_submission, record_submission, get_question_leaderboard,
    get_all_sessions_status, reset_all_questions, active_questions
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
            "aggregation": cfg.aggregation,
            # Add all questions info for admin dashboard
            "questions": {
                qid: {
                    "type": q.type,
                    "video_id": q.video_id,
                    "scene_id": q.scene_id,
                    "points": "-".join(map(str, q.points)),
                    "num_events": len(q.points) // 2,
                    # Default time settings based on question type
                    "default_time_limit": 300,  # 5 minutes default
                    "default_buffer_time": 10   # 10 seconds buffer
                }
                for qid, q in GT_TABLE.items()
            }
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
    body = None
    try:
        # Parse request body
        body = await request.json()
        
        # Log incoming request
        client_ip = request.client.host if request.client else "unknown"
        logger.info(f"📥 Submission from {client_ip} | Body: {body}")
        
        answer_sets = body.get("answerSets")
        
        if not answer_sets:
            raise HTTPException(status_code=400, detail="answerSets required")
        
        # SERVER AUTO-HANDLES: team_id always mapped to "0THING2LOSE"
        team_id = "0THING2LOSE"
        
        # SERVER AUTO-HANDLES: question_id from active question
        cfg = load_config()
        question_id = cfg.active_question_id
        
        if not question_id:
            raise HTTPException(
                status_code=400, 
                detail="No active question. Admin must start a question first."
            )
        
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
                normalized = normalize_kis(body, question_id)
            elif gt.type == "QA":
                normalized = normalize_qa(body, question_id)
            elif gt.type == "TR":
                normalized = normalize_tr(body, question_id)
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
        # Log detailed error with request body
        client_ip = request.client.host if request.client else "unknown"
        logger.error(
            f"❌ ERROR in /submit from {client_ip}\n"
            f"Request Body: {body}\n"
            f"Error: {str(e)}\n"
            f"Error Type: {type(e).__name__}",
            exc_info=True
        )
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


# ==================== LEADERBOARD UI ENDPOINTS ====================

@app.get("/api/leaderboard-data")
async def get_leaderboard_data():
    """
    Get comprehensive leaderboard data for all questions
    
    Returns data for rendering leaderboard UI with:
    - All questions
    - All teams (real + fake)
    - Submission counts (✅ correct, ❌ wrong)
    - Scores per question
    - Total scores
    """
    if not GT_TABLE:
        return {"questions": [], "teams": []}
    
    all_questions = sorted(GT_TABLE.keys())
    teams_data = {}
    
    # Collect data from all sessions
    for q_id in all_questions:
        session = get_question_session(q_id)
        if not session:
            continue
        
        # Merge real teams + fake teams
        all_teams = {**session.team_submissions, **session.fake_teams}
        
        for team_id, team_sub in all_teams.items():
            if team_id not in teams_data:
                teams_data[team_id] = {
                    "team_name": team_id,
                    "is_real": (team_id == "0THING2LOSE"),
                    "questions": {},
                    "total_score": 0
                }
            
            # Add question data
            teams_data[team_id]["questions"][q_id] = {
                "wrong_count": team_sub.wrong_count,
                "correct_count": team_sub.correct_count,
                "score": round(team_sub.final_score, 1) if team_sub.final_score else 0
            }
            
            # Accumulate total score
            teams_data[team_id]["total_score"] += (team_sub.final_score or 0)
    
    # Sort teams by total score (descending)
    teams_list = sorted(
        teams_data.values(),
        key=lambda x: x["total_score"],
        reverse=True
    )
    
    # Round total scores
    for team in teams_list:
        team["total_score"] = round(team["total_score"], 1)
    
    # Detect active question (most recent active session)
    active_question_id = None
    for q_id in sorted(active_questions.keys(), reverse=True):
        session = active_questions.get(q_id)
        if session and session.is_active:
            active_question_id = q_id
            break
    
    return {
        "active_question_id": active_question_id,  # NEW: For real-time view
        "questions": all_questions,
        "teams": teams_list
    }


@app.get("/leaderboard-ui", response_class=HTMLResponse)
async def leaderboard_ui():
    """Serve the leaderboard HTML page"""
    html_path = "static/leaderboard.html"
    
    if not os.path.exists(html_path):
        return HTMLResponse(
            content="<h1>Leaderboard UI not found</h1><p>Please create static/leaderboard.html</p>",
            status_code=404
        )
    
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/admin-dashboard", response_class=HTMLResponse)
async def admin_dashboard():
    """Serve the admin dashboard HTML page"""
    html_path = "static/admin.html"
    
    if not os.path.exists(html_path):
        return HTMLResponse(
            content="<h1>Admin Dashboard not found</h1><p>Please create static/admin.html</p>",
            status_code=404
        )
    
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# Mount static files directory
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
