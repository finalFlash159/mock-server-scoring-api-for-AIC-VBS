"""
Scoring functions for multiple events
"""
from typing import List, Tuple, Dict, Any
from app.models import NormalizedSubmission, GroundTruth, Config
from app.utils import points_to_events


def score_event_ms(user_ms: int, gt_start_ms: int, gt_end_ms: int, cfg: Config) -> float:
    """
    Score a single event for KIS/QA (using milliseconds)
    
    Scoring logic:
    - Tolerance applies to both ends of the event range
    - Valid range: [start - tolerance, end + tolerance]
    - Score decreases from 100 at midpoint to 0 at range boundaries
    
    Args:
        user_ms: User submitted millisecond value
        gt_start_ms: Ground truth event start (ms)
        gt_end_ms: Ground truth event end (ms)
        cfg: Configuration object
        
    Returns:
        Score for this event (0.0 to max_score)
    """
    # Convert tolerance to milliseconds
    frame_ms = 1000.0 / cfg.fps
    tolerance_ms = cfg.frame_tolerance * frame_ms
    
    # Calculate valid range (tolerance applies to both ends)
    range_start = gt_start_ms - tolerance_ms
    range_end = gt_end_ms + tolerance_ms
    
    # Check if user value is within valid range
    if user_ms < range_start or user_ms > range_end:
        return 0.0
    
    # Calculate midpoint and distance
    mid = (gt_start_ms + gt_end_ms) / 2.0
    dist_ms = abs(user_ms - mid)
    dist_frames = dist_ms / frame_ms
    
    # Calculate score with decay from midpoint
    score = cfg.max_score - (dist_frames * cfg.decay_per_frame)
    
    return max(score, 0.0)


def score_event_frame(user_frame: int, gt_start_f: int, gt_end_f: int, cfg: Config) -> float:
    """
    Score a single event for TR (using frame_id directly)
    
    Scoring logic:
    - Tolerance applies to both ends of the event range
    - Valid range: [start - tolerance, end + tolerance]
    - Score decreases from 100 at midpoint to 0 at range boundaries
    
    Args:
        user_frame: User submitted frame_id
        gt_start_f: Ground truth event start (frame_id)
        gt_end_f: Ground truth event end (frame_id)
        cfg: Configuration object
        
    Returns:
        Score for this event (0.0 to max_score)
    """
    # Calculate valid range (tolerance applies to both ends)
    range_start = gt_start_f - cfg.frame_tolerance
    range_end = gt_end_f + cfg.frame_tolerance
    
    # Check if user value is within valid range
    if user_frame < range_start or user_frame > range_end:
        return 0.0
    
    # Calculate midpoint and distance
    mid = (gt_start_f + gt_end_f) / 2.0
    dist_frames = abs(user_frame - mid)
    
    # Calculate score with decay from midpoint
    score = cfg.max_score - (dist_frames * cfg.decay_per_frame)
    
    return max(score, 0.0)


def score_submission(
    sub: NormalizedSubmission, 
    gt: GroundTruth, 
    cfg: Config
) -> Tuple[float, Dict[str, Any]]:
    """
    Score a complete submission with multiple events
    
    Args:
        sub: Normalized submission from user
        gt: Ground truth for the question
        cfg: Configuration object
        
    Returns:
        Tuple of (final_score, detail_dict)
        detail_dict contains:
            - per_event_scores: List of scores for each event
            - gt_events: List of ground truth event pairs
            - user_values: List of user submitted values
            - aggregation_method: Method used to aggregate scores
    """
    # Convert ground truth points to events
    gt_events = points_to_events(gt.points)
    user_values = sub.values
    
    per_event_scores = []
    
    # Score each event in order
    for idx, gt_evt in enumerate(gt_events):
        gt_start, gt_end = gt_evt
        
        # Check if user submitted this event
        if idx < len(user_values):
            user_val = user_values[idx]
        else:
            # User didn't submit this event -> 0 score
            per_event_scores.append(0.0)
            continue
        
        # Score based on task type
        if sub.qtype in ("KIS", "QA"):
            # KIS/QA use milliseconds
            s = score_event_ms(user_val, gt_start, gt_end, cfg)
        else:  # TR
            # TR uses frame_id
            s = score_event_frame(user_val, gt_start, gt_end, cfg)
        
        per_event_scores.append(s)
    
    # Aggregate scores based on configuration
    if not per_event_scores:
        final_score = 0.0
    elif cfg.aggregation == "mean":
        final_score = sum(per_event_scores) / len(per_event_scores)
    elif cfg.aggregation == "sum":
        final_score = sum(per_event_scores)
    elif cfg.aggregation == "min":
        final_score = min(per_event_scores)
    else:
        # Default to mean
        final_score = sum(per_event_scores) / len(per_event_scores)
    
    detail = {
        "per_event_scores": per_event_scores,
        "gt_events": gt_events,
        "user_values": user_values,
        "aggregation_method": cfg.aggregation,
        "num_gt_events": len(gt_events),
        "num_user_events": len(user_values)
    }
    
    return final_score, detail
