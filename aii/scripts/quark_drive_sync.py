#!/usr/bin/env python3
"""夸克网盘 → 本地书源链 同步器(对齐 math_drive_sync.sh 模式)。

把夸克网盘里的 PDF/EPUB 下载到 /home/soffy/books/{数学,Economic,其它}，
feeder(pull_ingest.sh) 每 600s 自动 convert → books/MD → 三个 KU 飞轮消费。

流程:
  1. 列夸克目录(默认根目录; QUARK_FOLDER 可指定 fid) 的 pdf/epub
  2. 与 .quarkid.json(按目标目录) 比对, 只下载新增(幂等)
  3. 按文件名关键词分流: 数学 → books/数学; 经济 → books/Economic; 其他 → books/其它
  4. 记录 fid → 下次跳过

用法:
    .venv/bin/python scripts/quark_drive_sync.py [--dry-run] [--folder <fid>]
凭据: quark_pipeline/quark_cookies_full.txt(过期时重新复制浏览器 Cookie)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"
COOKIE_FILE = PIPE / "quark_cookies_full.txt"
CATALOG = PIPE / "quark_catalog.json"  # ★2026-08-10 目录树缓存: 夸克盘嵌套 3-4 层(主题包套娃),
#   全扫一次 30+ 分钟, 每轮重扫不可行; 缓存后 2h 轮次秒读, 后台异步刷新。
API = "https://drive-pc.quark.cn"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
BOOKS = Path("/home/soffy/books")
DEST_MAP = {
    "数学": BOOKS / "数学",
    "Economic": BOOKS / "Economic",
    "教辅": BOOKS / "教辅",   # ★2026-08-10 新分流: 中考/高考/知识点/真题(夸克最大类型 1985 本)
    "计算机": BOOKS / "计算机",  # ★2026-08-10 新分流: 编程/AI/算法(254 本)
    "其它": BOOKS / "其它",
}
# 关键词分流(按文件名; 命中即分流, 按优先级)
MATH_KW = r"数学|代数|几何|微积分|概率|统计|拓扑|方程|数论|矩阵|微分|积分|线性|傅里叶|群论|组合|概率论|高数|calculus|algebra|geometry|topology|probability|statistic|linear|matrix|equation|number theory"
ECON_KW = r"经济|金融|宏观|微观|贸易|财政|投资|市场|货币|证券|会计|管理|营销|博弈|econ|finance|macro|micro|trade|fiscal|monetary|investment|market|business"
# ★2026-08-10 教辅/计算机分流(优先级在 其它 之前)
EDU_KW = r"年级|中考|高考|知识点|初中|高中|小学|试卷|考点|真题|教辅|复习|课本|试题|题库|训练|培优"
CS_KW = r"编程|python|java|算法|人工智能|机器学习|深度学习|计算机|linux|数据结构|programming|algorithm|machine|软件工程|数据库|网络协议|操作系统"
EXT_OK = (".pdf", ".epub")


def _req(url: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Cookie": COOKIE_FILE.read_text().strip(),
            "Referer": "https://pan.quark.cn/",
            "User-Agent": UA,
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("status") != 200:
        raise RuntimeError(f"API {payload.get('status')}: {payload.get('message')} (cookie 过期?)")
    return payload


def _list_dir(fid: str, page: int = 1, size: int = 200) -> list[dict]:
    url = f"{API}/1/clouddrive/file/sort?pr=ucpro&fr=pc&uc_param_str=&pdir_fid={fid}&_page={page}&_size={size}&_sort=file_type:asc,file_name:asc"
    return _req(url)["data"].get("list", [])


def _walk(fid: str, depth: int = 2) -> list[dict]:
    """递归列出文件(默认 2 层), 返回 [item...]。
    2026-08-10: 跳过壁纸/文档工具等非书目录(扫描慢的根因, 这几百上千条拖死每轮)。"""
    _SKIP_DIR = ("壁纸", "文档工具")
    out: list[dict] = []
    for item in _list_dir(fid):
        if item.get("file"):
            out.append(item)
        elif item.get("dir") and depth > 0:
            if any(k in (item.get("file_name") or "") for k in _SKIP_DIR):
                continue
            out.extend(_walk(item["fid"], depth - 1))
    return out


def _download(item: dict, dest: Path) -> Path:
    d = _req(f"{API}/1/clouddrive/file/download?pr=ucpro&fr=pc&uc_param_str=", "POST",
             {"fids": [item["fid"]]})["data"][0]
    dl = d.get("download_url")
    if not dl:
        raise RuntimeError(f"{item['file_name']}: 无下载链接")
    name = re.sub(r'[\\/:*?"<>|]', "_", item["file_name"])
    out = dest / name
    part = dest / (name + ".part")
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "identity",
        "Referer": "https://pan.quark.cn/",
        "Cookie": COOKIE_FILE.read_text().strip(),
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
    }
    tmp = part if part.exists() else out
    if part.exists():
        headers["Range"] = f"bytes={part.stat().st_size}-"
    mode = "ab" if part.exists() else "wb"
    # ★2026-08-09: 下载 URL 为单次签名, 失败重试必须重新取 URL(旧 URL 复用→412 Precondition Failed)
    for attempt in range(3):
        try:
            if attempt > 0:
                fresh = _req(f"{API}/1/clouddrive/file/download?pr=ucpro&fr=pc&uc_param_str=", "POST",
                             {"fids": [item["fid"]]})["data"][0]
                dl = fresh.get("download_url")
            req = urllib.request.Request(dl, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, mode) as fh:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
            break
        except (urllib.error.URLError, OSError) as e:
            if attempt == 2:
                raise
            print(f"  ⚠ 下载中断({type(e).__name__}), 重试 {attempt+2}/3", flush=True)
            time.sleep(3)
    if part.exists():
        part.rename(out)
    return out


async def _apply_skill_rules(file_name: str, ext: str, size_bytes: int,
                             downloaded: Path) -> str | None:
    """应用 aii.skill_rules(静态预处理规则): 命中 → 挪 OCR 队列 + hits++。

    返回命中规则名(未命中 None)。任何异常静默(规则是建议, 不阻断主流程)。
    """
    import asyncpg as _apg
    try:
        conn = await _apg.connect(os.getenv("AII_KG_URL",
                                            "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg"),
                                  timeout=5)
        try:
            return await _apply_rules_with_conn(conn, file_name, ext, size_bytes, downloaded)
        finally:
            await conn.close()
    except Exception:  # noqa: BLE001
        return None


async def _apply_rules_with_conn(conn, file_name: str, ext: str, size_bytes: int,
                                 downloaded: Path) -> str | None:
    try:
        rules = await conn.fetch(
            "SELECT rule_id, rule_name, condition, action FROM aii.skill_rules"
            " WHERE enabled AND source IN ('static','distilled')")
        for rule in rules:
            cond = json.loads(rule["condition"])
            hit = True
            if "file_name_contains" in cond and cond["file_name_contains"] not in file_name:
                hit = False
            if hit and "ext" in cond and cond["ext"] != ext.lower().lstrip("."):
                hit = False
            if hit and "size_mb_gt" in cond and (size_bytes / 1048576) <= cond["size_mb_gt"]:
                hit = False
            if hit and "size_mb_lt" in cond and (size_bytes / 1048576) >= cond["size_mb_lt"]:
                hit = False
            if hit:
                action = json.loads(rule["action"])
                if action.get("route") == "ocr_queue":
                    ocr_dir = BOOKS / "待OCR"
                    ocr_dir.mkdir(exist_ok=True)
                    dest = ocr_dir / downloaded.name
                    if not dest.exists():
                        downloaded.rename(dest)
                    await conn.execute(
                        "UPDATE aii.skill_rules SET hits = hits + 1 WHERE rule_id=$1",
                        rule["rule_id"])
                    return rule["rule_name"]
        return None
    except Exception:  # noqa: BLE001
        return None


def _classify(name: str) -> Path:
    if re.search(EDU_KW, name, re.IGNORECASE):
        return DEST_MAP["教辅"]
    if re.search(CS_KW, name, re.IGNORECASE):
        return DEST_MAP["计算机"]
    if re.search(MATH_KW, name, re.IGNORECASE):
        return DEST_MAP["数学"]
    if re.search(ECON_KW, name, re.IGNORECASE):
        return DEST_MAP["Economic"]
    return DEST_MAP["其它"]


def _state_file(dest: Path) -> Path:
    return dest / ".quarkid.json"


def _load_state(dest: Path) -> set[str]:
    f = _state_file(dest)
    if f.exists():
        try:
            return set(json.loads(f.read_text()).get("fids", []))
        except Exception:
            return set()
    return set()


def _save_state(dest: Path, fids: set[str]) -> None:
    _state_file(dest).write_text(json.dumps({"fids": sorted(fids)}, ensure_ascii=False))


def _refresh_catalog(folder: str, depth: int) -> dict:
    """全量扫目录树(深层) → 缓存文件清单。慢(30+分钟), 只应由后台刷新调用。"""
    items = _walk(folder, depth)
    books = [i for i in items if i["file_name"].lower().endswith(EXT_OK)]
    cat = {"scanned_at": time.time(),
           "files": [{"fid": i["fid"], "file_name": i["file_name"], "size": i.get("size") or 0}
                      for i in books]}
    PIPE.mkdir(parents=True, exist_ok=True)
    tmp = CATALOG.with_suffix(".tmp")
    tmp.write_text(json.dumps(cat, ensure_ascii=False))
    tmp.replace(CATALOG)
    return cat


def _load_catalog(max_age: float = 12 * 3600) -> dict | None:
    try:
        cat = json.loads(CATALOG.read_text())
        if time.time() - cat.get("scanned_at", 0) < max_age:
            return cat
    except Exception:
        pass
    return None


def _spawn_refresh(folder: str, depth: int) -> None:
    """后台异步刷新目录树缓存(flock 防并发, nohup 不阻塞本轮下载)。"""
    lock = ROOT / ".locks" / "quark_catalog_refresh.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    cmd = (f"flock -n {lock} sh -c 'cd {ROOT} && nohup .venv/bin/python scripts/quark_drive_sync.py "
           f"--refresh-catalog --folder {folder} --depth {depth} "
           f">> quark_pipeline/catalog_refresh.log 2>&1 &'")
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        print("  ⚠ 目录树刷新已在跑(flock), 跳过", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh-catalog", action="store_true",
                    help="全量扫目录树并缓存文件清单(慢, 后台用)")
    ap.add_argument("--folder", default=os.getenv("QUARK_FOLDER", "0"),
                    help="夸克目录 fid(默认 0=根目录; 可在夸克建『待入库』文件夹后填其 fid)")
    ap.add_argument("--depth", type=int, default=4,
                    help="目录树深度(默认 4 — 夸克盘主题包套娃 3-4 层, 2 层看不到书)")
    ap.add_argument("--limit", type=int, default=30,
                    help="每轮最多下载数(默认 30, 0=不限; 小文件优先, 防一轮卡死)")
    args = ap.parse_args()

    if not COOKIE_FILE.exists():
        print(f"❌ 缺 Cookie 文件: {COOKIE_FILE}")
        return 1

    if args.refresh_catalog:
        print(f"🔍 全量刷新目录树(fid={args.folder}, 深度 {args.depth}) ...", flush=True)
        cat = _refresh_catalog(args.folder, args.depth)
        print(f"   目录树已缓存: {len(cat['files'])} 个 PDF/EPUB", flush=True)
        return 0

    # 缓存新鲜 → 直接用; 稍旧(>3h) → 后台刷新+用旧; 无缓存 → 浅扫兜底 + 后台全量
    cat = _load_catalog()
    if cat is None:
        print(f"⚠ 无目录树缓存, 先浅扫(深度2)兜底, 后台全量刷新中...", flush=True)
        cat = {"scanned_at": time.time(),
               "files": [{"fid": i["fid"], "file_name": i["file_name"], "size": i.get("size") or 0}
                          for i in _walk(args.folder, 2)
                          if i["file_name"].lower().endswith(EXT_OK)]}
        _spawn_refresh(args.folder, args.depth)
    elif time.time() - cat["scanned_at"] > 3 * 3600:
        print(f"   (目录树缓存 {int((time.time()-cat['scanned_at'])/3600)}h 前, 后台刷新中)", flush=True)
        _spawn_refresh(args.folder, args.depth)

    books = list(cat["files"])
    print(f"📚 目录树 {len(books)} 个 PDF/EPUB (缓存于 {time.strftime('%H:%M', time.localtime(cat['scanned_at']))})", flush=True)

    # ★2026-08-10 教材类优先: 教辅/计算机/数学/经济先拉(每轮限额内), 其它(杂学/网文)垫底,
    #   避免小垃圾文件占满每轮 30 个限额。同类内仍小文件优先。
    def _prio(nm: str) -> int:
        if re.search(EDU_KW, nm, re.IGNORECASE): return 0
        if re.search(CS_KW, nm, re.IGNORECASE): return 1
        if re.search(MATH_KW, nm, re.IGNORECASE): return 2
        if re.search(ECON_KW, nm, re.IGNORECASE): return 3
        return 4

    books.sort(key=lambda i: (_prio(i["file_name"]), i.get("size") or 0))

    # ★2026-08-10 过滤拆分/垃圾: "每天一篇/DAY N/第N天" 单篇(非完整书)、<200KB 杂文件
    #   占满每轮限额但 convert 全拒(无章节/无文字层), 白耗 API。
    import re as _re

    def _junk(nm: str, sz: int) -> bool:
        if sz and sz < 200 * 1024:
            return True
        return bool(_re.search(r"DAY\s*\d+|每天一篇|第\d+天|\d+天搞定|口袋学堂", nm, _re.I))

    before = len(books)
    books = [i for i in books if not _junk(i["file_name"], i.get("size") or 0)]
    print(f"   (过滤拆分/小文件后: {before} → {len(books)} 本)", flush=True)

    seen_total: set[str] = set()
    new_total = 0
    # ★2026-08-10 每类独立限额: 教辅/计算机/数学/经济/其它 各自拉 limit 本(原来总限额被
    #   1985 本教辅占满, 计算机要等 400 轮)。改后每轮 = 5 类 × limit, 吞吐 x5。
    per_class = {i: 0 for i in range(5)}
    for item in books:
        dest = _classify(item["file_name"])
        dest.mkdir(parents=True, exist_ok=True)
        state = _load_state(dest)
        seen_total |= state
        if item["fid"] in state:
            continue
        cls = _prio(item["file_name"])
        if args.limit and per_class[cls] >= args.limit:
            continue
        if per_class[cls] >= args.limit:
            continue
        size_mb = (item.get("size") or 0) / 1048576
        print(f"📥 [{dest.name}] {item['file_name']} ({size_mb:.1f}MB)", flush=True)
        if not args.dry_run:
            try:
                out = _download(item, dest)
                print(f"   ✅ {out.name}", flush=True)
                # ★P2d 静态规则预筛: 命中(如 z-lib 扫描版) → 直接进 OCR 队列
                import asyncio as _asyncio
                hit = _asyncio.run(_apply_skill_rules(
                    item["file_name"], Path(item["file_name"]).suffix,
                    item.get("size") or 0, out))
                if hit:
                    print(f"   🔀 规则命中 [{hit}] → 待OCR 队列", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"   ⚠ 失败: {e}", flush=True)
                continue
        state.add(item["fid"])
        _save_state(dest, state)
        per_class[cls] += 1
        new_total += 1

    print(f"\n完成: 新增 {new_total} 个 (已记录 {len(seen_total)} 个去重)", flush=True)
    print("feeder 每 600s 自动 convert → books/MD → 飞轮抽取", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
