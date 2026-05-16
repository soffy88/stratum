#!/usr/bin/env python3
"""Run unstructured (fast strategy) on all 5 PDFs."""
import os, time, json
from pathlib import Path

BASE = Path(__file__).parent
SAMPLES = BASE / "samples" / "pdf"
PARSED = BASE / "parsed"

PDFS = {
    "S1": SAMPLES / "S1-chinese-novel-history.pdf",
    "S2": SAMPLES / "S2-marchenko-pastur-1998.pdf",
    "S3": SAMPLES / "S3-real-analysis-notes.pdf",
    "S4": SAMPLES / "S4-attention-is-all-you-need.pdf",
    "S5": SAMPLES / "S5-pride-and-prejudice.pdf",
}

from unstructured.partition.pdf import partition_pdf
import unstructured
print(f"unstructured version: checking...", flush=True)

results = {}
for sid, pdf_path in PDFS.items():
    out_dir = PARSED / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "unstructured.md"
    meta_file = out_dir / "unstructured.meta.yaml"
    print(f"\n{sid}: {pdf_path.name}", flush=True)
    t0 = time.perf_counter()
    try:
        elements = partition_pdf(filename=str(pdf_path), strategy="fast", languages=["eng"])
        elapsed = time.perf_counter() - t0

        md_lines = []
        counts = {}
        for el in elements:
            etype = type(el).__name__
            counts[etype] = counts.get(etype, 0) + 1
            text = str(el).strip()
            if not text:
                continue
            if etype in ("Title", "Header"):
                md_lines.append(f"## {text}\n\n")
            elif etype == "ListItem":
                md_lines.append(f"- {text}\n")
            else:
                md_lines.append(f"{text}\n\n")

        md_text = "".join(md_lines)
        paras = [p.strip() for p in md_text.split("\n\n") if p.strip() and len(p.strip()) > 20]
        para_lengths = [len(p) for p in paras]
        short_ratio = sum(1 for l in para_lengths if l < 50) / max(len(para_lengths), 1)
        avg_len = sum(para_lengths) / max(len(para_lengths), 1)

        out_file.write_text(md_text, encoding="utf-8")
        meta = {
            "parser": "unstructured",
            "version": "0.18.32",
            "strategy": "fast",
            "sample": sid,
            "elapsed_s": round(elapsed, 2),
            "total_elements": len(elements),
            "element_counts": json.dumps(counts),
            "para_count": len(paras),
            "avg_para_length": round(avg_len, 1),
            "short_para_ratio": round(short_ratio, 3),
            "total_chars": len(md_text),
        }
        meta_file.write_text(
            "\n".join(f"{k}: {v}" for k, v in meta.items()),
            encoding="utf-8"
        )
        results[sid] = meta
        print(f"  OK: {len(elements)} elements, {len(paras)} paras, {avg_len:.0f} avg_len, {elapsed:.1f}s", flush=True)
        print(f"  Sample text: {repr(md_text[:120])}", flush=True)
    except Exception as e:
        elapsed = time.perf_counter() - t0
        results[sid] = {"error": str(e), "elapsed_s": round(elapsed, 2)}
        print(f"  FAIL: {e}", flush=True)
        import traceback; traceback.print_exc()

print("\n=== DONE ===", flush=True)
print(json.dumps(results, indent=2, ensure_ascii=False))
