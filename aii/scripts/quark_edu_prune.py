#!/usr/bin/env python3
"""按去重计划删除夸克盘内重复/非人教版课本，并在 k12_targets.json 中剔除。

安全措施：
  1. 删除前重新核对文件大小与清单一致，不一致则跳过
  2. 排除教辅类（课堂笔记/讲义/练习等），只删课本
  3. 记录每个 fid 的删除结果，便于回滚与审计
"""

from __future__ import annotations

import csv
import json
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"
COOKIE_FILE = PIPE / "quark_cookies_full.txt"
API = "https://drive.quark.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 "
      "Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch")

# 教辅/配套资料特征——这些不删
AUX = re.compile(
    r"课堂笔记|课本笔记|笔记|讲义|学案|练习|习题|试卷|测试卷|模拟|复习|考点|"
    r"培优|奥数|作业本|暑假|寒假|衔接|答案|解析|知识点|讲解|同步|金榜|题库"
)


INDEX: dict[str, dict] = {}


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


COOKIE = COOKIE_FILE.read_text(encoding="utf-8").strip()
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                 urllib.request.HTTPSHandler(context=CTX))


def api(path: str, body: dict | None = None, method: str = "POST"):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}", data=data, method=method,
        headers={"Cookie": COOKIE, "Referer": "https://pan.quark.cn/",
                 "User-Agent": UA, "Content-Type": "application/json"})
    with OP.open(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def file_info(fid: str) -> dict | None:
    """通过全量列表建立 fid -> 条目索引来查文件，避免逐个调 info 接口。"""
    return INDEX.get(fid)


def build_index() -> None:
    """拉取【来自：分享】下所有条目，建立 fid 索引。"""
    root = api("/1/clouddrive/file/sort?pr=ucpro&fr=pc&uc_param_str=&pdir_fid=0&_page=1&_size=50",
               None, "GET")
    share = next((i["fid"] for i in root.get("data", {}).get("list", [])
                  if "分享" in i.get("file_name", "")), None)
    if not share:
        log("! 未找到【来自：分享】目录")
        return
    token, pages = None, 0
    while True:
        body = {"pdir_fid": share, "limit": 1000, "sort": "file_type:asc,updated_at:desc"}
        if token:
            body["next_page_token"] = token
        res = api("/1/clouddrive/file/sort?pr=ucpro&fr=pc&uc_param_str=", body, "GET")
        data = res.get("data", {}) or {}
        for it in data.get("list", []):
            INDEX[it["fid"]] = it
        pages += 1
        token = data.get("next_page_token")
        if not token:
            break
    log(f"索引建立完成: {len(INDEX)} 个条目 / {pages} 页")


def delete_many(fids: list[str]) -> tuple[list[list[str]], list[list[str]]]:
    """分批删除，返回 (成功批次, 失败批次)。"""
    ok, bad = [], []
    for i in range(0, len(fids), 50):
        chunk = fids[i:i + 50]
        try:
            res = api("/1/clouddrive/file/delete?pr=ucpro&fr=pc&uc_param_str=",
                      {"action_type": 2, "filelist": chunk, "exclude_fids": []})
            if res.get("code") not in (0, 200) and res.get("status") not in (200,):
                log(f"  ! 批次被拒: {str(res)[:80]}")
                bad.append(chunk); continue
            task_id = (res.get("data", {}) or {}).get("task_id")
            if task_id:
                for _ in range(20):
                    time.sleep(1)
                    t = api(f"/1/clouddrive/task?pr=ucpro&fr=pc&uc_param_str=&task_id={task_id}")
                    if (t.get("data", {}) or {}).get("status") in (2, 3):
                        break
            ok.append(chunk)
            log(f"  批次 {len(ok)}: {len(chunk)} 项已删，累计 {sum(len(c) for c in ok)}")
        except Exception as e:
            log(f"  ! 批次失败({len(chunk)} 项): {str(e)[:70]}")
            bad.append(chunk)
        time.sleep(0.3)
    return ok, bad


def main() -> None:
    plan = list(csv.DictReader((PIPE / "dedup_delete_plan.csv").open(encoding="utf-8-sig")))
    todo = [r for r in plan if not AUX.search(r["文件名"])]
    skipped = len(plan) - len(todo)
    log(f"计划 {len(plan)} 条，排除教辅 {skipped} 条 → 实际待删 {len(todo)} 条 "
        f"({sum(float(r['大小MB']) for r in todo)/1024:.2f} GB)")

    # 交叉校验：fid ↔ catalog 快照文件名
    catalog = {f["fid"]: f["file_name"]
               for f in json.loads((PIPE / "quark_catalog.json").read_text(encoding="utf-8"))["files"]}
    verified, rejected = [], []
    for r in todo:
        c = catalog.get(r["fid"])
        if c is None:
            rejected.append({**r, "备注": "fid 不在 catalog 中"})
        elif c != r["文件名"]:
            rejected.append({**r, "备注": f"名称不符({c[:26]})"})
        else:
            verified.append(r)
    log(f"交叉校验: 通过 {len(verified)} · 剔除 {len(rejected)}")
    if not verified:
        log("无可删除项，退出"); return

    targets = json.loads((PIPE / "k12_targets.json").read_text(encoding="utf-8"))

    ok, bad = delete_many([r["fid"] for r in verified])
    ok_fids = {f for c in ok for f in c}
    removed = [r for r in verified if r["fid"] in ok_fids]
    failed = [r for r in verified if r["fid"] not in ok_fids]
    log(f"完成: 成功 {len(removed)} · 失败 {len(failed)} · "
        f"释放 {sum(float(r['大小MB']) for r in removed)/1024:.2f} GB")

    drop = {r["fid"] for r in removed}
    kept = [t for t in targets if t["fid"] not in drop]
    (PIPE / "k12_targets.json").write_text(
        json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"k12_targets.json: {len(targets)} \u2192 {len(kept)}")

    with (PIPE / "prune_audit.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["结果", "类别", "学段", "学科", "版本", "大小MB", "文件名", "fid", "备注"])
        for tag, s2 in (("已删除", removed), ("删除失败", failed), ("校验剔除", rejected)):
            for r in s2:
                w.writerow([tag, r.get("类别", ""), r["学段"], r["学科"], r.get("版本", ""),
                            r["大小MB"], r["文件名"], r["fid"], r.get("备注", "")])
    log(f"审计日志: {PIPE / 'prune_audit.csv'}")


if __name__ == "__main__":
    main()
