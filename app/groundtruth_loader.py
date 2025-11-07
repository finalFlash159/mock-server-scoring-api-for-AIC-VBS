"""
Ground truth loader from CSV
"""
import csv
from pathlib import Path
from typing import Dict
from app.models import GroundTruth


def load_groundtruth(csv_path: str) -> Dict[int, GroundTruth]:
    """
    Load ground truth from CSV file
    
    CSV format:
        id,type,scene_id,video_id,points
        1,KIS,L26,V017,4890,5000,5001,5020
        2,QA,K01,V021,12000,12345
        3,TR,L26,V017,240,252,300,312
    
    Args:
        csv_path: Path to CSV file
        
    Returns:
        Dictionary mapping question ID to GroundTruth
        
    Raises:
        FileNotFoundError: If CSV file not found
        ValueError: If points count is not even
    """
    path = Path(csv_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {csv_path}")
    
    gt_table = {}
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            qid = int(row['id'])
            qtype = row['type'].strip().upper()
            scene_id = row['scene_id'].strip()
            video_id = row['video_id'].strip()
            
            # Parse points - comma-separated
            points_str = row['points'].strip().strip('"')  # Remove quotes if present
            points = [int(p.strip()) for p in points_str.split(',') if p.strip() and p.strip().isdigit()]
            
            # Validate even number of points
            if len(points) % 2 != 0:
                raise ValueError(
                    f"Question {qid}: points count must be even, got {len(points)}"
                )
            
            # Validate points are sorted
            if points != sorted(points):
                raise ValueError(
                    f"Question {qid}: points must be sorted in ascending order"
                )
            
            gt = GroundTruth(
                stt=qid,
                type=qtype,
                scene_id=scene_id,
                video_id=video_id,
                points=points
            )
            
            gt_table[qid] = gt
    
    if not gt_table:
        raise ValueError(f"No ground truth data loaded from {csv_path}")
    
    print(f"✅ Loaded {len(gt_table)} ground truth entries from {csv_path}")
    
    return gt_table
