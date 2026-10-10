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
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"
COOKIE_FILE = PIPE / "quark_cookies_full.txt"
STATE_FILE = PIPE / "quark_transfer_2_4_state.json"
LOG_FILE = PIPE / "quark_transfer_2_4.log"
BBC_TARGETS = PIPE / "bbc_targets.json"
EDU_TARGETS = PIPE / "edu_targets.json"
BILI_TARGETS = PIPE / "bilibili_targets.json"
# K12 教育类目标（由 quark_k12_selector.py 生成，含 remote_path）
K12_TARGETS = PIPE / "k12_targets.json"
# 通过 QUARK_TARGETS 指定本次要迁移的清单（文件名，不含路径）
TARGET_SET = os.environ.get("QUARK_TARGETS", "").strip()

# ── 并发/性能调优 ──────────────────────────────────────────────
# 单文件内多分片并发数。实测（535MB 样本，夸克侧）：6→4.06MB/s, 10→7.79MB/s,
# 16→8.69MB/s（最优）, 24→3.53MB/s 且报错（触发 CDN 限流）。
CHUNK_CONCURRENCY = int(os.environ.get("QUARK_CHUNK_CONCURRENCY", "16"))
# 跨文件并发数：Google Drive 使用的是 rclone 公共 client_id，天然被限流
# （403 rateLimitExceeded）。并发越高越容易触发，实测 2 会频繁失败，
# 因此保持 1，靠分片并发（16）拉高带宽。
FILE_CONCURRENCY = int(os.environ.get("QUARK_FILE_CONCURRENCY", "1"))
# rclone 写入 Drive 失败时的重试策略（应对 403 限流）
RCLONE_RETRIES = int(os.environ.get("QUARK_RCLONE_RETRIES", "10"))
RCLONE_LOW_LEVEL_RETRIES = int(os.environ.get("QUARK_RCLONE_LL_RETRIES", "20"))

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


class SourceGone(Exception):
    """夸克端源文件已不存在（404），通常因哈希去重：同内容孪生文件被一并删除。"""


class CookieExpired(Exception):
    """夸克返回 412，Cookie（__pus token）已过期，必须停止并刷新。"""


