"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";
import { useState } from "react";

const schema = z.object({
  email_or_username: z.string().min(1, "必填"),
  password: z.string().min(1, "必填"),
});
type FormData = z.infer<typeof schema>;

export function LoginForm() {
  const { login } = useAuthStore();
  const router = useRouter();
  const [error, setError] = useState("");
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    setError("");
    try {
      await login(data.email_or_username, data.password);
      router.push("/documents");
    } catch (e) {
      setError(e instanceof Error ? e.message : "登录失败");
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <input {...register("email_or_username")} placeholder="邮箱或用户名" className="w-full border border-[var(--color-border)] rounded px-3 py-2" />
        {errors.email_or_username && <p className="text-red-600 text-xs mt-1">{errors.email_or_username.message}</p>}
      </div>
      <div>
        <input {...register("password")} type="password" placeholder="密码" className="w-full border border-[var(--color-border)] rounded px-3 py-2" />
        {errors.password && <p className="text-red-600 text-xs mt-1">{errors.password.message}</p>}
      </div>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <button type="submit" disabled={isSubmitting} className="w-full bg-[var(--color-primary)] text-white rounded py-2 disabled:opacity-50">
        {isSubmitting ? "登录中..." : "登录"}
      </button>
    </form>
  );
}
