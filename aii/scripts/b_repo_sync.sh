#!/usr/bin/env bash
# A→B 仓增量同步(止血落后 + M0 + 4.5 readout)
#
# 设计对齐:
#   - B = f(A仓, 决策台账); 只 append, 幂等(已入 raw_ku_id 跳过)
#   - 命门: 宁冗余不误删 / 宁碎片不错合
#   - 默认同学科 --singletons-only 先灌入(不做并簇), 避免未过金集的自动强并
#   - 经济域可另跑不带 --singletons-only 的判同轮(词典齐全)
#
# 用法:
#   bash scripts/b_repo_sync.sh                  # 默认: econ+math+misc 单例增量 + M0 + readout
#   bash scripts/b_repo_sync.sh --dry-run        # 只报告不落库
#   bash scripts/b_repo_sync.sh --disc econ      # 只经济
#   bash scripts/b_repo_sync.sh --max-new 500    # 每学科最多 500 条新 KU
#   bash scripts/b_repo_sync.sh --with-judge     # 经济域额外跑判同并簇(费 LLM)
#   bash scripts/b_repo_sync.sh --skip-m0 --skip-readout
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DISC="all"          # all = econ then math then misc
MAX_NEW=800         # 每学科每轮上限(定时器安全阀)
DRY=""
WITH_JUDGE=0
SKIP_M0=0
SKIP_READOUT=0
READOUT_LIMIT=200
CONC=4
# ★嵌入走共享 aii-embed 微服务(已迁笔记本GPU, 禁止用本机GPU); 勿再 systemctl start 本机单元
#   (与 advmath/cs/econ 等飞轮脚本一致)
export AII_EMBED_URL="${AII_EMBED_URL:-http://100.119.113.90:8102}"
export AII_KG_URL="${AII_KG_URL:-postgresql://aii:aii_safe_pass@localhost:5435/aii_kg}"
export REFINED_URL="${REFINED_URL:-postgresql://aii:aii_safe_pass@localhost:5436/aii_refined}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY="1"; shift ;;
    --disc) DISC="$2"; shift 2 ;;
    --max-new) MAX_NEW="$2"; shift 2 ;;
    --with-judge) WITH_JUDGE=1; shift ;;
    --skip-m0) SKIP_M0=1; shift ;;
    --skip-readout) SKIP_READOUT=1; shift ;;
    --readout-limit) READOUT_LIMIT="$2"; shift 2 ;;
    --concurrency) CONC="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="uv run --project ${ROOT} python"
fi

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[b_repo_sync $(ts)] $*"; }

# embed 必须可达(落库要重算 B 仓向量); dry-run 可跳过
ensure_embed() {
  if [[ -n "$DRY" ]]; then return 0; fi
  if curl -sf --max-time 3 "${AII_EMBED_URL}/health" >/dev/null 2>&1; then
    return 0
  fi
  # embed 已迁笔记本(100.68.x), 本机无对应单元可启动 — 直接报错等人工/自愈
  log "ERROR: aii-embed(${AII_EMBED_URL}) 不可达 — 检查笔记本WSL的 aii-embed.service 与 tailscale"
  return 1
}

run_orch() {
  local disc="$1"
  local extra=("--singletons-only" "--disc" "$disc" "--max-new" "$MAX_NEW" "--concurrency" "$CONC")
  if [[ -z "$DRY" ]]; then extra+=(--apply); fi
  log "orchestrate disc=${disc} max-new=${MAX_NEW} dry=${DRY:-0}"
  # shellcheck disable=SC2086
  $PY scripts/dedup/orchestrate.py "${extra[@]}"
}

run_judge_econ() {
  # 经济域判同并簇(词典齐全); 只对仍未入 B 的 KU 做候选
  local extra=("--disc" "econ" "--cap" "200" "--concurrency" "$CONC")
  if [[ -z "$DRY" ]]; then extra+=(--apply); fi
  log "orchestrate JUDGE disc=econ (no singletons-only)"
  $PY scripts/dedup/orchestrate.py "${extra[@]}"
}

ensure_embed

case "$DISC" in
  all)
    run_orch econ
    run_orch math
    run_orch misc
    ;;
  econ|math|misc)
    run_orch "$DISC"
    ;;
  *)
    log "ERROR: --disc must be econ|math|misc|all, got $DISC"
    exit 2
    ;;
esac

if [[ "$WITH_JUDGE" -eq 1 ]]; then
  run_judge_econ
fi

if [[ "$SKIP_M0" -eq 0 ]]; then
  m0_extra=(--concurrency "$CONC")
  if [[ -z "$DRY" ]]; then m0_extra+=(--apply); fi
  log "M0 concept canonical ${DRY:+(dry-run)}"
  $PY scripts/dedup/m0.py "${m0_extra[@]}" || log "WARN: m0 exited $?"
fi

if [[ "$SKIP_READOUT" -eq 0 ]]; then
  # 默认 NIM 多 key 池(.pipeline_keys.json); 每 key 硬顶 40 rpm(免费层)
  # 不走 deepseek(402)。并发默认=key 数, 勿用 --concurrency 抬过 key 数。
  export NIM_RPM="${NIM_RPM:-40}"
  ro_extra=(--provider nim --limit "$READOUT_LIMIT")
  if [[ -z "$DRY" ]]; then ro_extra+=(--apply); fi
  log "readout directed edges NIM limit=${READOUT_LIMIT} rpm/key=${NIM_RPM} ${DRY:+(dry-run)}"
  $PY scripts/dedup/readout.py "${ro_extra[@]}" || log "WARN: readout exited $?"
fi

log "done"
