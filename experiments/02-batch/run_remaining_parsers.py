#!/usr/bin/env python3
"""
Run unstructured, marker, and docling on all 5 PDF samples.
Saves output to experiments/02-batch/parsed/S{N}/{parser}.md
"""
import os, sys, time, json, re, traceback
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

results = {}

# ──────────────────────────────────────────────
# PARSER 1: unstructured
# ──────────────────────────────────────────────
print("\n" + "="*60)
print("PARSER: unstructured")
print("="*60, flush=True)

try:
    from unstructured.partition.pdf import partition_pdf
    unstructured_ok = True
except Exception as e:
    print(f"IMPORT FAIL: {e}", flush=True)
    unstructured_ok = False

if unstructured_ok:
    for sid, pdf_path in PDFS.items():
        out_dir = PARSED / sid
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "unstructured.md"
        meta_file = out_dir / "unstructured.meta.yaml"
        print(f"\n  {sid}: {pdf_path.name}", flush=True)
        t0 = time.perf_counter()
        try:
            elements = partition_pdf(filename=str(pdf_path), strategy="fast")
            elapsed = time.perf_counter() - t0

            # Build markdown from elements
            md_lines = []
            counts = {}
            for el in elements:
                etype = type(el).__name__
                counts[etype] = counts.get(etype, 0) + 1
                text = str(el).strip()
                if not text:
                    continue
                if etype in ("Title", "Header"):
                    md_lines.append(f"## {text}\n")
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
                "version": "0.18.x",
                "strategy": "fast",
                "sample": sid,
                "elapsed_s": round(elapsed, 2),
                "total_elements": len(elements),
                "element_counts": counts,
                "para_count": len(paras),
                "avg_para_length": round(avg_len, 1),
                "short_para_ratio": round(short_ratio, 3),
                "total_chars": len(md_text),
            }
            meta_file.write_text(
                "\n".join(f"{k}: {json.dumps(v) if isinstance(v, (dict,list)) else v}" for k, v in meta.items()),
                encoding="utf-8"
            )
            results[f"{sid}_unstructured"] = meta
            print(f"    OK: {len(elements)} elements, {len(paras)} paras, {elapsed:.1f}s", flush=True)
        except Exception as e:
            elapsed = time.perf_counter() - t0
            results[f"{sid}_unstructured"] = {"error": str(e), "elapsed_s": round(elapsed, 2)}
            print(f"    FAIL: {e}", flush=True)
            traceback.print_exc()

# ──────────────────────────────────────────────
# PARSER 2: marker-pdf
# ──────────────────────────────────────────────
print("\n" + "="*60)
print("PARSER: marker-pdf")
print("="*60, flush=True)

try:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
    marker_ok = True
    print("  marker import OK", flush=True)
except ImportError as e:
    try:
        # Older API
        from marker.convert import convert_single_pdf
        from marker.models import load_all_models
        marker_ok = True
        marker_api = "old"
        print("  marker import OK (old API)", flush=True)
    except ImportError as e2:
        print(f"  IMPORT FAIL: {e} | {e2}", flush=True)
        marker_ok = False
        marker_api = None
    else:
        marker_api = "old"
else:
    marker_api = "new"

if marker_ok:
    try:
        if marker_api == "new":
            print("  Loading marker models (CPU)...", flush=True)
            t_load = time.perf_counter()
            model_dict = create_model_dict(device="cpu", dtype="float32")
            print(f"  Models loaded in {time.perf_counter()-t_load:.1f}s", flush=True)
        else:
            print("  Loading marker models (old API)...", flush=True)
            t_load = time.perf_counter()
            model_list = load_all_models()
            print(f"  Models loaded in {time.perf_counter()-t_load:.1f}s", flush=True)
    except Exception as e:
        print(f"  Model load FAIL: {e}", flush=True)
        traceback.print_exc()
        marker_ok = False

