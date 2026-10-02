#!/usr/bin/env python3
"""夸克网盘深度去重与空间释放工具。

主要功能：
1. 识别并删除【来自：分享】中重复转存的多重套娃冗余文件夹（如 `*(1)`, `*(2)` 等），保留唯一正本。
2. 识别并清理已同步或已清空的空文件夹外壳。
3. 统计并汇报释放的空间与清理项。
"""

import argparse
import json
import re
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"
COOKIE_FILE = PIPE / "quark_cookies_full.txt"
STATE_FILE = PIPE / "quark_sync_state.json"

API = "https://drive-pc.quark.cn"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


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
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)
    with opener.open(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def delete_quark_fids(fids: list[str]) -> bool:
    """批量删除夸克网盘中的文件/文件夹 (按批次每批最多 50 个)"""
    if not fids:
        return True
    url = f"{API}/1/clouddrive/file/delete?pr=ucpro&fr=pc&uc_param_str="
    batch_size = 50
    for i in range(0, len(fids), batch_size):
        chunk = fids[i:i + batch_size]
        body = {"action_type": 2, "filelist": chunk, "exclude_fids": []}
        try:
            res = _req(url, "POST", body)
            task_id = res.get("data", {}).get("task_id")
            if task_id:
                for _ in range(10):
                    time.sleep(1)
                    t_res = _req(f"{API}/1/clouddrive/task?pr=ucpro&fr=pc&uc_param_str=&task_id={task_id}")
                    if t_res.get("data", {}).get("status") in (2, 3):
                        break
            print(f"  ✓ 成功删除批次 {i // batch_size + 1}: {len(chunk)} 项", flush=True)
        except Exception as e:
            print(f"  ❌ 删除失败: {e}", flush=True)
            return False
    return True


def scan_share_dir() -> tuple[list[dict], list[dict]]:
    """扫描【来自：分享】目录下的所有直接子项"""
    # 查找来自：分享 fid
    root_items = _req(f"{API}/1/clouddrive/file/sort?pr=ucpro&fr=pc&uc_param_str=&pdir_fid=0&_page=1&_size=50")
    share_fid = None
    for it in root_items.get("data", {}).get("list", []):
        if "分享" in it.get("file_name", ""):
            share_fid = it["fid"]
            break

    if not share_fid:
        raise RuntimeError("未找到【来自：分享】目录")

    page = 1
    all_items = []
    while True:
        url = f"{API}/1/clouddrive/file/sort?pr=ucpro&fr=pc&uc_param_str=&pdir_fid={share_fid}&_page={page}&_size=200&_sort=file_type:asc,file_name:asc"
        res = _req(url)
        items = res.get("data", {}).get("list", [])
        if not items:
            break
        all_items.extend(items)
        page += 1
        if len(items) < 200:
            break

    dirs = [x for x in all_items if x.get("dir")]
    files = [x for x in all_items if x.get("file")]
    return dirs, files


def analyze_redundant_dirs(dirs: list[dict]) -> tuple[list[tuple[dict, dict]], list[dict]]:
    """分析重复目录与空目录"""
    # 按标准名称归组
    groups = defaultdict(list)
    for d in dirs:
        name = d["file_name"]
        # 去掉尾部的 (1), (2), (2)(1) 等
        clean = re.sub(r'(\(\d+\))+$', '', name).strip()
        groups[clean].append(d)

    redundant_copies = []
    for clean_name, group in groups.items():
        if len(group) > 1:
            # 排序：优先保留没有后缀的最简名称，其次按创建时间最早的保留
            def sort_key(item):
                has_suffix = 1 if re.search(r'\(\d+\)$', item["file_name"]) else 0
                return (has_suffix, len(item["file_name"]), item.get("created_at", 0))

            sorted_group = sorted(group, key=sort_key)
            canonical = sorted_group[0]
            for dup in sorted_group[1:]:
                redundant_copies.append((dup, canonical))

    return redundant_copies


def check_empty_dirs(dirs: list[dict]) -> list[dict]:
    """检查哪些目录完全为空"""
    empty = []
    print(f"正在检查 {len(dirs)} 个目录的空状态...", flush=True)
    for d in dirs:
        url = f"{API}/1/clouddrive/file/sort?pr=ucpro&fr=pc&uc_param_str=&pdir_fid={d['fid']}&_page=1&_size=1"
        try:
            sub = _req(url).get("data", {}).get("list", [])
            if len(sub) == 0:
                empty.append(d)
        except Exception:
            pass
    return empty


def main():
    parser = argparse.ArgumentParser(description="夸克网盘深度去重与空间释放")
    parser.add_argument("--execute", action="store_true", help="实际执行删除（默认仅预览）")
    parser.add_argument("--clean-empty", action="store_true", help="同时清理空目录")
    args = parser.parse_args()

    print("════════════════════════════════════════════════════")
    print(" 夸克网盘去重与空间优化分析")
    print("════════════════════════════════════════════════════")

    dirs, files = scan_share_dir()
    print(f"📁 【来自：分享】包含：{len(dirs)} 个文件夹，{len(files)} 个独立文件\n")

    redundant = analyze_redundant_dirs(dirs)
    print(f"🔍 发现重复冗余文件夹: {len(redundant)} 个")
    for dup, canon in redundant:
        print(f"  • [待删除] {dup['file_name']}")
        print(f"    └── [保留正本] {canon['file_name']}")

    empty_dirs = []
    if args.clean_empty:
        empty_dirs = check_empty_dirs(dirs)
        print(f"\n🗑 发现完全为空的文件夹: {len(empty_dirs)} 个")
        for ed in empty_dirs[:15]:
            print(f"  • [空目录] {ed['file_name']}")
        if len(empty_dirs) > 15:
            print(f"  ... 以及其余 {len(empty_dirs) - 15} 个")

    to_delete_fids = [dup["fid"] for dup, _ in redundant]
    if args.clean_empty:
        # 去除已经在 redundant 中的 fid
        seen_fids = set(to_delete_fids)
        for ed in empty_dirs:
            if ed["fid"] not in seen_fids:
                to_delete_fids.append(ed["fid"])

    print(f"\n📊 汇总待清理项: 共 {len(to_delete_fids)} 个目录/项目")

    if not args.execute:
        print("\n💡 当前处于分析预览模式（--dry-run）。若确认删除，请添加 --execute 参数运行。")
        return

    print("\n🚀 开始执行批量删除清理...")
    success = delete_quark_fids(to_delete_fids)
    if success:
        print("\n✅ 去重与清理全部完成！已成功释放重复占用的网盘空间。")
    else:
        print("\n⚠ 部分项目清理时出现异常，请检查网络或重试。")


if __name__ == "__main__":
    main()
