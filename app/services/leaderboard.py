"""
Leaderboard service - Assemble and format leaderboard data
"""
from typing import Dict, List
from app.core.session import get_question_leaderboard, active_questions


def get_leaderboard_data(question_id: int = None) -> Dict:
    """
    Get leaderboard data for display
    
    Args:
        question_id: Optional question ID (if None, use first active question)
        
    Returns:
        Formatted leaderboard data
    """
    # If no question_id specified, use first active question
    if question_id is None and active_questions:
        question_id = next(iter(active_questions))
    
    if question_id is None:
        return {
            "active_question_id": None,
            "teams": [],
            "message": "No active question"
        }
    
    # Get leaderboard from session
    leaderboard = get_question_leaderboard(question_id)
    
    return {
        "active_question_id": question_id,
        "teams": leaderboard,
        "total_teams": len(leaderboard)
    }
