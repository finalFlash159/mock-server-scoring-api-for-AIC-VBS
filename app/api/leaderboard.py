"""
Leaderboard and UI endpoints
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import os

from app import state
from app.core.session import get_question_session, active_questions


router = APIRouter(tags=["leaderboard"])


@router.get("/api/leaderboard-data")
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
    if not state.GT_TABLE:
        return {"questions": [], "teams": []}
    
    all_questions = sorted(state.GT_TABLE.keys())
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
        "active_question_id": active_question_id,
        "questions": all_questions,
        "teams": teams_list
    }


@router.get("/leaderboard-ui", response_class=HTMLResponse)
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


@router.get("/admin-dashboard", response_class=HTMLResponse)
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
