"""
AIC 2025 Scoring Engine - Competition Rules

Formula:
  fT(t) = 1 - (t_submit / T_task)
  Score = max(0, P_base + (P_max - P_base) × fT(t) - k × P_penalty) × correctness_factor

Rules:
  - Tolerance: KIS/QA = ±2500ms, TR = ±12 frames
  - Score decreases linearly with distance from event center
  - 100% at center, 50% at tolerance boundary, 0% outside tolerance
  - KIS/QA: Only score if all events matched
  - TRAKE: 100% → factor 1.0, 50-99% → factor 0.5, <50% → factor 0.0
"""
from typing import List, Tuple, Dict
from app.models import GroundTruth, NormalizedSubmission, ScoringParams
from app.utils import points_to_events


# Tolerance settings
TOLERANCE_MS = 2500      # ±2.5 seconds for KIS/QA (milliseconds)
TOLERANCE_FRAMES = 12    # ±12 frames for TR


def calculate_time_factor(t_submit: float, t_task: float) -> float:
    """
    Calculate time factor fT(t)
    
    Formula: fT(t) = 1 - (t_submit / T_task)
    
    Args:
        t_submit: Submission time (seconds)
        t_task: Time limit (seconds)
    
    Returns:
        Time factor in range [0.0, 1.0]
    """
    if t_submit >= t_task:
        return 0.0
    return 1.0 - (t_submit / t_task)


def calculate_match_score(user_val: int, gt_start: int, gt_end: int, tolerance: int) -> float:
    """
    Calculate match score with tolerance and distance-based decay
    
    Logic:
    1. Calculate event center: center = (start + end) / 2
    2. Calculate distance from center: distance = |user_val - center|
    3. Define max allowed distance: max_dist = (end - start) / 2 + tolerance
    4. Score formula:
       - Outside tolerance (distance > max_dist): 0.0
       - At center (distance = 0): 1.0
       - Linear decay: score = 1.0 - 0.5 * (distance / max_dist)
       - Minimum score at tolerance boundary: 0.5
    
    Example (TR):
        GT: [10000, 10050], tolerance = 12
        Center: 10025
        Half_range: 25
        Max_dist: 25 + 12 = 37
        
        User = 10025 → distance = 0   → score = 1.0 (100%)
        User = 10037 → distance = 12  → score = 0.838 (~84%)
        User = 10050 → distance = 25  → score = 0.662 (~66%)
        User = 10062 → distance = 37  → score = 0.5 (50%, at boundary)
        User = 10063 → distance = 38  → score = 0.0 (outside tolerance)
    
    Args:
        user_val: User submitted value
        gt_start: Ground truth event start
        gt_end: Ground truth event end
        tolerance: Tolerance value (frames or ms)
    
    Returns:
        Score factor in range [0.0, 1.0]
    """
    # Calculate event center
    center = (gt_start + gt_end) / 2.0
    
    # Calculate distance from center
    distance = abs(user_val - center)
    
    # Calculate maximum allowed distance (half range + tolerance)
    half_range = (gt_end - gt_start) / 2.0
    max_distance = half_range + tolerance
    
    # Check if outside tolerance
    if distance > max_distance:
        return 0.0
    
    # Linear decay: 100% at center, 50% at tolerance boundary
    score_factor = 1.0 - 0.5 * (distance / max_distance)
    
    return score_factor


