"""
Global application state
Shared resources accessible across all modules
"""
from typing import Dict, Optional

# Global ground truth table
# Loaded at startup and accessible throughout the application
GT_TABLE: Optional[Dict] = None
