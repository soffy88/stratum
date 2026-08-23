"""其它学科源文件(PDF/EPUB, 哲学/社科心理/科学/量化与AI)→ MD: 找未转的, 检查可转性, 转换+入 其它 文件夹.
仿 econ_convert.py, 但去掉经济关键词密度门(内容五花八门, 无统一关键词集)——只按
章节结构(analyze() 的 chapter 正则, 同 math/econ 通用)门禁, 密度由下游 misc_discover.py
的 ≥3章检测把关。
用法: misc_convert.py          # 分析报告(不转)
      misc_convert.py --do     # 转换可转的(文字层+章节)并入 /books/MD/其它
"""

import os, re, sys, glob, subprocess
import fitz  # pymupdf
try:
    fitz.TOOLS.mupdf_display_errors(False)  # 静音 EPUB HTML/CSS 解析噪音(immersive-translate 导出书 css 大量垃圾)
except Exception:
    pass
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
try:
    from convert_analyze_cache import get as _cat_cache_get, put as _cat_cache_put  # noqa: E402
except Exception:
    _cat_cache_get = lambda _p: None
    _cat_cache_put = lambda _p, _r: None

SRC = os.getenv("CONVERT_SRC", "/home/soffy/books/其它")
DST = os.getenv("CONVERT_DST", "/home/soffy/books/MD/其它")
TAG = os.getenv("CONVERT_TAG", "其它")
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


# 已完成的归一标题(查重): 已有MD(其它目录+MD根) ∪ 已入库标题
existing = set()
for d in (DST, "/home/soffy/books/MD"):
    for f in glob.glob(f"{d}/*.md"):
        existing.add(norm(Path(f).stem))
for t in _ingested_titles():
    existing.add(norm(t))


def matched(stem):
    ns = norm(stem)
    if ns in existing:  # 精确(短标题也算)
        return True
    for e in existing:
        if len(e) >= 6 and (e in ns or ns in e):  # 子串含(长标题/带描述)
            return True
    return False


def chapters(text):
    # ★2026-08-10 修复: PDF 提取行常带前导空格("  第一章"), ^第 匹配不到→全判无章节;
    #   扩展教辅结构(单元/讲/课/节/部分)与 chapter_ingest 对齐。
    return len(
        re.findall(
            r"(?m)^\s*#+\s*Chapter\s+\d|^\s*#+\s*第[一二三四五六七八九十百千0-9]+(章|单元|讲|课|节|部分|回|篇)|^\s*Chapter\s+\d",
            text,
        )
    )


def analyze(path):
    """查可转性(带缓存: 文件未变则直接用上次分类, 省掉每轮全量重扫)."""
    stem = Path(path).stem
    if matched(stem):
        return ("已转", stem, None)
    hit = _cat_cache_get(path)
    if hit is not None:
        return hit
    res = _analyze_uncached(path)
    _cat_cache_put(path, res)
    return res


