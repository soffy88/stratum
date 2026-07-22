#!/usr/bin/env python3
"""PERSON-INTAKE：抽取候选人物机械四查 → 正式注册表（PERSON-INTAKE-PROTOCOL.md）。

四查：(a) 名在 source_para_ulid 段实存 (b) 泛称/单字黑名单无氏不入 (c) 撞名→candidate-same 不自动并
(d) intake 批次号可回滚。--apply 写 seeds/persons.json；--rollback <batch> 移除整批。

用法：python3 tools/history/person_intake.py [--apply] [--rollback W-H1a-4-001]
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "docs" / "history"
BATCH = "W-H1a-4-001"
CAND = ROOT / "extract" / "W-H1a-3-arc-candidates.json"
PERSONS = ROOT / "seeds" / "persons.json"

# (b) 黑名单：官爵/泛称单字 + 势力国名 + 泛称词
BLACK_SINGLE = set(
    "公侯君王師师子伯臣民人氏卿大夫士帝后妃女男父母兄弟晉楚齊秦鄭宋衛陳蔡曹魯燕韓趙魏吳越邾莒杞滕薛戎狄夷蠻周天巴虞虢邢曲沃郑晋齐"
)
# X師/X师/X人（军队/民众，非人物）后缀拒
BLACK_SUFFIX = "師师"


def is_generic(nm):
    if len(nm) == 1 or nm in BLACK_WORD or all(ch in BLACK_SINGLE for ch in nm):
        return True
    if len(nm) <= 3 and nm[-1] in BLACK_SUFFIX:  # 巴師/秦師=军队
        return True
    if len(nm) == 2 and nm[-1] == "人" and nm[0] in BLACK_SINGLE:  # 邾人/戎人=民众
        return True
    return False


BLACK_WORD = {
    "大夫",
    "諸侯",
    "國人",
    "群臣",
    "左右",
    "太子",
    "夫人",
    "君子",
    "小人",
    "百姓",
    "先君",
    "寡人",
    "使者",
    "將軍",
    "士卒",
    "二三子",
    "公子",
    "公孫",
    "王子",
}


def corpus_para_index():
    idx = {}
    for cf in sorted((ROOT / "corpus").glob("*.json")):
        d = json.loads(cf.read_text(encoding="utf-8"))
        for p in d["paragraphs"]:
            idx[p["para_ulid"]] = p["text"]
    return idx


def existing_names():
    pj = json.loads(PERSONS.read_text(encoding="utf-8"))
    lst = pj["persons"] if isinstance(pj, dict) else pj
    names = {}
    for e in lst:
        for nm in e.get("names_by_source", {}):
            names[nm] = e["person_id"]
    return pj, lst, names


def rollback(batch):
    pj, lst, _ = existing_names()
    keep = [e for e in lst if (e.get("intake") or {}).get("batch") != batch]
    removed = len(lst) - len(keep)
    if isinstance(pj, dict):
        pj["persons"] = keep
    else:
        pj = keep
    PERSONS.write_text(json.dumps(pj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"rollback {batch}: 移除 {removed} 条")


def main():
    if "--rollback" in sys.argv:
        rollback(sys.argv[sys.argv.index("--rollback") + 1])
        return
    apply = "--apply" in sys.argv
    idx = corpus_para_index()
    pj, lst, existing = existing_names()

    cand = json.loads(CAND.read_text(encoding="utf-8"))
    # (name → source_para_ulid) 首次出现
    pairs = {}
    for c in cand["candidates"]:
        pu = c["source_para_ulid"]
        for nm in c["registry_resolution"]["persons_candidate"]:
            pairs.setdefault(nm, pu)

    passed, rejected, same = [], [], []
    for nm, pu in pairs.items():
        # (b) 黑名单
        if is_generic(nm):
            rejected.append((nm, "b:泛称/单字/国名无氏"))
            continue
        # (a) 实存
        seg = idx.get(pu, "")
        if nm not in seg:
            # opencc 简繁：候选是简体, 段是繁体 → 转繁再查
            try:
                from opencc import OpenCC

                if OpenCC("s2t").convert(nm) not in seg:
                    rejected.append((nm, "a:名不在所引段(幻觉)"))
                    continue
            except Exception:
                rejected.append((nm, "a:名不在所引段(幻觉)"))
                continue
        # (c) 撞名
        hit = existing.get(nm)
        if hit:
            same.append((nm, hit))
            continue
        passed.append((nm, pu))

    # 入库
    start = len(lst) + 1
    new_entries = []
    for i, (nm, pu) in enumerate(passed):
        new_entries.append(
            {
                "person_id": f"per:i4-{i + 1:03d}",
                "names_by_source": {nm: ["src:zuozhuan"]},
                "谥字号": "(候选·待考)",
                "active_range": "(候选)",
                "force_affiliations": [],
                "intake": {
                    "batch": BATCH,
                    "source_para_ulid": pu,
                    "method": "qwen3-8b 抽取候选·机械四查过",
                    "status": "candidate-verified",
                },
            }
        )
    if apply and new_entries:
        lst.extend(new_entries)
        if isinstance(pj, dict):
            pj["persons"] = lst
        else:
            pj = lst
        PERSONS.write_text(json.dumps(pj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"候选唯一 {len(pairs)} → PASS {len(passed)} / REJECT {len(rejected)} / CANDIDATE-SAME {len(same)}"
    )
    print("\n--- CANDIDATE-SAME（全部·候裁，不自动并）---")
    for nm, pid in same:
        print(f"  {nm}  ⟷  {pid}")
    print("\n--- PASS 抽样 15（送裁）---")
    for nm, pu in passed[:15]:
        print(f"  {nm}  ({pu})")
    print(f"\n--- REJECT 抽样 10 ---")
    for nm, r in rejected[:10]:
        print(f"  {nm}  [{r}]")
    if apply:
        print(f"\n★已入库 {len(new_entries)} 条 (batch {BATCH}, 可 --rollback)")


if __name__ == "__main__":
    main()
