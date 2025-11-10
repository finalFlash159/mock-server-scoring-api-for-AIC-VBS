"""
Configuration endpoints
"""
from fastapi import APIRouter, HTTPException
import logging

from app import state
from app.deprecated.config import load_config


logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])


@router.get("/config")
async def get_config():
    """Get current active question configuration and all questions info"""
    try:
        cfg = load_config("config/current_task.yaml")
        
        if state.GT_TABLE is None or cfg.active_question_id not in state.GT_TABLE:
            raise HTTPException(
                status_code=404, 
                detail=f"Active question {cfg.active_question_id} not found in ground truth"
            )
        
        gt = state.GT_TABLE[cfg.active_question_id]
        
        return {
            "active_question_id": cfg.active_question_id,
            "type": gt.type,
            "video_id": gt.video_id,
            "scene_id": gt.scene_id,
            "num_events": len(gt.points) // 2,
            # Scoring parameters
            "p_max": cfg.p_max,
            "p_base": cfg.p_base,
            "p_penalty": cfg.p_penalty,
            "time_limit": cfg.time_limit,
            "buffer_time": cfg.buffer_time,
            # All questions info for admin dashboard
            "questions": {
                qid: {
                    "type": q.type,
                    "video_id": q.video_id,
                    "scene_id": q.scene_id,
                    "points": "-".join(map(str, q.points)),
                    "num_events": len(q.points) // 2,
                    # Default time settings
                    "default_time_limit": cfg.time_limit,
                    "default_buffer_time": cfg.buffer_time
                }
                for qid, q in state.GT_TABLE.items()
            }
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
