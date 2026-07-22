#!/usr/bin/env python3
"""W-H1a-3 全书入库（raw wikitext 路径，ARC-SPEC §4.2 改走 raw）。

R5：底本 = zh.wikisource.org **?action=raw** 原始 wikitext（curl 经既通代理），剥模板得白文；
**禁渲染型抓取（WebFetch 有损）**；raw 不通再退 wikimedia dumps。CC BY-SA 逐字、禁点校本。

管线：curl raw → 剥模板/markup → 按 ==节== 与段落切 → 段落级 ULID → corpus/*.json（全文）。
para_ulid = `<substrate-ULID>:NNNN`（合契约模式）。幂等：先 fetch 到 scratchpad/raw 缓存，再解析。

用法：
  python3 tools/history/ingest_raw.py --fetch   # curl 抓所有 BOOKS 页到 raw 缓存
  python3 tools/history/ingest_raw.py --build    # 解析缓存 → corpus/*.json
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "docs" / "history"
OUT = ROOT / "corpus"
RAW = Path(
    "/tmp/claude-1000/-data-soffy-projects-stratum/2a48e2c8-7f78-4cfb-87de-961000b21fa3/scratchpad/raw"
)
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# 书 → [(章名, wikisource 页标题)]
BOOKS = {
    "src:zuozhuan": (
        "左传（春秋左氏传）",
        "CC BY-SA 3.0（维基文库 raw wikitext）",
        [
            (d, f"春秋左氏傳/{d}")
            for d in [
                "隱公",
                "桓公",
                "莊公",
                "閔公",
                "僖公",
                "文公",
                "宣公",
                "成公",
                "襄公",
                "昭公",
                "定公",
                "哀公",
            ]
        ],
    ),
    "src:guoyu": (
        "国语",
        "CC BY-SA 3.0（维基文库 raw wikitext）",
        [
            (c, f"國語/{c}")
            for c in [
                "晉語一",
                "晉語二",
                "晉語三",
                "晉語四",
                "晉語五",
                "晉語六",
                "晉語七",
                "晉語八",
                "晉語九",
            ]
        ],
    ),
    "src:zztj": (
        "资治通鉴",
        "CC BY-SA 3.0（维基文库 raw wikitext）",
        [("周紀一", "資治通鑑/卷001")],
    ),
    "src:shiji": (
        "史记",
        "CC BY-SA 3.0（维基文库 raw wikitext）",
        [
            ("晉世家", "史記/卷039"),
            ("趙世家", "史記/卷043"),
            ("魏世家", "史記/卷044"),
            ("韓世家", "史記/卷045"),
            ("田敬仲完世家", "史記/卷046"),
            ("項羽本紀", "史記/卷007"),
            ("白起王翦列傳", "史記/卷073"),
            ("蘇秦列傳", "史記/卷069"),
            ("五帝本紀", "史記/卷001"),
            ("周本紀", "史記/卷004"),
            ("高祖本紀", "史記/卷008"),
            ("樊酈滕灌列傳", "史記/卷095"),
            ("六國年表", "史記/卷015"),
        ],
    ),
    "src:sanguozhi": (
        "三国志（含裴注）",
        "CC BY-SA 3.0（维基文库 raw wikitext）",
        [
            ("魏書·武帝紀", "三國志/卷001"),
            ("蜀書·諸葛亮傳", "三國志/卷035"),
            ("蜀書·馬良傳", "三國志/卷039"),
            ("蜀書·董劉馬陳董呂傳", "三國志/卷039"),
            ("吳書·周瑜魯肅呂蒙傳", "三國志/卷054"),
        ],
    ),
    "src:zhanguoce": (
        "战国策",
        "CC BY-SA 3.0（维基文库 raw wikitext）",
        [
            ("趙策一", "戰國策/卷18"),
            ("趙策二", "戰國策/卷19"),
            ("趙策三", "戰國策/卷20"),
            ("趙策四", "戰國策/卷21"),
            ("魏策一", "戰國策/卷22"),
            ("魏策二", "戰國策/卷23"),
            ("魏策三", "戰國策/卷24"),
            ("魏策四", "戰國策/卷25"),
            ("韓策一", "戰國策/卷26"),
            ("韓策二", "戰國策/卷27"),
            ("韓策三", "戰國策/卷28"),
        ],
    ),
}


def derive_ulid(src_id: str) -> str:
    n = int.from_bytes(hashlib.sha256((src_id + "|ulid").encode()).digest()[:17], "big") >> 6
    s = ""
    for _ in range(26):
        s = CROCKFORD[n & 31] + s
        n >>= 5
    return s


def slug(title):
    # 中文标题不可用 [^0-9A-Za-z]→_（会全撞名）；改哈希前缀保唯一。
    h = hashlib.sha1(title.encode()).hexdigest()[:10]
    tail = re.sub(r"[^0-9A-Za-z]", "", title)[-8:]
    return f"{h}_{tail}" if tail else h


def fetch():
    RAW.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    for src_id, (_book, _lic, pages) in BOOKS.items():
        for chap, title in pages:
            f = RAW / (slug(title) + ".txt")
            if f.exists() and f.stat().st_size > 200:
                ok += 1
                continue
            url = f"https://zh.wikisource.org/wiki/{title}?action=raw"
            out = subprocess.run(
                ["curl", "-s", "--retry", "4", "--retry-delay", "5", "--max-time", "50", url],
                capture_output=True,
                text=True,
                timeout=45,
            ).stdout
            if len(out) > 200 and "{{" in out:
                f.write_text(out, encoding="utf-8")
                ok += 1
                print(f"OK  {title}  {len(out)}B")
            else:
                fail += 1
                print(f"FAIL {title}  ({len(out)}B)")
    print(f"--- fetch: {ok} ok, {fail} fail")


TEMPL = re.compile(r"\{\{([^{}]*)\}\}")


def strip_wikitext(t: str) -> str:
    t = re.sub(r"\{\{header2.*?\}\}", "", t, flags=re.S)
    t = re.sub(r"\{\{PD.*?\}\}", "", t, flags=re.S)
    t = t.replace("<onlyinclude>", "").replace("</onlyinclude>", "")

    def repl(m):
        body = m.group(1)
        if body.startswith("YL|"):
            parts = body.split("|")
            return parts[1] + ("（" + parts[2] + "）" if len(parts) > 2 else "")
        if body.startswith("+|"):
            return body[2:]
        if body.startswith("PUA|") or body.startswith("!"):
            return ""
        parts = body.split("|")
        return parts[-1]

    for _ in range(4):
        t = TEMPL.sub(repl, t)
    t = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[\[([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"'''?", "", t)
    t = re.sub(r"<ref.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "", t)
    t = t.replace("----", "")
    return t


def parse_page(text, chap):
    """→ [(subchap, paragraph_text)]，按 ==节== 归属，段落按行。"""
    text = strip_wikitext(text)
    paras = []
    cur = chap
    for line in text.split("\n"):
        line = line.strip().replace("　", "")
        if not line:
            continue
        h = re.match(r"^=+\s*(.*?)\s*=+$", line)
        if h:
            name = h.group(1)
            if name not in ("經", "傳", "经", "传"):
                cur = f"{chap}·{name}" if name != chap else chap
            continue
        if len(line) >= 4:
            paras.append((cur, line))
    return paras


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    stats = []
    for src_id, (book, lic, pages) in BOOKS.items():
        sub = derive_ulid(src_id)
        objs = []
        chars = 0
        for chap, title in pages:
            f = RAW / (slug(title) + ".txt")
            if not f.exists():
                continue
            for subchap, ptext in parse_page(f.read_text(encoding="utf-8"), chap):
                chars += len(ptext)
                objs.append({"chapter": subchap, "text": ptext})
        if not objs:
            # raw 全失败（国语/战国策：子页命名异/仅注本 R5 禁）——不覆盖既有快照文件
            print(
                f"SKIP {src_id}: 无 raw 段, 保留既有快照 corpus/{src_id.replace('src:', '')}.json"
            )
            continue
        # 分配 para_ulid
        for i, o in enumerate(objs, 1):
            o["para_ulid"] = f"{sub}:{i:04d}"
        # reorder keys
        objs = [
            {"para_ulid": o["para_ulid"], "chapter": o["chapter"], "text": o["text"]} for o in objs
        ]
        doc = {
            "substrate": {
                "substrate_ulid": sub,
                "source_ref": src_id,
                "book": book,
                "base_text": {
                    "source": "zh.wikisource.org ?action=raw（原始 wikitext 剥模板）",
                    "license": lic,
                    "fetch_date": "2026-07-22",
                    "char_count": chars,
                    "form": "白文（raw wikitext 剥模板，CC BY-SA）",
                    "r5": "禁渲染抓取/禁点校本；curl raw 逐字剥模板",
                },
                "coverage": f"{len([1 for c, t in pages if (RAW / (slug(t) + '.txt')).exists()])}/{len(pages)} 页",
                "ulid_scheme": "substrate ULID = SHA256(src_id) 派生 Crockford base32",
            },
            "paragraphs": objs,
        }
        out = OUT / (src_id.replace("src:", "") + ".json")
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stats.append((book, len(objs), chars))
        print(f"{out.name}: {len(objs)} paras, {chars} chars")
    for b, n, c in stats:
        print(f"  {b}: {n} 段 / {c} 字")


if __name__ == "__main__":
    if "--fetch" in sys.argv:
        fetch()
    if "--build" in sys.argv:
        build()
    if not any(a.startswith("--") for a in sys.argv[1:]):
        print("用 --fetch 和/或 --build")
