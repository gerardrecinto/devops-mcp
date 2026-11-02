import pytest

from devops_mcp.slo import (
    budget_remaining,
    burn_rate,
    error_ratio,
    evaluate,
    hours_to_exhaust,
)


def test_burn_rate_one_means_budget_lasts_the_period():
    assert burn_rate(0.001, 0.999) == pytest.approx(1.0)


def test_fast_burn_pages_when_both_windows_agree():
    # 2% errors against a 99.9% SLO is a 20x burn on both windows
    windows = {"1h": (200, 10000), "5m": (20, 1000)}
    fired = evaluate(windows, 0.999)
    assert [f["severity"] for f in fired] == ["page"]
    assert fired[0]["long_burn_rate"] == pytest.approx(20.0)


def test_old_spike_that_has_stopped_does_not_page():
    # long window still hot, short window already clean
    windows = {"1h": (200, 10000), "5m": (0, 1000)}
    assert evaluate(windows, 0.999) == []


def test_slow_burn_files_a_ticket_not_a_page():
    # 0.35% errors is about 3.5x: below 6x, above 3x
    windows = {"1d": (350, 100000), "2h": (35, 10000)}
    fired = evaluate(windows, 0.999)
    assert [f["severity"] for f in fired] == ["ticket"]


def test_missing_windows_are_skipped_not_guessed():
    assert evaluate({"1h": (500, 1000)}, 0.999) == []


def test_no_traffic_is_not_an_error():
    assert error_ratio(0, 0) == 0.0


def test_errors_cannot_exceed_total():
    with pytest.raises(ValueError):
        error_ratio(5, 4)


def test_slo_target_must_be_a_fraction():
    with pytest.raises(ValueError):
        burn_rate(0.01, 99.9)


def test_budget_remaining_goes_negative_when_overspent():
    # 99.9% of 10000 allows 10 errors
    assert budget_remaining(5, 10000, 0.999) == pytest.approx(0.5)
    assert budget_remaining(20, 10000, 0.999) == pytest.approx(-1.0)


def test_hours_to_exhaust_at_14_4x_is_50_hours():
    assert hours_to_exhaust(14.4) == pytest.approx(50.0)
