"""
Data models for scoring server
"""
from pydantic import BaseModel
from typing import List


class GroundTruth(BaseModel):
    """Ground truth model for a question"""
    stt: int
    type: str  # "KIS" | "QA" | "TR"
    scene_id: str
    video_id: str
    points: List[int]  # sorted ascending, must have even number of elements


class NormalizedSubmission(BaseModel):
    """Normalized submission from client"""
    question_id: int
    qtype: str  # "KIS" | "QA" | "TR"
    video_id: str
    values: List[int]  # KIS/QA: ms, TR: frame_id


class Config(BaseModel):
    """Configuration for scoring"""
    active_question_id: int
    fps: float = 25.0
    max_score: float = 100.0
    frame_tolerance: float = 12.0
    decay_per_frame: float = 1.0
    aggregation: str = "mean"  # "mean" | "min" | "sum"
