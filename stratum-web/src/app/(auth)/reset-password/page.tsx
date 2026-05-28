export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-sm space-y-6 p-6 text-center">
        <h1 className="text-2xl font-semibold">重置密码</h1>
        <p className="text-[var(--color-muted)]">
          密码重置功能将在 v1.1 版本接入 SMTP 邮件服务后启用。
        </p>
        <p className="text-sm text-[var(--color-muted)]">
          当前 alpha 版本请联系管理员手动重置密码。
        </p>
        <a href="/login" className="inline-block underline text-sm">
          返回登录
        </a>
      </div>
    </div>
  );
}