def check_match_with_tolerance(
    user_values: List[int], 
    gt_events: List[Tuple[int, int]], 
    tolerance: int
) -> Tuple[int, int, float]:
    """
    Check match with tolerance and calculate weighted correctness
    
    Logic:
    - For each user value, find best matching event (highest score)
    - Each event can only be matched once (greedy matching)
    - Calculate average match quality across all events
    
    Args:
        user_values: User submitted values
        gt_events: Ground truth events [(start, end), ...]
        tolerance: Tolerance value (frames or ms)
    
    Returns:
        (matched_events, total_events, average_match_quality)
    """
    total_events = len(gt_events)
    if total_events == 0:
        return 0, 0, 0.0
    
    # Track which events have been matched
    event_scores = {}  # event_idx -> best_score
    
    for user_val in user_values:
        best_event_idx = -1
        best_score = 0.0
        
        # Find best matching event for this user value
        for idx, (gt_start, gt_end) in enumerate(gt_events):
            score = calculate_match_score(user_val, gt_start, gt_end, tolerance)
            
            if score > 0 and score > best_score:
                best_event_idx = idx
                best_score = score
        
        # Record the best match (if any)
        if best_event_idx >= 0:
            # Keep the best score for this event
            if best_event_idx not in event_scores or best_score > event_scores[best_event_idx]:
                event_scores[best_event_idx] = best_score
    
    matched_events = len(event_scores)
    
    # Calculate average match quality
    if matched_events > 0:
        avg_quality = sum(event_scores.values()) / total_events
    else:
        avg_quality = 0.0
    
    return matched_events, total_events, avg_quality


def calculate_correctness_factor(
    matched: int, 
    total: int, 
    task_type: str, 
    avg_quality: float = 1.0
) -> float:
    """
    Calculate correctness factor based on task type and match quality
    
    Rules:
    - Match quality affects final score (from tolerance-based matching)
    - KIS/QA: Only get score if all events matched (matched == total)
    - TRAKE: 
      - 100%: factor = avg_quality (affected by distance from center)
      - 50-99%: factor = avg_quality * 0.5
      - <50%: factor = 0.0 (no score)
    
    Args:
        matched: Number of matched events
        total: Total number of events
        task_type: "KIS" | "QA" | "TR"
        avg_quality: Average match quality (0.5 to 1.0 from tolerance matching)
    
    Returns:
        Correctness factor: 0.0 to 1.0 (can be fractional with quality adjustment)
    """
    if total == 0:
        return 0.0
    
    percentage = (matched / total) * 100
    
    if task_type in ["KIS", "QA"]:
        # KIS/QA: Must match all events, but quality affects score
        if matched == total:
            return avg_quality  # Full match but adjusted by quality
        else:
            return 0.0  # Missing events → no score
    
    elif task_type == "TR":
        # TRAKE: Partial scoring allowed
        if percentage >= 100:
            return avg_quality  # Full match, adjusted by quality
        elif percentage >= 50:
            return avg_quality * 0.5  # Half score, adjusted by quality
        else:
            return 0.0  # Too few matches
    
    return 0.0


def calculate_final_score(
    matched: int,
    total: int,
    task_type: str,
    t_submit: float,
    k: int,
    params: ScoringParams,
    avg_quality: float = 1.0
) -> Dict:
    """
    Calculate final score using AIC 2025 formula with quality adjustment
    
    Formula:
        fT(t) = 1 - (t_submit / T_task)
        base_score = P_base + (P_max - P_base) × fT(t)
        penalty = k × P_penalty
        score_before_correctness = max(0, base_score - penalty)
        final_score = score_before_correctness × correctness_factor
        
        correctness_factor = affected by match quality (distance from event center)
    
    Args:
        matched: Number of matched events
        total: Total number of events
        task_type: Task type (KIS/QA/TR)
        t_submit: Submission time (seconds)
        k: Number of wrong submissions before this
        params: ScoringParams object
        avg_quality: Average match quality (0.5-1.0 from tolerance matching)
    
    Returns:
        Dictionary with scoring details
    """
    # 1. Calculate time factor
    fT = calculate_time_factor(t_submit, params.time_limit)
    
    # 2. Calculate correctness factor (with quality adjustment)
    correctness_factor = calculate_correctness_factor(matched, total, task_type, avg_quality)
    percentage = (matched / total * 100) if total > 0 else 0
    
    # 3. Calculate base score (before penalty and correctness)
    base_score = params.p_base + (params.p_max - params.p_base) * fT
    
    # 4. Calculate penalty
    penalty = k * params.p_penalty
    
    # 5. Calculate final score
    score_before_correctness = max(0, base_score - penalty)
    final_score = score_before_correctness * correctness_factor
    
    return {
        "score": round(final_score, 2),
        "correctness_factor": round(correctness_factor, 4),
        "match_quality": round(avg_quality, 4),
        "time_factor": round(fT, 4),
        "base_score": round(base_score, 2),
        "penalty": penalty,
        "percentage": round(percentage, 2),
        "matched_events": matched,
        "total_events": total
    }


