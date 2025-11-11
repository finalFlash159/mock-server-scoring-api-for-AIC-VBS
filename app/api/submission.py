"""
Submission endpoint for team answers
"""
from fastapi import APIRouter, HTTPException, Request
import logging

from app import state
from app.core.normalizer import normalize_kis, normalize_qa, normalize_tr
from app.core.scoring import score_submission
from app.core.session import (
    is_question_active, get_elapsed_time, get_remaining_time,
    get_team_submission, record_submission, get_question_session,
    get_current_active_question_id
)
from app.models import TeamSubmission
from app.services.team_registry import get_team_by_session


router = APIRouter(tags=["submission"])
logger = logging.getLogger(__name__)


@router.post("/submit")
async def submit_answer(request: Request):
    """
    Submit answer (Competition Mode - Auto team_id and question_id)
    
    Request:
        {
            "teamSessionId": "<token>",
            "answerSets": [...]  # Format depends on task type (KIS/QA/TR)
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
        
        team_session_id = body.get("teamSessionId") or body.get("team_session_id")
        if not team_session_id:
            raise HTTPException(status_code=400, detail="teamSessionId is required")

        team_info = get_team_by_session(team_session_id)
        if not team_info:
            raise HTTPException(status_code=404, detail="Invalid teamSessionId")
        team_id = team_info["team_id"]
        team_name = team_info["team_name"]
        
        # SERVER AUTO-HANDLES: question_id from active session
        question_id = get_current_active_question_id()
        
        if not question_id:
            raise HTTPException(
                status_code=400, 
                detail="No active question. Admin must start a question first."
            )
        
        session = get_question_session(question_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Question {question_id} session not found")
        
        # Check if question is active (includes buffer time check)
        if not is_question_active(question_id):
            elapsed = get_elapsed_time(question_id)
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
                    "completed_at": round(team_sub.first_correct_time - session.start_time, 2) if team_sub.first_correct_time else None
                },
                "message": f"You already completed this question with score {team_sub.final_score}"
            }
        
        session = get_question_session(question_id)
        if not session:
            raise HTTPException(status_code=404, detail="Question session not found")
        if team_sub is None:
            session.team_submissions[team_id] = TeamSubmission(
                team_id=team_id,
                team_name=team_name,
                team_session_id=team_session_id,
                question_id=question_id
            )
            team_sub = session.team_submissions[team_id]

        # Get ground truth from state
        gt = state.GT_TABLE.get(question_id) if state.GT_TABLE else None
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
            logger.error(f"❌ Normalization error for Q{question_id} ({gt.type}): {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid submission format: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Unexpected error normalizing Q{question_id} ({gt.type}): {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error processing submission: {str(e)}")
        
        # Get elapsed time and wrong count
        elapsed_time = get_elapsed_time(question_id)
        k = team_sub.wrong_count if team_sub else 0
        
        # Load scoring params
        base_params = state.SCORING_PARAMS
        params = base_params.copy(
            update={
                "time_limit": session.time_limit,
                "buffer_time": session.buffer_time
            }
        )
        
        # Score submission
        result = score_submission(normalized, gt, elapsed_time, k, params)
        
        # Determine if correct
        is_correct = result["correctness_factor"] > 0
        
        # Record submission
        record_submission(
            question_id,
            team_id,
            is_correct,
            result["score"] if is_correct else None,
            team_name=team_name,
            team_session_id=team_session_id
        )
        
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


@router.get("/questions")
async def list_questions():
    """List all available questions"""
    if not state.GT_TABLE:
        return {"questions": []}
    
    questions = []
    for qid, gt in sorted(state.GT_TABLE.items()):
        questions.append({
            "id": qid,
            "type": gt.type,
            "video_id": gt.video_id,
            "scene_id": gt.scene_id,
            "num_events": len(gt.points) // 2
        })
    
    return {"questions": questions}
