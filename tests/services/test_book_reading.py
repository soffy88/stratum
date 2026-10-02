import pytest
import json
import uuid
import datetime

# Mock DB layer to test logic
import stratum.db as db

class MockDB:
    def __init__(self):
        self.tables = {
            "stratum.book_reading_run": {},
            "stratum.reading_ledger": {}
        }
        
    def query(self, sql, params=None, limit=100):
        if "book_reading_run" in sql:
            uid = params.get("user_id")
            sid = params.get("source_id")
            res = [v for v in self.tables["stratum.book_reading_run"].values() if v.get("user_id") == uid and v.get("source_id") == sid and v.get("status") not in ("completed", "failed")]
            return res[:limit]
        if "reading_ledger" in sql:
            rid = params.get("run_id")
            it = params.get("item_type")
            ii = params.get("item_identifier")
            res = [v for v in self.tables["stratum.reading_ledger"].values() if v.get("run_id") == rid and v.get("item_type") == it and v.get("item_identifier") == ii]
            return res[:limit]
        return []

    def insert(self, table, data):
        self.tables[table][data["id"]] = data
        return data["id"]
        
    def write(self, table, data, conflict_on=None):
        if conflict_on:
            for k, v in self.tables[table].items():
                match = True
                for c in conflict_on:
                    if v.get(c) != data.get(c):
                        match = False
                        break
                if match:
                    # Update
                    v.update(data)
                    return k
        # Insert
        self.tables[table][data["id"]] = data
        return data["id"]
        
    def update(self, table, rid, data):
        if rid in self.tables[table]:
            self.tables[table][rid].update(data)

# Patch DB
import builtins
real_query = db.query
real_insert = db.insert
real_write = db.write
real_update = db.update

@pytest.fixture
def mock_db():
    mdb = MockDB()
    db.query = mdb.query
    db.insert = mdb.insert
    db.write = mdb.write
    db.update = mdb.update
    yield mdb
    db.query = real_query
    db.insert = real_insert
    db.write = real_write
    db.update = real_update

from stratum.services.book_reading import create_reading_run, initialize_source_accounting, update_ledger_status

def test_reading_run_lifecycle(mock_db):
    user_id = "user_1"
    source_id = "src_1"
    
    # 1. Create run
    run = create_reading_run(user_id, source_id, "v1")
    assert run.user_id == user_id
    assert run.source_id == source_id
    
    # Check separate coverage
    assert "reading" in run.coverage_json
    assert "evidence" in run.coverage_json
    assert "understanding" in run.coverage_json
    
    # 2. Idempotent create
    run2 = create_reading_run(user_id, source_id, "v1")
    assert run.id == run2.id
    
    # 3. Source accounting
    accounting = [
        {"item_type": "chapter", "item_identifier": "ch1", "page_number": 1},
        {"item_type": "page", "item_identifier": "p1", "page_number": 1}
    ]
    initialize_source_accounting(run.id, accounting)
    
    # 4. Update status
    update_ledger_status(run.id, "chapter", "ch1", "READ", {"trace": "trace_id_1"})
    
    # Verify update
    ledgers = mock_db.tables["stratum.reading_ledger"].values()
    ch1 = [l for l in ledgers if l["item_type"] == "chapter" and l["item_identifier"] == "ch1"][0]
    assert ch1["status"] == "READ"
    trace = ch1["trace_json"]
    if isinstance(trace, str):
        trace = json.loads(trace)
    assert trace.get("trace") == "trace_id_1"

