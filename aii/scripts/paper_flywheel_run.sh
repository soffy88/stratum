#!/usr/bin/env bash
# ★论文飞轮 — 连续运行(不停, 非定时). 同 advmath_flywheel_run.sh / misc_flywheel_run.sh 的模式.
# 用法:  nohup bash scripts/paper_flywheel_run.sh >> paper_pipeline/flywheel.log 2>&1 &
# 可选:  PAPER_IDLE_SLEEP=600(无新论文时sleep秒, 默认600)
set -uo pipefail
cd "$(dirname "$0")/.."
# ★2026-08-27 修复 LLM 412/429: 使用本地 Veya 网关 (gpt-5.6-luna), 避开 opencode.ai 412(额度用尽) 与 NIM 429(免费层限流)
export OPENCODE_BASE_URL="${OPENCODE_BASE_URL:-http://192.168.80.1:8791/v1/chat/completions}"
export OPENCODE_MODEL="${OPENCODE_MODEL:-opencode-go/space-bunny-free}"
export NIM_MODEL="${NIM_MODEL:-z-ai/glm-5.3}"
# ★2026-10-03 NIM 兜底链修复: 之前飞轮 env 里没有 NVIDIA_NIM_API_KEY → _provider.py:488
#   nim_key=None → 整个 NIM 分支被跳过 → fallback 链里【没有 NIM】。而NIM_MODEL 写的
#   nvidia/nemotron-3-super-120b-a12b 已下线(410 Gone)。key 本身有效, 从
#   .pipeline_keys.json(gitignored) 取, 与 math_flywheel_prog.sh 同惯例。
export NVIDIA_NIM_API_KEY="${NVIDIA_NIM_API_KEY:-$("$PWD/.venv/bin/python" -c "
import json
d = json.load(open('.pipeline_keys.json'))
for k in ('econ_zh','econ','math_en','math_zh','advmath_verify','learning'):
    if d.get(k):
        print(d[k]); break
" 2>/dev/null)}"
export NIM_KEY_POOL="${NIM_KEY_POOL:-$("$PWD/.venv/bin/python" -c "
import json
d = json.load(open('.pipeline_keys.json'))
ks = [d.get(k) for k in ('econ_zh','econ','math_en','math_zh','advmath_2','advmath_3','advmath_verify','learning')]
print(','.join(x for x in ks if x))
" 2>/dev/null)}"
export OPENCODE_KEY_POOL="${OPENCODE_KEY_POOL:-sk-veya}"
export AII_LLM_PRIMARY="${AII_LLM_PRIMARY:-opencode}"
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,192.168.80.1,::1}"
export no_proxy="${no_proxy:-$NO_PROXY}"
# ★单实例锁: 防止 systemd 服务 + 手动 nohup 双跑(实测双实例同 key 打 NIM → 限流风暴
# → ReadTimeout 重试地狱 → 整批隔离, 零入库)。已持锁实例正常跑, 新实例立即退出。
mkdir -p .locks
exec 9>.locks/paper_flywheel.lock
flock -n 9 || { echo "⚠ 已有实例在运行({lock}), 本次启动退出"; exit 0; }

IDLE="${PAPER_IDLE_SLEEP:-120}"
BOOKLIST="paper_pipeline/flywheel_booklist.txt"

echo "════════════════════════════════════════════════════"
echo "★ 论文飞轮 — 连续运行启动 $(date '+%Y-%m-%d %H:%M')"
echo "  模式: 不停(处理完一批→下一批; 无新论文sleep ${IDLE}s 再查)"
echo "════════════════════════════════════════════════════"

while true; do
    bash scripts/paper_flywheel.sh || echo "  ⚠️ 本轮飞轮异常(继续循环) $(date '+%H:%M')"
    if [ ! -s "$BOOKLIST" ]; then
        echo "── [连续] 无新论文, sleep ${IDLE}s 后再发现… $(date '+%H:%M') ──"
        sleep "$IDLE"
    fi
done
