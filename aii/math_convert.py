"""数学源文件(PDF/EPUB)→ MD: 找未转的, 检查可转性, 转换+入文件夹.
用法: math_convert.py          # 分析报告(不转)
      math_convert.py --do     # 转换可转的(文字层+章节)并入文件夹
"""

import os, re, sys, glob, unicodedata, subprocess
import fitz  # pymupdf
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from math_ocr_gate import needs_ocr  # noqa: E402

SRC = "/home/soffy/books/数学"
MD_ZH = "/home/soffy/books/MD/中文数学"
MD_EN = "/home/soffy/books/MD/英文数学"
DO = "--do" in sys.argv

import json


def _load_drive_ids() -> dict:
    """源文件基名 → Drive 直链 映射; 由 scripts/math_drive_sync.sh 同步时写到 SRC/.driveid.json。
    缺失/损坏 → 空 dict(照常转换, source_url 留空, 不阻塞)。"""
    try:
        return json.loads((Path(SRC) / ".driveid.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


_DRIVE_IDS = _load_drive_ids()


def _frontmatter(title: str, src_path: str, lang: str) -> str:
    """YAML frontmatter; source_url 按源文件基名取自 Drive 同步映射(没有则留空)。
    值用 JSON 串做双引号标量, 安全处理冒号/引号/CJK。"""
    fname = Path(src_path).name

    def y(v):
        return json.dumps(v, ensure_ascii=False)

    return "\n".join(
        [
            "---",
            f"title: {y(title)}",
            f"source_file: {y(fname)}",
            f"source_url: {y(_DRIVE_IDS.get(fname, ''))}",
            f"lang: {y(lang)}",
            "converter: markitdown",
            "---",
            "",
            "",
        ]
    )


def norm(s):  # 归一标题(去 z-lib/作者括号/空格标点)用于匹配
    s = re.sub(r"\(z-lib[^)]*\)|\(z-library[^)]*\)|\([^)]*1lib[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\.(pdf|epub)$", "", s, flags=re.I)
    s = re.sub(r"[\s_\-（）()【】\[\]·,，.。、:：;；]+", "", s)
    return s.lower()


def _ingested_titles():
    """权威已完成清单: aii.ingested_substrate 书名(已入库的不能再转, 否则文件名不同→重复入库)."""
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


# 已完成的归一标题: 已有MD(中英数学+MD根) ∪ 已入库标题
existing = set()
for d in (MD_ZH, MD_EN, "/home/soffy/books/MD"):
    for f in glob.glob(f"{d}/*.md"):
        existing.add(norm(Path(f).stem))
for t in _ingested_titles():
    existing.add(norm(t))


def matched(stem):
    ns = norm(stem)
    if ns in existing:  # 精确(短标题也算)
        return True
    for e in existing:
        if len(e) >= 6 and (e in ns or ns in e):  # 子串含
            return True
    return False


def chapters(text):
    # ★"第N 章"(数字后带空格)是烂文本层/扫描书常见的 fitz 抽取排版噪音, 原正则要求
    # 紧贴无空格, 会让这类书永远判"无章节结构"、连 OCR 门槛都进不去(实测斯图: 0→362命中).
    # ★中文分支原来不认"# "前缀——但 math_ocr_convert.ocr_pdf_to_text() 会把匹配到的中英文
    # 章节行统一提升成"# 标题"markdown格式, 导致新鲜OCR出来的中文书章节行变成"# 第N章",
    # 恰好只有英文分支认这个前缀, 中文分支永远算0章(实测斯图尔特今晚OCR复现: 0章被拒,
    # 而同一本书旧版手工转换的MD因为没有"#"前缀反而能通过). 中文分支也加上同样的可选前缀.
    return len(
        re.findall(r"(?m)^(?:#\s+)?Chapter\s+\d|^(?:#\s+)?第[一二三四五六七八九十百\d]+\s*章", text)
    )


def analyze(path):
    stem = Path(path).stem
    if matched(stem):
        return ("已转", stem, None)
    try:
        d = fitz.open(path)
    except Exception as e:
        return ("打不开", stem, None)
    npg = d.page_count
    # 抽样查文字层
    txt = ""
    for p in range(0, min(npg, 60), 6):
        txt += d[p].get_text()
    txt_ratio = len(txt) / max(min(npg, 60) // 6, 1)
    # 全文(估章节)
    full = "".join(d[p].get_text() for p in range(npg))
    nch = chapters(full)
    if txt_ratio < 200:
        return ("需OCR(无文字层)", stem, npg)
    if nch < 3:
        return ("无章节结构", stem, npg)
    # 有文字层、有章节, 但文字层可能是烂 OCR(扫描书自带识别错误, 例→囹/圆盘→罔盘/ε-δ→ε-Ò 这类)
    # 与"无文字层"不同, 这类书 txt_ratio/章节检测都过, 会被误判'可转'直接产出乱码 MD.
    ocr_flag, _ = needs_ocr(full)
    if ocr_flag:
        return ("需OCR(烂文本层)", stem, npg)
    return ("可转", stem, npg)


from collections import Counter


def convert(path):
    """PDF/EPUB → 清洗后的 MD 文本(去页眉页脚/页码, 章节行提升为 # 标题).
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
        if re.match(r"^(Chapter\s+\d+|第[一二三四五六七八九十百\d]+\s*章|CHAPTER\s+\d+)\b", s):
            out.append(f"\n# {s}\n")
        else:
            out.append(s)
    return "\n".join(out)


def math_textbook(text):
    """判定: 是否数学教材(带编号定理+章节+数学密度) → (是否, 中/英)."""
    n = len(text)
    low = text[:300000].lower()
    math = sum(
        low.count(k)
        for k in (
            "定理",
            "定义",
            "证明",
            "函数",
            "极限",
            "导数",
            "积分",
            "微分",
            "矩阵",
            "向量",
            "拓扑",
            "收敛",
            "theorem",
            "lemma",
            "proof",
            "calculus",
            "derivative",
            "integral",
            "matrix",
            "topology",
        )
    )
    thm = len(re.findall(r"(定理|定义|引理|推论)\s*[\d一二三四五六七八九十]", text[:300000])) + len(
        re.findall(r"\b(theorem|definition|lemma|corollary)\s+\d", low)
    )
    nch = chapters(text)
    zh = len(re.findall(r"[一-鿿]", text[:300000]))
    dens = math / max(n / 1000, 1)
    # 管道需 第N章/Chapter 结构(章≥3); 数学性: 大量编号定理 或 高数学密度
    ok = nch >= 3 and (thm >= 30 or dens >= 1.2)
    return ok, ("中文数学" if zh > 1000 else "英文数学"), f"dens{dens:.1f} 定理{thm} 章{nch}"


results = {}
for path in sorted(glob.glob(f"{SRC}/*.pdf") + glob.glob(f"{SRC}/*.epub")):
    cat, stem, npg = analyze(path)
    results.setdefault(cat, []).append((stem, npg, path))

for cat in ["可转", "需OCR(烂文本层)", "需OCR(无文字层)", "无章节结构", "已转", "打不开"]:
    items = results.get(cat, [])
    print(f"\n=== {cat} ({len(items)}) ===")
    for stem, npg, _ in items[:40]:
        print(f"  {'%4d页 ' % npg if npg else ''}{stem[:60]}")


def _write_if_math_textbook(stem, text, path):
    """判定+写文件(可转/OCR共用尾段). 返回 True=已写入.
    path=源文件路径, 用于在 frontmatter 里写 source_url(Drive 直链)."""
    ok, lang, m = math_textbook(text)
    if not ok:
        print(f"  – 跳过[{m}]: {stem[:42]}")
        return False
    tgt = MD_ZH if lang == "中文数学" else MD_EN
    clean = re.sub(r"\s*\(z-lib[^)]*\)|\s*\(z-library[^)]*\)", "", stem).strip()
    if matched(clean):  # 同轮稍早已转/已入库的近似书 → 不重复
        print(f"  – 重复(已转/已入库), 跳过: {clean[:40]}")
        return False
    dst = f"{tgt}/{clean}.md"
    if os.path.exists(dst):
        print(f"  – 已存在, 跳过: {clean[:40]}")
        return False
    open(dst, "w", encoding="utf-8").write(_frontmatter(clean, path, lang) + text)
    existing.add(norm(clean))  # 记入, 防同轮后续重复
    print(f"  ✓ [{lang}] {clean[:45]} ({len(text) // 1024}KB)")
    return True


if DO:
    print("\n=== 转换「可转」+ 分类入文件夹 ===")
    for stem, npg, path in results.get("可转", []):
        try:
            text = convert(path)
        except Exception as e:
            print(f"  ✗ 转换失败 {stem[:40]}: {e}")
            continue
        _write_if_math_textbook(stem, text, path)

    # ★自主 OCR: 遇到烂文本层/无文字层的数学扫描书, 自己拉起 vLLM 容器转清后再入常规流程,
    # 不需要人工干预. 只在确有此类书时才启动容器(不白占 GPU); 处理完统一释放.
    # ★默认关(env门禁): 大书OCR一本能到~80min, 这一步不能塞进三个飞轮每轮都调的
    # pull_ingest.sh(有600s超时, 会把没转完的OCR任务腰斩)——只在 scripts/ocr_daemon.sh
    # 那条独立、慢节奏、无短超时的常驻循环里打开 MATH_CONVERT_AUTO_OCR=1。
    ocr_books = (
        (results.get("需OCR(烂文本层)", []) + results.get("需OCR(无文字层)", []))
        if os.getenv("MATH_CONVERT_AUTO_OCR") == "1"
        else []
    )
    if ocr_books:
        import signal

        from math_ocr_convert import ensure_container, ocr_pdf_to_text, release_container

        # ★进程被杀(SIGTERM/SIGINT, 如 timeout 命令/手动中断/systemd stop)也要释放容器,
        # 否则 vLLM 白占 GPU 到下次人工发现为止(实测踩过: 30分钟测试超时后容器泄漏, GPU
        # 剩 479MiB 直到手动 docker stop). 已缓存的页(ocr_cache/)不受影响, 下次重跑续传.
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
                    _write_if_math_textbook(stem, text, path)
            finally:
                release_container()
        else:
            print("  ✗ vLLM 容器未就绪(显存不足或启动失败), 本轮跳过 OCR")

    print("✓ 完成. 需OCR/无章节 的未处理(见上).")
