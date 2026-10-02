"""Mastery Authority — sole canonical mastery adapter routing through C-warehouse.

``cx.learning_progress`` (C-warehouse, ``aii_context``) is the sole canonical
mastery authority.  This adapter is the single entry point for mastery
reads/writes.  It does NOT create a new mastery store; it uses the existing
``cx.learning_progress`` table.

Non-authorities (NOT mastery):
- ``localStorage`` completion/read/review state (frontend Deep Cards)
- ``cornell_progress`` (stratum) — Cornell note telemetry
- ``stratum.flashcards`` — flashcard scheduling/review state (FSRS/SM-2)

The flashcard scheduler and its history are preserved as-is; they are
scheduling state, not mastery authority.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from stratum.knowledge.knowledge_ref import KnowledgeRef, REPOSITORY_C

log = logging.getLogger(__name__)

DEFAULT_CONTEXT_DSN = "postgresql://aii:***REMOVED***@localhost:5436/aii_context"

GRADE_UNVERIFIED = "unverified"
GRADE_LEARNING = "learning"
GRADE_VERIFIED = "verified"

_VALID_GRADES = frozenset({GRADE_UNVERIFIED, GRADE_LEARNING, GRADE_VERIFIED})


@dataclass(frozen=True)
class MasteryState:
    """Mastery state for a knowledge object, read from cx.learning_progress."""

    ref: KnowledgeRef
    grade: str
    mastery_score: float
    attempts: int
    last_tested_at: datetime | None
    next_review_at: datetime | None


class MasteryAuthority:
    """Sole canonical mastery authority — routes through cx.learning_progress.

    This adapter is the ONLY way to read/write mastery.  It connects to the
    C-warehouse (``aii_context``) and uses the existing ``cx.learning_progress``
    table.  No new mastery store is created.

    Non-authority stores (flashcards, cornell_progress, localStorage) must
    NOT be used for mastery reads/writes.  They retain their own scheduling
    and telemetry state, but that state is not mastery.
    """

    def __init__(self, context_dsn: str | None = None) -> None:
        self._context_dsn = context_dsn or os.getenv(
            "CONTEXT_DATABASE_URL", DEFAULT_CONTEXT_DSN
        )

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self._context_dsn)

    def get_mastery(self, ref: KnowledgeRef) -> MasteryState | None:
        """Read mastery state for a knowledge ref from cx.learning_progress.

        Returns None if no learning progress record exists for the ref.
        The ref's object_id must be the point_id (as a string) for
        C-warehouse learning_point refs.
        """
        if ref.repository != REPOSITORY_C:
            log.warning(
                "MasteryAuthority.get_mastery called with non-C repository: %s",
                ref.repository,
            )
        try:
            point_id = int(ref.object_id)
        except (TypeError, ValueError):
            return None

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT point_id, grade, mastery_score, attempts, "
                    "last_tested_at, next_review_at "
                    "FROM cx.learning_progress WHERE point_id = %s",
                    (point_id,),
                )
                row = cur.fetchone()
        if not row:
            return None

        attempts_raw = row[3]
        if isinstance(attempts_raw, str):
            attempts_raw = json.loads(attempts_raw)
        attempts = attempts_raw if isinstance(attempts_raw, list) else []

        return MasteryState(
            ref=ref,
            grade=row[1] or GRADE_UNVERIFIED,
            mastery_score=float(row[2] or 0.0),
            attempts=len(attempts),
            last_tested_at=row[4],
            next_review_at=row[5],
        )

    def get_due_reviews(
        self, profile_id: int, *, now: datetime | None = None, limit: int = 50
    ) -> list[MasteryState]:
        """Get due review queue from cx.learning_progress for a profile."""
        now = now or datetime.now(timezone.utc)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT point_id, grade, mastery_score, attempts, "
                    "last_tested_at, next_review_at "
                    "FROM cx.learning_progress "
                    "WHERE profile_id = %s AND next_review_at IS NOT NULL "
                    "AND next_review_at <= %s "
                    "ORDER BY next_review_at ASC LIMIT %s",
                    (profile_id, now, limit),
                )
                rows = cur.fetchall()

        result = []
        for row in rows:
            ref = KnowledgeRef(
                repository=REPOSITORY_C,
                object_type="learning_point",
                object_id=str(row[0]),
            )
            attempts_raw = row[3]
            if isinstance(attempts_raw, str):
                attempts_raw = json.loads(attempts_raw)
            attempts = attempts_raw if isinstance(attempts_raw, list) else []
            result.append(
                MasteryState(
                    ref=ref,
                    grade=row[1] or GRADE_UNVERIFIED,
                    mastery_score=float(row[2] or 0.0),
                    attempts=len(attempts),
                    last_tested_at=row[4],
                    next_review_at=row[5],
                )
            )
        return result

    def record_attempt(
        self,
        ref: KnowledgeRef,
        *,
        passed: bool,
        judge: str,
        profile_id: int,
        point_name: str,
        b_repo_ku_ids: list[str] | None = None,
        knowledge_type: str | None = None,
    ) -> MasteryState:
        """Record a test attempt and return updated mastery state.

        This is the canonical write path for mastery.  It inserts or updates
        a cx.learning_progress row.  The ref's object_id is the point_id.

        For new points (ref.object_id == "0" or empty), a new row is created
        and the returned MasteryState has the updated ref with the real point_id.
        """
        now = datetime.now(timezone.utc)

        with self._connect() as conn:
            with conn.cursor() as cur:
                if ref.object_id and ref.object_id != "0":
                    point_id = int(ref.object_id)
                    cur.execute(
                        "SELECT attempts FROM cx.learning_progress WHERE point_id = %s",
                        (point_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise ValueError(
                            f"learning_progress point_id={point_id} not found"
                        )
                    attempts_raw = row[0]
                    if isinstance(attempts_raw, str):
                        attempts_raw = json.loads(attempts_raw)
                    attempts = attempts_raw if isinstance(attempts_raw, list) else []
                else:
                    cur.execute(
                        "INSERT INTO cx.learning_progress "
                        "(profile_id, point_name, b_repo_ku_ids, knowledge_type) "
                        "VALUES (%s, %s, %s, %s) RETURNING point_id",
                        (
                            profile_id,
                            point_name,
                            json.dumps(b_repo_ku_ids or []),
                            knowledge_type,
                        ),
                    )
                    point_id = cur.fetchone()[0]
                    ref = KnowledgeRef(
                        repository=REPOSITORY_C,
                        object_type="learning_point",
                        object_id=str(point_id),
                    )
                    attempts = []

                prior_passes = sum(1 for a in attempts if a.get("passed"))
                was_due = False
                cur.execute(
                    "SELECT next_review_at FROM cx.learning_progress WHERE point_id = %s",
                    (point_id,),
                )
                nra_row = cur.fetchone()
                if nra_row and nra_row[0]:
                    was_due = now >= nra_row[0]
                is_review = bool(passed and prior_passes >= 1 and was_due)

                attempts.append(
                    {
                        "ts": now.isoformat(),
                        "type": judge,
                        "passed": passed,
                        "is_review": is_review,
                    }
                )

                mastery = _compute_mastery_score(attempts)
                total_passes = sum(1 for a in attempts if a.get("passed"))
                review_passes = sum(
                    1 for a in attempts if a.get("passed") and a.get("is_review")
                )
                if passed and total_passes >= 2 and review_passes >= 1:
                    new_grade = GRADE_VERIFIED
                else:
                    new_grade = GRADE_LEARNING

                next_review = now + _next_review_interval(prior_passes, passed)

                cur.execute(
                    "UPDATE cx.learning_progress SET "
                    "grade = %s, verified_by = %s, last_tested_at = %s, "
                    "next_review_at = %s, attempts = %s, mastery_score = %s, "
                    "updated_at = now() WHERE point_id = %s",
                    (
                        new_grade,
                        judge,
                        now,
                        next_review,
                        json.dumps(attempts, ensure_ascii=False),
                        mastery,
                        point_id,
                    ),
                )
                conn.commit()

        return MasteryState(
            ref=ref,
            grade=new_grade,
            mastery_score=mastery,
            attempts=len(attempts),
            last_tested_at=now,
            next_review_at=next_review,
        )


def _compute_mastery_score(attempts: list[dict]) -> float:
    """Recency-weighted mastery score with confidence cap.

    1 attempt max 0.5, 2 attempts max 0.8 — prevents premature mastery.
    """
    if not attempts:
        return 0.0
    recent = attempts[-5:]
    weights = [0.5, 0.7, 0.85, 0.95, 1.0][-len(recent):]
    num = sum(w * (1.0 if a.get("passed") else 0.0) for w, a in zip(weights, recent))
    den = sum(weights)
    score = (num / den) if den else 0.0
    cap = {1: 0.5, 2: 0.8}.get(len(attempts), 1.0)
    return round(min(score, cap), 3)


def _next_review_interval(attempt_count: int, passed: bool):
    """SM-2-style interval: 1/3/7/14/30/60 days."""
    from datetime import timedelta

    if not passed:
        return timedelta(days=1)
    schedule = [1, 3, 7, 14, 30, 60]
    return timedelta(days=schedule[min(attempt_count, len(schedule) - 1)])
