"""PDF/image rendering into user-scoped, hash-addressed visual projections."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

from stratum.common import generate_ulid
from stratum.config import DATA_DIR
from stratum.db import get_conn
from stratum.utils.user_id_hash import hash_user_id


def _immutable_tile(data: bytes, source_hash: str, page: int, region: int) -> tuple[str, str]:
    tile_hash = hashlib.sha256(data).hexdigest()
    uri = f"sha256://visual/{tile_hash[:2]}/{tile_hash}.png"
    out = DATA_DIR / "visual" / source_hash / f"p{page}-r{region}-{tile_hash}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        out.write_bytes(data)
    return uri, tile_hash


def render_source_regions(source_path: str, source_hash: str) -> list[dict[str, Any]]:
    """Render one region per page for a deterministic first projection.

    Region segmentation can be upgraded independently; provenance is retained
    because every row records page and bbox.  PyMuPDF/Pillow remain optional.
    """
    path = Path(source_path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            import fitz  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PDF visual projection requires optional PyMuPDF") from exc
        doc = fitz.open(path)
        regions: list[dict[str, Any]] = []
        for page_no, page in enumerate(doc, 1):
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            data = pix.tobytes("png")
            uri, tile_hash = _immutable_tile(data, source_hash, page_no, 0)
            regions.append(
                {
                    "page_number": page_no,
                    "region_index": 0,
                    "bbox": {"x0": 0, "y0": 0, "x1": pix.width, "y1": pix.height},
                    "tile_uri": uri,
                    "tile_hash": tile_hash,
                    "render_hash": hashlib.sha256(data).hexdigest(),
                    "width": pix.width,
                    "height": pix.height,
                    "tile_path": str(
                        DATA_DIR / "visual" / source_hash / f"p{page_no}-r0-{tile_hash}.png"
                    ),
                }
            )
        return regions
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as image:
            image = image.convert("RGB")
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            data = buf.getvalue()
            uri, tile_hash = _immutable_tile(data, source_hash, 1, 0)
            return [
                {
                    "page_number": 1,
                    "region_index": 0,
                    "bbox": {"x0": 0, "y0": 0, "x1": image.width, "y1": image.height},
                    "tile_uri": uri,
                    "tile_hash": tile_hash,
                    "render_hash": hashlib.sha256(data).hexdigest(),
                    "width": image.width,
                    "height": image.height,
                    "tile_path": str(path),
                }
            ]
    except ImportError as exc:
        raise RuntimeError("image visual projection requires optional Pillow") from exc


def persist_regions(
    user_id: str, source_id: str, regions: list[dict[str, Any]], *, embedding_provider=None
) -> int:
    owner = hash_user_id(user_id)
    with get_conn() as conn:
        # Rebuild is idempotent and never touches canonical source/fragments.
        conn.execute(
            "UPDATE visual_region_projection SET deleted_at=NOW() WHERE user_id=? AND source_id=? AND deleted_at IS NULL",
            (owner, source_id),
        )
        for region in regions:
            embedding = None
            model = None
            dim = None
            if embedding_provider:
                embedding = embedding_provider.validate(
                    embedding_provider.embed_image(region["tile_path"])
                )
                model, dim = embedding_provider.model, embedding_provider.dimension
            import psycopg2.extras

            conn.execute(
                """INSERT INTO visual_region_projection
                (id,user_id,source_id,fragment_id,page_number,region_index,bbox_json,tile_uri,tile_hash,render_hash,width,height,embedding,embedding_model,embedding_dim)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    generate_ulid(),
                    owner,
                    source_id,
                    region.get("fragment_id"),
                    region["page_number"],
                    region["region_index"],
                    psycopg2.extras.Json(region["bbox"]),
                    region["tile_uri"],
                    region["tile_hash"],
                    region["render_hash"],
                    region["width"],
                    region["height"],
                    embedding,
                    model,
                    dim,
                ),
            )
    return len(regions)
