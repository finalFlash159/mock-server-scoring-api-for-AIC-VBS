"""
Global application state
Shared resources accessible across all modules
"""
from typing import Dict, Optional

from app.models import ScoringParams

# Global ground truth table
# Loaded at startup and accessible throughout the application
GT_TABLE: Optional[Dict] = None

# Default scoring parameters (applied to every session unless overridden)
SCORING_PARAMS: ScoringParams = ScoringParams()

# Registered teams: mapping session-id -> team info (team_id, team_name)
TEAM_REGISTRY: Dict[str, Dict[str, str]] = {}

# Convenience index from team_id -> session-id
TEAM_INDEX: Dict[str, str] = {}
