"""
FastAPI main application
AIC 2025 - Scoring Server for Multiple Events with Competition Mode

Modular architecture with separated API routers in app/api/:
- health.py: Health check and system status
- admin.py: Admin management (start/stop questions, sessions, reset)
- submission.py: Team submission and question listing
- leaderboard.py: Leaderboard data and UI serving
- config.py: Configuration retrieval

All routers access shared state via app.state module.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os

from app import state
from app.core.groundtruth import load_groundtruth

# Import all API routers
from app.api import health, admin, submission, leaderboard
from app.api import config as config_router


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Load ground truth into global state
    try:
        state.GT_TABLE = load_groundtruth("data/groundtruth.csv")
        logger.info(f"✅ Server started with {len(state.GT_TABLE)} ground truth entries")
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
    version="2.0.0",
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


# ==================== INCLUDE ROUTERS ====================

# Health check (GET /)
app.include_router(health.router)

# Admin endpoints (POST /admin/start-question, etc.)
app.include_router(admin.router)

# Submission endpoints (POST /submit, GET /questions)
app.include_router(submission.router)

# Leaderboard endpoints (GET /api/leaderboard-data, /leaderboard-ui, /admin-dashboard)
app.include_router(leaderboard.router)

# Config endpoint (GET /config)
app.include_router(config_router.router)


# ==================== STATIC FILES ====================

# Mount static files directory for CSS/JS/images
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ==================== RUN SERVER ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
