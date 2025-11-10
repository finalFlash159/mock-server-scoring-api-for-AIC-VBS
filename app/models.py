"""
Data models for scoring server
"""
from pydantic import BaseModel
from typing import List, Dict, Optional


class GroundTruth(BaseModel):
    """Ground truth model for a question"""
    stt: int
    type: str  # "KIS" | "QA" | "TR"
    scene_id: str
    video_id: str
    points: List[int]  # sorted ascending, must have even number of elements
    answer: Optional[str] = None  # For QA: correct answer (uppercase, no accents, no spaces)


class NormalizedSubmission(BaseModel):
    """Normalized submission from client"""
    question_id: int
    qtype: str  # "KIS" | "QA" | "TR"
    scene_id: str
    video_id: str
    values: List[int]  # KIS/QA: ms, TR: frame_id
    answer: Optional[str] = None  # For QA: user's answer text


class Config(BaseModel):
    """
    Configuration for scoring
    
    DEPRECATED: Most fields moved to ScoringParams.
    This model is kept for backward compatibility with /config endpoint only.
    """
    active_question_id: int
    # Competition parameters (use ScoringParams in new code)
    p_max: float = 100.0
    p_base: float = 50.0
    p_penalty: float = 10.0
    time_limit: int = 300
    buffer_time: int = 10


class ScoringParams(BaseModel):
    """Scoring parameters for AIC 2025 Competition"""
    p_max: float = 100.0      # Maximum score
    p_base: float = 50.0      # Base score at time limit
    p_penalty: float = 10.0   # Penalty per wrong submission
    time_limit: int = 300     # Time limit in seconds
    buffer_time: int = 10     # Buffer for network delay


class TeamSubmission(BaseModel):
    """Track one team's submissions for a question"""
    team_id: str
    question_id: int
    submit_times: List[float] = []        # Timestamps of all submissions
    wrong_count: int = 0                  # k = number of wrong submissions
    correct_count: int = 0                # Number of correct submissions (0 or 1)
    first_correct_time: Optional[float] = None
    final_score: Optional[float] = None
    is_completed: bool = False


class QuestionSession(BaseModel):
    """Server-controlled session for one question"""
    question_id: int
    start_time: float                     # Unix timestamp
    time_limit: int = 300                 # seconds
    buffer_time: int = 10                 # ±10s buffer
    is_active: bool = True
    team_submissions: Dict[str, TeamSubmission] = {}
    fake_teams: Dict[str, TeamSubmission] = {}  # Fake teams for leaderboard
    
    class Config:
        arbitrary_types_allowed = True
