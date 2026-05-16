#!/usr/bin/env python3
"""
PDF Parser Evaluation Script - Batch 2 Experiment #1
Runs available parsers on 5 test PDFs and records metrics.
"""
import time, os, sys, re, yaml, json, traceback
from pathlib import Path
from datetime import datetime

SAMPLES_DIR = Path(__file__).parent / "samples/pdf"
PARSED_DIR = Path(__file__).parent / "parsed"
PARSED_DIR.mkdir(exist_ok=True)

SAMPLES = {
    "S1": ("S1-chinese-novel-history.pdf", "Chinese traditional text (中國小說史略, Lu Xun)"),
    "S2": ("S2-marchenko-pastur-1998.pdf", "Math paper with formulas (Marchenko-Pastur, dual-col)"),
    "S3": ("S3-real-analysis-notes.pdf", "Math lecture notes (real analysis, formulas, symbols)"),
    "S4": ("S4-attention-is-all-you-need.pdf", "Dual-column academic paper with tables and figures (NOT scanned - archive.org 503)"),
    "S5": ("S5-pride-and-prejudice.pdf", "English novel generated from EPUB (regular prose)"),
}

def measure_math_symbols(text: str) -> dict:
    """Count LaTeX/Unicode math indicators."""
    latex_inline = len(re.findall(r'\$[^\$]+\$', text))
    latex_block = len(re.findall(r'\$\$[^\$]+\$\$', text))
    latex_env = len(re.findall(r'\\(?:begin|end)\{[^}]+\}', text))
    unicode_math = sum(1 for c in text if '∀' <= c <= '⋿')
    # Also count known math symbols
    math_words = len(re.findall(r'\\(?:alpha|beta|gamma|delta|sigma|lambda|sum|int|frac|sqrt|infty|leq|geq|neq|cdot|times)', text))
    return {
        "latex_inline": latex_inline,
        "latex_block": latex_block,
        "latex_env": latex_env,
        "unicode_math_chars": unicode_math,
        "math_commands": math_words,
        "total_math_indicators": latex_inline + latex_block + latex_env + unicode_math + math_words
    }

def measure_tables(text: str) -> dict:
    """Detect markdown tables."""
    md_table_rows = len(re.findall(r'^\|.*\|.*$', text, re.MULTILINE))
    md_table_sep = len(re.findall(r'^\|[-|: ]+\|$', text, re.MULTILINE))
    html_tables = len(re.findall(r'<table', text, re.IGNORECASE))
    return {
        "markdown_table_rows": md_table_rows,
        "markdown_table_separators": md_table_sep,
        "html_tables": html_tables,
    }

def measure_paragraphs(text: str) -> dict:
    """Measure paragraph structure quality."""
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    para_lengths = [len(p) for p in paras]
    avg_len = sum(para_lengths) / len(para_lengths) if para_lengths else 0
    # Count single-word "paragraphs" (sign of bad splitting)
    short_paras = sum(1 for l in para_lengths if l < 30)
    return {
        "paragraph_count": len(paras),
        "avg_para_length": round(avg_len, 1),
        "short_para_ratio": round(short_paras / max(len(paras), 1), 3),
    }

def score_D1(stats: dict) -> float:
    """Paragraph completeness: penalize short_para_ratio, reward reasonable avg_len."""
    ratio = stats.get("short_para_ratio", 1.0)
    avg_len = stats.get("avg_para_length", 0)
    score = 5.0
    if ratio > 0.5: score -= 2.0
    elif ratio > 0.3: score -= 1.0
    if avg_len < 50: score -= 1.0
    elif avg_len > 2000: score -= 0.5  # overly long paragraphs
    return max(0, min(5, score))

def score_D2(math_stats: dict, sample_id: str) -> float:
    """Math formula preservation - only meaningful for S2, S3."""
    if sample_id not in ("S2", "S3"):
        return None  # N/A
    total = math_stats.get("total_math_indicators", 0)
    # S2 (Marchenko-Pastur) should have many formulas
    # S3 (Real analysis notes) also has formulas
    if total > 20: return 4.5
    if total > 5: return 3.0
    if total > 0: return 1.5
    return 0.5  # no math detected in a math paper = bad

def score_D3(table_stats: dict, sample_id: str) -> float:
    """Table recognition - only meaningful for S4 (Attention paper has tables)."""
    if sample_id != "S4":
        return None  # N/A
    rows = table_stats.get("markdown_table_rows", 0)
    sep = table_stats.get("markdown_table_separators", 0)
    if sep >= 1: return 4.5  # proper markdown table
    if rows > 0: return 2.5  # rows but no separator
    return 1.0  # no table detected

def score_D4(text: str, sample_id: str) -> float:
    """OCR accuracy - S4 was meant to be scanned but archive.org was down.
    Return None since we don't have a genuine scanned PDF."""
    return None  # N/A - no scanned PDF available

