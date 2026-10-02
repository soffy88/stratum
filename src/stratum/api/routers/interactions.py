"""Reading progress + Reader action recording."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import insert

router = APIRouter(prefix="/api/v1/interactions", tags=["interactions"])


class ProgressUpdate(BaseModel):
    position: str
    completed: bool = False


class ReaderAction(BaseModel):
    action: Literal["important", "question", "contradict"]
    note: str | None = Field(None, max_length=20_000)

    @model_validator(mode="after")
    def semantic_actions_need_text(self) -> "ReaderAction":
        if self.action in {"question", "contradict"} and not (self.note or "").strip():
            raise ValueError(f"{self.action} action requires note")
        return self


ACTION_EVENT_TYPES = {
    "important": "content_marked_important",
    "question": "content_question",
    "contradict": "content_contradiction",
}


@router.post("/content/{content_id}/progress")
async def record_progress(content_id: str, body: ProgressUpdate, user_id: str = Depends(jwt_auth)):
    insert(
        "user_content_interaction",
        {
            "id": generate_ulid(),
            "user_id": user_id,
            "content_id": content_id,
            "interaction_type": "view",
            "payload": {"position": body.position, "completed": body.completed},
            "created_at": now_utc(),
        },
    )
    try:
        from stratum.services.personal_model import record_learning_event

        record_learning_event(
            user_id,
            object_type="substrate",
            object_id=content_id,
            event_type="content_progress",
            result={"position": body.position, "completed": body.completed},
            source="reader",
        )
    except Exception:
        # Keep the legacy interaction path available until migration 023 is
        # applied on every deployment.
        pass
    return {"status": "recorded"}


@router.post("/content/{content_id}/actions")
async def record_reader_action(
    content_id: str,
    body: ReaderAction,
    user_id: str = Depends(jwt_auth),
):
    """Record a semantic Reader action without pretending it is a Claim yet."""
    action_id = generate_ulid()
    payload = {"action": body.action, "note": body.note}
    insert(
        "user_content_interaction",
        {
            "id": action_id,
            "user_id": user_id,
            "content_id": content_id,
            "interaction_type": f"reader_{body.action}",
            "payload": payload,
            "created_at": now_utc(),
        },
    )

    from stratum.services.personal_model import record_learning_event

    event_id = record_learning_event(
        user_id,
        object_type="substrate",
        object_id=content_id,
        event_type=ACTION_EVENT_TYPES[body.action],
        result=payload,
        source="reader",
    )

    # “Important” is a user-level relevance signal only when content_id is a
    # substrate owned by this user. Platform-content actions stay auditable but
    # do not create a cross-namespace PersonalState by assumption.
    if body.action == "important":
        try:
            from stratum.db import get_conn
            from stratum.services.personal_model import owned_object_exists, upsert_personal_state

            with get_conn() as conn:
                if owned_object_exists(conn, user_id, "substrate", content_id):
                    upsert_personal_state(
                        conn,
                        user_id,
                        object_type="substrate",
                        object_id=content_id,
                        mastery=0.0,
                        interest=1.0,
                        certainty=1.0,
                        relevance=1.0,
                        source="explicit",
                        source_event_id=event_id or action_id,
                    )
        except Exception:
            # The interaction and event remain useful during migration rollout;
            # the optional ranking bridge must not turn the action into a 5xx.
            pass

    return {"status": "recorded", "action_id": action_id, "event_id": event_id}


@router.get("/content/{content_id}/progress")
async def get_progress(content_id: str, user_id: str = Depends(jwt_auth)):
    from stratum.db import query

    rows = query(
        "SELECT payload FROM user_content_interaction "
        "WHERE user_id = %(uid)s AND content_id = %(cid)s AND interaction_type = 'view' "
        "ORDER BY created_at DESC",
        {"uid": user_id, "cid": content_id},
        limit=1,
    )
    if rows:
        return rows[0].get("payload") or {"position": "start", "completed": False}
    return {"position": "start", "completed": False}
