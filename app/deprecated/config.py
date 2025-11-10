"""
Configuration loader (legacy support only)
"""
import yaml
from pathlib import Path
from app.models import Config


def load_config(config_path: str = "config/current_task.yaml") -> Config:
    """
    Load configuration from YAML file
    
    DEPRECATED: This is kept for backward compatibility only.
    New code should use ScoringParams with hard-coded defaults.
    
    Args:
        config_path: Path to config file
        
    Returns:
        Config object
    """
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    # Filter out deprecated fields
    allowed_fields = {'active_question_id', 'p_max', 'p_base', 'p_penalty', 'time_limit', 'buffer_time'}
    filtered_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    return Config(**filtered_data)
