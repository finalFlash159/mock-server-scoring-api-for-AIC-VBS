"""
Configuration loader
"""
import yaml
from pathlib import Path
from app.models import Config


def load_config(config_path: str = "config/current_task.yaml") -> Config:
    """
    Load configuration from YAML file
    
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
    
    return Config(**data)


def update_active_question(question_id: int, config_path: str = "config/current_task.yaml") -> None:
    """
    Update active_question_id in config file
    
    Args:
        question_id: New active question ID
        config_path: Path to config file
    """
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    # Read current config
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    # Update
    data['active_question_id'] = question_id
    
    # Write back
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    print(f"✅ Updated active_question_id to {question_id}")
