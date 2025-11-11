"""
Fake teams generator for leaderboard simulation
"""
import random
from typing import List, Tuple

# Pool of real AIC 2025 team names
TEAM_NAMES = [
    "0THING2LOSE", "UIT@Dzeus", "TKU.TonNGoYsss", "UTE AI LAB", "UIT-SHAMROCK",
    "TKU@MBZUAI", "TKU@UNIVORN&WHEAT", "Althena", "Your answer",
    "float97", "KPT", "GALAXY-AI", "Lucifer",
    "FLameReavers", "OpenCubee_1", "OpenCubee2", "Nomial",
    "AIO - Neural Weavers", "5bros", "AeThanhHoa", "AIO_Trinh"
]


def generate_fake_team_names(count: int = 20) -> List[str]:
    """
    Generate unique team names for fake leaderboard slots
    
    Args:
        count: Number of fake teams to generate (default 20 - all AIC 2025 teams)
        
    Returns:
        List of unique team names
    """
    available = TEAM_NAMES[:]
    
    # Use all available teams, or sample if count is less
    if count >= len(available):
        return available
    
    return random.sample(available, count)


def generate_weighted_score() -> float:
    """
    Generate random score with weighted distribution
    
    Score distribution:
    - 80-100: 10%  (buff high rollers)
    - 60-80: 30%  (good scores)
    - 40-60: 35%  (medium scores)
    - 0-40 : 25%  (low scores)
    
    Returns:
        Score between 0 and 100
    """
    rand = random.random()
    
    if rand < 0.10:
        return round(random.uniform(80, 100), 1)
    elif rand < 0.40:
        return round(random.uniform(60, 80), 1)
    elif rand < 0.75:
        return round(random.uniform(40, 60), 1)
    else:
        return round(random.uniform(0, 40), 1)


def should_submit() -> bool:
    """
    Determine if a team should submit
    
    85% of teams submit, 15% don't submit
    
    Returns:
        True if team submits, False otherwise
    """
    return random.random() < 0.85


def generate_submission_attempts() -> Tuple[int, int]:
    """
    Generate random submission attempts (wrong and correct)
    
    Distribution:
    - 60%: Correct on first try (0 wrong, 1 correct)
    - 25%: 1 wrong attempt then correct (1 wrong, 1 correct)
    - 10%: 2-3 wrong attempts then correct (2-3 wrong, 1 correct)
    - 5%: Only wrong attempts, no correct (1-3 wrong, 0 correct)
    - 15%: No submission at all (handled by should_submit)
    
    Returns:
        Tuple of (wrong_count, correct_count)
    """
    if not should_submit():
        return (0, 0)  # No submission
    
    rand = random.random()
    
    if rand < 0.60:  # 60% - Correct first try
        return (0, 1)
    elif rand < 0.85:  # 25% - 1 wrong then correct
        return (1, 1)
    elif rand < 0.95:  # 10% - 2-3 wrong then correct
        return (random.randint(2, 3), 1)
    else:  # 5% - Only wrong attempts, no correct
        return (random.randint(1, 3), 0)


def generate_submit_delay(time_limit: float) -> float:
    """
    Generate random delay before fake team submits.
    
    Delay is scaled to the current question time limit so fake teams always
    submit while the question is still active.
    """
    if time_limit <= 0:
        return 1.0
    
    min_delay = max(0.5, time_limit * 0.02)   # 2% of duration (>=0.5s)
    max_delay = max(min_delay, time_limit * 0.6)  # cap ở 60% thời lượng để leaderboard lên điểm sớm
    return random.uniform(min_delay, max_delay)
