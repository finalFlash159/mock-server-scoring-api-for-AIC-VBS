"""
Configuration endpoints
"""
import logging
from fastapi import APIRouter, HTTPException

from app import state
from app.core.session import (
    get_current_active_question_id,
    get_question_session,
    is_question_active,
)


logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])


@router.get("/config")
async def get_config():
    """Get current active question configuration and all questions info"""
    if state.GT_TABLE is None:
        raise HTTPException(status_code=500, detail="Ground truth table is not loaded")
    
    active_question_id = get_current_active_question_id()
    active_gt = state.GT_TABLE.get(active_question_id) if active_question_id else None
    active_session = get_question_session(active_question_id) if active_question_id else None
    
    base_params = state.SCORING_PARAMS
    
    return {
        "active_question_id": active_question_id,
        "active_question": {
            "type": active_gt.type,
            "video_id": active_gt.video_id,
            "scene_id": active_gt.scene_id,
            "num_events": len(active_gt.points) // 2,
            "time_limit": active_session.time_limit if active_session else base_params.time_limit,
            "buffer_time": active_session.buffer_time if active_session else base_params.buffer_time,
            "is_active": is_question_active(active_question_id) if active_question_id else False,
        } if active_gt else None,
        "scoring": base_params.dict(),
        "questions": {
            qid: {
                "type": gt.type,
                "video_id": gt.video_id,
                "scene_id": gt.scene_id,
                "points": gt.points,
                "num_events": len(gt.points) // 2,
                "default_time_limit": base_params.time_limit,
                "default_buffer_time": base_params.buffer_time,
            }
            for qid, gt in state.GT_TABLE.items()
        }
    }
