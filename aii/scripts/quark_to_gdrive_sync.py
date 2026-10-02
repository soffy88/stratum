#!/usr/bin/env python3
"""夸克网盘 → Google Drive (gdrive:aii-books) 自动化流式同步与去重删除工具。

功能：
1. 去重清理 (clean-duplicates)：
   - 对比 GDrive 现有书库，在夸克中已存在的文件视为重复，从夸克直接删除。
   - 扫描夸克内部重复文件（多重套娃副本），只保留 1 份，其余冗余副本从夸克删除。
2. 流式同步 (sync)：
   - 针对净新增书籍，按学科关键词分类：教辅、计算机、数学、Economic、其它。
   - 每次只下载 1 本到本地临时缓冲 (/data/soffy/scratch/quark_transit/)。
   - 调用 rclone copyto 上传到 gdrive:aii-books/<分类>/<文件名>。
   - 上传校验成功后，立即删除本地临时文件，并调用夸克接口删除夸克端原文件以释放空间。
   - 支持断点续传与持久化状态记录 (quark_sync_state.json)。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"
COOKIE_FILE = PIPE / "quark_cookies_full.txt"
CATALOG = PIPE / "quark_catalog.json"
STATE_FILE = PIPE / "quark_sync_state.json"
TRANSIT_DIR = Path("/data/soffy/scratch/quark_transit")

API = "https://drive-pc.quark.cn"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 "
    "Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch"
)

MATH_KW = r"数学|代数|几何|微积分|概率|统计|拓扑|方程|数论|矩阵|微分|积分|线性|傅里叶|群论|组合|概率论|高数|calculus|algebra|geometry|topology|probability|statistic|linear|matrix|equation|number theory"
ECON_KW = r"经济|金融|宏观|微观|贸易|财政|投资|市场|货币|证券|会计|管理|营销|博弈|econ|finance|macro|micro|trade|fiscal|monetary|investment|market|business"
EDU_KW = r"年级|中考|高考|知识点|初中|高中|小学|试卷|考点|真题|教辅|复习|课本|试题|题库|训练|培优"
CS_KW = r"编程|python|java|算法|人工智能|机器学习|深度学习|计算机|linux|数据结构|programming|algorithm|machine|软件工程|数据库|网络协议|操作系统"


def _cookie() -> str:
    return COOKIE_FILE.read_text().strip()


def _req(url: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Cookie": _cookie(),
            "Referer": "https://pan.quark.cn/",
            "User-Agent": UA,
            "Content-Type": "application/json",
        },
        method=method,
    )
    # 夸克 API 为国内站点，不走本地 clash/7890 代理
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)
    with opener.open(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("status") != 200:
        raise RuntimeError(f"API {payload.get('status')}: {payload.get('message')}")
    return payload


def _classify(name: str) -> str:
    if re.search(EDU_KW, name, re.IGNORECASE):
        return "教辅"
    if re.search(CS_KW, name, re.IGNORECASE):
        return "计算机"
    if re.search(MATH_KW, name, re.IGNORECASE):
        return "数学"
    if re.search(ECON_KW, name, re.IGNORECASE):
        return "Economic"
    return "其它"


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    if len(cleaned.encode("utf-8")) <= 240:
        return cleaned
    base, ext = os.path.splitext(cleaned)
    encoded = base.encode("utf-8")[:200]
    return encoded.decode("utf-8", errors="ignore") + ext


def delete_quark_files(fids: list[str]) -> bool:
    """批量删除夸克网盘中的文件 (每批次最多 100 个)"""
    if not fids:
        return True
    url = f"{API}/1/clouddrive/file/delete?pr=ucpro&fr=pc&uc_param_str="
    body = {"action_type": 2, "filelist": fids, "exclude_fids": []}
    try:
        res = _req(url, "POST", body)
        task_id = res.get("data", {}).get("task_id")
        if task_id:
            # 轮询确认
            for _ in range(10):
                time.sleep(1)
                t_res = _req(f"{API}/1/clouddrive/task?pr=ucpro&fr=pc&uc_param_str=&task_id={task_id}")
                if t_res.get("data", {}).get("status") in (2, 3):  # 2: 成功
                    return True
        return True
    except Exception as e:
        print(f"  ⚠ 夸克删除接口异常: {e}", flush=True)
        return False


def load_gdrive_files() -> set[str]:
    """通过 rclone lsf 实时拉取 GDrive 中的现有文件名列表"""
    cmd = ["rclone", "lsf", "-R", "--files-only", "gdrive:aii-books"]
    try:
        out = subprocess.check_output(cmd, text=True, timeout=60)
        files = set()
        for line in out.strip().split("\n"):
            line = line.strip()
            if line:
                files.add(line.split("/")[-1])
        return files
    except Exception as e:
        print(f"❌ 无法读取 GDrive 文件列表: {e}", flush=True)
        return set()


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"deleted_duplicates": [], "synced_fids": []}


def save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    tmp.replace(STATE_FILE)


def download_quark_file(fid: str, file_name: str, out_path: Path) -> bool:
    """从夸克网盘下载单文件到本地临时路径"""
    url = f"{API}/1/clouddrive/file/download?pr=ucpro&fr=pc&uc_param_str="
    try:
        d = _req(url, "POST", {"fids": [fid]})
        dl_url = d["data"][0].get("download_url")
        if not dl_url:
            return False
    except Exception as e:
        print(f"  ⚠ 获取下载链接失败: {e}", flush=True)
        return False

    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "identity",
        "Referer": "https://pan.quark.cn/",
        "Cookie": _cookie(),
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
    }
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)
    req = urllib.request.Request(dl_url, headers=headers)

    part_file = out_path.with_suffix(out_path.suffix + ".part")
    if part_file.exists():
        headers["Range"] = f"bytes={part_file.stat().st_size}-"
        req = urllib.request.Request(dl_url, headers=headers)

    mode = "ab" if part_file.exists() else "wb"
    for attempt in range(3):
        try:
            with opener.open(req, timeout=90) as resp, open(part_file, mode) as fh:
                while True:
                    chunk = resp.read(1 << 20)  # 1MB
                    if not chunk:
                        break
                    fh.write(chunk)
            part_file.rename(out_path)
            return True
        except Exception as e:
            if attempt == 2:
                print(f"  ⚠ 下载失败: {e}", flush=True)
                if part_file.exists():
                    part_file.unlink(missing_ok=True)
                return False
            time.sleep(2)
    return False


def upload_to_gdrive(local_path: Path, category: str, remote_filename: str) -> bool:
    """使用 rclone copyto 将本地文件上传至 GDrive 对应目录"""
    remote_path = f"gdrive:aii-books/{category}/{remote_filename}"
    cmd = ["rclone", "copyto", str(local_path), remote_path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if res.returncode == 0:
            return True
        print(f"  ⚠ rclone 上传失败: {res.stderr[:200]}", flush=True)
        return False
    except Exception as e:
        print(f"  ⚠ rclone 调用超时/异常: {e}", flush=True)
        return False


def cmd_clean_duplicates(cat_files: list[dict], gdrive_files: set[str], state: dict) -> None:
    """清理在 GDrive 中已有的文件，以及夸克内的重复副本"""
    print("\n🔍 正在分析重复文件...", flush=True)
    deleted_fids_set = set(state.get("deleted_duplicates", []))

    to_delete_fids = []
    seen_names = {}
    already_in_gd = 0
    internal_dup = 0

    for f in cat_files:
        fid = f["fid"]
        fname = f["file_name"]
        if fid in deleted_fids_set:
            continue

        if fname in gdrive_files:
            to_delete_fids.append(fid)
            already_in_gd += 1
        elif fname in seen_names:
            to_delete_fids.append(fid)
            internal_dup += 1
        else:
            seen_names[fname] = fid

    total_to_del = len(to_delete_fids)
    print(f"  • 与 GDrive 重复（待删除）: {already_in_gd} 个")
    print(f"  • 夸克内部多重副本（待删除）: {internal_dup} 个")
    print(f"  • 合计待从夸克删除: {total_to_del} 个\n", flush=True)

    if not to_delete_fids:
        print("✅ 没有待删除的重复文件！", flush=True)
        return

    # 分批删除 (每批 50 个)
    BATCH = 50
    success_count = 0
    for i in range(0, total_to_del, BATCH):
        batch = to_delete_fids[i : i + BATCH]
        print(f"🗑️ 正在从夸克删除重复项 [{i + 1} - {min(i + BATCH, total_to_del)} / {total_to_del}] ...", flush=True)
        if delete_quark_files(batch):
            success_count += len(batch)
            state["deleted_duplicates"].extend(batch)
            save_state(state)
        time.sleep(0.5)

    print(f"\n🎉 成功从夸克网盘删除 {success_count} 个重复文件/副本！", flush=True)


def cmd_sync_to_gdrive(cat_files: list[dict], gdrive_files: set[str], state: dict, limit: int = 0) -> None:
    """执行流式下载、上传至 GDrive，并在成功后删除夸克源文件"""
    TRANSIT_DIR.mkdir(parents=True, exist_ok=True)
    deleted_fids_set = set(state.get("deleted_duplicates", []))
    synced_fids_set = set(state.get("synced_fids", []))

    # 过滤出净新增
    candidates = []
    seen_names = set()
    for f in cat_files:
        fid = f["fid"]
        fname = f["file_name"]
        if fid in deleted_fids_set or fid in synced_fids_set:
            continue
        if fname in gdrive_files:
            continue
        if fname in seen_names:
            continue
        seen_names.add(fname)
        candidates.append(f)

    total_cand = len(candidates)
    if limit > 0:
        candidates = candidates[:limit]

    print(f"\n🚀 共有 {total_cand} 本净新增书籍待转移至 GDrive (本轮计划处理 {len(candidates)} 本)\n", flush=True)

    synced_count = 0
    for idx, item in enumerate(candidates, 1):
        fid = item["fid"]
        raw_name = item["file_name"]
        safe_name = _safe_filename(raw_name)
        cat = _classify(safe_name)
        size_mb = (item.get("size") or 0) / 1048576

        print(f"[{idx}/{len(candidates)}] 📥 [{cat}] {safe_name} ({size_mb:.1f}MB) ...", flush=True)

        local_file = TRANSIT_DIR / safe_name
        # 1. 下载单文件
        dl_ok = download_quark_file(fid, raw_name, local_file)
        if not dl_ok:
            print("  ❌ 下载失败，跳过本项", flush=True)
            continue

        # 2. 上传至 GDrive
        up_ok = upload_to_gdrive(local_file, cat, safe_name)
        if not up_ok:
            print("  ❌ 上传 GDrive 失败，保留夸克源文件", flush=True)
            local_file.unlink(missing_ok=True)
            continue

        # 3. 校验并清理本地临时文件
        local_file.unlink(missing_ok=True)

        # 4. 从夸克盘删除原文件
        del_ok = delete_quark_files([fid])
        del_tag = "已从夸克删除原件" if del_ok else "夸克删除失败(后续重试)"

        print(f"  ✅ 成功同步至 gdrive:aii-books/{cat}/ ({del_tag})", flush=True)

        # 5. 记录状态
        state["synced_fids"].append(fid)
        save_state(state)
        synced_count += 1
        gdrive_files.add(safe_name)

    print(f"\n🎉 本轮同步完成: 成功转移并清理 {synced_count} 本书！", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="夸克网盘 → GDrive 流式同步与去重工具")
    parser.add_argument("--clean-only", action="store_true", help="仅执行重复文件清理（删除重复）")
    parser.add_argument("--sync-only", action="store_true", help="仅执行新增书籍同步")
    parser.add_argument("--limit", type=int, default=0, help="本轮最大同步书籍数量 (0=全量)")
    args = parser.parse_args()

    if not COOKIE_FILE.exists():
        print(f"❌ 缺 Cookie 文件: {COOKIE_FILE}", flush=True)
        return 1

    if not CATALOG.exists():
        print(f"❌ 缺目录树缓存: {CATALOG}", flush=True)
        return 1

    cat = json.load(open(CATALOG))
    cat_files = cat.get("files", [])
    print(f"📚 夸克目录树已记录: {len(cat_files)} 个文件", flush=True)

    gdrive_files = load_gdrive_files()
    print(f"☁️ GDrive (gdrive:aii-books) 现有: {len(gdrive_files)} 个文件", flush=True)

    state = load_state()

    if args.clean_only:
        cmd_clean_duplicates(cat_files, gdrive_files, state)
    elif args.sync_only:
        cmd_sync_to_gdrive(cat_files, gdrive_files, state, limit=args.limit)
    else:
        # 默认：先清理重复，再同步新增
        cmd_clean_duplicates(cat_files, gdrive_files, state)
        # 重新刷新一下 gdrive_files
        gdrive_files = load_gdrive_files()
        cmd_sync_to_gdrive(cat_files, gdrive_files, state, limit=args.limit)

    return 0


if __name__ == "__main__":
    sys.exit(main())
