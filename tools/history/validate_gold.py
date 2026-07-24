#!/usr/bin/env python3
"""W-H0 gold fixtures 校验 harness（D-015 校验尺子）。

校验四件事，任一失败 exit 1：
  1. contracts/sample.sanjiafenjin.json 对契约 schema 原样 validate（README 冻结命令等价，无预处理）。
  2. fixtures/F*.json 逐个对 gold-bundle.schema.json validate（内层 $ref 契约 $defs）。
  3. 注册表引用零悬空：fixture 内所有 src:/per:/pl:/fo:/chr: 引用必须能在 seeds/ 解析。
     （⚠ fo: 前缀曾被临时脚本写成 frc: 而漏测——F10 的 force 引用当时根本没被验过。
       本 harness 的前缀表从 seeds 实际 id 归纳，不再手拍。）
  4. 束内引用闭合：event.accounts/conflicts 与 mainline_account_ref 指向的 ac:/cf: 必须在束内定义；
     account.event_ref 反向亦然。零下划线前缀键红线一并查。

用法：python3 tools/history/validate_gold.py   （仓库任意位置均可）
"""

import json
import re
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
except ImportError:  # jsonschema<4.18 无 referencing
    sys.exit("需要 jsonschema>=4.18（含 referencing）。pip install -U jsonschema")

ROOT = Path(__file__).resolve().parents[2] / "docs" / "history"
CONTRACT = ROOT / "contracts" / "history-query-response.schema.json"
BUNDLE = ROOT / "fixtures" / "gold-bundle.schema.json"
SAMPLE = ROOT / "contracts" / "sample.sanjiafenjin.json"

