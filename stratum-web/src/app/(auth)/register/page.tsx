"use client";

import { RegisterForm } from "@/components/auth/RegisterForm";

export default function RegisterPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-sm space-y-6 p-6">
        <h1 className="text-2xl font-semibold text-center">注册 Stratum</h1>
        <RegisterForm />
        <p className="text-center text-sm text-[var(--color-muted)]">
          已有账号？<a href="/login" className="underline">登录</a>
        </p>
      </div>
    </div>
  );
}