def score_submission(
    submission: NormalizedSubmission,
    ground_truth: GroundTruth,
    t_submit: float,
    k: int,
    params: ScoringParams
) -> Dict:
    """
    Main scoring entry point with tolerance-based matching
    
    Args:
        submission: Normalized user submission
        ground_truth: Ground truth data
        t_submit: Submission time (seconds since question started)
        k: Number of wrong submissions before this
        params: Scoring parameters
    
    Returns:
        Scoring result dictionary
    """
    time_factor = calculate_time_factor(t_submit, params.time_limit)
    
    # Validate scene_id and video_id match - return 0 score if wrong
    if submission.scene_id != ground_truth.scene_id or submission.video_id != ground_truth.video_id:
        return {
            "score": 0,
            "correctness_factor": 0.0,
            "match_quality": 0.0,
            "matched_events": 0,
            "total_events": len(ground_truth.points) // 2,
            "percentage": 0.0,
            "time_factor": time_factor,
            "elapsed_time": t_submit,
            "wrong_attempts": k,
            "penalty": k * params.p_penalty,
            "message": f"Wrong video/scene. Expected: {ground_truth.scene_id}_{ground_truth.video_id}, Got: {submission.scene_id}_{submission.video_id}"
        }
    
    # For QA: Check answer text first (must match to continue)
    if ground_truth.type == "QA":
        if ground_truth.answer:  # If groundtruth has answer
            if not submission.answer:  # User didn't provide answer
                return {
                    "score": 0,
                    "correctness_factor": 0.0,
                    "match_quality": 0.0,
                    "matched_events": 0,
                    "total_events": len(ground_truth.points) // 2,
                    "percentage": 0.0,
                    "time_factor": time_factor,
                    "elapsed_time": t_submit,
                    "wrong_attempts": k,
                    "penalty": k * params.p_penalty,
                    "message": "QA answer text is required but not provided"
                }
            
            # STRICT comparison - no normalization, exact match only
            if submission.answer != ground_truth.answer:
                return {
                    "score": 0,
                    "correctness_factor": 0.0,
                    "match_quality": 0.0,
                    "matched_events": 0,
                    "total_events": len(ground_truth.points) // 2,
                    "percentage": 0.0,
                    "time_factor": time_factor,
                    "elapsed_time": t_submit,
                    "wrong_attempts": k,
                    "penalty": k * params.p_penalty,
                    "message": f"Wrong QA answer. Expected: {ground_truth.answer}, Got: {submission.answer}"
                }
    
    # Determine tolerance based on task type
    if ground_truth.type == "TR":
        tolerance = TOLERANCE_FRAMES  # ±12 frames
    else:  # KIS or QA
        tolerance = TOLERANCE_MS  # ±2500 ms (2.5 seconds)
    
    # Parse GT events from points
    gt_events = points_to_events(ground_truth.points)
    
    # Check match with tolerance (returns match quality)
    matched, total, avg_quality = check_match_with_tolerance(
        submission.values, 
        gt_events, 
        tolerance
    )
    
    # Calculate final score with quality adjustment
    result = calculate_final_score(
        matched=matched,
        total=total,
        task_type=ground_truth.type,
        t_submit=t_submit,
        k=k,
        params=params,
        avg_quality=avg_quality
    )
    
    return result
