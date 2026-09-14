"""Multimodal Extraction — 图像、表格、公式的结构化提取与描述.

功能:
  - 图像提取: PDF 内嵌图像的 bbox 提取 + OCR + VLM 描述
  - 表格提取: PDF 表格解析 → HTML/Markdown → 结构化存储
  - 公式提取: LaTeX 公式分离 + 渲染预览 + 语义描述
  - 存储: 统一的 multimodal_assets 表 + derivative 关联

架构:
  pdf-inspector (原生提取) → 分类存储 → VLM 增强描述 → 向量化

对比现有 pdf-inspector:
  pdf-inspector 已支持表格提取 (~1237 tables/benchmark)
  本模块在其之上增加:
  1. 图像 extraction + VLM 描述
  2. 公式的独立存储和描述
  3. 统一的 metadata schema
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from stratum.db import get_conn
from stratum.config import VLM_BASE_URL

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_VLM_BASE = VLM_BASE_URL
_VLM_MODEL = os.environ.get("STRATUM_VLM_MODEL", "qwen2.5-vl:7b")
_EMBED_MODEL = "qwen3-embedding"
_EMBED_DIM = 1024
_MAX_IMAGE_CHARS = 8000  # Max text from image OCR before truncation

# ── Data Structures ──────────────────────────────────────────────────────────


@dataclass
class ImageAsset:
    """An extracted image from a document."""

    asset_id: str
    substrate_id: str
    page_num: int
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1)
    width: int
    height: int
    format: str  # "png" | "jpeg" | "svg"
    ocr_text: str = ""
    vlm_description: str = ""
    thumbnail_b64: str = ""  # Base64 thumbnail for preview
    embedding: list[float] | None = None


@dataclass
class TableAsset:
    """An extracted table from a document."""

    asset_id: str
    substrate_id: str
    page_num: int
    bbox: tuple[float, float, float, float]
    row_count: int
    col_count: int
    markdown: str = ""
    html: str = ""
    header_row: list[str] = field(default_factory=list)
    vlm_description: str = ""
    embedding: list[float] | None = None


@dataclass
class FormulaAsset:
    """An extracted formula from a document."""

    asset_id: str
    substrate_id: str
    page_num: int
    position: int  # order on page
    latex: str
    is_display: bool = False  # Display (centered) vs inline
    vlm_description: str = ""
    embedding: list[float] | None = None


# ── Embedding ────────────────────────────────────────────────────────────────


def _get_embedding(text: str) -> list[float] | None:
    """Get embedding vector for text."""
    try:
        text = text[:4000] if len(text) > 4000 else text
        resp = httpx.post(
            f"{_VLM_BASE}/api/embeddings",
            json={"model": _EMBED_MODEL, "prompt": text.replace("\x00", "")},
            timeout=30.0,
        )
        resp.raise_for_status()
        emb = resp.json().get("embedding", [])
        return emb[:_EMBED_DIM] if len(emb) > _EMBED_DIM else emb
    except Exception as exc:
        logger.warning("multimodal: embedding failed: %s", exc)
        return None


# ── VLM Description ──────────────────────────────────────────────────────────


def _describe_image_vlm(image_bytes: bytes, context: str = "") -> str:
    """Generate a text description of an image using VLM.

    Args:
        image_bytes: Raw image bytes (PNG/JPEG)
        context: Optional surrounding text context

    Returns:
        VLM-generated description text.
    """
    try:
        b64 = base64.b64encode(image_bytes).decode("ascii")

        prompt = "Describe this image in detail. Include all text, diagrams, charts, or data visualizations. "
        if context:
            prompt += f"\n\nContext from surrounding text: {context[:500]}"
        prompt += "\n\nProvide a concise but complete description suitable for search indexing."

        resp = httpx.post(
            f"{_VLM_BASE}/api/chat",
            json={
                "model": _VLM_MODEL,
                "messages": [
                    {"role": "user", "content": prompt, "images": [b64]},
                ],
                "stream": False,
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip()
    except Exception as exc:
        logger.warning("multimodal: VLM image description failed: %s", exc)
        return ""


def _describe_formula_vlm(latex: str, context: str = "") -> str:
    """Generate a natural language description of a LaTeX formula.

    Args:
        latex: The raw LaTeX formula string
        context: Optional surrounding text

    Returns:
        Natural language explanation of the formula.
    """
    try:
        prompt = f"Explain this mathematical formula in plain language:\n\n{latex}\n\n"
        if context:
            prompt += f"Context: {context[:300]}\n\n"
        prompt += (
            "Explain what this formula represents, what each variable means, and its significance."
        )

        resp = httpx.post(
            f"{_VLM_BASE}/api/chat",
            json={
                "model": "qwen3-8b",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip()
    except Exception as exc:
        logger.warning("multimodal: VLM formula description failed: %s", exc)
        return ""


# ── Image Extraction ─────────────────────────────────────────────────────────


def extract_images_from_pdf(
    pdf_path: str, substrate_id: str, vlm_enhance: bool = True
) -> list[ImageAsset]:
    """Extract images from a PDF file.

    Uses pdf-inspector's native image extraction capability.

    Args:
        pdf_path: Path to the PDF file
        substrate_id: Associated substrate ID
        vlm_enhance: Whether to generate VLM descriptions

    Returns:
        List of ImageAsset objects.
    """
    assets: list[ImageAsset] = []

    try:
        from pdf_inspector import PDFInspector

        inspector = PDFInspector(pdf_path)
    except Exception as exc:
        logger.warning("multimodal: pdf_inspector failed: %s", exc)
        return []

    try:
        for page_num in range(1, inspector.page_count + 1):
            page = inspector[page_num - 1]
            images = page.images if hasattr(page, "images") else []

            for img_idx, img in enumerate(images):
                asset_id = hashlib.sha256(
                    f"{substrate_id}-img-{page_num}-{img_idx}".encode()
                ).hexdigest()[:24]

                asset = ImageAsset(
                    asset_id=asset_id,
                    substrate_id=substrate_id,
                    page_num=page_num,
                    bbox=getattr(img, "bbox", (0, 0, 0, 0)),
                    width=getattr(img, "width", 0),
                    height=getattr(img, "height", 0),
                    format=getattr(img, "format", "png"),
                )

                # VLM enhancement
                if vlm_enhance and hasattr(img, "data"):
                    img_bytes = img.data if isinstance(img.data, bytes) else b""
                    if img_bytes:
                        asset.vlm_description = _describe_image_vlm(
                            img_bytes,
                            context=getattr(page, "text", "")[:1000],
                        )

                        # Generate embedding from description
                        if asset.vlm_description:
                            asset.embedding = _get_embedding(asset.vlm_description)

                assets.append(asset)

    except Exception as exc:
        logger.warning("multimodal: image extraction failed for %s: %s", pdf_path, exc)

    logger.info("multimodal: extracted %d images from %s", len(assets), substrate_id[:16])
    return assets


# ── Table Extraction ─────────────────────────────────────────────────────────


def extract_tables_from_pdf(
    pdf_path: str, substrate_id: str, vlm_enhance: bool = True
) -> list[TableAsset]:
    """Extract tables from a PDF file.

    Uses pdf-inspector's native table extraction (already benchmarked at 1237 tables).

    Args:
        pdf_path: Path to the PDF file
        substrate_id: Associated substrate ID
        vlm_enhance: Whether to generate VLM descriptions

    Returns:
        List of TableAsset objects.
    """
    assets: list[TableAsset] = []

    try:
        from pdf_inspector import PDFInspector

        inspector = PDFInspector(pdf_path)
    except Exception as exc:
        logger.warning("multimodal: pdf_inspector failed: %s", exc)
        return []

    try:
        for page_num in range(1, inspector.page_count + 1):
            page = inspector[page_num - 1]
            tables = page.tables if hasattr(page, "tables") else []

            for tbl_idx, table in enumerate(tables):
                asset_id = hashlib.sha256(
                    f"{substrate_id}-tbl-{page_num}-{tbl_idx}".encode()
                ).hexdigest()[:24]

                # Extract table data
                data = getattr(table, "data", [])
                markdown = _table_to_markdown(data)
                html = _table_to_html(data)
                header = data[0] if data else []

                asset = TableAsset(
                    asset_id=asset_id,
                    substrate_id=substrate_id,
                    page_num=page_num,
                    bbox=getattr(table, "bbox", (0, 0, 0, 0)),
                    row_count=len(data) - 1 if data else 0,
                    col_count=len(data[0]) if data else 0,
                    markdown=markdown,
                    html=html,
                    header_row=header,
                )

                # VLM description
                if vlm_enhance and data:
                    asset.vlm_description = _describe_table_vlm(
                        markdown,
                        context=getattr(page, "text", "")[:500],
                    )
                    if asset.vlm_description:
                        asset.embedding = _get_embedding(asset.vlm_description)

                assets.append(asset)

    except Exception as exc:
        logger.warning("multimodal: table extraction failed for %s: %s", pdf_path, exc)

    logger.info("multimodal: extracted %d tables from %s", len(assets), substrate_id[:16])
    return assets


def _table_to_markdown(data: list[list[str]]) -> str:
    """Convert table data to markdown format."""
    if not data:
        return ""
    lines = []
    # Header
    lines.append("| " + " | ".join(str(c) for c in data[0]) + " |")
    # Separator
    lines.append("| " + " | ".join("---" for _ in data[0]) + " |")
    # Data rows
    for row in data[1:]:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def _table_to_html(data: list[list[str]]) -> str:
    """Convert table data to HTML format."""
    if not data:
        return ""
    html = ["<table>"]
    html.append("  <thead><tr>")
    for cell in data[0]:
        html.append(f"    <th>{cell}</th>")
    html.append("  </tr></thead>")
    html.append("  <tbody>")
    for row in data[1:]:
        html.append("    <tr>")
        for cell in row:
            html.append(f"      <td>{cell}</td>")
        html.append("    </tr>")
    html.append("  </tbody>")
    html.append("</table>")
    return "\n".join(html)


def _describe_table_vlm(markdown: str, context: str = "") -> str:
    """Generate a natural language description of a table."""
    try:
        prompt = f"Describe this table in detail:\n\n{markdown[:3000]}\n\n"
        if context:
            prompt += f"Context: {context[:300]}\n\n"
        prompt += "Explain what data this table contains, its structure, and key insights."

        resp = httpx.post(
            f"{_VLM_BASE}/api/chat",
            json={
                "model": "qwen3-8b",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip()
    except Exception as exc:
        logger.warning("multimodal: VLM table description failed: %s", exc)
        return ""


# ── Formula Extraction ───────────────────────────────────────────────────────


def extract_formulas_from_text(
    text: str, substrate_id: str, vlm_enhance: bool = True
) -> list[FormulaAsset]:
    """Extract LaTeX formulas from markdown text.

    Detects both inline ($...$) and display ($$...$$) formulas.

    Args:
        text: Markdown content containing formulas
        substrate_id: Associated substrate ID
        vlm_enhance: Whether to generate VLM descriptions

    Returns:
        List of FormulaAsset objects.
    """
    assets: list[FormulaAsset] = []
    position = 0

    # Find display formulas ($$...$$)
    display_pattern = r"\$\$([^$]+)\$\$"
    for match in re.finditer(display_pattern, text, re.DOTALL):
        latex = match.group(1).strip()
        if len(latex) < 2:
            continue
        asset_id = hashlib.sha256(f"{substrate_id}-formula-{position}".encode()).hexdigest()[:24]

        asset = FormulaAsset(
            asset_id=asset_id,
            substrate_id=substrate_id,
            page_num=1,  # TODO: resolve actual page from position
            position=position,
            latex=latex,
            is_display=True,
        )

        if vlm_enhance:
            # Get context around formula
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            context = text[start:end]
            asset.vlm_description = _describe_formula_vlm(latex, context)
            if asset.vlm_description:
                asset.embedding = _get_embedding(asset.vlm_description)

        assets.append(asset)
        position += 1

    # Find inline formulas ($...$)
    inline_pattern = r"(?<!\$)\$([^\$\n]+)\$(?!\$)"
    for match in re.finditer(inline_pattern, text):
        latex = match.group(1).strip()
        if len(latex) < 2:
            continue
        asset_id = hashlib.sha256(f"{substrate_id}-formula-{position}".encode()).hexdigest()[:24]

        asset = FormulaAsset(
            asset_id=asset_id,
            substrate_id=substrate_id,
            page_num=1,
            position=position,
            latex=latex,
            is_display=False,
        )

        if vlm_enhance and len(latex) > 5:  # Only describe longer formulas
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            context = text[start:end]
            asset.vlm_description = _describe_formula_vlm(latex, context)
            if asset.vlm_description:
                asset.embedding = _get_embedding(asset.vlm_description)

        assets.append(asset)
        position += 1

    logger.info("multimodal: extracted %d formulas from %s", len(assets), substrate_id[:16])
    return assets


# ── DB Persistence ───────────────────────────────────────────────────────────

# NOTE: Requires migration to create multimodal_assets table:
# CREATE TABLE IF NOT EXISTS stratum.multimodal_assets (
#   id TEXT PRIMARY KEY,
#   substrate_id TEXT NOT NULL REFERENCES substrates(id),
#   asset_type TEXT NOT NULL,  -- 'image' | 'table' | 'formula'
#   page_num INTEGER,
#   position INTEGER,
#   bbox TEXT,                 -- JSON: [x0, y0, x1, y1]
#   width INTEGER,
#   height INTEGER,
#   format TEXT,               -- 'png' | 'jpeg' | 'svg' | 'latex' | 'markdown'
#   content TEXT,              -- Main content (OCR text, markdown table, LaTeX)
#   html_content TEXT,         -- HTML version (for tables)
#   description TEXT,          -- VLM-generated description
#   embedding VECTOR(1024),    -- Embedding of description
#   thumbnail_b64 TEXT,        -- Base64 thumbnail (for images)
#   metadata JSONB DEFAULT '{}',
#   created_at TIMESTAMPTZ DEFAULT NOW(),
#   updated_at TIMESTAMPTZ DEFAULT NOW()
# );


def persist_image_asset(asset: ImageAsset) -> None:
    """Persist an ImageAsset to the multimodal_assets table."""
    emb_str = None
    if asset.embedding:
        emb_str = "[" + ",".join(str(x) for x in asset.embedding) + "]"

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO multimodal_assets
               (id, substrate_id, asset_type, page_num, bbox, width, height,
                format, content, description, embedding, thumbnail_b64, metadata)
               VALUES (?, ?, 'image', ?, ?, ?, ?, 'png', ?, ?, ?::vector, ?, '{}')
               ON CONFLICT (id) DO UPDATE
               SET description = EXCLUDED.description,
                   embedding = EXCLUDED.embedding,
                   updated_at = NOW()""",
            (
                asset.asset_id,
                asset.substrate_id,
                asset.page_num,
                json.dumps(list(asset.bbox)),
                asset.width,
                asset.height,
                asset.ocr_text,
                asset.vlm_description,
                emb_str,
                asset.thumbnail_b64,
            ),
        )


