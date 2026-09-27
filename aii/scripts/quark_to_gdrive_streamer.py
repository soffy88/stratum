#!/usr/bin/env python3
"""夸克网盘 → Google Drive 零磁盘直连流式传输与自动减负工具。

使用 rclone copyurl --header-download 直接从夸克 CDN 流式写入 GDrive，
不消耗任何本地临时磁盘空间。文件在 GDrive 上传校验成功后，
立即调用夸克删除接口删除云端原文件，实现边转存边释放夸克网盘空间。

目标：
1. 【纪录片】BBC纪录片78部合集 (500 文件，974.30 GB) -> gdrive:aii-media/BBC纪录片78部合集/
2. 中小学教辅/考研/外语教育 (77,445 文件，1781.44 GB) -> gdrive:aii-edu/中小学教辅与外语教育/
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
STATE_FILE = PIPE / "quark_transfer_2_4_state.json"
LOG_FILE = PIPE / "quark_transfer_2_4.log"
BBC_TARGETS = PIPE / "bbc_targets.json"
EDU_TARGETS = PIPE / "edu_targets.json"
BILI_TARGETS = PIPE / "bilibili_targets.json"

API = "https://drive.quark.cn"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 "
    "Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch"
)


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


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
    import ssl
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
    with opener.open(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"transferred_fids": [], "deleted_fids": [], "total_bytes_transferred": 0}


def save_state(state: dict):
    try:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(STATE_FILE)
    except Exception as e:
        log(f"  ⚠ 保存状态文件异常: {e}")
        try:
            backup = Path("/tmp/quark_transfer_2_4_state.json")
            backup.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


def get_download_url(fid: str) -> str | None:
    try:
        res = _req(f"{API}/1/clouddrive/file/download?pr=ucpro&fr=pc&uc_param_str=", "POST", {"fids": [fid]})
        items = res.get("data", [])
        if items and items[0].get("download_url"):
            return items[0]["download_url"]
    except Exception as e:
        log(f"  ⚠ 获取下载链接失败 (fid={fid}): {e}")
    return None


def delete_quark_file(fid: str) -> bool:
    try:
        url = f"{API}/1/clouddrive/file/delete?pr=ucpro&fr=pc&uc_param_str="
        body = {"action_type": 2, "filelist": [fid], "exclude_fids": []}
        res = _req(url, "POST", body)
        return res.get("status") == 200
    except Exception as e:
        log(f"  ⚠ 删除原文件失败 (fid={fid}): {e}")
        return False


def get_quark_used_tb() -> float | None:
    try:
        cmd = ["/home/soffy/.local/bin/quark-drive", "get-user-info"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            used = data.get("data", {}).get("vipInfo", {}).get("used", 0)
            return used / (1024**4)
    except Exception:
        pass
    return None


def stream_to_gdrive(
    fid: str,
    remote_dest_path: str,
    expected_size: int,
    chunk_size: int = 8 * 1024 * 1024,
    concurrency: int = 6
) -> bool:
    """使用 multi-range chunking 多线程拉取 + rclone rcat 零磁盘流式写入 GDrive"""
    if expected_size <= 0:
        dl_url = get_download_url(fid)
        if not dl_url:
            return False
        cmd = [
            "rclone", "copyurl",
            "--header-download", f"Cookie: {_cookie()}",
            "--header-download", f"User-Agent: {UA}",
            "--header-download", "Referer: https://pan.quark.cn/",
            dl_url,
            remote_dest_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return res.returncode == 0

    num_chunks = (expected_size + chunk_size - 1) // chunk_size

    for attempt in range(1, 4):
        dl_url = get_download_url(fid)
        if not dl_url:
            log(f"  ⚠ 尝试 {attempt}: 获取下载链接失败，重试中...")
            time.sleep(2)
            continue

        proc = None
        try:
            rcat_cmd = ["rclone", "rcat", "--size", str(expected_size), remote_dest_path]
            proc = subprocess.Popen(
                rcat_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

            def fetch_chunk(idx):
                start = idx * chunk_size
                end = min(expected_size - 1, start + chunk_size - 1)
                creq = urllib.request.Request(
                    dl_url,
                    headers={
                        "User-Agent": UA,
                        "Referer": "https://pan.quark.cn/",
                        "Range": f"bytes={start}-{end}",
                        "Cookie": _cookie(),
                    }
                )
                for sub_retry in range(3):
                    try:
                        with opener.open(creq, timeout=45) as resp:
                            return idx, resp.read()
                    except Exception:
                        if sub_retry == 2:
                            raise
                        time.sleep(1)

            from concurrent.futures import ThreadPoolExecutor, as_completed

            # 采用滑动窗口调度，保证最多 concurrency + 2 个 chunk 在内存中，内存占用 <= 64MB
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                submitted = 0
                in_flight = {}
                buffered_results = {}
                next_to_write = 0

                while submitted < num_chunks and len(in_flight) < concurrency + 2:
                    fut = executor.submit(fetch_chunk, submitted)
                    in_flight[fut] = submitted
                    submitted += 1

                while in_flight:
                    done_futs = []
                    for fut in as_completed(list(in_flight.keys())):
                        c_idx, data = fut.result()
                        buffered_results[c_idx] = data
                        done_futs.append(fut)
                        break

                    for df in done_futs:
                        del in_flight[df]

                    while next_to_write in buffered_results:
                        proc.stdin.write(buffered_results.pop(next_to_write))
                        next_to_write += 1

                    while submitted < num_chunks and len(in_flight) < concurrency + 2:
                        fut = executor.submit(fetch_chunk, submitted)
                        in_flight[fut] = submitted
                        submitted += 1

                proc.stdin.flush()
                proc.stdin.close()
                stdout, stderr = proc.communicate(timeout=120)

                if proc.returncode == 0:
                    chk = subprocess.run(
                        ["rclone", "size", "--json", remote_dest_path],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if chk.returncode == 0:
                        info = json.loads(chk.stdout)
                        if info.get("bytes", 0) >= expected_size:
                            return True
                        log(f"  ⚠ 校验大小不匹配: 期望 {expected_size}, 实际 {info.get('bytes', 0)}")
                else:
                    log(f"  ⚠ rcat 退出码异常 ({proc.returncode}): {stderr.decode('utf-8', errors='ignore')[:150]}")
        except Exception as e:
            log(f"  ⚠ 流式传输尝试 {attempt} 异常: {e}")
        finally:
            if proc:
                for pipe in (proc.stdin, proc.stdout, proc.stderr):
                    if pipe and not pipe.closed:
                        try:
                            pipe.close()
                        except Exception:
                            pass
                if proc.poll() is None:
                    try:
                        proc.kill()
                        proc.wait(timeout=2)
                    except Exception:
                        pass
        time.sleep(3)

    return False



def main():
    parser = argparse.ArgumentParser(description="夸克网盘 BBC与教辅 零磁盘流式迁移至 GDrive")
    parser.add_argument("--limit", type=int, default=0, help="最多传输文件数量 (0 表示全部)")
    parser.add_argument("--target-freed-gb", type=float, default=0.0, help="释放达到指定 GB 后停止 (0 表示不限)")
    args = parser.parse_args()

    log("════════════════════════════════════════════════════")
    log(" 夸克网盘 [2.BBC纪录片] & [4.教辅与外语] 流式转移任务启动")
    log("════════════════════════════════════════════════════")

    state = load_state()
    done_fids = set(state.get("transferred_fids", []))
    deleted_fids = set(state.get("deleted_fids", []))
    log(f"📌 历史已转存文件数: {len(done_fids)}, 已删除原文件数: {len(deleted_fids)}")

    # 1. 加载目标列表
    all_targets = []
    if False and BBC_TARGETS.exists():
        bbc_list = json.loads(BBC_TARGETS.read_text(encoding="utf-8"))
        all_targets.extend(bbc_list)
        log(f"  ✓ 成功载入 BBC纪录片 目标: {len(bbc_list)} 个文件")
    
    if False and EDU_TARGETS.exists():
        edu_list = json.loads(EDU_TARGETS.read_text(encoding="utf-8"))
        all_targets.extend(edu_list)
        log(f"  ✓ 成功载入 教辅与外语 目标: {len(edu_list)} 个文件")

    if BILI_TARGETS.exists():
        bili_list = json.loads(BILI_TARGETS.read_text(encoding="utf-8"))
        all_targets.extend(bili_list)
        log(f"  ✓ 成功载入 B站付费课程 目标: {len(bili_list)} 个文件")

    # 去重
    seen_fids = set()
    unique_targets = []
    for it in all_targets:
        if it["fid"] not in seen_fids:
            seen_fids.add(it["fid"])
            unique_targets.append(it)

    # 过滤掉已完全处理好的文件
    pending_files = [x for x in unique_targets if x["fid"] not in deleted_fids]
    pending_bytes = sum(x.get("size", 0) for x in pending_files)
    
    log(f"\n📊 汇总待传输规模:")
    log(f"  • 总目标文件数: {len(unique_targets)} 个")
    log(f"  • 待流式处理: {len(pending_files)} 个")
    log(f"  • 待释放总空间: {pending_bytes / (1024**3):.2f} GB ({pending_bytes / (1024**4):.2f} TB)")

    # 按文件由大到小排序流式推送，尽快将网盘总占用打入 6T 以下安全线！
    pending_files.sort(key=lambda x: x.get("size", 0), reverse=True)

    if args.limit > 0:
        pending_files = pending_files[:args.limit]
        log(f"  * 已应用单次上限限制: 仅传输前 {args.limit} 个大文件")

    log("\n🚀 正在开始全自动流式传输并实时删除释放夸克空间...")

    success_count = 0
    fail_count = 0
    bytes_in_session = 0

    for idx, item in enumerate(pending_files, 1):
        fid = item["fid"]
        fname = item.get("file_name", "")
        fsize = item.get("size", 0)
        remote_dest = item["remote_path"]
        fsize_mb = fsize / (1024 * 1024)
        fsize_gb = fsize / (1024**3)

        # 如果之前已上传到 GDrive 但未成功删除夸克原件
        if fid in done_fids and fid not in deleted_fids:
            log(f"[{idx}/{len(pending_files)}] [补偿删除] {fname} ({fsize_mb:.1f} MB) 已在 GDrive，正在补删夸克端原文件...")
            if delete_quark_file(fid):
                deleted_fids.add(fid)
                state["deleted_fids"].append(fid)
                bytes_in_session += fsize
                save_state(state)
                log(f"  🎉 夸克原文件已补删成功！")
            continue

        log(f"[{idx}/{len(pending_files)}] 📥 开始流式推送: {fname} ({fsize_gb:.2f} GB) -> {remote_dest}")

        t0 = time.time()
        ok = stream_to_gdrive(fid, remote_dest, fsize)
        dur = max(0.1, time.time() - t0)
        speed = fsize_mb / dur
        if ok:
            log(f"  ✓ GDrive 上传校验通过！耗时 {dur:.1f}s (均速 {speed:.2f} MB/s)，正在删除夸克端原文件以释放空间...")
            del_ok = delete_quark_file(fid)
            if del_ok:
                log(f"  🎉 夸克原文件已删除，即时释放 {fsize_gb:.2f} GB 空间！")
                deleted_fids.add(fid)
                state["deleted_fids"].append(fid)
            else:
                log(f"  ⚠ 夸克删除接口返回非成功，记录稍后统一重试")

            done_fids.add(fid)
            state["transferred_fids"].append(fid)
            state["total_bytes_transferred"] += fsize
            bytes_in_session += fsize
            save_state(state)
            success_count += 1
        else:
            log(f"  ❌ 流式传输失败: {fname}")
            fail_count += 1

        # 动态汇报累计进度与网盘容量
        if success_count > 0:
            current_tb = get_quark_used_tb()
            if False: # current_tb and current_tb <= 6.000:
                freed_session_gb = bytes_in_session / (1024**3)
                log(f"🎉 夸克网盘当前占用已降至 {current_tb:.3f} TB，已达标 (< 6.0 TB 安全线)！本次累计释放 {freed_session_gb:.2f} GB。")
                break
            if success_count % 5 == 0:
                freed_session_gb = bytes_in_session / (1024**3)
                tb_str = f"，当前网盘实际占用: {current_tb:.3f} TB" if current_tb else ""
                log(f"📈 [阶段进度] 已成功迁移 {success_count} 项，本次累计释放 {freed_session_gb:.2f} GB{tb_str}")

        if args.target_freed_gb > 0 and (bytes_in_session / (1024**3)) >= args.target_freed_gb:
            log(f"🎯 已达成目标释放量 ({args.target_freed_gb:.1f} GB)，自动暂停。")
            break

    total_freed_gb = bytes_in_session / (1024**3)
    final_tb = get_quark_used_tb()
    tb_str = f"，网盘当前占用: {final_tb:.3f} TB" if final_tb else ""
    log("\n════════════════════════════════════════════════════")
    log(f"🏁 本轮迁移结束: 成功 {success_count} 项, 失败 {fail_count} 项, 累计释放 {total_freed_gb:.2f} GB{tb_str}")
    log("════════════════════════════════════════════════════")


if __name__ == "__main__":
    main()
