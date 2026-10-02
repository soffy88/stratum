"""Spaced-repetition scheduling for knowledge cards.

The production scheduler is the public ``py-fsrs`` implementation.  The
adapter keeps the old SM-2 fields in the public row shape so existing clients
and cards can be upgraded without a destructive rewrite.  If an old, minimal
development image does not have ``fsrs`` installed, the legacy scheduler is
used explicitly as a compatibility fallback; production images declare FSRS
as a runtime dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

RATINGS: tuple[str, ...] = ("again", "hard", "good", "easy")

_MIN_EASE = 1.3
_AGAIN_REVIEW_MINUTES = 10

try:  # pragma: no cover - exercised in the runtime image and integration CI
    from fsrs import Card as FSRSCard
    from fsrs import Rating as FSRSRating
    from fsrs import Scheduler as FSRSScheduler
    from fsrs import State as FSRSState

    FSRS_AVAILABLE = True
except ImportError:  # pragma: no cover - compatibility path for minimal images
    FSRSCard = None  # type: ignore[assignment,misc]
    FSRSRating = None  # type: ignore[assignment,misc]
    FSRSScheduler = None  # type: ignore[assignment,misc]
    FSRSState = None  # type: ignore[assignment,misc]
    FSRS_AVAILABLE = False


@dataclass(frozen=True)
class ReviewState:
    """Persisted scheduler state.

    ``easiness`` and ``interval_days`` are retained for backwards-compatible
    exports and old clients.  FSRS uses ``fsrs_state``, ``fsrs_step``,
    ``stability``, ``difficulty`` and ``last_review`` as its canonical state.
    """

    repetitions: int = 0
    easiness: float = 2.5
    interval_days: float = 0.0
    fsrs_state: int = 1
    fsrs_step: int | None = 0
    stability: float | None = None
    difficulty: float | None = None
    last_review: datetime | None = None


def _as_utc(value: datetime | None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _legacy_schedule_review(
    state: ReviewState, rating: str, now: datetime
) -> tuple[ReviewState, datetime]:
    """Old SM-2 behavior used only when FSRS is unavailable."""
    reps, ease, interval = state.repetitions, state.easiness, state.interval_days

    if rating == "again":
        reps = 0
        interval = 0.0
        ease = max(_MIN_EASE, ease - 0.2)
        due = now + timedelta(minutes=_AGAIN_REVIEW_MINUTES)
    elif rating == "hard":
        reps = max(1, reps + 1)
        ease = max(_MIN_EASE, ease - 0.15)
        interval = max(1.0, interval * 1.2)
        due = now + timedelta(days=interval)
    elif rating == "good":
        reps += 1
        if reps == 1:
            interval = 1.0
        elif reps == 2:
            interval = 6.0
        else:
            interval = round(interval * ease, 1)
        due = now + timedelta(days=interval)
    else:  # easy
        reps += 1
        if reps == 1:
            interval = 4.0
        elif reps == 2:
            interval = 10.0
        else:
            interval = round(interval * ease * 1.3, 1)
        ease += 0.15
        due = now + timedelta(days=interval)

    return replace(state, repetitions=reps, easiness=ease, interval_days=interval), due


def schedule_review(
    state: ReviewState,
    rating: str,
    now: datetime | None = None,
    *,
    desired_retention: float = 0.9,
) -> tuple[ReviewState, datetime]:
    """Apply a review rating and return ``(new_state, due_at)``.

    ``desired_retention`` is the user's FSRS control knob.  Fuzzing is disabled
    here so an API request is deterministic and reproducible; the scheduler can
    still be configured with fuzzing in an offline optimizer later.
    """
    if rating not in RATINGS:
        raise ValueError(f"rating must be one of {RATINGS}, got {rating!r}")
    if not 0.5 <= desired_retention <= 0.99:
        raise ValueError("desired_retention must be between 0.5 and 0.99")
    now = _as_utc(now)

    if not FSRS_AVAILABLE:
        return _legacy_schedule_review(state, rating, now)

    # py-fsrs uses the same four ratings and three card states as the API.
    try:
        fsrs_state = FSRSState(state.fsrs_state)
    except ValueError:
        fsrs_state = FSRSState.Learning

    card = FSRSCard(
        card_id=1,
        state=fsrs_state,
        step=state.fsrs_step,
        stability=state.stability,
        difficulty=state.difficulty,
        due=now,
        last_review=state.last_review,
    )
    scheduler = FSRSScheduler(
        desired_retention=desired_retention,
        enable_fuzzing=False,
    )
    updated, _ = scheduler.review_card(
        card,
        getattr(FSRSRating, rating.capitalize()),
        review_datetime=now,
    )
    interval_days = max(0.0, (updated.due - now).total_seconds() / 86400)
    return replace(
        state,
        repetitions=state.repetitions + 1,
        interval_days=round(interval_days, 6),
        fsrs_state=int(updated.state),
        fsrs_step=updated.step,
        stability=updated.stability,
        difficulty=updated.difficulty,
        last_review=updated.last_review,
    ), updated.due


def card_retrievability(
    state: ReviewState,
    at: datetime | None = None,
    *,
    desired_retention: float = 0.9,
) -> float:
    """Return FSRS's predicted recall probability for a persisted state."""
    if not FSRS_AVAILABLE or state.stability is None or state.last_review is None:
        return 0.0
    at = _as_utc(at)
    try:
        fsrs_state = FSRSState(state.fsrs_state)
    except ValueError:
        fsrs_state = FSRSState.Learning
    card = FSRSCard(
        card_id=1,
        state=fsrs_state,
        step=state.fsrs_step,
        stability=state.stability,
        difficulty=state.difficulty,
        due=at,
        last_review=_as_utc(state.last_review),
    )
    scheduler = FSRSScheduler(
        desired_retention=desired_retention,
        enable_fuzzing=False,
    )
    card_method = getattr(card, "get_retrievability", None)
    if callable(card_method):
        return round(float(card_method(at)), 6)
    scheduler_method = getattr(scheduler, "get_card_retrievability", None)
    if callable(scheduler_method):
        return round(float(scheduler_method(card, at)), 6)
    return 0.0


def review_priority(
    state: ReviewState,
    *,
    personal_relevance: float = 1.0,
    prerequisite_importance: float = 1.0,
    at: datetime | None = None,
) -> float:
    """Score a card from FSRS forgetting risk and explicit product signals."""
    risk = 1.0 - card_retrievability(state, at=at)
    return round(
        max(0.0, risk)
        * max(0.0, min(1.0, personal_relevance))
        * max(0.0, min(1.0, prerequisite_importance)),
        6,
    )
