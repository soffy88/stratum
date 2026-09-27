"""Small SLO/error-budget evaluator used by release gates."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SLOTarget:
    name: str
    metric: str
    threshold: float
    objective: float


@dataclass(frozen=True)
class SLOResult:
    name: str
    good_event_ratio: float
    objective: float
    error_budget: float
    remaining_budget: float
    passed: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "good_event_ratio": round(self.good_event_ratio, 6),
            "objective": self.objective,
            "error_budget": round(self.error_budget, 6),
            "remaining_budget": round(self.remaining_budget, 6),
            "passed": self.passed,
        }


def evaluate(target: SLOTarget, good_event_ratio: float) -> SLOResult:
    if (
        not isinstance(target.threshold, (int, float))
        or not math.isfinite(float(target.threshold))
        or target.threshold < 0.0
    ):
        raise ValueError("threshold must be a finite non-negative number")
    if not 0.0 <= target.objective <= 1.0 or not math.isfinite(float(target.objective)):
        raise ValueError("objective must be between 0 and 1")
    if (
        not isinstance(good_event_ratio, (int, float))
        or isinstance(good_event_ratio, bool)
        or not math.isfinite(float(good_event_ratio))
        or not 0.0 <= good_event_ratio <= 1.0
    ):
        raise ValueError("good_event_ratio must be between 0 and 1")
    remaining = good_event_ratio - target.objective
    return SLOResult(
        name=target.name,
        good_event_ratio=good_event_ratio,
        objective=target.objective,
        error_budget=1.0 - target.objective,
        remaining_budget=remaining,
        passed=remaining >= 0.0,
    )


def release_allowed(results: list[SLOResult]) -> bool:
    """Return false when any paging SLO has exhausted its error budget."""
    return bool(results) and all(result.passed for result in results)