def persist_table_asset(asset: TableAsset) -> None:
    """Persist a TableAsset to the multimodal_assets table."""
    emb_str = None
    if asset.embedding:
        emb_str = "[" + ",".join(str(x) for x in asset.embedding) + "]"

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO multimodal_assets
               (id, substrate_id, asset_type, page_num, bbox,
                width, height, format, content, html_content,
                description, embedding, metadata)
               VALUES (?, ?, 'table', ?, ?, ?, ?, 'markdown', ?, ?, ?, ?::vector, '{}')
               ON CONFLICT (id) DO UPDATE
               SET content = EXCLUDED.content,
                   html_content = EXCLUDED.html_content,
                   description = EXCLUDED.description,
                   embedding = EXCLUDED.embedding,
                   updated_at = NOW()""",
            (
                asset.asset_id,
                asset.substrate_id,
                asset.page_num,
                json.dumps(list(asset.bbox)),
                asset.col_count,
                asset.row_count,
                asset.markdown,
                asset.html,
                asset.vlm_description,
                emb_str,
            ),
        )


def persist_formula_asset(asset: FormulaAsset) -> None:
    """Persist a FormulaAsset to the multimodal_assets table."""
    emb_str = None
    if asset.embedding:
        emb_str = "[" + ",".join(str(x) for x in asset.embedding) + "]"

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO multimodal_assets
               (id, substrate_id, asset_type, page_num, position,
                format, content, description, embedding, metadata)
               VALUES (?, ?, 'formula', ?, ?, ?, 'latex', ?, ?, ?::vector, '{}')
               ON CONFLICT (id) DO UPDATE
               SET content = EXCLUDED.content,
                   description = EXCLUDED.description,
                   embedding = EXCLUDED.embedding,
                   updated_at = NOW()""",
            (
                asset.asset_id,
                asset.substrate_id,
                asset.page_num,
                asset.position,
                asset.latex,
                asset.vlm_description,
                emb_str,
            ),
        )


