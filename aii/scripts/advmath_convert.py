"""高级数学经济专用源文件(PDF/EPUB)→ MD: 同一个文件夹里放源文件+转换出的MD(方便用户
自己抽查转换质量), 不像econ_convert.py/math_convert.py那样分流到不同学科文件夹.
用法: advmath_convert.py          # 分析报告(不转)
      advmath_convert.py --do     # 转换可转的(文字层+章节)入同一文件夹
      ADVMATH_CONVERT_AUTO_OCR=1 advmath_convert.py --do   # 连需OCR的也自主转(慢, 见 ocr_daemon.sh)
"""

import os, re, sys, glob, subprocess
import fitz  # pymupdf
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from math_ocr_gate import needs_ocr  # noqa: E402
from chapter_ingest import chapter_numbers  # noqa: E402

SRC = "/mnt/d/books/高级数学经济专用"
DO = "--do" in sys.argv


def norm(s):  # 归一标题(去 z-lib/作者括号/空格标点)用于匹配
    s = re.sub(r"\(z-lib[^)]*\)|\(z-library[^)]*\)|\([^)]*1lib[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\.(pdf|epub)$", "", s, flags=re.I)
    s = re.sub(r"[\s_\-（）()【】\[\]·,，.。、:：;；]+", "", s)
    return s.lower()


