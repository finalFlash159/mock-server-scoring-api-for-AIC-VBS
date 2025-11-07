"""
Tests for AIC 2025 Competition Scoring
"""
import pytest
from app.scoring import (
    calculate_time_factor,
    check_exact_match,
    calculate_correctness_factor,
    calculate_final_score
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


def test_exact_match_perfect():
    """Perfect exact match: all events matched"""
    user = [4890, 5000]
    events = [(4890, 5000)]
    matched, total = check_exact_match(user, events)
    assert matched == 1
    assert total == 1


def test_exact_match_partial():
    """Partial match: only 1 of 2 events"""
    user = [4890, 5000]
    events = [(4890, 5000), (5001, 5020)]
    matched, total = check_exact_match(user, events)
    assert matched == 1
    assert total == 2


def test_exact_match_no_match():
    """No match: different values"""
    user = [1000, 2000]
    events = [(4890, 5000)]
    matched, total = check_exact_match(user, events)
    assert matched == 0
    assert total == 1


def test_exact_match_multiple_values_one_event():
    """Multiple user values matching same event"""
    user = [4890, 5000]  # Both match event
    events = [(4890, 5000)]
    matched, total = check_exact_match(user, events)
    assert matched == 1  # Still counts as 1 event matched
    assert total == 1


def test_correctness_kis_full():
    """KIS: 100% correct → factor 1.0"""
    factor = calculate_correctness_factor(2, 2, "KIS")
    assert factor == 1.0


def test_correctness_kis_partial():
    """KIS: 50% correct → factor 0.0 (no score)"""
    factor = calculate_correctness_factor(1, 2, "KIS")
    assert factor == 0.0


def test_correctness_qa_full():
    """QA: 100% correct → factor 1.0"""
    factor = calculate_correctness_factor(1, 1, "QA")
    assert factor == 1.0


def test_correctness_qa_partial():
    """QA: 50% correct → factor 0.0 (no score)"""
    factor = calculate_correctness_factor(1, 2, "QA")
    assert factor == 0.0


def test_correctness_trake_full():
    """TRAKE: 100% → factor 1.0"""
    factor = calculate_correctness_factor(2, 2, "TR")
    assert factor == 1.0


def test_correctness_trake_partial_high():
    """TRAKE: 50-99% → factor 0.5"""
    factor = calculate_correctness_factor(1, 2, "TR")
    assert factor == 0.5


def test_correctness_trake_partial_75():
    """TRAKE: 75% (3/4) → factor 0.5"""
    factor = calculate_correctness_factor(3, 4, "TR")
    assert factor == 0.5


def test_correctness_trake_low():
    """TRAKE: <50% → factor 0.0"""
    factor = calculate_correctness_factor(1, 3, "TR")
    assert factor == 0.0


def test_final_score_perfect():
    """Perfect submission: t=0, k=0, 100% correct"""
    params = ScoringParams()
    result = calculate_final_score(2, 2, "KIS", 0, 0, params)
    assert result["score"] == 100.0
    assert result["penalty"] == 0
    assert result["correctness_factor"] == 1.0
    assert result["time_factor"] == 1.0


def test_final_score_with_penalty():
    """Score with penalty: k=2, perfect timing and correctness"""
    params = ScoringParams()
    result = calculate_final_score(2, 2, "KIS", 0, 2, params)
    # base_score = 100, penalty = 20, final = 80
    assert result["score"] == 80.0
    assert result["penalty"] == 20.0


def test_final_score_with_time():
    """Score with time factor: t=150s (half)"""
    params = ScoringParams()
    result = calculate_final_score(2, 2, "KIS", 150, 0, params)
    # fT = 0.5, base = 50 + (100-50)*0.5 = 75
    assert result["score"] == 75.0
    assert result["time_factor"] == 0.5


def test_final_score_trake_partial():
    """TRAKE partial: 50% correct, score halved"""
    params = ScoringParams()
    result = calculate_final_score(1, 2, "TR", 0, 0, params)
    # base = 100, correctness = 0.5, final = 50
    assert result["score"] == 50.0
    assert result["correctness_factor"] == 0.5


def test_final_score_time_and_penalty():
    """Combined: time factor + penalty"""
    params = ScoringParams()
    result = calculate_final_score(2, 2, "KIS", 150, 1, params)
    # fT=0.5, base=75, penalty=10, final=65
    assert result["score"] == 65.0
    assert result["penalty"] == 10.0
    assert result["time_factor"] == 0.5


def test_final_score_kis_incorrect():
    """KIS: Partial match → 0 score"""
    params = ScoringParams()
    result = calculate_final_score(1, 2, "KIS", 0, 0, params)
    assert result["score"] == 0.0
    assert result["correctness_factor"] == 0.0


def test_final_score_high_penalty():
    """Very high penalty can bring score to 0"""
    params = ScoringParams()
    result = calculate_final_score(2, 2, "KIS", 0, 15, params)
    # base = 100, penalty = 150, max(0, 100-150) = 0
    assert result["score"] == 0.0


def test_final_score_trake_with_time_and_penalty():
    """TRAKE partial with time and penalty"""
    params = ScoringParams()
    result = calculate_final_score(2, 3, "TR", 100, 1, params)
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
