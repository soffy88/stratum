"""SM-2 间隔复习调度 (闪卡复习核心, 纯函数, 无外部依赖).

评级: again / hard / good / easy
- again: 重学, 10 分钟后到期, 熟练度清零, 易度 -0.2
- hard:  间隔 ×1.2 (至少 1 天), 易度 -0.15
- good:  SM-2 标准间隔 (1d → 6d → 间隔×易度), 易度不变
- easy:  加速间隔 (4d → 10d → 间隔×易度×1.3), 易度 +0.15

未来可无缝替换为 FSRS (镜像内已装 `fsrs`), 接口不变。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

RATINGS: tuple[str, ...] = ("again", "hard", "good", "easy")

_MIN_EASE = 1.3
_AGAIN_REVIEW_MINUTES = 10


@dataclass(frozen=True)
class ReviewState:
    repetitions: int = 0
    easiness: float = 2.5
    interval_days: float = 0.0


def schedule_review(
    state: ReviewState, rating: str, now: datetime | None = None
) -> tuple[ReviewState, datetime]:
    """应用一次复习评级, 返回 (新状态, 下次到期时间)。now 传 UTC aware datetime。"""
    if rating not in RATINGS:
        raise ValueError(f"rating must be one of {RATINGS}, got {rating!r}")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

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
