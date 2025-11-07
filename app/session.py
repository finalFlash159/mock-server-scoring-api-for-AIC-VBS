"""
Question-level session management for AIC 2025 Competition
Server-controlled timing with per-team submission tracking
"""
import time
from typing import Dict, Optional, List
from app.models import QuestionSession, TeamSubmission


# Global storage: question_id → QuestionSession
active_questions: Dict[int, QuestionSession] = {}


def initialize_fake_teams(question_id: int, time_limit: int) -> Dict[str, TeamSubmission]:
    """
    Initialize fake teams with random submissions for leaderboard simulation
    
    Args:
        question_id: Question ID
        time_limit: Time limit for the question
        
    Returns:
        Dictionary of fake team submissions
    """
    from app.fake_teams import (
        generate_fake_team_names,
        generate_weighted_score,
        generate_submission_attempts,
        generate_random_submit_time
    )
    
    fake_teams = {}
    team_names = generate_fake_team_names(15)  # Generate 15 fake teams
    current_time = time.time()
    
    for name in team_names:
        wrong_count, correct_count = generate_submission_attempts()
        
        # Generate submission time if team submitted
        submit_time = None
        if correct_count > 0:
            elapsed = generate_random_submit_time(time_limit)
            submit_time = current_time + elapsed
        
        # Generate score based on whether team completed
        score = 0.0
        if correct_count > 0:
            score = generate_weighted_score()
        
        team_sub = TeamSubmission(
            team_id=name,
            question_id=question_id,
            wrong_count=wrong_count,
            correct_count=correct_count,
            is_completed=(correct_count > 0),
            final_score=score if correct_count > 0 else None,
            first_correct_time=submit_time
        )
        fake_teams[name] = team_sub
    
    return fake_teams


def start_question(question_id: int, time_limit: int = 300, buffer_time: int = 10) -> QuestionSession:
    """
    Start a question session (admin-controlled)
    
    Args:
        question_id: Question ID
        time_limit: Time limit in seconds (default 300 = 5 min)
        buffer_time: Buffer time for network delay (default ±10s)
    
    Returns:
        QuestionSession object
    """
    session = QuestionSession(
        question_id=question_id,
        start_time=time.time(),
        time_limit=time_limit,
        buffer_time=buffer_time,
        is_active=True,
        team_submissions={},
        fake_teams=initialize_fake_teams(question_id, time_limit)
    )
    active_questions[question_id] = session
    print(f"✅ Question {question_id} started at {session.start_time}")
    print(f"✅ Generated {len(session.fake_teams)} fake teams for leaderboard")
    return session


def get_question_session(question_id: int) -> Optional[QuestionSession]:
    """Get active question session"""
    return active_questions.get(question_id)


def is_question_active(question_id: int) -> bool:
    """
    Check if question is currently accepting submissions
    
    Returns True if:
    - Question session exists
    - is_active = True
    - elapsed_time <= time_limit + buffer_time
    """
    session = active_questions.get(question_id)
    if not session or not session.is_active:
        return False
    
    elapsed = time.time() - session.start_time
    return elapsed <= (session.time_limit + session.buffer_time)


def get_elapsed_time(question_id: int) -> float:
    """Get elapsed time since question started (seconds)"""
    session = active_questions.get(question_id)
    if not session:
        return 0.0
    return time.time() - session.start_time


def get_remaining_time(question_id: int) -> float:
    """Get remaining time (excluding buffer, seconds)"""
    session = active_questions.get(question_id)
    if not session:
        return 0.0
    
    elapsed = get_elapsed_time(question_id)
    remaining = session.time_limit - elapsed
    return max(0.0, remaining)


def get_team_submission(question_id: int, team_id: str) -> Optional[TeamSubmission]:
    """Get team's submission record for a question"""
    session = active_questions.get(question_id)
    if not session:
        return None
    return session.team_submissions.get(team_id)


def record_submission(
    question_id: int,
    team_id: str,
    is_correct: bool,
    score: Optional[float] = None
) -> TeamSubmission:
    """
    Record a team's submission
    
    Args:
        question_id: Question ID
        team_id: Team ID
        is_correct: Whether submission is correct
        score: Final score if correct
    
    Returns:
        Updated TeamSubmission
    """
    session = active_questions[question_id]
    
    # Get or create team submission record
    if team_id not in session.team_submissions:
        session.team_submissions[team_id] = TeamSubmission(
            team_id=team_id,
            question_id=question_id,
            submit_times=[],
            wrong_count=0,
            correct_count=0
        )
    
    team_sub = session.team_submissions[team_id]
    team_sub.submit_times.append(time.time())
    
    if not is_correct:
        team_sub.wrong_count += 1
    else:
        team_sub.correct_count += 1
        if not team_sub.is_completed:  # First correct submission
            team_sub.is_completed = True
            team_sub.first_correct_time = time.time()
            team_sub.final_score = score
    
    return team_sub


def stop_question(question_id: int) -> None:
    """Admin stops a question (close submissions immediately)"""
    session = active_questions.get(question_id)
    if session:
        session.is_active = False
        print(f"🛑 Question {question_id} stopped")


def get_question_leaderboard(question_id: int) -> List[dict]:
    """
    Get leaderboard for a question
    
    Returns:
        Sorted list of teams by score (desc), then time (asc)
    """
    session = active_questions.get(question_id)
    if not session:
        return []
    
    results = []
    for team_id, team_sub in session.team_submissions.items():
        if team_sub.is_completed and team_sub.final_score is not None:
            time_taken = team_sub.first_correct_time - session.start_time
            results.append({
                "team_id": team_id,
                "score": team_sub.final_score,
                "time_taken": round(time_taken, 2),
                "submit_count": len(team_sub.submit_times),
                "wrong_count": team_sub.wrong_count
            })
    
    # Sort by score (desc), then time (asc)
    results.sort(key=lambda x: (-x["score"], x["time_taken"]))
    
    # Add rank
    for idx, result in enumerate(results):
        result["rank"] = idx + 1
    
    return results


def get_all_sessions_status() -> List[dict]:
    """Get status of all active questions"""
    status = []
    for qid, session in active_questions.items():
        status.append({
            "question_id": qid,
            "is_active": is_question_active(qid),
            "elapsed_time": round(get_elapsed_time(qid), 2),
            "remaining_time": round(get_remaining_time(qid), 2),
            "total_teams": len(session.team_submissions),
            "completed_teams": sum(1 for ts in session.team_submissions.values() if ts.is_completed)
        })
    return status


def reset_all_questions() -> int:
    """Reset all questions (testing only)"""
    count = len(active_questions)
    active_questions.clear()
    print(f"🔄 Reset all questions. Cleared {count} sessions.")
    return count