def _ingested_titles():
    """权威已完成清单: aii.ingested_substrate 的书名(已入库的不能再转, 否则文件名不同→重复入库)."""
    try:
        out = subprocess.run(
            [
                "docker",
                "exec",
                "aii-postgres",
                "psql",
                "-U",
                "aii",
                "-d",
                "aii_kg",
                "-tAc",
                "SELECT title FROM aii.ingested_substrate WHERE title IS NOT NULL",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout
        return [l for l in out.splitlines() if l.strip()]
    except Exception as e:
        print(f"  ⚠ 取已入库清单失败(只按MD去重): {e}", file=sys.stderr)
        return []


# 已完成的归一标题(查重): 已有MD(本目录+中英数学+经济学+MD根) ∪ 已入库标题
# ★同一本书常同时躺在多个学科源文件夹(如范里安既在Economic也在本目录), 只查本目录会漏判
# 让已有MD/已入库的书白跑一趟OCR(实测复现: 周华/范里安两本).
existing = set()
for d in (
    SRC,
    "/home/soffy/books/MD/中文数学",
    "/home/soffy/books/MD/英文数学",
    "/home/soffy/books/MD/经济学",
    "/home/soffy/books/MD",
):
    for f in glob.glob(f"{d}/*.md"):
        existing.add(norm(Path(f).stem))
for t in _ingested_titles():
    existing.add(norm(t))


def matched(stem):
    ns = norm(stem)
    if ns in existing:
        return True
    for e in existing:
        if len(e) >= 6 and (e in ns or ns in e):
            return True
    return False


def analyze(path):
    stem = Path(path).stem
    if matched(stem):
        return ("已转", stem, None)
    try:
        d = fitz.open(path)
    except Exception:
        return ("打不开", stem, None)
    npg = d.page_count
    txt = ""
    for p in range(0, min(npg, 60), 6):
        txt += d[p].get_text()
    txt_ratio = len(txt) / max(min(npg, 60) // 6, 1)
    full = "".join(d[p].get_text() for p in range(npg))
    nch = len(chapter_numbers(full))
    if txt_ratio < 200:
        return ("需OCR(无文字层)", stem, npg)
    if nch < 3:
        return ("无章节结构", stem, npg)
    ocr_flag, _ = needs_ocr(full)
    if ocr_flag:
        return ("需OCR(烂文本层)", stem, npg)
    return ("可转", stem, npg)


def convert(path):
    """PDF/EPUB → 清洗后的 MD 文本. 用markitdown(同econ_convert.py/math_convert.py 2026-07-07起的换用),
    页眉页脚按全文行频率剔除(markitdown无天然页边界), 阈值沿用 0.12*页数。"""
    from markitdown import MarkItDown

    npg = fitz.open(path).page_count
    text = MarkItDown().convert(path).text_content
    lines = text.split("\n")
    cnt = Counter(l.strip() for l in lines if l.strip())
    thresh = max(3, int(npg * 0.12))
    headers = {l for l, c in cnt.items() if c > thresh and len(l) < 80}
    out = []
    for l in lines:
        s = l.strip()
        if not s or s in headers or re.fullmatch(r"\d{1,4}", s):
            continue
        if re.match(r"^(Chapter\s+\d+|第[一二三四五六七八九十百\d]+\s*章|CHAPTER\s+\d+)\b", s):
            out.append(f"\n# {s}\n")
        else:
            out.append(s)
    return "\n".join(out)


def _write(stem, text):
    dst = f"{SRC}/{stem}.md"
    if os.path.exists(dst):
        print(f"  – 已存在, 跳过: {stem[:40]}")
        return False
    zh = len(re.findall(r"[一-鿿]", text[:300000]))
    en = len(re.findall(r"[A-Za-z]", text[:300000]))
    lang = "zh" if zh > en else "en"
    fm = f"---\ndoc_type: book\nlanguage: {lang}\nsource: advmath_convert\ntitle: {stem}\n---\n\n"
    open(dst, "w", encoding="utf-8").write(fm + text)
    print(f"  ✓ {stem[:45]} ({len(text) // 1024}KB)")
    return True


results = {}
for path in sorted(glob.glob(f"{SRC}/*.pdf") + glob.glob(f"{SRC}/*.epub")):
    cat, stem, npg = analyze(path)
    results.setdefault(cat, []).append((stem, npg, path))

for cat in ["可转", "需OCR(烂文本层)", "需OCR(无文字层)", "无章节结构", "已转", "打不开"]:
    items = results.get(cat, [])
    print(f"\n=== {cat} ({len(items)}) ===")
    for stem, npg, _ in items[:60]:
        print(f"  {'%4d页 ' % npg if npg else ''}{stem[:60]}")

_IMG_PLACEHOLDER = re.compile(r"!\[\]\(Image\d+\.\w+\)")


def _formula_image_loss(text):
    """★2026-07-07实测发现: 有些书(尤其中文老式排版教材)把公式排成栅格图片嵌入PDF,
    markitdown(纯文本流, 不做图像OCR)只能留下"![](ImageNNNN.jpg)"占位符, 公式本身
    彻底丢失——不是markitdown选择性忽略, 是这部分内容在源PDF里本来就不是文字/矢量,
    任何纯文本抽取工具都读不出来。这类书直接转会产出"公式全丢、讲解自然空洞"的坏MD,
    该走OCR(vLLM能"看懂"图里的公式)而不是文本抽取。阈值: 占位符超过非空行5%即判定."""
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines:
        return False
    hits = sum(1 for l in lines if _IMG_PLACEHOLDER.search(l))
    return hits / len(lines) > 0.05


if DO:
    print("\n=== 转换「可转」===")
    formula_image_books = []
    for stem, npg, path in results.get("可转", []):
        try:
            text = convert(path)
        except Exception as e:
            print(f"  ✗ 转换失败 {stem[:40]}: {e}")
            continue
        if _formula_image_loss(text):
            print(f"  ⚠ 公式栅格图丢失严重, 转去OCR: {stem[:40]}")
            formula_image_books.append((stem, npg, path))
            continue
        _write(stem, text)

    # ★自主OCR: 默认关(env门禁, 同 math_convert.py 的 MATH_CONVERT_AUTO_OCR)——大书一本能
    # 到~80min, 只在独立慢节奏的 ocr_daemon.sh 循环里打开。
    ocr_books = (
        (
            results.get("需OCR(烂文本层)", [])
            + results.get("需OCR(无文字层)", [])
            + formula_image_books
        )
        if os.getenv("ADVMATH_CONVERT_AUTO_OCR") == "1"
        else []
    )
    if ocr_books:
        import signal

        from math_ocr_convert import ensure_container, ocr_pdf_to_text, release_container

        def _on_signal(signum, frame):
            print(f"\n  ⚠ 收到信号 {signum}, 释放 OCR 容器后退出")
            release_container()
            raise SystemExit(1)

        signal.signal(signal.SIGTERM, _on_signal)
        signal.signal(signal.SIGINT, _on_signal)

        print(f"\n=== 自主 OCR ({len(ocr_books)} 本, 拉起 vLLM 容器) ===")
        if ensure_container():
            try:
                for stem, npg, path in ocr_books:
                    print(f"  ── OCR: {stem[:50]} ({npg}页) ──")
                    try:
                        t0 = __import__("time").time()
                        text = ocr_pdf_to_text(
                            path,
                            progress_cb=lambda i, n, s=stem: print(
                                f"    {s[:30]} {i + 1}/{n}", end="\r", flush=True
                            ),
                        )
                        print(f"\n    OCR完成 {__import__('time').time() - t0:.0f}s")
                    except Exception as e:
                        print(f"  ✗ OCR失败 {stem[:40]}: {e}")
                        continue
                    _write(stem, text)
            finally:
                release_container()
        else:
            print("  ✗ vLLM 容器启动失败, 跳过本轮OCR")