REF_PREFIXES = ("src", "per", "pl", "fo", "chr")  # seeds 注册表前缀（见模块 docstring 第 3 条）
REF_RE = re.compile(r'"((?:%s):[a-z0-9-]+)"' % "|".join(REF_PREFIXES))


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def registry_ids() -> set:
    ids = set()

    def collect(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.endswith("_id") and isinstance(v, str):
                    ids.add(v)
                collect(v)
        elif isinstance(o, list):
            for v in o:
                collect(v)

    for sf in sorted((ROOT / "seeds").glob("*.json")):
        collect(load(sf))
    return ids


def underscore_keys(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if k.startswith("_"):
                yield f"{path}/{k}"
            yield from underscore_keys(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from underscore_keys(v, f"{path}[{i}]")


def main() -> int:
    contract = load(CONTRACT)
    bundle = load(BUNDLE)
    registry = Registry().with_resources(
        [(s["$id"], Resource.from_contents(s)) for s in (contract, bundle)]
    )
    contract_v = Draft202012Validator(contract, registry=registry)
    bundle_v = Draft202012Validator(bundle, registry=registry)

    failures = []

    # 1. 契约 sample（冻结命令等价）
    errs = list(contract_v.iter_errors(load(SAMPLE)))
    print(f"sample vs contract: {'VALID' if not errs else f'{len(errs)} errors'}")
    failures += [f"sample: {e.message}" for e in errs]

    # 2–4. fixtures
    seed_ids = registry_ids()
    fixtures = sorted((ROOT / "fixtures").glob("F*.json"))
    if not fixtures:
        failures.append("未找到任何 fixtures/F*.json")
    for f in fixtures:
        d = load(f)
        problems = [f"schema: {e.json_path} {e.message}" for e in bundle_v.iter_errors(d)]

        dangling = {r for r in REF_RE.findall(f.read_text(encoding="utf-8")) if r not in seed_ids}
        if dangling:
            problems.append(f"悬空注册表引用: {sorted(dangling)}")

        ev_ids = {e.get("event_id") for e in d.get("events", [])}
        ac_ids = {a.get("account_id") for a in d.get("accounts", [])}
        cf_ids = {c.get("conflict_id") for c in d.get("conflicts", [])}
        for e in d.get("events", []):
            missing = [r for r in e.get("accounts", []) if r not in ac_ids]
            missing += [r for r in e.get("conflicts", []) if r not in cf_ids]
            if e.get("mainline_account_ref") not in ac_ids:
                missing.append(e.get("mainline_account_ref"))
            if missing:
                problems.append(f"{e.get('event_id')} 束内引用未闭合: {missing}")
        for a in d.get("accounts", []):
            if a.get("event_ref") not in ev_ids:
                problems.append(f"{a.get('account_id')} event_ref 未闭合: {a.get('event_ref')}")

        problems += [f"下划线前缀键: {p}" for p in underscore_keys(d)]

        print(f"{f.name}: {'OK' if not problems else 'FAIL'}")
        failures += [f"{f.name}: {p}" for p in problems]

    # 5. 扩样例集（contracts/samples/**）：每文件必须过契约 schema（D-019 交付面②）
    samples = sorted((ROOT / "contracts" / "samples").glob("*/*.json"))
    for f in samples:
        d = load(f)
        problems = [f"schema: {e.json_path} {e.message}" for e in contract_v.iter_errors(d)]
        problems += [f"下划线前缀键: {p}" for p in underscore_keys(d)]
        bundle_ids = {
            e[k]
            for grp, k in [
                ("persons", "person_id"),
                ("places", "place_id"),
                ("forces", "force_id"),
                ("sources", "source_id"),
            ]
            for e in d.get("registry_bundle", {}).get(grp, [])
        }
        # 只扫响应体（event/accounts/conflicts）：body 引用须在 bundle 内闭合；
        # registry 条目自身的谱系边（derivation/succession/names_by_source）可指向未随包实体，不算悬空。
        body = json.dumps(
            {
                "event": d.get("event"),
                "accounts": d.get("accounts"),
                "conflicts": d.get("conflicts"),
            },
            ensure_ascii=False,
        )
        dangling = {r for r in REF_RE.findall(body) if r not in bundle_ids}
        if dangling:
            problems.append(f"registry_bundle 未携带的 body 引用: {sorted(dangling)}")
        print(f"samples/{f.parent.name}/{f.name}: {'OK' if not problems else 'FAIL'}")
        failures += [f"{f.name}: {p}" for p in problems]

    # 6. 语料库（corpus/*.json）：para_ulid 格式 + 零下划线（ARC-SPEC §4.2）
    import re as _re

    PARA_RE = _re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}:[0-9A-HJKMNP-TV-Z]{4,8}$")
    corpus = sorted((ROOT / "corpus").glob("*.json"))
    para_index = set()
    for f in corpus:
        d = load(f)
        problems = [f"下划线前缀键: {p}" for p in underscore_keys(d)]
        sub = d.get("substrate", {}).get("substrate_ulid", "")
        for p in d.get("paragraphs", []):
            pu = p.get("para_ulid", "")
            para_index.add(pu)
            if not PARA_RE.match(pu):
                problems.append(f"para_ulid 格式非法: {pu}")
            if not pu.startswith(sub + ":"):
                problems.append(f"para_ulid 前缀≠substrate: {pu}")
        print(f"corpus/{f.name}: {'OK' if not problems else 'FAIL'}")
        failures += [f"{f.name}: {p}" for p in problems]

    # 7. fixtures 回填的 para_ulid 必须解析到语料库（悬空即 FAIL）
    for f in fixtures:
        d = load(f)
        for a in d.get("accounts", []):
            pu = a.get("locator", {}).get("para_ulid")
            if pu and pu not in para_index:
                failures.append(f"{f.name}: 回填 para_ulid 悬空(不在语料库): {pu}")

    # 8. Arc/Thesis 束（arc/*.json vs arc-thesis.schema.json；仓内, 不进契约 D-025）
    arc_schema_path = ROOT / "arc" / "arc-thesis.schema.json"
    n_arc = 0
    if arc_schema_path.exists():
        arc_schema = load(arc_schema_path)
        arc_reg = Registry().with_resources(
            [(arc_schema["$id"], Resource.from_contents(arc_schema))]
        )
        arc_v = Draft202012Validator(arc_schema, registry=arc_reg)
        for f in sorted((ROOT / "arc").glob("*.json")):
            if f.name.endswith(".schema.json"):
                continue
            n_arc += 1
            d = load(f)
            problems = [f"schema: {e.json_path} {e.message}" for e in arc_v.iter_errors(d)]
            problems += [f"下划线前缀键: {p}" for p in underscore_keys(d)]
            # thesis 源内/后世公版 locator 若带 para_ulid, 必须解析到语料库
            for t in d.get("theses", []):
                pu = (t.get("attribution", {}).get("locator") or {}).get("para_ulid")
                if pu and pu not in para_index:
                    problems.append(f"{t.get('thesis_id')} locator para_ulid 悬空: {pu}")
            print(f"arc/{f.name}: {'OK' if not problems else 'FAIL'}")
            failures += [f"{f.name}: {p}" for p in problems]

    # 9. Arc 事件层灌注束（arc/events/*.json；OP-D-064 弧灌注）：不新造 schema，复用
    #    gold-bundle.schema.json（同 fixtures）；registry 引用零悬空 + 束内闭合同 fixtures 纪律；
    #    account.locator.para_ulid 须解析到语料库。
    events_dir = ROOT / "arc" / "events"
    event_bundles = sorted(events_dir.glob("*.json")) if events_dir.is_dir() else []
    for f in event_bundles:
        d = load(f)
        problems = [f"schema: {e.json_path} {e.message}" for e in bundle_v.iter_errors(d)]

        dangling = {r for r in REF_RE.findall(f.read_text(encoding="utf-8")) if r not in seed_ids}
        if dangling:
            problems.append(f"悬空注册表引用: {sorted(dangling)}")

        ev_ids = {e.get("event_id") for e in d.get("events", [])}
        ac_ids = {a.get("account_id") for a in d.get("accounts", [])}
        cf_ids = {c.get("conflict_id") for c in d.get("conflicts", [])}
        for e in d.get("events", []):
            missing = [r for r in e.get("accounts", []) if r not in ac_ids]
            missing += [r for r in e.get("conflicts", []) if r not in cf_ids]
            if e.get("mainline_account_ref") not in ac_ids:
                missing.append(e.get("mainline_account_ref"))
            if missing:
                problems.append(f"{e.get('event_id')} 束内引用未闭合: {missing}")
        for a in d.get("accounts", []):
            if a.get("event_ref") not in ev_ids:
                problems.append(f"{a.get('account_id')} event_ref 未闭合: {a.get('event_ref')}")
            pu = a.get("locator", {}).get("para_ulid")
            if pu and pu not in para_index:
                problems.append(f"{a.get('account_id')} locator para_ulid 悬空(不在语料库): {pu}")
        for c in d.get("conflicts", []):
            missing = [r for r in c.get("account_refs", []) if r not in ac_ids]
            if missing:
                problems.append(f"{c.get('conflict_id')} account_refs 未闭合: {missing}")

        problems += [f"下划线前缀键: {p}" for p in underscore_keys(d)]

        print(f"arc/events/{f.name}: {'OK' if not problems else 'FAIL'}")
        failures += [f"events/{f.name}: {p}" for p in problems]

    print(
        f"--- {len(fixtures)} fixtures · {len(samples)} samples · "
        f"{len(corpus)} corpus({len(para_index)} paras) · {n_arc} arc · "
        f"{len(event_bundles)} event-bundles · registry {len(seed_ids)} ids"
    )
    if failures:
        print("\n".join(failures))
        return 1
    print("ALL GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
