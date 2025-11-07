"""
Fake teams generator for leaderboard simulation
"""
import random
from typing import List, Tuple

# Pool of creative team names
TEAM_NAMES = [
    "CodeNinja", "ByteBusters", "AlgoMasters", "DataDragons",
    "PixelPirates", "QueryQueens", "FrameFinders", "ScriptSquad",
    "BinaryBandits", "LogicLords", "CacheCrusaders", "DebugDynasty",
    "RegexRebels", "StackSmashers", "HeapHeroes", "ArrayAces",
    "LinkedLegends", "TreeTraversers", "GraphGurus", "HashHustlers",
    "QueueKings", "RecursionRiders", "BitBrigade", "LoopLegends",
    "FunctionFury", "PointerPros", "MemoryMasters", "CompilerCrew"
]


def generate_fake_team_names(count: int = 15) -> List[str]:
    """
    Generate unique team names excluding 0THING2LOSE
    
    Args:
        count: Number of fake teams to generate
        
    Returns:
        List of unique team names
    """
    available = [name for name in TEAM_NAMES if name != "0THING2LOSE"]
    
    # Add more random names if needed
    while len(available) < count:
        available.append(f"Team{random.randint(100, 999)}")
    
    return random.sample(available, min(count, len(available)))


def generate_weighted_score() -> float:
    """
    Generate random score with weighted distribution
    
    Score distribution:
    - 80-100: 15% (high scores - rare)
    - 60-80: 30% (good scores)
    - 40-60: 35% (medium scores)
    - 0-40: 20% (low scores)
    
    Returns:
        Score between 0 and 100
    """
    rand = random.random()
    
    if rand < 0.15:  # 15% - High scores
        return round(random.uniform(80, 100), 1)
    elif rand < 0.45:  # 30% - Good scores
        return round(random.uniform(60, 80), 1)
    elif rand < 0.80:  # 35% - Medium scores
        return round(random.uniform(40, 60), 1)
    else:  # 20% - Low scores
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


def generate_random_submit_time(time_limit: float) -> float:
    """
    Generate random submission time within question duration
    
    Most submissions happen in first 50% of time limit,
    fewer near the end
    
    Args:
        time_limit: Maximum time in seconds
        
    Returns:
        Random time between 0 and time_limit
    """
    # Weighted toward earlier submissions
    rand = random.random()
    
    if rand < 0.50:  # 50% submit in first quarter
        return random.uniform(0, time_limit * 0.25)
    elif rand < 0.80:  # 30% submit in second quarter
        return random.uniform(time_limit * 0.25, time_limit * 0.50)
    elif rand < 0.95:  # 15% submit in third quarter
        return random.uniform(time_limit * 0.50, time_limit * 0.75)
    else:  # 5% submit in last quarter
        return random.uniform(time_limit * 0.75, time_limit)
