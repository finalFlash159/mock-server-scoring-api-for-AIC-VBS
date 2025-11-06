"""
Normalizer for different task types (KIS, QA, TR)
"""
import re
from typing import Dict
from app.models import NormalizedSubmission


def normalize_kis(body: Dict, question_id: int) -> NormalizedSubmission:
    """
    Normalize KIS submission
    
    Body format:
    {
        "answerSets": [{
            "answers": [
                {
                    "mediaItemName": "V017",
                    "start": "4999",
                    "end": "4999"
                },
                {
                    "mediaItemName": "V017",
                    "start": "5049",
                    "end": "5049"
                }
            ]
        }]
    }
    
    Args:
        body: Request body JSON
        question_id: Question ID
        
    Returns:
        NormalizedSubmission with values as list of ms
    """
    answers = body.get("answerSets", [{}])[0].get("answers", [])
    
    if not answers:
        raise ValueError("No answers provided in answerSets")
    
    values = []
    video_id = None
    
    for answer in answers:
        # Get video_id from first answer
        if video_id is None:
            video_id = answer.get("mediaItemName", "").strip()
        
        # Use start time as the submission value (ms)
        start = answer.get("start", "").strip()
        if start:
            values.append(int(start))
    
    if not video_id:
        raise ValueError("No mediaItemName found in KIS answers")
    
    return NormalizedSubmission(
        question_id=question_id,
        qtype="KIS",
        video_id=video_id,
        values=values
    )


def normalize_qa(body: Dict, question_id: int) -> NormalizedSubmission:
    """
    Normalize QA submission
    
    Body format (multiple events in separate answers):
    {
        "answerSets": [{
            "answers": [
                { "text": "QA-ANSWER1-V017-4999" },
                { "text": "QA-ANSWER2-V017-5049" }
            ]
        }]
    }
    
    OR single answer with multiple times (comma-separated):
    {
        "answerSets": [{
            "answers": [
                { "text": "QA-ANSWER1-V017-4999,5049" }
            ]
        }]
    }
    
    Text format: QA-<ANSWER>-<VIDEO_ID>-<MS1>,<MS2>,...
    
    Args:
        body: Request body JSON
        question_id: Question ID
        
    Returns:
        NormalizedSubmission with values as list of ms
    """
    answers = body.get("answerSets", [{}])[0].get("answers", [])
    
    if not answers:
        raise ValueError("No answers provided in answerSets")
    
    values = []
    video_id = None
    
    # Pattern: QA-<ANSWER>-<VIDEO_ID>-<TIME(s)>
    # Answer can be any text, times can be comma-separated
    pattern = r"QA-(.+?)-([A-Za-z0-9]+)-(.+)"
    
    for answer in answers:
        text = answer.get("text", "").strip()
        
        match = re.match(pattern, text)
        if not match:
            raise ValueError(f"Invalid QA answer format: {text}")
        
        answer_text = match.group(1)  # The answer part (e.g., "ANSWER1", "MyAnswer")
        vid = match.group(2)
        times_str = match.group(3)
        
        # Get video_id from first answer
        if video_id is None:
            video_id = vid
        elif video_id != vid:
            raise ValueError(f"Video ID mismatch: {video_id} vs {vid}")
        
        # Parse times (can be comma-separated)
        times = [int(t.strip()) for t in times_str.split(',') if t.strip()]
        values.extend(times)
    
    if not video_id:
        raise ValueError("No video_id found in QA answers")
    
    return NormalizedSubmission(
        question_id=question_id,
        qtype="QA",
        video_id=video_id,
        values=values
    )


def normalize_tr(body: Dict, question_id: int) -> NormalizedSubmission:
    """
    Normalize TR/TRAKE submission
    
    Body format (single answer with comma-separated frame IDs):
    {
        "answerSets": [{
            "answers": [
                { "text": "TR-V017-499,549,600" }
            ]
        }]
    }
    
    Text format: TR-<VIDEO_ID>-<FRAME_ID1>,<FRAME_ID2>,...
    
    Args:
        body: Request body JSON
        question_id: Question ID
        
    Returns:
        NormalizedSubmission with values as list of frame_id
    """
    answers = body.get("answerSets", [{}])[0].get("answers", [])
    
    if not answers:
        raise ValueError("No answers provided in answerSets")
    
    if len(answers) > 1:
        raise ValueError("TR/TRAKE should have exactly 1 answer with comma-separated frame IDs")
    
    text = answers[0].get("text", "").strip()
    
    # Pattern: TR-<VIDEO_ID>-<FRAME_IDS>
    # Frame IDs are comma-separated
    pattern = r"TR-([A-Za-z0-9]+)-(.+)"
    
    match = re.match(pattern, text)
    if not match:
        raise ValueError(f"Invalid TR answer format: {text}")
    
    video_id = match.group(1)
    frame_ids_str = match.group(2)
    
    # Parse frame IDs (comma-separated)
    values = [int(f.strip()) for f in frame_ids_str.split(',') if f.strip()]
    
    if not values:
        raise ValueError("No frame IDs found in TR answer")
    
    return NormalizedSubmission(
        question_id=question_id,
        qtype="TR",
        video_id=video_id,
        values=values
    )
