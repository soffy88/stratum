"""690 本存量全检: 逐本按 AII-STRATUM-MD-SPEC R1-R9 自检, 分类合格/不合格,
不合格批量写 rework 清单到 aii-to-stratum/md_rework_batch.json (Stratum 统一返工)."""
import json, os, re, sys
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, "scripts")
from run_first3 import strip_frontmatter
from aii.service.md_quality_check import check_md_quality

SRC = Path("/home/soffy/shared/stratum-to-aii")
OUT = Path("/home/soffy/shared/aii-to-stratum/md_rework_batch.json")

def main():
    mds = sorted(SRC.glob("*.md"))
    total=len(mds); passed=[]; failed=[]; no_sidecar=0; by_reason=Counter(); by_medium_fail=Counter(); by_medium_all=Counter()
    for md in mds:
        sc = md.with_suffix(".json")
        if not sc.exists():
            no_sidecar+=1; continue
        try:
            meta=json.loads(sc.read_text(encoding="utf-8"))
        except Exception:
            no_sidecar+=1; continue
        medium=(meta.get("medium") or "").lower()
        title=meta.get("title", md.stem); sid=meta.get("id","")
        by_medium_all[medium or "?"]+=1
        try:
            text=strip_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        q=check_md_quality(text, medium=medium, title=title)
        if q["ok"]:
            passed.append({"id":sid,"file":md.name,"medium":medium,"title":title[:60]})
        else:
            for f in q["hard_failures"]: by_reason[f["check"]]+=1
            by_medium_fail[medium or "?"]+=1
            failed.append({"id":sid,"file":md.name,"medium":medium,"title":title[:70],
                "hard_failures":[{"check":f["check"],"detail":f["detail"]} for f in q["hard_failures"]],
                "advisories":[a["check"] for a in q["advisories"]],
                "metrics":q["metrics"]})
    batch={"generated_at":datetime.now(timezone.utc).isoformat(),
           "spec":"AII-STRATUM-MD-SPEC-001",
           "summary":{"total_md":total,"with_sidecar":total-no_sidecar,"no_sidecar":no_sidecar,
                      "passed":len(passed),"failed":len(failed),
                      "fail_reason_distribution":dict(by_reason),
                      "fail_by_medium":dict(by_medium_fail),"all_by_medium":dict(by_medium_all)},
           "required_redelivery":"不合格 book 按 R1-R9 统一重新输出(章节规范标题/TOC分离/锚点/OCR结构恢复+剔页眉/公式LaTeX/图占位caption/表格列对齐)",
           "failed_books":failed}
    OUT.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
    s=batch["summary"]
    print(f"TOTAL md={s['total_md']}  with_sidecar={s['with_sidecar']}  no_sidecar={s['no_sidecar']}")
    print(f"PASS={s['passed']}  FAIL={s['failed']}")
    print(f"fail reasons: {s['fail_reason_distribution']}")
    print(f"fail by medium: {s['fail_by_medium']}")
    print(f"all by medium: {s['all_by_medium']}")
    print(f"wrote {OUT}")
main()
