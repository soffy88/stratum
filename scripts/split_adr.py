"""
split_adr.py — Split docs/decisions/_source.md into per-ADR files.

Output format: ADR-NNN.md (no slug, for cleanliness with CJK titles).
ADR-021 is skipped (CC's detailed 373-line version already exists).
"""

import re
import sys
from pathlib import Path

SOURCE = Path(__file__).parent.parent / "docs" / "decisions" / "_source.md"
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "decisions"

SKIP_NUMS = {"021"}  # CC's detailed version already committed; handled in Wave 3


def main():
    if not SOURCE.exists():
        print(f"ERROR: source not found: {SOURCE}", file=sys.stderr)
        sys.exit(1)

    content = SOURCE.read_text(encoding="utf-8")

    # Match "## ADR-NNN: title\n<body>" stopping at next "## " heading or end of file
    adr_pattern = re.compile(
        r"^## ADR-(\d{3}): (.+?)\n(.*?)(?=^## |\Z)",
        re.DOTALL | re.MULTILINE,
    )

    # Extract dependency graph + unresolved issues sections (for INDEX.md)
    dep_graph_match = re.search(
        r"^## 决策依赖关系图\n(.*?)(?=^## |\Z)",
        content,
        re.DOTALL | re.MULTILINE,
    )
    unresolved_match = re.search(
        r"^## 未决问题汇总.*?\n(.*?)(?=^## |\Z)",
        content,
        re.DOTALL | re.MULTILINE,
    )

    written = []
    skipped = []

    for m in adr_pattern.finditer(content):
        adr_num = m.group(1)
        adr_title = m.group(2).strip()
        # Strip trailing horizontal rules and whitespace from body
        adr_body = m.group(3).rstrip().rstrip("-").rstrip()

        if adr_num in SKIP_NUMS:
            skipped.append(adr_num)
            print(f"  SKIP: ADR-{adr_num} ({adr_title}) — CC detailed version kept")
            continue

        filename = f"ADR-{adr_num}.md"
        out_path = OUTPUT_DIR / filename

        file_content = f"# ADR-{adr_num}: {adr_title}\n\n{adr_body}\n"
        out_path.write_text(file_content, encoding="utf-8")
        written.append(adr_num)
        print(f"  WRITE: {filename}")

    # Build INDEX.md
    dep_section = dep_graph_match.group(0).rstrip() if dep_graph_match else ""
    unresolved_section = unresolved_match.group(0).rstrip() if unresolved_match else ""

    adr_list_lines = []
    for num in [f"{n:03d}" for n in range(1, 22)]:
        out_path = OUTPUT_DIR / f"ADR-{num}.md"
        if out_path.exists():
            # Read first line to get the title
            first_line = out_path.read_text(encoding="utf-8").split("\n")[0]
            title = first_line.lstrip("# ").strip()
            adr_list_lines.append(f"- [{title}](ADR-{num}.md)")
        else:
            adr_list_lines.append(f"- ADR-{num}: _missing_")

    adr_list = "\n".join(adr_list_lines)

    index_content = f"""# Stratum Decision Records Index

Source: `_source.md` (advisor DECISION_LOG.md, 21 ADRs)
Split: `scripts/split_adr.py`

## ADR 列表

{adr_list}

{dep_section}

{unresolved_section}
"""
    (OUTPUT_DIR / "INDEX.md").write_text(index_content, encoding="utf-8")
    print(f"  WRITE: INDEX.md")

    print(f"\nDone: {len(written)} ADRs written, {len(skipped)} skipped")
    print(f"Written: {written}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()
