"""textbook_parser — MD-structured textbook → clusters + KU chunks.

Heading hierarchy expected:
  # Book Title       (optional; overridden by JSON meta book_name)
  ## Chapter / Unit  → cluster
  ### Section        → sub-section within cluster
  Plain text         → content collected into that section's KU chunk

Output of parse_textbook():
  {
    "textbook": {id, subject, grade, edition, book_name},
    "clusters": [{id, name, chapter, order}],
    "raw_ku_chunks": [{cluster_id, chapter, section, text, order}],
  }
"""
from __future__ import annotations

import uuid
from typing import Any


def parse_textbook(md_text: str, textbook_meta: dict[str, Any]) -> dict[str, Any]:
    """Parse a structured textbook MD into ordered clusters and KU chunks.

    Each H2 (##) becomes a cluster; each H3 (###) within it becomes one
    raw_ku_chunk whose text is all plain lines below that H3 until the
    next heading.  H1 (#) is treated as the book title if book_name is
    absent from textbook_meta.
    """
    textbook_id = textbook_meta.get("id") or str(uuid.uuid4())
    subject = textbook_meta.get("subject", "")
    grade = textbook_meta.get("grade", "")
    edition = textbook_meta.get("edition", "")
    book_name = textbook_meta.get("book_name", "")

    clusters: list[dict] = []
    raw_ku_chunks: list[dict] = []

    current_chapter = ""
    chapter_idx = 0
    current_cluster_id = ""
    current_section = ""
    buffer: list[str] = []
    section_order = 0

    def _flush() -> None:
        nonlocal section_order
        if current_cluster_id and current_section and buffer:
            text = "\n".join(buffer).strip()
            if text:
                raw_ku_chunks.append({
                    "cluster_id": current_cluster_id,
                    "chapter": current_chapter,
                    "section": current_section,
                    "text": text,
                    "order": section_order,
                })
                section_order += 1
        buffer.clear()

    for line in md_text.splitlines():
        if line.startswith("### "):
            _flush()
            current_section = line[4:].strip()
        elif line.startswith("## "):
            _flush()
            current_chapter = line[3:].strip()
            chapter_idx += 1
            current_section = ""
            current_cluster_id = f"{textbook_id}::cluster-{chapter_idx:03d}"
            clusters.append({
                "id": current_cluster_id,
                "name": current_chapter,
                "chapter": current_chapter,
                "order": chapter_idx,
            })
        elif line.startswith("# "):
            if not book_name:
                book_name = line[2:].strip()
        else:
            if current_section:
                buffer.append(line)

    _flush()

    return {
        "textbook": {
            "id": textbook_id,
            "subject": subject,
            "grade": grade,
            "edition": edition,
            "book_name": book_name,
        },
        "clusters": clusters,
        "raw_ku_chunks": raw_ku_chunks,
    }
