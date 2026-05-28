"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";
import { useState } from "react";

const schema = z.object({
  email: z.string().email("无效邮箱"),
  username: z.string().min(3, "至少 3 字符").max(32).regex(/^[a-zA-Z0-9_]+$/, "仅字母数字下划线"),
  password: z.string().min(10, "至少 10 字符"),
});
type FormData = z.infer<typeof schema>;

export function RegisterForm() {
  const { register: registerUser, login } = useAuthStore();
  const router = useRouter();
  const [error, setError] = useState("");
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    setError("");
    try {
      await registerUser(data.email, data.username, data.password);
      await login(data.email, data.password);
      router.push("/search");
    } catch (e) {
      setError(e instanceof Error ? e.message : "注册失败");
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <input {...register("email")} placeholder="邮箱" className="w-full border border-[var(--color-border)] rounded px-3 py-2" />
        {errors.email && <p className="text-red-600 text-xs mt-1">{errors.email.message}</p>}
      </div>
      <div>
        <input {...register("username")} placeholder="用户名" className="w-full border border-[var(--color-border)] rounded px-3 py-2" />
        {errors.username && <p className="text-red-600 text-xs mt-1">{errors.username.message}</p>}
      </div>
      <div>
        <input {...register("password")} type="password" placeholder="密码 (至少 10 字符)" className="w-full border border-[var(--color-border)] rounded px-3 py-2" />
        {errors.password && <p className="text-red-600 text-xs mt-1">{errors.password.message}</p>}
      </div>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <button type="submit" disabled={isSubmitting} className="w-full bg-[var(--color-primary)] text-white rounded py-2 disabled:opacity-50">
        {isSubmitting ? "注册中..." : "注册"}
      </button>
    </form>
  );
}
