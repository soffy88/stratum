"use client";

import { LoginForm } from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-sm space-y-6 p-6">
        <h1 className="text-2xl font-semibold text-center">登录 Stratum</h1>
        <LoginForm />
        <p className="text-center text-sm text-[var(--color-muted)]">
          没有账号？<a href="/register" className="underline">注册</a>
        </p>
      </div>
    </div>
  );
}
