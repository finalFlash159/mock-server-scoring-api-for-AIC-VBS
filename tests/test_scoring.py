"""
Tests for AIC 2025 Competition Scoring with Tolerance-Based Matching
"""
import pytest
from app.scoring import (
    calculate_time_factor,
    check_match_with_tolerance,
    calculate_correctness_factor,
    calculate_final_score,
    TOLERANCE_MS,
    TOLERANCE_FRAMES
)
from app.models import ScoringParams


def test_time_factor_start():
    """Time factor at t=0 should be 1.0"""
    assert calculate_time_factor(0, 300) == 1.0


def test_time_factor_half():
    """Time factor at t=150s (half) should be 0.5"""
    assert calculate_time_factor(150, 300) == 0.5


def test_time_factor_end():
    """Time factor at t=300s (end) should be 0.0"""
    assert calculate_time_factor(300, 300) == 0.0


def test_time_factor_exceeded():
    """Time factor past time limit should be 0.0"""
    assert calculate_time_factor(350, 300) == 0.0


def test_tolerance_match_perfect():
    """Perfect match at event center"""
    user = [10025]  # Center of event [10000, 10050]
    events = [(10000, 10050)]
    matched, total, quality = check_match_with_tolerance(user, events, TOLERANCE_FRAMES)
    assert matched == 1
    assert total == 1
    assert quality == 1.0  # Perfect center


def test_tolerance_match_partial():
    """Match with distance decay"""
    user = [10000]  # At event start (boundary)
    events = [(10000, 10050)]
    matched, total, quality = check_match_with_tolerance(user, events, TOLERANCE_FRAMES)
    assert matched == 1
    assert total == 1
    assert 0.5 <= quality <= 1.0  # Some decay from center


def test_tolerance_match_outside():
    """Value outside tolerance"""
    user = [9000]  # Far from event [10000, 10050]
    events = [(10000, 10050)]
    matched, total, quality = check_match_with_tolerance(user, events, TOLERANCE_FRAMES)
    assert matched == 0
    assert total == 1
    assert quality == 0.0


def test_tolerance_match_multiple_events():
    """Multiple events with tolerance matching"""
    user = [10025, 10150]  # Match both events at centers
    events = [(10000, 10050), (10125, 10175)]
    matched, total, quality = check_match_with_tolerance(user, events, TOLERANCE_FRAMES)
    assert matched == 2
    assert total == 2
    assert quality == 1.0  # Both at centers


def test_correctness_kis_full():
    """KIS: 100% correct with quality → factor = quality"""
    factor = calculate_correctness_factor(2, 2, "KIS", avg_quality=1.0)
    assert factor == 1.0
    
    # With lower quality
    factor = calculate_correctness_factor(2, 2, "KIS", avg_quality=0.75)
    assert factor == 0.75


def test_correctness_kis_partial():
    """KIS: <100% correct → factor 0.0 (no score)"""
    factor = calculate_correctness_factor(1, 2, "KIS", avg_quality=1.0)
    assert factor == 0.0


def test_correctness_qa_full():
    """QA: 100% correct with quality → factor = quality"""
    factor = calculate_correctness_factor(1, 1, "QA", avg_quality=1.0)
    assert factor == 1.0
    
    # With lower quality
    factor = calculate_correctness_factor(1, 1, "QA", avg_quality=0.8)
    assert factor == 0.8


def test_correctness_qa_partial():
    """QA: <100% correct → factor 0.0 (no score)"""
    factor = calculate_correctness_factor(1, 2, "QA", avg_quality=1.0)
    assert factor == 0.0


def test_correctness_trake_full():
    """TRAKE: 100% with quality → factor = quality"""
    factor = calculate_correctness_factor(2, 2, "TR", avg_quality=1.0)
    assert factor == 1.0
    
    # With lower quality
    factor = calculate_correctness_factor(2, 2, "TR", avg_quality=0.9)
    assert factor == 0.9


def test_correctness_trake_partial_high():
    """TRAKE: 50-99% → factor = quality * 0.5"""
    factor = calculate_correctness_factor(1, 2, "TR", avg_quality=1.0)
    assert factor == 0.5
    
    # With lower quality
    factor = calculate_correctness_factor(1, 2, "TR", avg_quality=0.8)
    assert factor == 0.4  # 0.8 * 0.5