def _analyze_uncached(path):
    stem = Path(path).stem
    if matched(stem):
        return ("已转", stem, None)
    try:
        d = fitz.open(path)
        npg = d.page_count
        # 抽样查文字层
        txt = ""
        for p in range(0, min(npg, 60), 6):
            txt += d[p].get_text()
        if len(txt) / max(min(npg, 60) // 6, 1) < 200:
            # ★2026-08-22 优化: 无文字层(扫描版)书早退, 不做全文采样(最慢的书全是这类)。
            return ("需OCR(无文字层)", stem, npg)
        # ★2026-08-22 修复: 原来全量抽取所有页(range(npg))对杂源大书拖垮 feeder 预算;
        # 改首目录+均抽页采样(≤400页), 与全文判定一致(章节行密集分布)。
        full = "".join(d[p].get_text() for p in range(0, min(npg, 400), 2))
    except Exception:
        # 个别PDF损坏字体表等会让pymupdf在读页时直接崩(不是open()阶段) ——
        # 同"打不开"处理, 不能让一本坏书拖垮整批(misc来源杂, 比math/econ更常见)
        return ("打不开", stem, None)
    txt_ratio = len(txt) / max(min(npg, 60) // 6, 1)
    nch = chapters(full)
    if nch < 3:
        return ("无章节结构", stem, npg)
    return ("可转", stem, npg)


def convert(path):
    """PDF/EPUB → 清洗后的 MD 文本(去页眉页脚/页码, 章节行提升为 # 标题). 同 econ_convert."""
    # ★2026-08-11 微服务化: 转换引擎迁入 stratum-docs 容器(oprim parse_pdf, 同引擎零差异)
    try:
        import sys as _sys
        from pathlib import Path as _P
        _sys.path.insert(0, str(_P(__file__).resolve().parent / "scripts"))
        from docs_client import pdf_to_md
        return pdf_to_md(str(path))
    except Exception as _e:
        print(f"  ⚠ 容器转换失败({str(_e)[:70]}), 本地兜底", flush=True)
    # ★2026-08-07 全面接入 opendataloader(benchmark#1 表格/无cid), PDF 优先; 失败回退 markitdown
    text = None
    if str(path).lower().endswith(".pdf"):
        try:
            from oprim.parser.parse_pdf import parse_pdf
            # ★2026-08-07: 默认 pdf_inspector(firecrawl, benchmark 0.875/表格0.814/0.47s,
            # 原生 CID 解码); ODL_HYBRID=1 时走 opendataloader hybrid(公式 LaTeX 深加工)
            if os.getenv("ODL_HYBRID") == "1":
                pc = parse_pdf(path, provider="opendataloader", hint={"hybrid": True})
            else:
                pc = parse_pdf(path, provider="pdf_inspector")
            text = pc.markdown
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠ pdf_inspector 回退 markitdown: {str(e)[:80]}", flush=True)
    if text is None:
        from markitdown import MarkItDown
        # ★2026-08-09 修复: 原调用在 if 外 → pdf_inspector 成功时 MarkItDown 未 import
        #   UnboundLocalError 全文件转换失败; 且成功结果被 markitdown 覆盖(违背 PDF 优先)
        text = MarkItDown().convert(path).text_content

    npg = fitz.open(path).page_count
    lines = text.split("\n")
    cnt = Counter(l.strip() for l in lines if l.strip())
    thresh = max(3, int(npg * 0.12))
    headers = {l for l, c in cnt.items() if c > thresh and len(l) < 80}
    out = []
    for l in lines:
        s = l.strip()
        if not s or s in headers or re.fullmatch(r"\d{1,4}", s):
            continue
        if re.match(r"^(Chapter\s+\d+|第[一二三四五六七八九十百\d]+章|CHAPTER\s+\d+)\b", s):
            out.append(f"\n# {s}\n")
        else:
            out.append(s)
    return "\n".join(out)


results = {}
for path in sorted(glob.glob(f"{SRC}/*.pdf") + glob.glob(f"{SRC}/*.epub")):
    cat, stem, npg = analyze(path)
    results.setdefault(cat, []).append((stem, npg, path))

for cat in ["可转", "需OCR(无文字层)", "无章节结构", "已转", "打不开"]:
    items = results.get(cat, [])
    print(f"\n=== {cat} ({len(items)}) ===")
    for stem, npg, _ in items[:40]:
        print(f"  {'%4d页 ' % npg if npg else ''}{stem[:60]}")


def _write(stem, text, force=False):
    """写文件(可转/OCR共用尾段). 返回 True=已写入.
    analyze() 已按章节结构门禁过一次("可转"分类才会走到这里); force=True(仅OCR调用路径用)
    时门禁没过也写(OCR是几十分钟到数小时一次性投入, 结果不能丢)。"""
    clean = re.sub(r"\s*\(z-lib[^)]*\)|\s*\(z-library[^)]*\)", "", stem).strip()
    if matched(clean):  # 同轮稍早已转/已入库的近似书 → 不重复
        print(f"  – 重复(已转/已入库), 跳过: {clean[:40]}")
        return False
    dst = f"{DST}/{clean}.md"
    if os.path.exists(dst):
        print(f"  – 已存在, 跳过: {clean[:40]}")
        return False
    open(dst, "w", encoding="utf-8").write(text)
    existing.add(norm(clean))  # 记入, 防同轮后续重复
    print(f"  ✓ [{TAG}] {clean[:45]} ({len(text) // 1024}KB)")
    return True


if DO:
    os.makedirs(DST, exist_ok=True)  # ★2026-08-10 教辅/计算机等新 DST 目录可能不存在, 先建
    print("\n=== 转换「可转」+ 入 其它 文件夹 ===")
    for stem, npg, path in results.get("可转", []):
        try:
            text = convert(path)
        except Exception as e:
            print(f"  ✗ 转换失败 {stem[:40]}: {e}")
            continue
        if _write(stem, text):
            _rm_src(path)  # ★2026-08-10 转换成功删源省空间(KEEP_SRC=1 跳过)

    # ★自主OCR(与math_convert.py/econ_convert.py同款, 复用同一套vLLM容器逻辑): 默认关,
    # 只在 scripts/ocr_daemon.sh 那条独立慢节奏循环里打开(若日后接入), 别塞进
    # pull_ingest.sh(有600s超时, 大书OCR一本能到~80min会被腰斩)。
    ocr_books = (
        results.get("需OCR(无文字层)", []) if os.getenv("MATH_CONVERT_AUTO_OCR") == "1" else []
    )
    if ocr_books:
        import signal

        sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
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
                        import time as _time

                        t0 = _time.time()
                        text = ocr_pdf_to_text(
                            path,
                            progress_cb=lambda i, n, s=stem: print(
                                f"    {s[:30]} {i + 1}/{n}", end="\r", flush=True
                            ),
                        )
                        print(f"\n    OCR完成 {_time.time() - t0:.0f}s")
                    except Exception as e:
                        print(f"  ✗ OCR失败 {stem[:40]}: {e}")
                        continue
                    _write(stem, text, force=True)
            finally:
                release_container()
        else:
            print("  ✗ vLLM 容器未就绪(显存不足或启动失败), 本轮跳过 OCR")

    print("✓ 完成. 需OCR/无章节 的未处理(见上).")


def _rm_src(path) -> None:
    """★2026-08-10 转换成功删源文件省空间(磁盘94%)。KEEP_SRC=1 时保留。"""
    import os as _os
    if _os.getenv("KEEP_SRC") == "1":
        return
    try:
        _os.remove(path)
        print(f"  🗑 已删源文件: {Path(path).name[:50]}")
    except OSError as e:
        print(f"  ⚠ 删源失败 {Path(path).name[:40]}: {e}")
