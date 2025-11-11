"""Team registration utilities"""
import uuid
from typing import Dict

from app import state
from app.core import session as session_core
from app.models import TeamSubmission


def _generate_team_ids(team_name: str) -> Dict[str, str]:
    slug = team_name.strip().lower().replace(' ', '-')[:20]
    unique_suffix = uuid.uuid4().hex[:6]
    team_id = f"team-{slug}-{unique_suffix}" if slug else f"team-{unique_suffix}"
    team_session_id = uuid.uuid4().hex
    return {"team_id": team_id, "team_session_id": team_session_id}


def register_team(team_name: str) -> Dict[str, str]:
    clean_name = team_name.strip()
    if not clean_name:
        raise ValueError("team_name required")

    ids = _generate_team_ids(clean_name)
    info = {
        "team_id": ids["team_id"],
        "team_name": clean_name,
        "team_session_id": ids["team_session_id"],
    }
    state.TEAM_REGISTRY[info["team_session_id"]] = info
    state.TEAM_INDEX[info["team_id"]] = info["team_session_id"]

    # Add placeholder submissions to active sessions
    session_core.add_team_to_active_sessions(
        team_id=info["team_id"],
        team_name=clean_name,
        team_session_id=info["team_session_id"],
    )

    return info


def get_team_by_session(team_session_id: str) -> Dict[str, str]:
    return state.TEAM_REGISTRY.get(team_session_id)


def get_team_name(team_id: str) -> str:
    session_id = state.TEAM_INDEX.get(team_id)
    if not session_id:
        return team_id
    return state.TEAM_REGISTRY.get(session_id, {}).get("team_name", team_id)
