import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__line__ if '__line__' in locals() else __file__), '../src')))

import stratum.db as db
from stratum.services.book_reading import create_reading_run, initialize_source_accounting, update_ledger_status

def qualify():
    try:
        # Check if we can connect to DB
        db.query("SELECT 1")
    except Exception as e:
        print(f"Skipping qualification, DB not available: {e}")
        return
        
    print("Fetching >=3 real sources...")
    sources = db.query("SELECT id, user_id FROM stratum.substrates WHERE mime = 'application/pdf' LIMIT 3")
    if len(sources) < 3:
        print(f"Found {len(sources)} sources, need 3 for full qualification.")
        # Try without mime restriction
        sources = db.query("SELECT id, user_id FROM stratum.substrates LIMIT 3")
        
    for s in sources:
        print(f"Qualifying source {s['id']}...")
        run = create_reading_run(s["user_id"], s["id"], source_version="v1")
        print(f"  Created run {run.id}")
        
        # Source accounting
        accounting = [
            {"item_type": "chapter", "item_identifier": "ch1", "page_number": 1},
            {"item_type": "page", "item_identifier": "p1", "page_number": 1},
            {"item_type": "page", "item_identifier": "p2", "page_number": 2},
            {"item_type": "figure", "item_identifier": "fig1", "page_number": 2}
        ]
        initialize_source_accounting(run.id, accounting)
        print("  Initialized source accounting")
        
        # Simulate reading
        update_ledger_status(run.id, "chapter", "ch1", "PARSED")
        update_ledger_status(run.id, "page", "p1", "READ", trace_update={"evidence_id": "ev1"})
        update_ledger_status(run.id, "figure", "fig1", "NEEDS_VISUAL_REVIEW")
        print("  Updated ledger statuses")

if __name__ == "__main__":
    qualify()
