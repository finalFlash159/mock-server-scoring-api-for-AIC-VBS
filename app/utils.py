"""
Utility functions
"""
from typing import List, Tuple


def points_to_events(points: List[int]) -> List[Tuple[int, int]]:
    """
    Convert a list of points to a list of events (pairs of points)
    
    Args:
        points: List of integers [p1, p2, p3, p4, ...]
               Must have even number of elements
               
    Returns:
        List of tuples [(p1, p2), (p3, p4), ...]
        
    Raises:
        AssertionError: If points count is not even
        
    Example:
        >>> points_to_events([4890, 5000, 5001, 5020])
        [(4890, 5000), (5001, 5020)]
    """
    assert len(points) % 2 == 0, "Points count must be even"
    
    events = []
    for i in range(0, len(points), 2):
        events.append((points[i], points[i + 1]))
    
    return events
