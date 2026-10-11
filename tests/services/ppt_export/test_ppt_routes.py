"""PPT export routes: auth, ownership (IDOR), job lifecycle, download safety."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-sl-unit-tests-32x")

from stratum.api.routers import ppt_export as router_mod  # noqa: E402
from stratum.common import create_token  # noqa: E402
from stratum.services.ppt_export import jobs  # noqa: E402

ALICE, BOB = "user-alice", "user-bob"


def _auth(uid: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(uid)}"}


class FakeStore:
    """In-memory stand-in for the jobs table, keyed exactly like the SQL is."""

    def __init__(self):
        self.books = {"sub_alice": jobs.owner_of(ALICE), "sub_raw": ALICE}
        self.runs = {"br_alice": "sub_alice"}
        self.rows: dict[str, dict] = {}
        self.ran: list[tuple[str, str]] = []

    def owned_substrate(self, uid, sid):
        owner = self.books.get(sid)
        return {"id": sid, "title": "书"} if owner in (uid, jobs.owner_of(uid)) else None

    def owned_run(self, uid, rid):
        sid = self.runs.get(rid)
        return self.owned_substrate(uid, sid) if sid else None

    def create_job(self, uid, sid, *, style, pages, chapter_id=None, run_id=None, options=None):
        jid = f"job{len(self.rows) + 1}"
        self.rows[jid] = {
            "id": jid,
            "user_id": jobs.owner_of(uid),
            "substrate_id": sid,
            "run_id": run_id,
            "chapter_id": chapter_id,
            "style": style,
            "pages": pages,
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "preview_count": 0,
            "qa_json": {},
            "created_at": datetime.now(UTC),
        }
        return dict(self.rows[jid])

    def get_job(self, uid, jid):
        row = self.rows.get(jid)
        return dict(row) if row and row["user_id"] == jobs.owner_of(uid) else None

    def list_jobs(self, uid, sid=None, limit=20):
        return [
            dict(r)
            for r in self.rows.values()
            if r["user_id"] == jobs.owner_of(uid) and (sid is None or r["substrate_id"] == sid)
        ]

    def run_job(self, jid, owner):
        self.ran.append((jid, owner))


@pytest.fixture
def store(monkeypatch, tmp_path):
    s = FakeStore()
    for name in ("owned_substrate", "owned_run", "create_job", "get_job", "list_jobs", "run_job"):
        monkeypatch.setattr(jobs, name, getattr(s, name))
    monkeypatch.setattr(jobs, "exports_root", lambda: tmp_path / "ppt_exports")
    return s


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router_mod.router)
    return TestClient(app)


def test_styles_are_public_and_list_14_presets(client):
    r = client.get("/api/v1/ppt/styles")
    assert r.status_code == 200
    body = r.json()
    assert len(body["styles"]) == 14
    assert body["default"] in {s["id"] for s in body["styles"]}
    assert body["pages"]["min"] <= body["pages"]["default"] <= body["pages"]["max"]


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/v1/ppt/exports"),
        ("get", "/api/v1/ppt/exports"),
        ("get", "/api/v1/ppt/exports/job1"),
        ("get", "/api/v1/ppt/exports/job1/download"),
        ("get", "/api/v1/ppt/books/sub_alice/chapters"),
    ],
)
def test_endpoints_require_a_token(client, store, method, path):
    r = getattr(client, method)(path, **({"json": {}} if method == "post" else {}))
    assert r.status_code == 401


def test_create_export_queues_background_job(client, store):
    r = client.post(
        "/api/v1/ppt/exports",
        json={"substrate_id": "sub_alice", "style": "paper-notes", "pages": 10},
        headers=_auth(ALICE),
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued" and body["download_url"] is None
    assert store.ran == [(body["job_id"], jobs.owner_of(ALICE))]


def test_raw_owner_id_books_are_accepted(client, store):
    r = client.post("/api/v1/ppt/exports", json={"substrate_id": "sub_raw"}, headers=_auth(ALICE))
    assert r.status_code == 202


def test_foreign_book_is_404_and_starts_nothing(client, store):
    r = client.post("/api/v1/ppt/exports", json={"substrate_id": "sub_alice"}, headers=_auth(BOB))
    assert r.status_code == 404
    assert store.rows == {} and store.ran == []
    r = client.post("/api/v1/ppt/exports", json={"run_id": "br_alice"}, headers=_auth(BOB))
    assert r.status_code == 404
    r = client.get("/api/v1/ppt/books/sub_alice/chapters", headers=_auth(BOB))
    assert r.status_code == 404


def test_run_id_must_belong_to_the_named_book(client, store):
    store.books["sub_other"] = jobs.owner_of(ALICE)
    r = client.post(
        "/api/v1/ppt/exports",
        json={"substrate_id": "sub_other", "run_id": "br_alice"},
        headers=_auth(ALICE),
    )
    assert r.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"substrate_id": "sub_alice", "style": "comic-sans"},
        {"substrate_id": "sub_alice", "pages": 2},
        {"substrate_id": "sub_alice", "pages": 200},
        {"style": "paper-notes"},
    ],
)
def test_invalid_requests_are_422(client, store, payload):
    r = client.post("/api/v1/ppt/exports", json=payload, headers=_auth(ALICE))
    assert r.status_code == 422
    assert store.ran == []


def test_other_users_job_is_indistinguishable_from_missing(client, store):
    jid = client.post(
        "/api/v1/ppt/exports", json={"substrate_id": "sub_alice"}, headers=_auth(ALICE)
    ).json()["job_id"]
    for path in ("", "/download", "/previews/1"):
        r = client.get(f"/api/v1/ppt/exports/{jid}{path}", headers=_auth(BOB))
        assert r.status_code == 404, path
    assert client.get("/api/v1/ppt/exports", headers=_auth(BOB)).json()["exports"] == []
    mine = client.get("/api/v1/ppt/exports?substrate_id=sub_alice", headers=_auth(ALICE))
    assert [e["job_id"] for e in mine.json()["exports"]] == [jid]


def test_download_lifecycle(client, store, tmp_path):
    jid = client.post(
        "/api/v1/ppt/exports", json={"substrate_id": "sub_alice"}, headers=_auth(ALICE)
    ).json()["job_id"]
    assert (
        client.get(f"/api/v1/ppt/exports/{jid}/download", headers=_auth(ALICE)).status_code == 409
    )

    d = jobs.job_dir(jobs.owner_of(ALICE), jid)
    (d / "previews").mkdir(parents=True)
    (d / "deck.pptx").write_bytes(b"PK\x03\x04fake-pptx")
    (d / "previews" / "slide-01.png").write_bytes(b"\x89PNG fake")
    store.rows[jid].update(
        status="succeeded",
        progress=100,
        file_path=str(d / "deck.pptx"),
        preview_count=1,
        title="导数让变化可以精确度量",
    )
    status = client.get(f"/api/v1/ppt/exports/{jid}", headers=_auth(ALICE)).json()
    assert status["download_url"].endswith("/download")
    assert status["preview_urls"] == [f"/api/v1/ppt/exports/{jid}/previews/1"]

    r = client.get(f"/api/v1/ppt/exports/{jid}/download", headers=_auth(ALICE))
    assert r.status_code == 200 and r.content.startswith(b"PK")
    assert "presentationml" in r.headers["content-type"]
    assert "filename*=utf-8''" in r.headers["content-disposition"]
    assert (
        client.get(f"/api/v1/ppt/exports/{jid}/previews/1", headers=_auth(ALICE)).status_code == 200
    )
    assert (
        client.get(f"/api/v1/ppt/exports/{jid}/previews/2", headers=_auth(ALICE)).status_code == 404
    )


def test_download_refuses_paths_outside_the_job_dir(client, store, tmp_path):
    jid = client.post(
        "/api/v1/ppt/exports", json={"substrate_id": "sub_alice"}, headers=_auth(ALICE)
    ).json()["job_id"]
    outside = tmp_path / "secret.pptx"
    outside.write_bytes(b"PK secret")
    store.rows[jid].update(status="succeeded", file_path=str(outside))
    r = client.get(f"/api/v1/ppt/exports/{jid}/download", headers=_auth(ALICE))
    assert r.status_code == 404
