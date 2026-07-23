"""经济源文件(PDF/EPUB)→ MD: 找未转的, 检查可转性, 转换+入 经济学 文件夹.
仿 math_convert.py, 但用经济关键词密度门(经济书无编号定理).
用法: econ_convert.py          # 分析报告(不转)
      econ_convert.py --do     # 转换可转的(文字层+章节)并入 /books/MD/经济学
"""

import os, re, sys, glob, subprocess
import fitz  # pymupdf
from pathlib import Path
from collections import Counter

SRC = "/home/soffy/books/Economic"
DST = "/home/soffy/books/MD/经济学"
DO = "--do" in sys.argv

# 经济关键词(同 classify_md.py 的 ECON), 用于密度判定
ECON = [
    "经济",
    "市场",
    "需求",
    "供给",
    "价格",
    "成本",
    "货币",
    "资本",
    "利润",
    "通货",
    "宏观",
    "微观",
    "贸易",
    "金融",
    "投资",
    "边际",
    "弹性",
    "需求曲线",
    "gdp",
    "demand",
    "supply",
    "market",
    "price",
    "cost",
    "profit",
    "capital",
    "inflation",
    "macroeconom",
    "microeconom",
    "marginal",
    "elasticity",
    "fiscal",
    "monetary",
    "economy",
    "economic",
]


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


# 已完成的归一标题(查重): 已有MD(经济学目录+MD根) ∪ 已入库标题
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
    return len(
        re.findall(r"(?m)^#\s+Chapter\s+\d|^第[一二三四五六七八九十百\d]+章|^Chapter\s+\d", text)
    )


def analyze(path):
    stem = Path(path).stem
    if matched(stem):
        return ("已转", stem, None)
    try:
        d = fitz.open(path)
    except Exception:
        return ("打不开", stem, None)
    npg = d.page_count
    # 抽样查文字层
    txt = ""
    for p in range(0, min(npg, 60), 6):
        txt += d[p].get_text()
    txt_ratio = len(txt) / max(min(npg, 60) // 6, 1)
    full = "".join(d[p].get_text() for p in range(npg))
    nch = chapters(full)
    if txt_ratio < 200:
        return ("需OCR(无文字层)", stem, npg)
    if nch < 3:
        return ("无章节结构", stem, npg)
    return ("可转", stem, npg)


def convert(path):
    """PDF/EPUB → 清洗后的 MD 文本(去页眉页脚/页码, 章节行提升为 # 标题). 同 math_convert.
    ★2026-07-07: 正文抽取换成 markitdown(pdfminer.six/pdfplumber), 换掉裸 fitz.get_text()
    ——统一转换工具链, 见 platform/3O/oprim/parser/parse_pdf.py 的同步改动(那边的
    pymupdf4llm 复现过整段内容按固定字符间隔重复的bug, 这边虽未复现但一起换)。markitdown
    不像 fitz 那样有天然页边界, 页眉页脚剔除从"按页首尾行频率"改成"全文行频率", 阈值沿用
    原有的 0.12*页数(页数仍用 fitz 快速取一次, 比按总行数算更准——总行数会随大部头/合集类
    书暴涨, 稀释掉真正逐页重复的页眉页脚)。"""
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
        if re.match(r"^(Chapter\s+\d+|第[一二三四五六七八九十百\d]+章|CHAPTER\s+\d+)\b", s):
            out.append(f"\n# {s}\n")
        else:
            out.append(s)
    return "\n".join(out)


def econ_textbook(text):
    """判定: 是否经济教材(经济密度 + 章节). 经济书无编号定理, 只看密度+章节."""
    n = len(text)
    low = text[:300000].lower()
    econ = sum(low.count(k) for k in ECON)
    nch = chapters(text)
    dens = econ / max(n / 1000, 1)
    # 管道需 第N章/Chapter 结构(章≥3); 经济性: 密度≥2.0(同 classify_md 经济学门)
    ok = nch >= 3 and dens >= 2.0
    return ok, f"econ密度{dens:.1f} 章{nch}"


results = {}
for path in sorted(glob.glob(f"{SRC}/*.pdf") + glob.glob(f"{SRC}/*.epub")):
    cat, stem, npg = analyze(path)
    results.setdefault(cat, []).append((stem, npg, path))

for cat in ["可转", "需OCR(无文字层)", "无章节结构", "已转", "打不开"]:
    items = results.get(cat, [])
    print(f"\n=== {cat} ({len(items)}) ===")
    for stem, npg, _ in items[:40]:
        print(f"  {'%4d页 ' % npg if npg else ''}{stem[:60]}")


def _write_if_econ_textbook(stem, text, force=False):
    """判定+写文件(可转/OCR共用尾段). 返回 True=已写入.
    force=True(仅OCR调用路径用): OCR是几十分钟到数小时一次性投入, 门禁(关键词密度/章节)
    没过也必须写出MD——门禁只该决定"是否自动入飞轮队列", 不该决定"OCR结果要不要保留"。"""
    ok, m = econ_textbook(text)
    if not ok:
        if not force:
            print(f"  – 跳过[{m}]: {stem[:42]}")
            return False
        print(f"  ⚠ 质量门未过[{m}], 仍写入(OCR产物不丢): {stem[:35]}")
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
    print(f"  ✓ [经济学] {clean[:45]} ({len(text) // 1024}KB)")
    return True


if DO:
    print("\n=== 转换「可转」+ 入 经济学 文件夹 ===")
    for stem, npg, path in results.get("可转", []):
        try:
            text = convert(path)
        except Exception as e:
            print(f"  ✗ 转换失败 {stem[:40]}: {e}")
            continue
        _write_if_econ_textbook(stem, text)

    # ★自主OCR(与math_convert.py同款, 复用同一套vLLM容器逻辑): 默认关, 只在
    # scripts/ocr_daemon.sh 那条独立慢节奏循环里打开, 别塞进三个飞轮每轮调的
    # pull_ingest.sh(有600s超时, 大书OCR一本能到~80min会被腰斩).
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
                    _write_if_econ_textbook(stem, text, force=True)
            finally:
                release_container()
        else:
            print("  ✗ vLLM 容器未就绪(显存不足或启动失败), 本轮跳过 OCR")

    print("✓ 完成. 需OCR/无章节 的未处理(见上).")
