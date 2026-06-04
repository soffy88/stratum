#!/usr/bin/env python3
"""Self-check the substrate.book schema and its examples.

Acceptance:
1. Schema itself is a valid JSON Schema (Draft 2020-12)
2. valid.yaml passes validation
3. invalid.yaml fails validation (with multiple errors caught)
"""
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas"


def check_schema(name: str) -> tuple[bool, list[str]]:
    """Returns (ok, messages)."""
    msgs = []
    schema_path = SCHEMAS_DIR / f"{name}.schema.json"
    valid_path = SCHEMAS_DIR / "examples" / f"{name}.valid.yaml"
    invalid_path = SCHEMAS_DIR / "examples" / f"{name}.invalid.yaml"

    # Load schema
    try:
        schema = json.loads(schema_path.read_text())
    except Exception as e:
        return False, [f"Cannot load schema: {e}"]

    # Check schema is itself valid
    try:
        Draft202012Validator.check_schema(schema)
        msgs.append("✓ schema is valid Draft 2020-12")
    except SchemaError as e:
        return False, [f"✗ schema invalid: {e.message}"]

    validator = Draft202012Validator(schema)

    # Check valid example
    try:
        valid_doc = yaml.safe_load(valid_path.read_text())
    except Exception as e:
        return False, msgs + [f"Cannot load valid example: {e}"]

    errors = list(validator.iter_errors(valid_doc))
    if errors:
        msgs.append(f"✗ valid example failed validation ({len(errors)} errors):")
        for err in errors:
            msgs.append(f"    - {err.json_path}: {err.message}")
        return False, msgs
    msgs.append("✓ valid example passes validation")

    # Check invalid example
    try:
        invalid_doc = yaml.safe_load(invalid_path.read_text())
    except Exception as e:
        return False, msgs + [f"Cannot load invalid example: {e}"]

    errors = list(validator.iter_errors(invalid_doc))
    if not errors:
        msgs.append("✗ invalid example unexpectedly passed validation!")
        return False, msgs
    msgs.append(f"✓ invalid example correctly rejected ({len(errors)} errors caught)")
    # Show first 5 errors as evidence
    for err in errors[:5]:
        path = "/".join(str(p) for p in err.absolute_path) or "<root>"
        msgs.append(f"    [caught] {path}: {err.message[:100]}")
    if len(errors) > 5:
        msgs.append(f"    ... and {len(errors) - 5} more")

    return True, msgs


def main():
    targets = [
        "substrate.book",
        "substrate.paper",
        "substrate.webpage",
        "substrate.transcript",
        "substrate.chat",
        "concept.person",
        "concept.event",
        "concept.theorem",
        "concept.technique",
        "concept.place",
        "concept.domain",
        "note.adr",
        "note.postmortem",
        "note.reading",
        "note.idea",
        "note.daily",
    ]
    all_ok = True
    for name in targets:
        print(f"\n=== {name} ===")
        ok, msgs = check_schema(name)
        for m in msgs:
            print(m)
        if not ok:
            all_ok = False
    print()
    if all_ok:
        print("All checks passed.")
        sys.exit(0)
    else:
        print("Some checks failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
