#!/usr/bin/env bash
# ★Rclone Google Drive 自定义 client_id 配置脚本
# 背景: rclone 共享 Google Drive client_id 将在 2026 年停用, 日志中已出现:
#   "gdrive: This remote uses rclone's shared Google Drive client_id, which is being
#    retired and will stop working during 2026."
# 本脚本指导创建自定义 OAuth 凭据并更新 rclone 配置.
#
# 用法: bash scripts/setup_rclone_client_id.sh
# 前提: 需要 Google 账号, 能在浏览器中完成 OAuth 授权.

set -uo pipefail

echo "════════════════════════════════════════════════════"
echo "★ Rclone Google Drive 自定义 client_id 配置"
echo "════════════════════════════════════════════════════"
echo ""

# 检查 rclone 是否安装
if ! command -v rclone &>/dev/null; then
    echo "❌ rclone 未安装. 请先安装: curl https://rclone.org/install.sh | sudo bash"
    exit 1
fi

echo "━━━ 第一步: 创建 Google Cloud OAuth 凭据 ━━━"
echo ""
echo "1. 打开 Google Cloud Console: https://console.cloud.google.com/"
echo "2. 选择或创建一个项目"
echo "3. 左侧菜单 → 「API和服务」→「库」→ 搜索并启用「Google Drive API」"
echo "4. 左侧菜单 → 「API和服务」→「凭据」→「+ 创建凭据」→「OAuth 客户端 ID」"
echo "   - 应用类型: 「桌面应用」"
echo "   - 名称: 随意(如 rclone-aii)"
echo "   - 点击「创建」"
echo "5. 记下「客户端 ID」和「客户端密钥」"
echo ""
echo "★ 如果提示需要配置 OAuth 同意屏幕:"
echo "   - 「API和服务」→「OAuth 同意屏幕」→「External」"
echo "   - 填写应用名称/支持邮箱/开发者联系邮箱(都用你自己的)"
echo "   - 作用域: 添加 Google Drive API 的 scope"
echo "   - 测试用户: 添加你自己的 Gmail 地址"
echo ""

read -p "完成后按 Enter 继续(或 Ctrl-C 取消)..."

echo ""
echo "━━━ 第二步: 配置 rclone ━━━"
echo ""

# 获取用户输入
read -p "请输入 Google OAuth Client ID: " CLIENT_ID
read -p "请输入 Google OAuth Client Secret: " CLIENT_SECRET

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    echo "❌ Client ID 或 Secret 为空"
    exit 1
fi

echo ""
echo "将更新以下 rclone remote:"
echo "  - gdrive (只读)"
echo "  - gdrive-rw (读写)"
echo ""

# 更新 gdrive (只读)
rclone config update gdrive client_id "$CLIENT_ID" client_secret "$CLIENT_SECRET" 2>/dev/null
echo "✅ gdrive 已更新"

# 更新 gdrive-rw (读写)
rclone config update gdrive-rw client_id "$CLIENT_ID" client_secret "$CLIENT_SECRET" 2>/dev/null
echo "✅ gdrive-rw 已更新"

echo ""
echo "━━━ 第三步: 重新授权(刷新 token) ━━━"
echo ""
echo "需要重新授权以使用新的 client_id. 依次运行:"
echo ""
echo "  rclone config reconnect gdrive:"
echo "  rclone config reconnect gdrive-rw:"
echo ""
echo "每个命令会打开浏览器让你登录 Google 账号授权."
echo ""
echo "授权完成后, 验证:"
echo "  rclone config show gdrive | grep client_id"
echo "  rclone ls gdrive: --max-depth 0   # 测试连接"
echo ""
echo "════════════════════════════════════════════════════"
echo "★ 配置完成! 飞轮和 feeder 下次运行时将使用自定义 client_id"
echo "════════════════════════════════════════════════════"
