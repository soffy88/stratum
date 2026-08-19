"""康奈尔笔记 API — 机器(B仓汇编) + 人类笔记共存。

GET  /api/v1/cornell              列表(机器共享 + 本人 human)
GET  /api/v1/cornell/{id}         详情
POST /api/v1/cornell/generate     从 B仓 concept 生成/刷新机器笔记
POST /api/v1/cornell              人类新建康奈尔
PUT  /api/v1/cornell/{id}         更新(仅 human 本人)
DELETE /api/v1/cornell/{id}       软删
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import execute, insert, query, read, update
from stratum.services.cornell_generator import (
    generate_for_concept,
    list_core_concept_ids,
    stable_note_id,
)

router = APIRouter(prefix="/api/v1/cornell", tags=["cornell"])


def _parse_json_field(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def _row_out(row: dict) -> dict:
    if not row:
        return row
    out = dict(row)
    for k in ("content", "refined_ku_ids", "refined_concept_ids"):
        if k in out:
            out[k] = _parse_json_field(out[k])
    # 统一前端字段
    out["kind"] = "cornell"
    out["content_preview"] = None
    c = out.get("content")
    if isinstance(c, dict):
        out["content_preview"] = (c.get("oneLiner") or c.get("summary") or "")[:160]
        out["cue_count"] = len(c.get("cues") or [])
        out["module_count"] = len(c.get("modules") or [])
    return out


class GenerateBody(BaseModel):
    concept_id: int | None = None
    concept_ids: list[int] = Field(default_factory=list)
    discipline: str | None = None
    limit: int = 20
    max_kus: int = 8
    polish: bool = False  # NIM 润色线索/总结(每 key 40rpm)


class PolishBody(BaseModel):
    note_ids: list[str] = Field(default_factory=list)
    limit: int = 10  # 未指定 note_ids 时处理最新 N 条机器笔记


class ProgressBody(BaseModel):
    topic_id: str
    note_id: str | None = None
    state: dict
    # state: {version, mastered, collapsed, selfTest, showAnswers, updatedAt, drills?}


class CornellCreate(BaseModel):
    title: str
    subject: str | None = None
    topic_id: str | None = None
    content: dict


class CornellUpdate(BaseModel):
    title: str | None = None
    subject: str | None = None
    content: dict | None = None


def _merge_progress(local: dict, remote: dict) -> dict:
    """mastered/collapsed 键级并集; 布尔偏好取 updatedAt 较新。"""
    out = dict(remote or {})
    loc = local or {}
    mastered = dict(out.get("mastered") or {})
    for k, v in (loc.get("mastered") or {}).items():
        if v:
            mastered[k] = True
    collapsed = {**(out.get("collapsed") or {}), **(loc.get("collapsed") or {})}
    drills = {**(out.get("drills") or {}), **(loc.get("drills") or {})}
    newer = loc if (loc.get("updatedAt") or "") >= (out.get("updatedAt") or "") else out
    return {
        "version": 1,
        "topicId": loc.get("topicId") or out.get("topicId"),
        "mastered": mastered,
        "collapsed": collapsed,
        "drills": drills,
        "selfTest": bool(newer.get("selfTest")),
        "showAnswers": bool(newer.get("showAnswers")),
        "updatedAt": max(loc.get("updatedAt") or "", out.get("updatedAt") or ""),
    }


@router.get("")
async def list_cornell(
    source: str | None = Query(None, description="machine|human|all"),
    subject: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(jwt_auth),
):
    """机器笔记(共享) + 本人 human 笔记。"""
    clauses = ["deleted_at IS NULL"]
    params: dict[str, Any] = {"lim": limit}
    if source == "machine":
        clauses.append("source = 'machine'")
    elif source == "human":
        clauses.append("source = 'human' AND user_id = %(uid)s")
        params["uid"] = user_id
    else:
        clauses.append("(source = 'machine' OR (source = 'human' AND user_id = %(uid)s))")
        params["uid"] = user_id
    if subject:
        clauses.append("subject = %(subject)s")
        params["subject"] = subject
    where = " AND ".join(clauses)
    rows = query(
        f"""
        SELECT id, topic_id, title, subject, source, refined_ku_ids, refined_concept_ids,
               content, user_id, created_at, updated_at
        FROM cornell_notes
        WHERE {where}
        ORDER BY updated_at DESC
        LIMIT %(lim)s
        """,
        params,
    )
    return [_row_out(r) for r in rows]


@router.post("/generate")
async def generate_cornell(body: GenerateBody, user_id: str = Depends(jwt_auth)):
    """从 B仓概念生成/刷新机器康奈尔笔记(幂等 topic_id)。"""
    ids = list(body.concept_ids)
    if body.concept_id is not None:
        ids.append(body.concept_id)
    if not ids:
        ids = list_core_concept_ids(discipline=body.discipline, limit=body.limit)
    created, updated, skipped = [], [], []
    for cid in ids:
        try:
            gen = generate_for_concept(cid, max_kus=body.max_kus, polish=body.polish)
        except Exception as e:  # noqa: BLE001
            skipped.append({"concept_id": cid, "error": str(e)[:120]})
            continue
        if not gen:
            skipped.append({"concept_id": cid, "error": "no_kus"})
            continue
        note_id = stable_note_id(gen["topic_id"], "machine")
        existing = read("cornell_notes", note_id)
        ts = now_utc()
        payload = {
            "id": note_id,
            "topic_id": gen["topic_id"],
            "title": gen["title"],
            "subject": gen["subject"],
            "source": "machine",
            "refined_ku_ids": json.dumps(gen["refined_ku_ids"], ensure_ascii=False),
            "refined_concept_ids": json.dumps(gen["refined_concept_ids"], ensure_ascii=False),
            "content": json.dumps(gen["content"], ensure_ascii=False),
            "user_id": None,
            "updated_at": ts,
            "deleted_at": None,
        }
        if existing and not existing.get("deleted_at"):
            update(
                "cornell_notes",
                note_id,
                {
                    "title": payload["title"],
                    "subject": payload["subject"],
                    "refined_ku_ids": payload["refined_ku_ids"],
                    "refined_concept_ids": payload["refined_concept_ids"],
                    "content": payload["content"],
                    "updated_at": ts,
                },
            )
            updated.append(note_id)
        else:
            payload["created_at"] = ts
            if existing and existing.get("deleted_at"):
                update(
                    "cornell_notes",
                    note_id,
                    {
                        "title": payload["title"],
                        "subject": payload["subject"],
                        "refined_ku_ids": payload["refined_ku_ids"],
                        "refined_concept_ids": payload["refined_concept_ids"],
                        "content": payload["content"],
                        "updated_at": ts,
                        "deleted_at": None,
                    },
                )
                updated.append(note_id)
            else:
                insert("cornell_notes", payload)
                created.append(note_id)
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "n_created": len(created),
        "n_updated": len(updated),
        "n_skipped": len(skipped),
    }


@router.post("/polish")
async def polish_cornell(body: PolishBody, user_id: str = Depends(jwt_auth)):
    """NIM 润色已有机器笔记的线索/总结(不改 modules 原文)。"""
    from stratum.services.cornell_polish import polish_content, build_drills

    ids = list(body.note_ids)
    if not ids:
        rows = query(
            """
            SELECT id FROM cornell_notes
            WHERE deleted_at IS NULL AND source = 'machine'
            ORDER BY updated_at DESC LIMIT %(lim)s
            """,
            {"lim": body.limit},
        )
        ids = [r["id"] for r in rows]
    done, failed = [], []
    for i, nid in enumerate(ids):
        row = read("cornell_notes", nid)
        if not row or row.get("deleted_at"):
            failed.append({"id": nid, "error": "not_found"})
            continue
        content = _parse_json_field(row.get("content"))
        if not isinstance(content, dict):
            failed.append({"id": nid, "error": "bad_content"})
            continue
        try:
            polished = polish_content(content)
            polished["drills"] = build_drills(polished)
            update(
                "cornell_notes",
                nid,
                {
                    "content": json.dumps(polished, ensure_ascii=False),
                    "updated_at": now_utc(),
                },
            )
            done.append(nid)
        except Exception as e:  # noqa: BLE001
            failed.append({"id": nid, "error": str(e)[:120]})
    return {"polished": done, "failed": failed, "n_ok": len(done), "n_fail": len(failed)}


@router.get("/progress/{topic_id}")
async def get_progress(topic_id: str, user_id: str = Depends(jwt_auth)):
    """拉取云端进度(CloudSyncAdapter.pull)。"""
    rows = query(
        """
        SELECT user_id, topic_id, note_id, state, updated_at
        FROM cornell_progress
        WHERE user_id = %(uid)s AND topic_id = %(tid)s
        """,
        {"uid": user_id, "tid": topic_id},
    )
    if not rows:
        return {"topic_id": topic_id, "state": None}
    r = rows[0]
    return {
        "topic_id": r["topic_id"],
        "note_id": r.get("note_id"),
        "state": _parse_json_field(r.get("state")),
        "updated_at": r.get("updated_at"),
    }


@router.put("/progress/{topic_id}")
async def put_progress(
    topic_id: str, body: ProgressBody, user_id: str = Depends(jwt_auth)
):
    """推送进度: 与云端并集合并后写回(CloudSyncAdapter.push)。"""
    if body.topic_id and body.topic_id != topic_id:
        raise HTTPException(400, "topic_id mismatch")
    rows = query(
        "SELECT state FROM cornell_progress WHERE user_id=%(uid)s AND topic_id=%(tid)s",
        {"uid": user_id, "tid": topic_id},
    )
    remote = _parse_json_field(rows[0]["state"]) if rows else {}
    if not isinstance(remote, dict):
        remote = {}
    local = dict(body.state or {})
    local.setdefault("topicId", topic_id)
    merged = _merge_progress(local, remote)
    if not merged.get("updatedAt"):
        merged["updatedAt"] = now_utc().isoformat() if hasattr(now_utc(), "isoformat") else str(now_utc())
    ts = now_utc()
    state_json = json.dumps(merged, ensure_ascii=False)
    if rows:
        execute(
            """
            UPDATE cornell_progress
            SET state=%(st)s, note_id=%(nid)s, updated_at=%(ts)s
            WHERE user_id=%(uid)s AND topic_id=%(tid)s
            """,
            {
                "st": state_json,
                "nid": body.note_id,
                "ts": ts,
                "uid": user_id,
                "tid": topic_id,
            },
        )
    else:
        insert(
            "cornell_progress",
            {
                "user_id": user_id,
                "topic_id": topic_id,
                "note_id": body.note_id,
                "state": state_json,
                "updated_at": ts,
            },
        )
    return {"topic_id": topic_id, "state": merged, "status": "ok"}


@router.get("/{note_id}")
async def get_cornell(note_id: str, user_id: str = Depends(jwt_auth)):
    row = read("cornell_notes", note_id)
    if not row or row.get("deleted_at"):
        raise HTTPException(404, "Cornell note not found")
    if row.get("source") == "human" and row.get("user_id") != user_id:
        raise HTTPException(404, "Cornell note not found")
    return _row_out(row)


@router.post("")
async def create_human_cornell(body: CornellCreate, user_id: str = Depends(jwt_auth)):
    note_id = generate_ulid()
    ts = now_utc()
    topic = body.topic_id or f"human-{note_id[:10]}"
    content = dict(body.content)
    content.setdefault("version", 1)
    content.setdefault("topicId", topic)
    content.setdefault("title", body.title)
    content.setdefault("cues", [])
    content.setdefault("modules", [])
    content.setdefault("summary", "")
    content.setdefault("oneLiner", "")
    insert(
        "cornell_notes",
        {
            "id": note_id,
            "topic_id": topic,
            "title": body.title,
            "subject": body.subject,
            "source": "human",
            "refined_ku_ids": "[]",
            "refined_concept_ids": "[]",
            "content": json.dumps(content, ensure_ascii=False),
            "user_id": user_id,
            "created_at": ts,
            "updated_at": ts,
        },
    )
    return {"note_id": note_id, "status": "created", "kind": "cornell"}


@router.put("/{note_id}")
async def update_cornell(
    note_id: str, body: CornellUpdate, user_id: str = Depends(jwt_auth)
):
    row = read("cornell_notes", note_id)
    if not row or row.get("deleted_at"):
        raise HTTPException(404, "Cornell note not found")
    if row.get("source") != "human" or row.get("user_id") != user_id:
        raise HTTPException(403, "只能编辑自己的人类康奈尔笔记")
    changes: dict[str, Any] = {"updated_at": now_utc()}
    if body.title is not None:
        changes["title"] = body.title
    if body.subject is not None:
        changes["subject"] = body.subject
    if body.content is not None:
        changes["content"] = json.dumps(body.content, ensure_ascii=False)
    update("cornell_notes", note_id, changes)
    return {"note_id": note_id, "status": "updated"}


@router.delete("/{note_id}")
async def delete_cornell(note_id: str, user_id: str = Depends(jwt_auth)):
    row = read("cornell_notes", note_id)
    if not row or row.get("deleted_at"):
        raise HTTPException(404, "Cornell note not found")
    if row.get("source") == "machine":
        raise HTTPException(403, "机器康奈尔笔记不可删除")
    if row.get("source") == "human" and row.get("user_id") != user_id:
        raise HTTPException(403, "只能删除自己的笔记")
    update("cornell_notes", note_id, {"deleted_at": now_utc()})
    return {"note_id": note_id, "status": "deleted"}
