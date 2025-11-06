"""
Unit tests for scoring functions
"""
import pytest
from app.models import Config, GroundTruth, NormalizedSubmission
from app.scoring import score_event_ms, score_event_frame, score_submission
from app.utils import points_to_events


@pytest.fixture
def config():
    """Default test configuration"""
    return Config(
        active_question_id=1,
        fps=25.0,
        max_score=100.0,
        frame_tolerance=12.0,
        decay_per_frame=1.0,
        aggregation="mean"
    )


def test_points_to_events():
    """Test converting points to event pairs"""
    points = [4890, 5000, 5001, 5020]
    events = points_to_events(points)
    assert events == [(4890, 5000), (5001, 5020)]
    
    points = [100, 200]
    events = points_to_events(points)
    assert events == [(100, 200)]


def test_score_event_ms_perfect(config):
    """Test scoring with perfect submission (ms)"""
    # Event: 4890-5000, midpoint = 4945
    # User submits exactly 4945
    score = score_event_ms(4945, 4890, 5000, config)
    assert score == 100.0


def test_score_event_ms_close(config):
    """Test scoring with close submission (ms)"""
    # Event: 4890-5000, midpoint = 4945
    # User submits 4999, distance = 54ms = 1.35 frames
    # Score = 100 - 1.35 * 1.0 = 98.65
    score = score_event_ms(4999, 4890, 5000, config)
    assert 98.0 < score < 99.0


def test_score_event_ms_out_of_tolerance(config):
    """Test scoring beyond tolerance (ms)"""
    # Event: 4890-5000, midpoint = 4945
    # User submits 5500, distance = 555ms = 13.875 frames > 12
    score = score_event_ms(5500, 4890, 5000, config)
    assert score == 0.0


def test_score_event_frame_perfect(config):
    """Test scoring with perfect submission (frame)"""
    # Event: 240-252, midpoint = 246
    score = score_event_frame(246, 240, 252, config)
    assert score == 100.0


def test_score_event_frame_close(config):
    """Test scoring with close submission (frame)"""
    # Event: 240-252, midpoint = 246
    # User submits 250, distance = 4 frames
    # Score = 100 - 4 * 1.0 = 96.0
    score = score_event_frame(250, 240, 252, config)
    assert score == 96.0


def test_score_submission_tr_two_events(config):
    """Test TR submission with 2 events"""
    gt = GroundTruth(
        stt=1,
        type="TR",
        scene_id="L26",
        video_id="V017",
        points=[4890, 5000, 5001, 5020]  # 2 events
    )
    
    sub = NormalizedSubmission(
        question_id=1,
        qtype="TR",
        video_id="V017",
        values=[4999, 5049]  # User submits 2 events
    )
    
    final_score, detail = score_submission(sub, gt, config)
    
    # Should have 2 event scores
    assert len(detail["per_event_scores"]) == 2
    assert detail["num_gt_events"] == 2
    assert detail["num_user_events"] == 2
    
    # Check event 1: GT=[4890,5000], mid=4945, range=[4878,5012]
    # user=4999 in range, dist=54 frames -> score = 100-54 = 46
    assert detail["per_event_scores"][0] == 46.0
    
    # Check event 2: GT=[5001,5020], mid=5010.5, range=[4989,5032]
    # user=5049 > 5032 (outside range) -> 0
    assert detail["per_event_scores"][1] == 0.0
    
    # Mean of [46, 0] = 23
    assert final_score == 23.0


def test_score_submission_kis_missing_event(config):
    """Test KIS submission with missing event"""
    gt = GroundTruth(
        stt=2,
        type="KIS",
        scene_id="L26",
        video_id="V017",
        points=[4890, 5000, 5001, 5020]  # 2 events
    )
    
    sub = NormalizedSubmission(
        question_id=2,
        qtype="KIS",
        video_id="V017",
        values=[4945]  # User only submits 1 event
    )
    
    final_score, detail = score_submission(sub, gt, config)
    
    # Should have 2 event scores (second is 0)
    assert len(detail["per_event_scores"]) == 2
    assert detail["per_event_scores"][0] == 100.0  # Perfect
    assert detail["per_event_scores"][1] == 0.0    # Missing
    
    # Mean of [100, 0] = 50
    assert final_score == 50.0


def test_score_submission_aggregation_min(config):
    """Test min aggregation"""
    config.aggregation = "min"
    
    gt = GroundTruth(
        stt=1,
        type="KIS",
        scene_id="L26",
        video_id="V017",
        points=[4890, 5000, 5001, 5020]
    )
    
    sub = NormalizedSubmission(
        question_id=1,
        qtype="KIS",
        video_id="V017",
        values=[4945, 5010]  # Perfect scores
    )
    
    final_score, detail = score_submission(sub, gt, config)
    
    # Both events should be ~100
    assert detail["per_event_scores"][0] == 100.0
    assert 99.0 < detail["per_event_scores"][1] <= 100.0
    
    # Min should be close to 100
    assert 99.0 < final_score <= 100.0


def test_score_submission_aggregation_sum(config):
    """Test sum aggregation"""
    config.aggregation = "sum"
    
    gt = GroundTruth(
        stt=1,
        type="KIS",
        scene_id="L26",
        video_id="V017",
        points=[4890, 5000, 5001, 5020]
    )
    
    sub = NormalizedSubmission(
        question_id=1,
        qtype="KIS",
        video_id="V017",
        values=[4945, 5010]
    )
    
    final_score, detail = score_submission(sub, gt, config)
    
    # Sum of 2 ~100 scores should be ~200
    assert 190.0 < final_score <= 200.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
