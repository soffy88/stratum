import uuid
import datetime
import json
from typing import Any, Dict, List, Optional
import stratum.db as db

class BookReadingRun:
    def __init__(self, data: dict[str, Any]):
        self.id = data.get("id")
        self.user_id = data.get("user_id")
        self.source_id = data.get("source_id")
        self.source_version = data.get("source_version")
        self.status = data.get("status")
        self.current_pass = data.get("current_pass", 1)
        self.parser_version = data.get("parser_version")
        self.reader_version = data.get("reader_version")
        self.extractor_version = data.get("extractor_version")
        self.verifier_version = data.get("verifier_version")
        
        # P2: Keep ReadingCoverage, UnderstandingCoverage, EvidenceCoverage separate.
        cov = data.get("coverage_json")
        if isinstance(cov, str):
            cov = json.loads(cov)
        self.coverage_json = cov or {
            "reading": {},
            "evidence": {},
            "understanding": {}
        }
        
        gaps = data.get("open_gaps_json")
        if isinstance(gaps, str):
            gaps = json.loads(gaps)
        self.open_gaps_json = gaps or []
        
        self.started_at = data.get("started_at")
        self.completed_at = data.get("completed_at")
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")

class ReadingLedgerItem:
    def __init__(self, data: dict[str, Any]):
        self.id = data.get("id")
        self.run_id = data.get("run_id")
        self.item_type = data.get("item_type")
        self.item_identifier = data.get("item_identifier")
        self.status = data.get("status")
        
        loc = data.get("locator_json")
        if isinstance(loc, str):
            loc = json.loads(loc)
        self.locator_json = loc or {}
        
        self.page_number = data.get("page_number")
        self.expected = data.get("expected", True)
        
        trc = data.get("trace_json")
        if isinstance(trc, str):
            trc = json.loads(trc)
        self.trace_json = trc or {}
        
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")

def create_reading_run(user_id: str, source_id: str, source_version: str = None) -> BookReadingRun:
    """Runtime resumable/replayable creation of a reading run."""
    # Idempotency: check if there's already an active run
    existing = db.query(
        "SELECT * FROM stratum.book_reading_run WHERE user_id = %(user_id)s AND source_id = %(source_id)s AND status NOT IN ('completed', 'failed')",
        {"user_id": user_id, "source_id": source_id},
        limit=1
    )
    if existing:
        return BookReadingRun(existing[0])
        
    run_id = f"br_{uuid.uuid4().hex}"
    now = datetime.datetime.now(datetime.timezone.utc)
    data = {
        "id": run_id,
        "user_id": user_id,
        "source_id": source_id,
        "source_version": source_version,
        "status": "planned",
        "current_pass": 1,
        "coverage_json": json.dumps({"reading": {}, "evidence": {}, "understanding": {}}),
        "open_gaps_json": json.dumps([]),
        "started_at": None,
        "completed_at": None,
        "created_at": now,
        "updated_at": now
    }
    db.insert("stratum.book_reading_run", data)
    return BookReadingRun(data)

def initialize_source_accounting(run_id: str, expected_items: List[Dict[str, Any]]):
    """
    Full source accounting: expected pages/sections/figures/tables/equations
    known before claiming reading coverage.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    for item in expected_items:
        data = {
            "id": f"rl_{uuid.uuid4().hex}",
            "run_id": run_id,
            "item_type": item["item_type"],
            "item_identifier": item["item_identifier"],
            "status": "UNSEEN",
            "locator_json": json.dumps(item.get("locator_json", {})),
            "page_number": item.get("page_number"),
            "expected": True,
            "trace_json": json.dumps({}),
            "created_at": now,
            "updated_at": now
        }
        # Idempotent write
        db.write(
            "stratum.reading_ledger",
            data,
            conflict_on=["run_id", "item_type", "item_identifier"]
        )

def update_ledger_status(run_id: str, item_type: str, item_identifier: str, status: str, trace_update: dict = None):
    """
    Incrementally repairable / update item status.
    Statuses: UNSEEN, PARSED, READ, INTERPRETED, RECONCILED, VERIFIED, UNREADABLE, NEEDS_VISUAL_REVIEW.
    """
    items = db.query(
        "SELECT * FROM stratum.reading_ledger WHERE run_id = %(run_id)s AND item_type = %(item_type)s AND item_identifier = %(item_identifier)s",
        {"run_id": run_id, "item_type": item_type, "item_identifier": item_identifier},
        limit=1
    )
    if not items:
        # Unexpected item found during reading, add it
        data = {
            "id": f"rl_{uuid.uuid4().hex}",
            "run_id": run_id,
            "item_type": item_type,
            "item_identifier": item_identifier,
            "status": status,
            "expected": False,
            "locator_json": "{}",
            "trace_json": json.dumps(trace_update or {}),
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "updated_at": datetime.datetime.now(datetime.timezone.utc)
        }
        db.write("stratum.reading_ledger", data, conflict_on=["run_id", "item_type", "item_identifier"])
    else:
        # Update existing
        item = items[0]
        trc = item.get("trace_json", {})
        if isinstance(trc, str):
            trc = json.loads(trc)
        if trace_update:
            trc.update(trace_update)
            
        update_data = {
            "status": status,
            "trace_json": json.dumps(trc),
            "updated_at": datetime.datetime.now(datetime.timezone.utc)
        }
        db.update("stratum.reading_ledger", item["id"], update_data)
