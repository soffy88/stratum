"""向 Stratum 反馈: 某书 MD 不过 R1-R9, 请重新输出.

将失败书追加到 /home/soffy/shared/aii-to-stratum/md_rework_queue.json.
Stratum 监听此文件, 对 status=pending 的条目安排重新处理.

Usage:
  python scripts/econ_stratum_feedback.py <substrate_id> <title> <md_path> <fail_reason>
  # fail_reason: precheck输出的 FAIL:XXX 字符串

  # 也可读 stdin JSON 批量添加:
  echo '[{"id":"xxx","title":"...","md_path":"...","reason":"FAIL:..."}]' \
    | python scripts/econ_stratum_feedback.py --batch
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path

FEEDBACK_DIR = Path("/home/soffy/shared/aii-to-stratum")
QUEUE_FILE = FEEDBACK_DIR / "md_rework_queue.json"
SPEC_REF = "AII-STRATUM-MD-SPEC-001"


def _load_queue() -> dict:
    if QUEUE_FILE.exists():
        try:
            return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "doc_id": "AII-STRATUM-REWORK-QUEUE",
        "from": "AII",
        "to": "Stratum",
        "type": "md_rework_queue",
        "spec_ref": SPEC_REF,
        "description": "AII飞轮自动发现的MD质量不达标书目(R1-R9预检失败), 请Stratum重新输出",
        "items": [],
    }


def _parse_failures(reason: str) -> list[dict]:
    """把 'FAIL:R1:无章节结构; R4:跑页眉过多' 拆成结构化列表."""
    if not reason.startswith("FAIL:"):
        return [{"check": "unknown", "detail": reason}]
    body = reason[5:]
    parts = [p.strip() for p in body.split(";") if p.strip()]
    result = []
    for p in parts:
        if ":" in p:
            check, _, detail = p.partition(":")
            result.append({"check": check.strip(), "detail": detail.strip()[:200]})
        else:
            result.append({"check": "precheck", "detail": p[:200]})
    return result


def add_entry(substrate_id: str, title: str, md_path: str, reason: str) -> None:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    queue = _load_queue()

    # 去重: 同 substrate_id 只保留最新
    queue["items"] = [x for x in queue["items"] if x.get("substrate_id") != substrate_id]
    queue["items"].append({
        "substrate_id": substrate_id,
        "file": Path(md_path).name,
        "title": title[:200],
        "failures": _parse_failures(reason),
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "spec_ref": SPEC_REF,
    })
    queue["last_updated"] = datetime.now(timezone.utc).isoformat()
    queue["pending_count"] = sum(1 for x in queue["items"] if x.get("status") == "pending")

    QUEUE_FILE.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已反馈 Stratum → {QUEUE_FILE} (pending={queue['pending_count']})")


def main():
    if "--batch" in sys.argv:
        data = json.loads(sys.stdin.read())
        for item in data:
            add_entry(item["id"], item["title"], item.get("md_path", ""), item.get("reason", ""))
        return

    if len(sys.argv) < 5:
        print("Usage: econ_stratum_feedback.py <substrate_id> <title> <md_path> <fail_reason>",
              file=sys.stderr)
        sys.exit(1)

    _, substrate_id, title, md_path, reason = sys.argv[:5]
    add_entry(substrate_id, title, md_path, reason)


if __name__ == "__main__":
    main()
