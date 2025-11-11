"""Team registration endpoints"""
from fastapi import APIRouter, HTTPException

from app.services.team_registry import register_team


router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("/register")
async def register(payload: dict):
    team_name = payload.get("team_name") or payload.get("teamName")
    if not team_name:
        raise HTTPException(status_code=400, detail="team_name is required")
    try:
        info = register_team(team_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "team_id": info["team_id"],
        "team_name": info["team_name"],
        "team_session_id": info["team_session_id"],
        "message": "Team registered. Keep your teamSessionId secret."
    }
