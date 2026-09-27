#!/usr/bin/env python3
"""Validate SLO configuration or evaluate a measured report."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from stratum.services.slo import SLOTarget, evaluate, release_allowed


def load_config(path: Path) -> list[SLOTarget]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("SLO config must be a JSON object")
    raw_targets = data.get("targets")
    if not isinstance(raw_targets, list):
        raise ValueError("SLO config targets must be an array")
    targets: list[SLOTarget] = []
    seen_names: set[str] = set()
    for index, item in enumerate(raw_targets):
        if not isinstance(item, dict):
            raise ValueError(f"SLO target[{index}] must be an object")
        name = item.get("name")
        metric = item.get("metric")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"SLO target[{index}].name must be a non-empty string")
        if name in seen_names:
            raise ValueError(f"SLO target name is duplicated: {name}")
        seen_names.add(name)
        if not isinstance(metric, str) or not metric.strip():
            raise ValueError(f"SLO target[{index}].metric must be a non-empty string")
        try:
            threshold = float(item["threshold"])
            objective = float(item["objective"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"SLO target[{index}] threshold/objective must be numeric") from exc
        if not math.isfinite(threshold) or threshold < 0.0:
            raise ValueError(f"SLO target[{index}].threshold must be finite and non-negative")
        if not math.isfinite(objective) or not 0.0 <= objective <= 1.0:
            raise ValueError(f"SLO target[{index}].objective must be finite and in [0,1]")
        targets.append(
            SLOTarget(name=name, metric=metric, threshold=threshold, objective=objective)
        )
    if not targets:
        raise ValueError("SLO config has no targets")
    return targets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="docs/slo_targets.json")
    parser.add_argument("--report")
    args = parser.parse_args()
    try:
        targets = load_config(Path(args.config))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"SLO contract FAILED: {exc}")
        return 1
    if not args.report:
        print(f"SLO contract OK: {len(targets)} target(s)")
        return 0
    try:
        report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"SLO report FAILED: {exc}")
        return 1
    if not isinstance(report, dict):
        print("SLO report FAILED: report must be a JSON object")
        return 1
    results = []
    for target in targets:
        value = report.get(target.name)
        try:
            ratio = float(value)
        except (TypeError, ValueError):
            print(f"SLO report FAILED: missing or non-numeric value for {target.name}")
            return 1
        if not math.isfinite(ratio):
            print(f"SLO report FAILED: non-finite value for {target.name}")
            return 1
        try:
            results.append(evaluate(target, ratio))
        except ValueError as exc:
            print(f"SLO report FAILED: {target.name}: {exc}")
            return 1
    for result in results:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    if release_allowed(results):
        print("SLO gate: ALLOW")
        return 0
    print("SLO gate: FREEZE non-emergency release")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
