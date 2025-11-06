"""
FastAPI main application
AIC 2025 - Scoring Server for Multiple Events
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import load_config
from app.groundtruth_loader import load_groundtruth
from app.normalizer import normalize_kis, normalize_qa, normalize_tr
from app.scoring import score_submission

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
        "message": "AIC 2025 Scoring Server",
        "version": "1.0.0",
        "total_questions": len(GT_TABLE) if GT_TABLE else 0
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
    Submit answer for scoring
    
    Request body format depends on task type:
    
    KIS:
    {
        "answerSets": [{
            "answers": [
                {"mediaItemName": "V017", "start": "4999", "end": "4999"},
                {"mediaItemName": "V017", "start": "5049", "end": "5049"}
            ]
        }]
    }
    
    QA:
    {
        "answerSets": [{
            "answers": [
                {"text": "QA-ANSWER1-V017-4999"},
                {"text": "QA-ANSWER2-V017-5049"}
            ]
        }]
    }
    
    TR:
    {
        "answerSets": [{
            "answers": [
                {"text": "TR-V017-499"},
                {"text": "TR-V017-549"}
            ]
        }]
    }
    """
    try:
        # Parse request body
        body = await request.json()
        
        # Load current config
        cfg = load_config("config/current_task.yaml")
        qid = cfg.active_question_id
        
        # Check if question exists
        if qid not in GT_TABLE:
            raise HTTPException(
                status_code=400, 
                detail=f"Active question {qid} not found in ground truth"
            )
        
        gt = GT_TABLE[qid]
        
        # Normalize submission based on task type
        try:
            if gt.type == "KIS":
                sub = normalize_kis(body, qid)
            elif gt.type == "QA":
                sub = normalize_qa(body, qid)
            elif gt.type in ("TR", "TRAKE"):
                sub = normalize_tr(body, qid)
            else:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported task type: {gt.type}"
                )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid submission format: {str(e)}")
        
        # Validate video_id matches
        if sub.video_id != gt.video_id:
            raise HTTPException(
                status_code=400,
                detail=f"Video ID mismatch: submitted {sub.video_id}, expected {gt.video_id}"
            )
        
        # Score the submission
        final_score, detail = score_submission(sub, gt, cfg)
        
        # Log submission
        logger.info(
            f"Q{qid} ({gt.type}) | Video: {sub.video_id} | "
            f"Events: {len(sub.values)}/{len(gt.points)//2} | "
            f"Score: {final_score:.2f}"
        )
        
        # Return result
        return {
            "success": True,
            "question_id": qid,
            "type": gt.type,
            "video_id": sub.video_id,
            "score": round(final_score, 2),
            "detail": {
                "per_event_scores": [round(s, 2) for s in detail["per_event_scores"]],
                "gt_events": detail["gt_events"],
                "user_values": detail["user_values"],
                "aggregation_method": detail["aggregation_method"],
                "num_gt_events": detail["num_gt_events"],
                "num_user_events": detail["num_user_events"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
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