def get_download_url(fid: str) -> str | None:
    try:
        res = _req(f"{API}/1/clouddrive/file/download?pr=ucpro&fr=pc&uc_param_str=", "POST", {"fids": [fid]})
        items = res.get("data", [])
        if items and items[0].get("download_url"):
            return items[0]["download_url"]
        # 200 但无 download_url：接口本身正常，只是该 fid 无效。
        # 只有明确的 404/410 才认定文件消失，避免会话异常被误报成文件丢失。
        code = res.get("code")
        msg = (res.get("message") or "")
        if code in (404, 410) or msg.lower().startswith(("not found", "notfound")):
            raise SourceGone(f"fid={fid} code={code}")
        log(f"  \u26a0 无download_url (fid={fid[:12]}, code={code}, msg={msg[:40]})")
    except SourceGone:
        raise
    except Exception as e:
        if getattr(e, "code", None) in (404, 410):
            raise SourceGone(f"fid={fid}") from e
        log(f"  \u26a0 获取下载链接失败 (fid={fid}): {e}")
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
    """优先用官方 member 接口查占用（use_capacity）。
    旧 quark-drive CLI 已被上游加 Agent 环境检测，稳定返回 code -104。"""
    try:
        res = _req(f"{API}/1/clouddrive/member?pr=ucpro&fr=pc&uc_param_str=", "GET")
        used = (res.get("data") or {}).get("use_capacity")
        if res.get("code") == 0 and isinstance(used, (int, float)):
            return used / (1024**4)
    except Exception:
        pass
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
    concurrency: int = CHUNK_CONCURRENCY
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
        # 源文件已消失：不再浪费重试时间，直接放弃该条目
        dl_url = get_download_url(fid)
        if not dl_url:
            log(f"  ⚠ 尝试 {attempt}: 获取下载链接失败，重试中...")
            time.sleep(2)
            continue

        proc = None
        try:
            rcat_cmd = [
                "rclone", "rcat",
                "--size", str(expected_size),
                "--retries", str(RCLONE_RETRIES),
                "--low-level-retries", str(RCLONE_LOW_LEVEL_RETRIES),
                remote_dest_path,
            ]
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
                    except Exception as e:
                        if getattr(e, "code", None) == 412:
                            raise CookieExpired("HTTP 412 Precondition Failed: Cookie likely expired. Please refresh cookie.") from e
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
                # rclone 关闭 stdin 后仍需把缓冲区的数据推完并向 Drive 提交元数据，
                # 大文件 + Drive 限流下可能远超 120s。原固定 120s 会误判为失败并
                # 重建 rcat，重复上传浪费带宽。按体积估算：假设最差 2MB/s。
                flush_timeout = max(600, int(expected_size / (2 * 1024 * 1024)) + 300)
                try:
                    stdout, stderr = proc.communicate(timeout=flush_timeout)
                except subprocess.TimeoutExpired:
                    log(f"  ⚠ rcat 收尾超时 (>{flush_timeout}s)，放弃本次尝试")
                    raise

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
                    err_txt = stderr.decode("utf-8", errors="ignore")
                    # 完整错误写入单独文件，终端只显示关键尾部
                    try:
                        with open(PIPE / "rclone_errors.log", "a", encoding="utf-8") as ef:
                            ef.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {remote_dest} rc={proc.returncode}\n{err_txt}\n")
                    except Exception:
                        pass
                    # 过滤掉无意义的 NOTICE 行，只留真正的错误
                    key_lines = [l for l in err_txt.splitlines()
                                 if l.strip() and "NOTICE:" not in l and "INFO :" not in l]
                    log(f"  ⚠ rcat 退出码异常 ({proc.returncode}): {(key_lines[-1] if key_lines else err_txt.strip())[:200]}")
        except (CookieExpired, SourceGone):
            # 致命/不可重试：直接上抛到主循环，由 stop_flag 收敛全局
            raise
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
    # QUARK_TARGETS=k12_targets.json 时只跑指定清单，避免混入 B站清单
    if TARGET_SET:
        tp = PIPE / TARGET_SET
        if tp.exists():
            sel = json.loads(tp.read_text(encoding="utf-8"))
            all_targets.extend(sel)
            log(f"  ✓ 指定清单 {TARGET_SET}: {len(sel)} 个文件")
        else:
            log(f"  ❌ 指定清单不存在: {tp}")
            sys.exit(1)

    if False and BBC_TARGETS.exists():
        bbc_list = json.loads(BBC_TARGETS.read_text(encoding="utf-8"))
        all_targets.extend(bbc_list)
        log(f"  ✓ 成功载入 BBC纪录片 目标: {len(bbc_list)} 个文件")
    
    if False and EDU_TARGETS.exists():
        edu_list = json.loads(EDU_TARGETS.read_text(encoding="utf-8"))
        all_targets.extend(edu_list)
        log(f"  ✓ 成功载入 教辅与外语 目标: {len(edu_list)} 个文件")

    if not TARGET_SET and BILI_TARGETS.exists():
        bili_list = json.loads(BILI_TARGETS.read_text(encoding="utf-8"))
        # If it's a raw catalog without remote_path, just use what we can
        all_targets.extend(bili_list)
        log(f"  ✓ 成功载入 B站付费课程 目标: {len(bili_list)} 个文件")

    # 去重
    seen_fids = set()
    unique_targets = []
    for it in all_targets:
        if it["fid"] not in seen_fids:
            seen_fids.add(it["fid"])
            unique_targets.append(it)

    # 夸克按哈希去重：同名同大小 = 同一份内容，仅需搬运一次。
    # 重复条目建立指纹映射，命中则直接跳过，避免后续 404 重试浪费。
    content_fp = {}
    dup_fids = set()
    for it in unique_targets:
        key = (it.get("file_name", ""), it.get("size", 0))
        if key in content_fp:
            dup_fids.add(it["fid"])
        else:
            content_fp[key] = it["fid"]
    if dup_fids:
        log(f"  ℹ️ 检测到 {len(dup_fids)} 个同名同大小重复条目（夸克哈希去重），已预先折叠")

    # 过滤掉已完全处理好的文件
    pending_files = [x for x in unique_targets if x["fid"] not in deleted_fids and x["fid"] not in dup_fids]
    pending_bytes = sum(x.get("size", 0) for x in pending_files)
    
    log(f"\n📊 汇总待传输规模:")
    log(f"  • 总目标文件数: {len(unique_targets)} 个")
    log(f"  • 待流式处理: {len(pending_files)} 个")
    log(f"  • 待释放总空间: {pending_bytes / (1024**3):.2f} GB ({pending_bytes / (1024**4):.2f} TB)")

    # 按文件由大到小排序流式推送，尽快将网盘总占用打入 6T 以下安全线！
    # SKIP_SIZE_SORT=1 时保留清单原有顺序（用于「先跑指定批次」场景）
    if os.environ.get("SKIP_SIZE_SORT", "").strip() != "1":
        pending_files.sort(key=lambda x: x.get("size", 0), reverse=True)

    if args.limit > 0:
        pending_files = pending_files[:args.limit]
        log(f"  * 已应用单次上限限制: 仅传输前 {args.limit} 个大文件")

    log("\n🚀 正在开始全自动流式传输并实时删除释放夸克空间...")

    success_count = 0
    fail_count = 0
    skip_count = 0
    bytes_in_session = 0
    gone_fids = set(state.get("source_gone_fids", []))
    stop_flag = threading.Event()
    counter_lock = threading.Lock()

    def dest_of(item: dict) -> str:
        """解析目标 GDrive 路径，兼容缺失 remote_path 的旧版清单"""
        if "remote_path" in item:
            return item["remote_path"]
        file_path = item.get("file_path", "")
        if file_path:
            return f"gdrive-kimia:{file_path}"
        return f"gdrive-kimia:B站付费课程/{item.get('file_name', '')}"
    def process_one(item: dict) -> str:
        """处理单个文件，返回 'success' / 'skip' / 'fail'。仅由工作线程调用。"""
        nonlocal success_count, fail_count, skip_count, bytes_in_session
        fid = item["fid"]
        fname = item.get("file_name", "")
        fsize = item.get("size", 0)
        remote_dest = dest_of(item)
        fsize_mb = fsize / (1024 * 1024)
        fsize_gb = fsize / (1024**3)

        t0 = time.time()
        try:
            ok = stream_to_gdrive(fid, remote_dest, fsize)
        except SourceGone:
            # 夸克哈希去重：同内容的孪生条目已随首个文件一并消失，属预期情况
            log(f"  ⏭ 源文件在夸克已不存在（哈希去重），跳过: {fname}")
            with counter_lock:
                gone_fids.add(fid)
                state.setdefault("source_gone_fids", []).append(fid)
                save_state(state)
                skip_count += 1
            return "skip"
        except CookieExpired as e:
            # 致命错误（412 Cookie 过期）——置位停止信号，全局尽快收敛
            log(f"  ❌ 遇到致命错误: {e}")
            stop_flag.set()
            return "fail"
        dur = max(0.1, time.time() - t0)
        speed = fsize_mb / dur

        with counter_lock:
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
            return "success" if ok else "fail"

    # ── 并发调度：多文件同时传输 ────────────────────────────────
    workers = max(1, min(FILE_CONCURRENCY, len(pending_files)))
    log(f"   并发配置: 文件并发 {workers} × 分片并发 {CHUNK_CONCURRENCY}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for item in pending_files:
            if stop_flag.is_set():
                break
            f = pool.submit(process_one, item)
            futures[f] = item

        done_n = 0
        total_n = len(futures)
        for fut in as_completed(futures):
            done_n += 1
            try:
                fut.result()
            except Exception as e:
                log(f"  ⚠ 工作线程异常: {e}")
                with counter_lock:
                    fail_count += 1

            if stop_flag.is_set():
                log("⚠ 收到停止信号，不再提交新任务，等待在途任务结束...")
                break

            # 每完成 10 个任务汇报一次进度
            if done_n % 10 == 0 or done_n == total_n:
                current_tb = get_quark_used_tb()
                freed_gb = bytes_in_session / (1024**3)
                tb_str = f"，当前网盘实际占用: {current_tb:.3f} TB" if current_tb else ""
                log(f"📈 [阶段进度] 已扫描 {done_n}/{total_n}，成功 {success_count}，跳过 {skip_count}，失败 {fail_count}，本次释放 {freed_gb:.2f} GB{tb_str}")

            if args.target_freed_gb > 0 and (bytes_in_session / (1024**3)) >= args.target_freed_gb:
                log(f"🎯 已达成目标释放量 ({args.target_freed_gb:.1f} GB)，自动暂停。")
                stop_flag.set()
                break

    if stop_flag.is_set():
        log("⚠ 任务提前终止（致命错误或达成目标），已保存状态，下次运行可从断点继续。")

    total_freed_gb = bytes_in_session / (1024**3)
    final_tb = get_quark_used_tb()
    tb_str = f"，网盘当前占用: {final_tb:.3f} TB" if final_tb else ""
    log("\n════════════════════════════════════════════════════")
    log(f"🏁 本轮迁移结束: 成功 {success_count} 项, 跳过 {skip_count} 项, 失败 {fail_count} 项, 累计释放 {total_freed_gb:.2f} GB{tb_str}")
    log("════════════════════════════════════════════════════")


if __name__ == "__main__":
    main()