# ── Full Pipeline ────────────────────────────────────────────────────────────


def process_multimodal_pdf(
    pdf_path: str, substrate_id: str, vlm_enhance: bool = True
) -> dict[str, Any]:
    """Full multimodal extraction pipeline for a PDF file.

    Args:
        pdf_path: Path to the PDF
        substrate_id: Associated substrate ID
        vlm_enhance: Whether to use VLM for descriptions

    Returns:
        Summary with counts and asset IDs.
    """
    result = {
        "substrate_id": substrate_id,
        "pdf_path": pdf_path,
        "images": [],
        "tables": [],
        "formulas": [],
        "errors": [],
    }

    # Extract images
    try:
        images = extract_images_from_pdf(pdf_path, substrate_id, vlm_enhance=vlm_enhance)
        for img in images:
            persist_image_asset(img)
            result["images"].append(img.asset_id)
    except Exception as e:
        result["errors"].append(f"image_extraction: {e}")

    # Extract tables
    try:
        tables = extract_tables_from_pdf(pdf_path, substrate_id, vlm_enhance=vlm_enhance)
        for tbl in tables:
            persist_table_asset(tbl)
            result["tables"].append(tbl.asset_id)
    except Exception as e:
        result["errors"].append(f"table_extraction: {e}")

    # Extract formulas from derivative content
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT content FROM derivative WHERE substrate_id=? AND kind='markdown'",
                (substrate_id,),
            ).fetchone()
        if row and row[0]:
            formulas = extract_formulas_from_text(row[0], substrate_id, vlm_enhance=vlm_enhance)
            for fmt in formulas:
                persist_formula_asset(fmt)
                result["formulas"].append(fmt.asset_id)
    except Exception as e:
        result["errors"].append(f"formula_extraction: {e}")

    logger.info(
        "multimodal: substrate=%s images=%d tables=%d formulas=%d",
        substrate_id,
        len(result["images"]),
        len(result["tables"]),
        len(result["formulas"]),
    )
    return result


# ── Search ────────────────────────────────────────────────────────────────────


def search_multimodal(
    query: str, query_embedding: list[float], asset_type: str | None = None, top_k: int = 10
) -> list[dict[str, Any]]:
    """Search multimodal assets by embedding similarity.

    Args:
        query: Query text (for metadata display)
        query_embedding: Query embedding vector
        asset_type: Optional filter ('image' | 'table' | 'formula')
        top_k: Number of results

    Returns:
        List of multimodal asset results.
    """
    emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    type_filter = f"AND asset_type = '{asset_type}'" if asset_type else ""

    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT id, substrate_id, asset_type, page_num, format,
                       content, description,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM multimodal_assets
                WHERE embedding IS NOT NULL {type_filter}
                ORDER BY embedding <=> %s::vector
                LIMIT %s""",
            (emb_str, emb_str, top_k),
        ).fetchall()

    results = []
    for r in rows:
        results.append(
            {
                "asset_id": r[0],
                "substrate_id": r[1],
                "asset_type": r[2],
                "page_num": r[3],
                "format": r[4],
                "content_preview": (r[5] or "")[:500],
                "description": r[6],
                "score": float(r[7]),
            }
        )

    return results
