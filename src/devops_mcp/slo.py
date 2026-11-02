"""Multi-window, multi-burn-rate SLO alerts.

Follows the pattern in the Google SRE Workbook (alerting on SLOs): an alert
fires only when both a long window and a short window burn the error budget
faster than a threshold. The long window shows the burn is real, the short
window shows it is still happening.

Standard thresholds for a 30 day SLO period:

  14.4x over 1h  and 5m   -> page   (2% of the budget gone in 1 hour)
   6x   over 6h  and 30m  -> page   (5% of the budget gone in 6 hours)
   3x   over 1d  and 2h   -> ticket (10% of the budget gone in 1 day)
   1x   over 3d  and 6h   -> ticket (10% of the budget gone in 3 days)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

SLO_PERIOD_HOURS = 30 * 24


@dataclass(frozen=True)
class BurnRule:
    burn_rate: float
    long_window: str
    short_window: str
    severity: str


DEFAULT_RULES: tuple[BurnRule, ...] = (
    BurnRule(14.4, "1h", "5m", "page"),
    BurnRule(6.0, "6h", "30m", "page"),
    BurnRule(3.0, "1d", "2h", "ticket"),
    BurnRule(1.0, "3d", "6h", "ticket"),
)


def error_ratio(errors: float, total: float) -> float:
    """Fraction of failed events. No traffic counts as no errors."""
    if total < 0 or errors < 0:
        raise ValueError("errors and total must not be negative")
    if errors > total:
        raise ValueError("errors cannot exceed total")
    if total == 0:
        return 0.0
    return errors / total


def burn_rate(ratio: float, slo_target: float) -> float:
    """How many times faster than allowed the error budget is being spent.

    1.0 means the budget lasts exactly the SLO period. 14.4 means it is gone
    in 1/14.4 of the period.
    """
    if not 0 < slo_target < 1:
        raise ValueError("slo_target must be between 0 and 1, for example 0.999")
    return ratio / (1 - slo_target)


def budget_remaining(errors: float, total: float, slo_target: float) -> float:
    """Share of the error budget left for the events seen so far (can go negative)."""
    allowed = total * (1 - slo_target)
    if allowed == 0:
        return 1.0
    return 1 - errors / allowed


def evaluate(
    windows: dict[str, tuple[float, float]],
    slo_target: float,
    rules: tuple[BurnRule, ...] = DEFAULT_RULES,
) -> list[dict]:
    """Return the rules that fire.

    windows maps a window name such as "1h" to (errors, total) for that window.
    A rule whose windows are missing from the input is skipped, not guessed.
    """
    firing = []
    for rule in rules:
        if rule.long_window not in windows or rule.short_window not in windows:
            continue
        long_rate = burn_rate(error_ratio(*windows[rule.long_window]), slo_target)
        short_rate = burn_rate(error_ratio(*windows[rule.short_window]), slo_target)
        if long_rate >= rule.burn_rate and short_rate >= rule.burn_rate:
            firing.append(
                {
                    "severity": rule.severity,
                    "threshold": rule.burn_rate,
                    "long_window": rule.long_window,
                    "short_window": rule.short_window,
                    "long_burn_rate": round(long_rate, 2),
                    "short_burn_rate": round(short_rate, 2),
                }
            )
    return firing


def hours_to_exhaust(rate: float) -> float:
    """Hours until a 30 day budget is gone at a constant burn rate."""
    if rate <= 0:
        return float("inf")
    return SLO_PERIOD_HOURS / rate


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate multi-window burn-rate alerts"
    )
    parser.add_argument("--slo", type=float, required=True, help="target such as 0.999")
    parser.add_argument(
        "--window",
        action="append",
        required=True,
        metavar="NAME=ERRORS/TOTAL",
        help="repeatable, for example 1h=120/10000",
    )
    args = parser.parse_args()
    windows = {}
    for item in args.window:
        name, _, counts = item.partition("=")
        errors, _, total = counts.partition("/")
        windows[name] = (float(errors), float(total))
    print(json.dumps(evaluate(windows, args.slo), indent=2))


if __name__ == "__main__":
    main()
