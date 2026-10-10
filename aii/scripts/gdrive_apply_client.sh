#!/usr/bin/env bash
# 用自建 OAuth client 凭据更新 gdrive: remote
# 用法: ./gdrive_apply_client.sh <client_id> <client_secret> [token_json_file]
# 注意: refresh_token 含 '/',必须直接改配置文件,不能用 rclone config update
set -euo pipefail
CONF="${HOME}/.config/rclone/rclone.conf"
BACKUP="${CONF}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$CONF" "$BACKUP"
echo "✓ 已备份: $BACKUP"

python3 - "$1" "$2" "${3:-}" << 'PYEOF'
import configparser, json, sys
cid, secret, tokfile = sys.argv[1], sys.argv[2], sys.argv[3]
p = f"{__import__('os').path.expanduser('~')}/.config/rclone/rclone.conf"
c = configparser.RawConfigParser(); c.read(p)
if 'gdrive' not in c: c.add_section('gdrive')
c['gdrive']['type'] = 'drive'
c['gdrive']['client_id'] = cid
c['gdrive']['client_secret'] = secret
c['gdrive']['scope'] = 'drive'
c['gdrive']['team_drive'] = ''
if tokfile:
    d = json.load(open(tokfile))
    c['gdrive']['token'] = json.dumps(
        {k: d[k] for k in ('refresh_token','access_token','token_type','expiry') if k in d},
        separators=(',', ':'))
with open(p, 'w') as f: c.write(f)
print("✓ client_id 已写入:", cid[:30] + "...")
print("✓ token 已写入:", '是' if tokfile else '否(沿用旧 token，将需重新授权)')
PYEOF

echo "--- 验证 ---"
rclone lsd gdrive: --max-depth 1 2>&1 | grep -v NOTICE | head -3
rclone about gdrive: 2>&1 | grep -v NOTICE | head -2
