"""Rebuildable translated-block projection; canonical fragments remain authoritative."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from stratum.db import get_conn
from stratum.services.translation_alignment import align_fragment
from stratum.services.source_storage import resolve_storage_path
from stratum.utils.user_id_hash import hash_user_id


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def persist_translation_fragments(
    user_id: str, translation_id: str, translated_pdf: str
) -> dict[str, int]:
    """Persist only deterministic page/block matches; never guesses an owner.

    The PDF parser is optional at import time.  A block is aligned only when
    its page has a canonical fragment and the normalized source block is
    contained in that fragment; all other translated blocks remain unresolved.
    """
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise RuntimeError("translated PDF alignment requires PyMuPDF") from exc
    owner = hash_user_id(user_id)
    with get_conn() as conn:
        translation = conn.execute(
            """SELECT t.source_id, s.source_path
            FROM translation_projection t JOIN substrates s ON s.id=t.source_id
            WHERE t.id=? AND t.user_id=?""",
            (translation_id, owner),
        ).fetchone()
        if not translation:
            raise PermissionError("translation is not owned by authenticated user")
        source_id = translation[0]
        fragments = conn.execute(
            "SELECT id,text,anchor_json FROM substrate_chunk WHERE substrate_id=? ORDER BY chunk_idx",
            (source_id,),
        ).fetchall()
    if not fragments:
        return {"translated": 0, "aligned": 0, "unresolved": 0, "invalid": 0}
    doc = fitz.open(str(Path(translated_pdf)))
    original_doc = fitz.open(str(resolve_storage_path(translation[1])))
    original_blocks: list[tuple[int, str]] = []
    for page_no, page in enumerate(original_doc, 1):
        for block in page.get_text("blocks"):
            text = _clean(block[4] if len(block) > 4 else "")
            if text:
                original_blocks.append((page_no, text))
    blocks: list[tuple[int, str, dict[str, Any], int]] = []
    block_index = 0
    for page_no, page in enumerate(doc, 1):
        for block in page.get_text("blocks"):
            text = _clean(block[4] if len(block) > 4 else "")
            if text:
                blocks.append(
                    (
                        page_no,
                        text,
                        {"x0": block[0], "y0": block[1], "x1": block[2], "y1": block[3]},
                        block_index,
                    )
                )
                block_index += 1
    aligned = unresolved = invalid = 0
    with get_conn() as conn:
        for index, (page_no, text, anchor, original_index) in enumerate(blocks):
            # A translated block without a defensible source fragment is kept
            # as unresolved and is not assigned a fabricated fragment ID.
            candidate = None
            if original_index < len(original_blocks):
                original_page, original_text = original_blocks[original_index]
                if original_page == page_no:
                    # Only accept a complete normalized fragment contained in
                    # the source block.  A small block contained in a large
                    # fragment is not enough to establish semantic identity.
                    candidate = next(
                        (
                            row
                            for row in fragments
                            if _clean(row[1]) and _clean(row[1]).lower() in original_text.lower()
                        ),
                        None,
                    )
            if candidate and float(align_fragment(candidate[1], text)["alignment_score"]) < 0.5:
                candidate = None
            status = "aligned" if candidate else "unresolved"
            fragment_id = candidate[0] if candidate else None
            score = (
                float(align_fragment(candidate[1], text)["alignment_score"]) if candidate else None
            )
            if not candidate:
                # Migration 047 intentionally made original_fragment_id NOT
                # NULL.  Until a forward migration explicitly permits stored
                # unresolved rows, keep them as a run metric rather than
                # violating the schema or inventing an authority link.
                unresolved += 1
                continue
            row_id = hashlib.sha256(
                f"{translation_id}:{index}:{page_no}:{text}".encode()
            ).hexdigest()
            conn.execute(
                """INSERT INTO translation_fragment_projection
                (id,translation_id,user_id,source_id,original_fragment_id,translated_text,page_number,
                 alignment_score,translated_range,original_range,alignment_status,alignment_method)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (translation_id, original_fragment_id) DO UPDATE SET
                  translated_text=EXCLUDED.translated_text, page_number=EXCLUDED.page_number,
                  alignment_score=EXCLUDED.alignment_score, alignment_status=EXCLUDED.alignment_status,
                  alignment_method=EXCLUDED.alignment_method""",
                (
                    row_id,
                    translation_id,
                    owner,
                    source_id,
                    fragment_id,
                    text,
                    page_no,
                    score,
                    __import__("json").dumps(anchor),
                    None,
                    status,
                    "normalized_text" if candidate else "page_only",
                ),
            )
            aligned += 1
    return {
        "translated": len(blocks),
        "aligned": aligned,
        "unresolved": unresolved,
        "invalid": invalid,
    }
