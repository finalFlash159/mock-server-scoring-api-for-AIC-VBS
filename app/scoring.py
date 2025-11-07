"""
AIC 2025 Scoring Engine - Competition Rules

Formula:
  fT(t) = 1 - (t_submit / T_task)
  Score = max(0, P_base + (P_max - P_base) × fT(t) - k × P_penalty) × correctness_factor

Rules:
  - KIS/QA: Only score if 100% correct
  - TRAKE: 100% → factor 1.0, 50-99% → factor 0.5, <50% → factor 0.0
  - Exact match only (no tolerance)
"""
from typing import List, Tuple, Dict
from app.models import GroundTruth, NormalizedSubmission, ScoringParams
from app.utils import points_to_events


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


def check_exact_match(user_values: List[int], gt_events: List[Tuple[int, int]]) -> Tuple[int, int]:
    """
    Check exact match without tolerance
    
    Logic:
    - Each user_value must match EXACTLY with gt_start OR gt_end
    - One event can be matched by multiple user values
    - We count how many events have at least one match
    
    Args:
        user_values: User submitted values
        gt_events: Ground truth events [(start, end), ...]
    
    Returns:
        (matched_events, total_events)
    """
    total_events = len(gt_events)
    matched_events_set = set()
    
    for user_val in user_values:
        for idx, (gt_start, gt_end) in enumerate(gt_events):
            # Check exact match with start or end
            if user_val == gt_start or user_val == gt_end:
                matched_events_set.add(idx)
                break
    
    matched_events = len(matched_events_set)
    return matched_events, total_events


def calculate_correctness_factor(matched: int, total: int, task_type: str) -> float:
    """
    Calculate correctness factor based on task type
    
    Rules:
    - KIS/QA: Only get score if 100% correct (matched == total)
    - TRAKE: 
      - 100%: factor = 1.0 (full score)
      - 50-99%: factor = 0.5 (half score)
      - <50%: factor = 0.0 (no score)
    
    Args:
        matched: Number of matched events
        total: Total number of events
        task_type: "KIS" | "QA" | "TR"
    
    Returns:
        Correctness factor: 0.0 | 0.5 | 1.0
    """
    if total == 0:
        return 0.0
    
    percentage = (matched / total) * 100
    
    if task_type in ["KIS", "QA"]:
        # KIS/QA: Only score if 100%
        return 1.0 if percentage == 100 else 0.0
    
    elif task_type == "TR":
        # TRAKE: 100% → 1.0, 50-99% → 0.5, <50% → 0.0
        if percentage == 100:
            return 1.0
        elif percentage >= 50:
            return 0.5
        else:
            return 0.0
    
    return 0.0


def calculate_final_score(
    matched: int,
    total: int,
    task_type: str,
    t_submit: float,
    k: int,
    params: ScoringParams
) -> Dict:
    """
    Calculate final score using AIC 2025 formula
    
    Formula:
        fT(t) = 1 - (t_submit / T_task)
        base_score = P_base + (P_max - P_base) × fT(t)
        penalty = k × P_penalty
        score_before_correctness = max(0, base_score - penalty)
        final_score = score_before_correctness × correctness_factor
    
    Args:
        matched: Number of matched events
        total: Total number of events
        task_type: Task type (KIS/QA/TR)
        t_submit: Submission time (seconds)
        k: Number of wrong submissions before this
        params: ScoringParams object
    
    Returns:
        Dictionary with scoring details
    """
    # 1. Calculate time factor
    fT = calculate_time_factor(t_submit, params.time_limit)
    
    # 2. Calculate correctness factor
    correctness_factor = calculate_correctness_factor(matched, total, task_type)
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
        "correctness_factor": correctness_factor,
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
    Main scoring entry point
    
    Args:
        submission: Normalized user submission
        ground_truth: Ground truth data
        t_submit: Submission time (seconds since question started)
        k: Number of wrong submissions before this
        params: Scoring parameters
    
    Returns:
        Scoring result dictionary
    """
    # Parse GT events from points
    gt_events = points_to_events(ground_truth.points)
    
    # Check exact match
    matched, total = check_exact_match(submission.values, gt_events)
    
    # Calculate final score
    result = calculate_final_score(
        matched=matched,
        total=total,
        task_type=ground_truth.type,
        t_submit=t_submit,
        k=k,
        params=params
    )
    
    return result
