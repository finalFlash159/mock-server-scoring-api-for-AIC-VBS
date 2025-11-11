"""
Question-level session management for AIC 2025 Competition
Server-controlled timing with per-team submission tracking
"""
import asyncio
import logging
import random
import time
from typing import Dict, List, Optional

from app.models import QuestionSession, TeamSubmission


logger = logging.getLogger(__name__)

# Global storage: question_id → QuestionSession
active_questions: Dict[int, QuestionSession] = {}

# Track currently active question (last started that is still active)
current_active_question_id: Optional[int] = None


def _refresh_active_question_id() -> Optional[int]:
    """
    Ensure the cached current_active_question_id points to an active session.
    """
    global current_active_question_id
    if current_active_question_id and is_question_active(current_active_question_id):
        return current_active_question_id
    
    # Find the most recently started active session (if any)
    active_candidates = [
        (session.start_time, qid)
        for qid, session in active_questions.items()
        if is_question_active(qid)
    ]
    if active_candidates:
        _, qid = max(active_candidates)
        current_active_question_id = qid
        return current_active_question_id
    
    current_active_question_id = None
    return None


def get_current_active_question_id() -> Optional[int]:
    """Return the current active question id (if still accepting submissions)."""
    return _refresh_active_question_id()


def initialize_fake_teams(question_id: int) -> Dict[str, TeamSubmission]:
    """
    Initialize fake teams placeholders (submissions will be scheduled with delay)
    
    Args:
        question_id: Question ID
        
    Returns:
        Dictionary of fake team submissions (empty, to be populated by background tasks)
    """
    from app.services.fake_teams import generate_fake_team_names
    
    fake_teams = {}
    team_names = generate_fake_team_names(20)  # Generate 20 fake teams (all AIC 2025 competitors)
    
    # Initialize empty placeholders - submissions will be added by background tasks
    for name in team_names:
        team_sub = TeamSubmission(
            team_id=name,
            team_name=name,
            question_id=question_id,
            wrong_count=0,
            correct_count=0,
            is_completed=False,
            final_score=None,
            first_correct_time=None
        )
        fake_teams[name] = team_sub
    
    return fake_teams


async def schedule_fake_team_submission(
    question_id: int,
    team_name: str,
    delay: float,
    wrong_count: int,
    correct_count: int,
    score: Optional[float]
):
    """
    Schedule a fake team submission after a delay
    
    Args:
        question_id: Question ID
        team_name: Fake team name
        delay: Delay in seconds before submitting
        wrong_count: Number of wrong submissions
        correct_count: Number of correct submissions (0 or 1)
        score: Final score if correct
    """
    await asyncio.sleep(delay)
    
    # Check if question still exists
    session = active_questions.get(question_id)
    if not session:
        return
    
    def _is_accepting_submissions() -> bool:
        if not session.is_active:
            return False
        elapsed = time.time() - session.start_time
        return elapsed <= (session.time_limit + session.buffer_time)
    
    if not _is_accepting_submissions():
        return
    
    # Submit wrong attempts first
    for _ in range(wrong_count):
        if not _is_accepting_submissions():
            return
        record_submission(question_id, team_name, is_correct=False, score=None, team_name=team_name)
        await asyncio.sleep(random.uniform(1, 5))  # Small delay between attempts
    
    # Submit correct answer if still within allowed window
    if correct_count > 0 and _is_accepting_submissions():
        record_submission(question_id, team_name, is_correct=True, score=score, team_name=team_name)
        logger.info("Fake team %s completed Q%s with score %.2f", team_name, question_id, score)