if marker_ok:
    for sid, pdf_path in PDFS.items():
        out_dir = PARSED / sid
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "marker.md"
        meta_file = out_dir / "marker.meta.yaml"
        print(f"\n  {sid}: {pdf_path.name}", flush=True)
        t0 = time.perf_counter()
        try:
            if marker_api == "new":
                converter = PdfConverter(artifact_dict=model_dict)
                rendered = converter(str(pdf_path))
                md_text, _, _ = text_from_rendered(rendered)
            else:
                md_text, _, _ = convert_single_pdf(str(pdf_path), model_list)
            elapsed = time.perf_counter() - t0

            paras = [p.strip() for p in md_text.split("\n\n") if p.strip() and len(p.strip()) > 20]
            para_lengths = [len(p) for p in paras]
            short_ratio = sum(1 for l in para_lengths if l < 50) / max(len(para_lengths), 1)
            avg_len = sum(para_lengths) / max(len(para_lengths), 1)

            out_file.write_text(md_text, encoding="utf-8")
            meta = {
                "parser": "marker-pdf",
                "version": "1.10.2",
                "sample": sid,
                "elapsed_s": round(elapsed, 2),
                "para_count": len(paras),
                "avg_para_length": round(avg_len, 1),
                "short_para_ratio": round(short_ratio, 3),
                "total_chars": len(md_text),
            }
            meta_file.write_text(
                "\n".join(f"{k}: {v}" for k, v in meta.items()),
                encoding="utf-8"
            )
            results[f"{sid}_marker"] = meta
            print(f"    OK: {len(paras)} paras, {len(md_text)} chars, {elapsed:.1f}s", flush=True)
        except Exception as e:
            elapsed = time.perf_counter() - t0
            results[f"{sid}_marker"] = {"error": str(e), "elapsed_s": round(elapsed, 2)}
            print(f"    FAIL: {e}", flush=True)
            traceback.print_exc()

# ──────────────────────────────────────────────
# PARSER 3: docling
# ──────────────────────────────────────────────
print("\n" + "="*60)
print("PARSER: docling")
print("="*60, flush=True)

try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    docling_ok = True
    print("  docling import OK", flush=True)
except Exception as e:
    print(f"  IMPORT FAIL: {e}", flush=True)
    docling_ok = False

if docling_ok:
    try:
        print("  Initializing docling converter (no OCR, CPU)...", flush=True)
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True
        converter = DocumentConverter()
        print("  Converter ready", flush=True)
    except Exception as e:
        print(f"  Converter init FAIL: {e}", flush=True)
        traceback.print_exc()
        docling_ok = False

if docling_ok:
    for sid, pdf_path in PDFS.items():
        out_dir = PARSED / sid
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "docling.md"
        meta_file = out_dir / "docling.meta.yaml"
        print(f"\n  {sid}: {pdf_path.name}", flush=True)
        t0 = time.perf_counter()
        try:
            result = converter.convert(str(pdf_path))
            elapsed = time.perf_counter() - t0
            md_text = result.document.export_to_markdown()

            paras = [p.strip() for p in md_text.split("\n\n") if p.strip() and len(p.strip()) > 20]
            para_lengths = [len(p) for p in paras]
            short_ratio = sum(1 for l in para_lengths if l < 50) / max(len(para_lengths), 1)
            avg_len = sum(para_lengths) / max(len(para_lengths), 1)

            out_file.write_text(md_text, encoding="utf-8")
            meta = {
                "parser": "docling",
                "version": "2.x",
                "sample": sid,
                "elapsed_s": round(elapsed, 2),
                "para_count": len(paras),
                "avg_para_length": round(avg_len, 1),
                "short_para_ratio": round(short_ratio, 3),
                "total_chars": len(md_text),
                "num_pages": len(result.document.pages) if hasattr(result.document, 'pages') else "N/A",
            }
            meta_file.write_text(
                "\n".join(f"{k}: {v}" for k, v in meta.items()),
                encoding="utf-8"
            )
            results[f"{sid}_docling"] = meta
            print(f"    OK: {len(paras)} paras, {len(md_text)} chars, {elapsed:.1f}s", flush=True)
        except Exception as e:
            elapsed = time.perf_counter() - t0
            results[f"{sid}_docling"] = {"error": str(e), "elapsed_s": round(elapsed, 2)}
            print(f"    FAIL: {e}", flush=True)
            traceback.print_exc()

# ──────────────────────────────────────────────
# Save combined results
# ──────────────────────────────────────────────
combined_path = PARSED / "remaining_parsers_results.json"
combined_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n\nSaved results to {combined_path}", flush=True)
print("\n=== DONE ===", flush=True)