def run_pymupdf4llm(pdf_path: Path, sample_id: str, out_dir: Path):
    """Run pymupdf4llm parser."""
    try:
        import pymupdf4llm
        t0 = time.time()

        # Suppress upgrade notice
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            result = pymupdf4llm.to_markdown(str(pdf_path))

        elapsed = time.time() - t0

        out_md = out_dir / "pymupdf4llm.md"
        out_md.write_text(result, encoding="utf-8")

        # Get page count
        import fitz
        doc = fitz.open(str(pdf_path))
        pages = len(doc)
        doc.close()

        # Measure memory roughly
        import resource
        mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

        para_stats = measure_paragraphs(result)
        math_stats = measure_math_symbols(result)
        table_stats = measure_tables(result)

        meta = {
            "parser": "pymupdf4llm",
            "parser_version": "0.3.4",
            "parse_time_seconds": round(elapsed, 2),
            "output_chars": len(result),
            "detected_pages": pages,
            "ocr_used": False,
            "errors": None,
            "memory_mb_peak": round(mem_mb, 1),
            "paragraph_stats": para_stats,
            "math_stats": math_stats,
            "table_stats": table_stats,
            "scores": {
                "D1_paragraph": score_D1(para_stats),
                "D2_formulas": score_D2(math_stats, sample_id),
                "D3_tables": score_D3(table_stats, sample_id),
                "D4_ocr": score_D4(result, sample_id),
                "D5_speed_s": round(elapsed, 2),
                "D6_memory": "low" if mem_mb < 500 else "medium" if mem_mb < 2000 else "high",
                "D7_errors": 0,
            }
        }
        (out_dir / "pymupdf4llm.meta.yaml").write_text(yaml.dump(meta, allow_unicode=True))
        print(f"  ✅ pymupdf4llm: {elapsed:.2f}s, {len(result)} chars, D1={meta['scores']['D1_paragraph']}")
        return meta
    except Exception as e:
        print(f"  ❌ pymupdf4llm FAILED: {e}")
        traceback.print_exc()
        return {"parser": "pymupdf4llm", "errors": str(e), "scores": {}}

def run_unstructured(pdf_path: Path, sample_id: str, out_dir: Path):
    """Run unstructured parser."""
    try:
        from unstructured.partition.pdf import partition_pdf
        t0 = time.time()
        import resource

        elements = partition_pdf(str(pdf_path))
        elapsed = time.time() - t0
        mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

        # Convert to markdown
        lines = []
        for el in elements:
            cat = type(el).__name__
            text = str(el).strip()
            if not text:
                continue
            if cat == "Title":
                lines.append(f"## {text}\n")
            elif cat == "NarrativeText":
                lines.append(f"{text}\n")
            elif cat == "Table":
                lines.append(f"\n[TABLE]\n{text}\n")
            else:
                lines.append(f"{text}\n")

        result = "\n".join(lines)
        (out_dir / "unstructured.md").write_text(result, encoding="utf-8")

        import fitz
        doc = fitz.open(str(pdf_path))
        pages = len(doc)
        doc.close()

        para_stats = measure_paragraphs(result)
        math_stats = measure_math_symbols(result)
        table_stats = measure_tables(result)

        meta = {
            "parser": "unstructured",
            "parser_version": "unknown",
            "parse_time_seconds": round(elapsed, 2),
            "output_chars": len(result),
            "detected_pages": pages,
            "ocr_used": False,
            "errors": None,
            "memory_mb_peak": round(mem_mb, 1),
            "paragraph_stats": para_stats,
            "math_stats": math_stats,
            "table_stats": table_stats,
            "scores": {
                "D1_paragraph": score_D1(para_stats),
                "D2_formulas": score_D2(math_stats, sample_id),
                "D3_tables": score_D3(table_stats, sample_id),
                "D4_ocr": None,
                "D5_speed_s": round(elapsed, 2),
                "D6_memory": "low" if mem_mb < 500 else "medium" if mem_mb < 2000 else "high",
                "D7_errors": 0,
            }
        }
        (out_dir / "unstructured.meta.yaml").write_text(yaml.dump(meta, allow_unicode=True))
        print(f"  ✅ unstructured: {elapsed:.2f}s, {len(result)} chars, D1={meta['scores']['D1_paragraph']}")
        return meta
    except Exception as e:
        print(f"  ❌ unstructured FAILED: {e}")
        return {"parser": "unstructured", "errors": str(e), "scores": {}}

def main():
    print(f"=== PDF Parser Evaluation [{datetime.now().isoformat()}] ===\n")

    parsers = [run_pymupdf4llm, run_unstructured]

    all_results = {}

    for sample_id, (fname, desc) in SAMPLES.items():
        pdf_path = SAMPLES_DIR / fname
        if not pdf_path.exists():
            print(f"\n[{sample_id}] SKIPPED: {fname} not found")
            continue

        print(f"\n[{sample_id}] {desc}")
        print(f"  File: {fname} ({pdf_path.stat().st_size / 1024:.1f} KB)")

        out_dir = PARSED_DIR / sample_id
        out_dir.mkdir(exist_ok=True)

        sample_results = {}
        for parser_fn in parsers:
            meta = parser_fn(pdf_path, sample_id, out_dir)
            sample_results[meta.get("parser", parser_fn.__name__)] = meta

        all_results[sample_id] = sample_results

    # Save summary
    summary_path = PARSED_DIR / "eval_results.json"
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n\nResults saved to {summary_path}")
    print("Done.")

if __name__ == "__main__":
    main()