def start_fake_team_submissions(question_id: int):
    """
    Start background tasks for fake team submissions with random delays
    
    Args:
        question_id: Question ID
    """
    from app.services.fake_teams import (
        generate_submission_attempts,
        generate_weighted_score,
        generate_submit_delay
    )
    
    session = active_questions[question_id]
    
    for team_name in session.fake_teams.keys():
        is_special = team_name == "0THING2LOSE"
        wrong_count, correct_count = generate_submission_attempts()
        
        # Ensure special team always submits once
        if wrong_count == 0 and correct_count == 0:
            if is_special:
                correct_count = 1
            else:
                continue
        
        # Generate score if team completes
        score = None
        if correct_count > 0:
            score = generate_weighted_score() if not is_special else round(random.uniform(90, 99), 1)
        
        # Generate delay
        delay = 5 if is_special else generate_submit_delay(session.time_limit)
        
        # Create background task
        asyncio.create_task(
            schedule_fake_team_submission(
                question_id=question_id,
                team_name=team_name,
                delay=delay,
                wrong_count=wrong_count,
                correct_count=correct_count,
                score=score
            )
        )
    
    logger.info(
        "Scheduled fake team submissions for Q%s (delays scaled to %ss limit)",
        question_id,
        session.time_limit,
    )


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
    global current_active_question_id
    
    session = QuestionSession(
        question_id=question_id,
        start_time=time.time(),
        time_limit=time_limit,
        buffer_time=buffer_time,
        is_active=True,
        team_submissions={},
        fake_teams=initialize_fake_teams(question_id)
    )
    active_questions[question_id] = session
    current_active_question_id = question_id
    logger.info("Question %s started at %.3f (time=%ss, buffer=%ss)", question_id, session.start_time, time_limit, buffer_time)
    logger.info("Generated %s fake teams for Q%s", len(session.fake_teams), question_id)
    # include already registered real teams
    from app import state
    for session_id, info in state.TEAM_REGISTRY.items():
        if info["team_id"] not in session.team_submissions:
            session.team_submissions[info["team_id"]] = TeamSubmission(
                team_id=info["team_id"],
                team_name=info["team_name"],
                team_session_id=session_id,
                question_id=question_id,
                submit_times=[],
                wrong_count=0,
                correct_count=0
            )

    # Start background tasks for fake team submissions with delays
    start_fake_team_submissions(question_id)

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
    score: Optional[float] = None,
    *,
    team_name: Optional[str] = None,
    team_session_id: Optional[str] = None
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
    
    # Check if this is a fake team
    is_fake_team = team_id in session.fake_teams
    
    # Get or create team submission record
    if is_fake_team:
        # For fake teams, update the existing record in fake_teams
        team_sub = session.fake_teams[team_id]
        if not hasattr(team_sub, 'submit_times'):
            team_sub.submit_times = []
    else:
        # For real teams, use team_submissions
        if team_id not in session.team_submissions:
            session.team_submissions[team_id] = TeamSubmission(
                team_id=team_id,
                team_name=team_name or team_id,
                team_session_id=team_session_id,
                question_id=question_id,
                submit_times=[],
                wrong_count=0,
                correct_count=0
            )
        team_sub = session.team_submissions[team_id]
        if team_name and not team_sub.team_name:
            team_sub.team_name = team_name
        if team_session_id and not team_sub.team_session_id:
            team_sub.team_session_id = team_session_id
    
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
    global current_active_question_id
    session = active_questions.get(question_id)
    if session:
        session.is_active = False
        logger.info("Question %s stopped by admin", question_id)
        if current_active_question_id == question_id:
            _refresh_active_question_id()


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
        total_submissions = sum(len(ts.submit_times) for ts in session.team_submissions.values())
        status.append({
            "question_id": qid,
            "is_active": is_question_active(qid),
            "elapsed_time": round(get_elapsed_time(qid), 2),
            "remaining_time": round(get_remaining_time(qid), 2),
            "time_limit": session.time_limit,
            "buffer_time": session.buffer_time,
            "total_teams": len(session.team_submissions),
            "total_submissions": total_submissions,
            "completed_teams": sum(1 for ts in session.team_submissions.values() if ts.is_completed)
        })
    return status


def reset_all_questions() -> int:
    """Reset all questions (testing only)"""
    global current_active_question_id
    count = len(active_questions)
    active_questions.clear()
    current_active_question_id = None
    logger.info("Reset all questions. Cleared %s sessions.", count)
    return count


def add_team_to_active_sessions(team_id: str, team_name: str, team_session_id: str) -> None:
    for qid, session in active_questions.items():
        if team_id in session.team_submissions:
            continue
        session.team_submissions[team_id] = TeamSubmission(
            team_id=team_id,
            team_name=team_name,
            team_session_id=team_session_id,
            question_id=qid,
            submit_times=[],
            wrong_count=0,
            correct_count=0
        )
