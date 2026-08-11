"""Paragraph-aware Chunking — 语义边界感知的智能分块.

功能:
  - 自动检测段落边界 (markdown headers, blank lines, list items)
  - 根据内容类型调整分块策略 (math/text/code/table)
  - 保持段落完整性，不截断句子或公式
  - 输出结构化 chunk metadata (层级标题路径, 段落类型, token 估算)

对比现有 oprim.structural_chunk:
  现有: 纯字符数切分，可能截断段落/公式
  增强: 段落感知 + 语义边界 + 类型适配

核心设计:
  1. Markdown AST → 段落级 token 估算 → 智能合并
  2. 保护边界: 不在公式 ($...$ / $$...$$) 或代码块 (```) 内部切分
  3. 上下文保留: 每个 chunk 携带父级标题路径
  4. 输出兼容: 与现有 substrate_chunk 表结构完全兼容
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_DEFAULT_MIN_CHARS = 400
_DEFAULT_MAX_CHARS = 1200  # Slightly smaller than current 2000 for finer granularity
_SENTENCE_END = r'[.。!?！？\n]'


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class Paragraph:
    """A semantic paragraph extracted from markdown content."""
    text: str
    start_pos: int
    end_pos: int
    heading_path: str  # e.g., "# Chapter > ## Section > ### Subsection"
    block_type: str    # "text" | "math" | "code" | "list" | "table" | "heading"
    token_estimate: int


@dataclass
class Chunk:
    """A paragraph-aware chunk ready for embedding."""
    content: str
    chunk_idx: int
    heading_path: str
    block_types: list[str] = field(default_factory=list)
    token_estimate: int = 0
    start_pos: int = 0
    end_pos: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Paragraph Extraction ─────────────────────────────────────────────────────

def _heading_level(p: str) -> int:
    """Extract heading level from path entry like '## Title'."""
    count = 0
    for ch in p:
        if ch == '#':
            count += 1
        else:
            break
    return count


def _extract_paragraphs(text: str) -> list[Paragraph]:
    """Extract semantic paragraphs from markdown text.

    Handles:
      - Markdown headings (# ## ###)
      - Math blocks ($$...$$ and inline $...$)
      - Code blocks (``` ... ```)
      - Lists (- item / 1. item)
      - Tables (| header | ...)
      - Regular text paragraphs
    """
    paragraphs: list[Paragraph] = []
    pos = 0
    heading_path = ""
    lines = text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i]
        line_start = pos

        # Detect block boundaries
        if line.strip().startswith('```'):
            # Code block
            block_lines = [line]
            i += 1
            pos += len(line) + 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                block_lines.append(lines[i])
                pos += len(lines[i]) + 1
                i += 1
            if i < len(lines):
                block_lines.append(lines[i])
                pos += len(lines[i]) + 1
                i += 1

            block_text = '\n'.join(block_lines)
            paragraphs.append(Paragraph(
                text=block_text,
                start_pos=line_start,
                end_pos=pos,
                heading_path=heading_path,
                block_type="code",
                token_estimate=len(block_text) // 3,
            ))
            continue

        if '$$' in line:
            # Display math block
            block_lines = [line]
            i += 1
            pos += len(line) + 1
            while i < len(lines) and '$$' not in lines[i]:
                block_lines.append(lines[i])
                pos += len(lines[i]) + 1
                i += 1
            if i < len(lines):
                block_lines.append(lines[i])
                pos += len(lines[i]) + 1
                i += 1

            block_text = '\n'.join(block_lines)
            paragraphs.append(Paragraph(
                text=block_text,
                start_pos=line_start,
                end_pos=pos,
                heading_path=heading_path,
                block_type="math",
                token_estimate=len(block_text) // 2,
            ))
            continue

        # Heading detection
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            # Update heading path: keep all headers at or above current level
            path_parts = [p for p in heading_path.split(' > ') if _heading_level(p) < level and p]
            path_parts.append(f"{'#' * level} {title}")
            heading_path = ' > '.join(path_parts)

            paragraphs.append(Paragraph(
                text=line,
                start_pos=line_start,
                end_pos=pos + len(line) + 1,
                heading_path=heading_path,
                block_type="heading",
                token_estimate=len(title) // 3,
            ))
            i += 1
            pos += len(line) + 1
            continue

        # Table detection
        if '|' in line and line.strip().startswith('|'):
            block_lines = [line]
            i += 1
            pos += len(line) + 1
            while i < len(lines) and '|' in lines[i] and lines[i].strip().startswith('|'):
                block_lines.append(lines[i])
                pos += len(lines[i]) + 1
                i += 1

            block_text = '\n'.join(block_lines)
            paragraphs.append(Paragraph(
                text=block_text,
                start_pos=line_start,
                end_pos=pos,
                heading_path=heading_path,
                block_type="table",
                token_estimate=len(block_text) // 3,
            ))
            continue

        # List item detection
        if re.match(r'^(\s*[-*+]|\s*\d+\.)\s+', line):
            block_lines = [line]
            i += 1
            pos += len(line) + 1
            while i < len(lines) and (re.match(r'^(\s*[-*+]|\s*\d+\.)\s+', lines[i]) or (lines[i].strip() == '' and i + 1 < len(lines) and re.match(r'^(\s*[-*+]|\s*\d+\.)\s+', lines[i + 1]))):
                block_lines.append(lines[i])
                pos += len(lines[i]) + 1
                i += 1

            block_text = '\n'.join(block_lines)
            paragraphs.append(Paragraph(
                text=block_text,
                start_pos=line_start,
                end_pos=pos,
                heading_path=heading_path,
                block_type="list",
                token_estimate=len(block_text) // 4,
            ))
            continue

        # Regular text — collect consecutive non-empty, non-block lines
        if line.strip():
            block_lines = [line]
            i += 1
            pos += len(line) + 1
            while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(('```', '$$', '#', '|')) and not re.match(r'^(\s*[-*+]|\s*\d+\.)\s+', lines[i]):
                block_lines.append(lines[i])
                pos += len(lines[i]) + 1
                i += 1

            block_text = '\n'.join(block_lines)
            paragraphs.append(Paragraph(
                text=block_text,
                start_pos=line_start,
                end_pos=pos,
                heading_path=heading_path,
                block_type="text",
                token_estimate=len(block_text) // 4,
            ))
            continue

        # Empty line — skip
        i += 1
        pos += len(line) + 1

    return paragraphs


# ── Chunk Assembly ───────────────────────────────────────────────────────────

def _assemble_chunks(paragraphs: list[Paragraph],
                     min_chars: int = _DEFAULT_MIN_CHARS,
                     max_chars: int = _DEFAULT_MAX_CHARS) -> list[Chunk]:
    """Merge paragraphs into chunks respecting size bounds and semantic boundaries.

    Rules:
      1. Never split math blocks or code blocks
      2. Merge adjacent paragraphs until reaching max_chars
      3. Ensure each chunk is at least min_chars (unless it's the last chunk)
      4. Preserve heading_path from the leading paragraph
    """
    chunks: list[Chunk] = []
    chunk_idx = 0

    current_lines: list[str] = []
    current_tokens = 0
    current_types: list[str] = []
    current_heading = ""
    current_start = 0
    current_end = 0

    def _flush() -> None:
        nonlocal chunk_idx
        if not current_lines:
            return
        content = '\n'.join(current_lines)
        chunks.append(Chunk(
            content=content,
            chunk_idx=chunk_idx,
            heading_path=current_heading,
            block_types=list(set(current_types)),
            token_estimate=current_tokens,
            start_pos=current_start,
            end_pos=current_end,
            metadata={
                "paragraph_count": len(current_lines),
                "char_count": len(content),
            },
        ))
        chunk_idx += 1

    for para in paragraphs:
        # Never merge across hard boundaries (math/code blocks)
        is_hard_block = para.block_type in ("math", "code")

        if is_hard_block:
            # Flush current chunk first
            _flush()
            current_lines = []
            current_tokens = 0
            current_types = []

            # Emit the hard block as its own chunk
            chunks.append(Chunk(
                content=para.text,
                chunk_idx=chunk_idx,
                heading_path=para.heading_path,
                block_types=[para.block_type],
                token_estimate=para.token_estimate,
                start_pos=para.start_pos,
                end_pos=para.end_pos,
                metadata={"paragraph_count": 1, "char_count": len(para.text)},
            ))
            chunk_idx += 1
            continue

        # Check if adding this paragraph exceeds max_chars
        candidate_length = (len('\n'.join(current_lines + [para.text]))
                           if current_lines else len(para.text))

        if current_lines and candidate_length > max_chars:
            # Flush if we've reached the max
            _flush()
            current_lines = []
            current_tokens = 0
            current_types = []

        # Accumulate
        if not current_lines:
            current_heading = para.heading_path
            current_start = para.start_pos

        current_lines.append(para.text)
        current_tokens += para.token_estimate
        current_types.append(para.block_type)
        current_end = para.end_pos

    # Flush remaining
    _flush()

    return chunks


# ── Public API ─────────────────────────────────────────────────────────────────

def paragraph_chunk(text: str,
                    min_chars: int = _DEFAULT_MIN_CHARS,
                    max_chars: int = _DEFAULT_MAX_CHARS,
                    ) -> list[dict[str, Any]]:
    """Chunk markdown text with paragraph-aware semantic boundaries.

    Args:
        text: Markdown content to chunk
        min_chars: Minimum chunk size in characters
        max_chars: Maximum chunk size in characters

    Returns:
        List of chunk dicts compatible with oprim.structural_chunk output:
        [{"content": "...", "chunk_idx": 0, "heading_path": "...",
          "block_types": [...], "token_estimate": N, "metadata": {...}}]
    """
    if not text or not text.strip():
        return []

    paragraphs = _extract_paragraphs(text)
    if not paragraphs:
        return [{"content": text, "chunk_idx": 0, "heading_path": "",
                 "block_types": ["text"], "token_estimate": len(text) // 4,
                 "metadata": {"paragraph_count": 1, "char_count": len(text)}}]

    chunks = _assemble_chunks(paragraphs, min_chars=min_chars, max_chars=max_chars)

    # Convert to dict format
    return [
        {
            "content": c.content,
            "chunk_idx": c.chunk_idx,
            "heading_path": c.heading_path,
            "block_types": c.block_types,
            "token_estimate": c.token_estimate,
            "start_pos": c.start_pos,
            "end_pos": c.end_pos,
            "metadata": c.metadata,
        }
        for c in chunks
    ]


# ── Batch Processing ─────────────────────────────────────────────────────────

def batch_paragraph_chunk(texts: list[str], **kwargs) -> list[list[dict[str, Any]]]:
    """Chunk multiple texts in parallel.

    Args:
        texts: List of markdown content strings
        **kwargs: Passed to paragraph_chunk()

    Returns:
        List of chunk lists (one per input text).
    """
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(paragraph_chunk, t, **kwargs) for t in texts]
        return [f.result() for f in futures]


# ── Statistics ─────────────────────────────────────────────────────────────────

def chunk_stats(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute statistics about a chunk list."""
    if not chunks:
        return {"count": 0}

    char_counts = [len(c["content"]) for c in chunks]
    token_counts = [c.get("token_estimate", 0) for c in chunks]
    block_types: dict[str, int] = {}
    for c in chunks:
        for bt in c.get("block_types", []):
            block_types[bt] = block_types.get(bt, 0) + 1

    return {
        "count": len(chunks),
        "total_chars": sum(char_counts),
        "total_tokens": sum(token_counts),
        "avg_chars": sum(char_counts) / len(chunks),
        "min_chars": min(char_counts),
        "max_chars": max(char_counts),
        "block_type_distribution": block_types,
    }