def test_correctness_trake_partial_75():
    """TRAKE: 75% (3/4) → factor = quality * 0.5"""
    factor = calculate_correctness_factor(3, 4, "TR", avg_quality=1.0)
    assert factor == 0.5


def test_correctness_trake_low():
    """TRAKE: <50% → factor 0.0"""
    factor = calculate_correctness_factor(1, 3, "TR", avg_quality=1.0)
    assert factor == 0.0


def test_final_score_perfect():
    """Perfect submission: t=0, k=0, 100% correct, quality=1.0"""
    params = ScoringParams()
    result = calculate_final_score(2, 2, "KIS", 0, 0, params, avg_quality=1.0)
    assert result["score"] == 100.0
    assert result["penalty"] == 0
    assert result["correctness_factor"] == 1.0
    assert result["time_factor"] == 1.0
    assert result["match_quality"] == 1.0


def test_final_score_with_quality():
    """Score affected by match quality"""
    params = ScoringParams()
    result = calculate_final_score(2, 2, "KIS", 0, 0, params, avg_quality=0.75)
    # base = 100, correctness = 0.75 (quality-adjusted), final = 75
    assert result["score"] == 75.0
    assert result["match_quality"] == 0.75


def test_final_score_with_penalty():
    """Score with penalty: k=2, perfect timing and correctness"""
    params = ScoringParams()
    result = calculate_final_score(2, 2, "KIS", 0, 2, params, avg_quality=1.0)
    # base_score = 100, penalty = 20, final = 80
    assert result["score"] == 80.0
    assert result["penalty"] == 20.0


def test_final_score_with_time():
    """Score with time factor: t=150s (half)"""
    params = ScoringParams()
    result = calculate_final_score(2, 2, "KIS", 150, 0, params, avg_quality=1.0)
    # fT = 0.5, base = 50 + (100-50)*0.5 = 75
    assert result["score"] == 75.0
    assert result["time_factor"] == 0.5


def test_final_score_trake_partial():
    """TRAKE partial: 50% correct, quality-adjusted"""
    params = ScoringParams()
    result = calculate_final_score(1, 2, "TR", 0, 0, params, avg_quality=1.0)
    # base = 100, correctness = 0.5 (50% match), final = 50
    assert result["score"] == 50.0
    assert result["correctness_factor"] == 0.5


def test_final_score_time_and_penalty():
    """Combined: time factor + penalty"""
    params = ScoringParams()
    result = calculate_final_score(2, 2, "KIS", 150, 1, params, avg_quality=1.0)
    # fT=0.5, base=75, penalty=10, final=65
    assert result["score"] == 65.0
    assert result["penalty"] == 10.0
    assert result["time_factor"] == 0.5


def test_final_score_kis_incorrect():
    """KIS: Partial match → 0 score"""
    params = ScoringParams()
    result = calculate_final_score(1, 2, "KIS", 0, 0, params, avg_quality=1.0)
    assert result["score"] == 0.0
    assert result["correctness_factor"] == 0.0


def test_final_score_high_penalty():
    """Very high penalty can bring score to 0"""
    params = ScoringParams()
    result = calculate_final_score(2, 2, "KIS", 0, 15, params, avg_quality=1.0)
    # base = 100, penalty = 150, max(0, 100-150) = 0
    assert result["score"] == 0.0


def test_final_score_trake_with_time_and_penalty():
    """TRAKE partial with time and penalty"""
    params = ScoringParams()
    result = calculate_final_score(2, 3, "TR", 100, 1, params, avg_quality=1.0)
    # fT = 1 - 100/300 = 0.6667
    # base = 50 + 50*0.6667 = 83.33
    # penalty = 10
    # score_before = 73.33
    # correctness = 0.5 (2/3 = 66% → 50-99%)
    # final = 73.33 * 0.5 = 36.67
    assert 36 <= result["score"] <= 37
    assert result["correctness_factor"] == 0.5


def test_final_score_at_time_limit():
    """At time limit, time factor = 0, base score = p_base"""
    params = ScoringParams()
    result = calculate_final_score(2, 2, "KIS", 300, 0, params)
    # fT = 0, base = 50 + 50*0 = 50
    assert result["score"] == 50.0
    assert result["time_factor"] == 0.0
