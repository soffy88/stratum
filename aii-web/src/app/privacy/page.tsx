import Link from "next/link";

const PRIVACY_TEXT = `隐私政策

生效日期: 2026-05-27  |  版本: v1.0-alpha  |  适用产品: aii (https://aii.kanpan.co)

────────────────────────────────────────

1. 我们是谁

aii 是一个个人知识管理服务，由独立开发者维护（以下简称"我们"）。当前处于 alpha 测试期，服务可能随时变动或中断。

联系方式: wiki@kanpan.co

────────────────────────────────────────

2. 我们收集什么

2.1 你主动提供
  · 账号信息: 邮箱、用户名、密码（加密存储，我们看不到明文）
  · 你创建的内容: 笔记、上传的文档、AI 对话记录
  · 个人资料: 头像、显示名、简介（你自愿填写）

2.2 自动收集
  · 会话信息: 登录的设备类型、IP 地址前缀（用于安全防护）
  · 错误日志: 当应用崩溃时的技术信息（不含你的内容）

2.3 我们不收集
  ✗ 不使用第三方广告追踪（Google Analytics / Meta Pixel 等）
  ✗ 不收集设备指纹
  ✗ 不收集精确地理位置

────────────────────────────────────────

3. 我们如何使用

3.1 提供服务
  · 处理你的搜索、AI 问答、笔记保存等请求
  · 隔离不同用户的数据（你的内容只有你能看到，除非你主动分享）

3.2 安全防护
  · 检测异常登录、防暴力破解
  · 错误日志用于修复 bug

3.3 我们不做的
  ✗ 不出售你的数据
  ✗ 不将你的内容用于训练 AI 模型
  ✗ 不向第三方共享你的内容（除法律强制要求）

────────────────────────────────────────

4. AI 处理说明

当你使用 AI 功能（搜索、问答、摘要）时:
  · 你的查询会发送给第三方 AI 服务（DeepSeek / DashScope / Anthropic 等）
  · 这些服务可能保留 API 调用日志，遵循各自隐私政策
  · 我们不会在请求中传递你的邮箱、用户名等个人标识
  · 建议: 不要在笔记中存储高度敏感信息（身份证号、银行卡等）

────────────────────────────────────────

5. 数据存储和位置

  · 存储位置: 中国大陆（深圳）自托管服务器
  · 传输: 通过 Cloudflare CDN 加速（HTTPS 加密）
  · 保留期: 你的账号存在期间一直保留，注销后 30 天内彻底删除

────────────────────────────────────────

6. 你的权利

你可以随时:
  ✓ 在 /settings 查看自己的数据
  ✓ 编辑或删除任何笔记
  ✓ 撤销所有登录会话
  ✓ 注销账号（联系 wiki@kanpan.co）
  ✓ 导出你的数据（功能开发中，beta 版本提供）

────────────────────────────────────────

7. 分享机制

当你使用"分享"功能创建公开链接时:
  · 该笔记内容对任何拿到链接的人可见，不需要登录
  · 链接含你的用户名（公开标识）
  · 不会暴露你的邮箱、其他笔记、私人引用
  · 你可以随时撤销分享链接

────────────────────────────────────────

8. Cookie

我们仅使用必要 Cookie:
  · session cookie (httpOnly): 保持登录状态
  · theme preference (localStorage): 记住你的主题选择

不使用追踪 Cookie / 广告 Cookie。

────────────────────────────────────────

9. 未成年人

本服务不专门面向 13 岁以下未成年人。如果你是 13 岁以下用户，请勿注册。

────────────────────────────────────────

10. alpha 期特别说明

⚠ 当前为 alpha 测试期:
  · 服务可能随时中断、重置或下线
  · 不保证数据永久可用（建议定期导出重要内容）
  · 我们会努力保护数据，但 alpha 期不承担数据丢失的赔偿责任

────────────────────────────────────────

11. 政策变更

如有重大变更，我们会通过登录后页面通知。继续使用即视为接受变更。

────────────────────────────────────────

12. 联系我们

任何隐私相关问题: wiki@kanpan.co

— aii 团队`;

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      <header className="flex items-center justify-between px-8 py-4 border-b border-[var(--color-border)]">
        <Link href="/" className="font-semibold text-lg tracking-tight">aii</Link>
      </header>

      <article className="max-w-2xl mx-auto px-8 py-16">
        <pre className="whitespace-pre-wrap text-sm text-[var(--color-text)] leading-relaxed font-sans">
          {PRIVACY_TEXT}
        </pre>
      </article>

      <footer className="border-t border-[var(--color-border)] px-8 py-6 text-xs text-[var(--color-muted)]">
        <Link href="/" className="hover:underline">← 返回首页</Link>
      </footer>
    </main>
  );
}
