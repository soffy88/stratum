"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

interface AdminStats {
  users: number;
  substrates: number;
  active_sessions: number;
  feedback_submissions: number;
  share_tokens: number;
}

interface WukrMetrics {
  active_users: number;
  useful_reuse_users: number;
  wukr: number;
}

interface TelemetryMetrics {
  wukr?: WukrMetrics;
}

export default function AdminDashboardPage() {
  const [secret, setSecret] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["adminStats", secret],
    queryFn: async () => {
      const res = await fetch("/api/admin/stats", {
        headers: { "X-Admin-Secret": secret },
      });
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json() as Promise<AdminStats>;
    },
    enabled: submitted && secret.length > 0,
    retry: false,
  });

  const { data: telemetry, isLoading: telemetryLoading, error: telemetryError } = useQuery({
    queryKey: ["adminTelemetry", secret],
    queryFn: async () => {
      const res = await fetch("/api/v1/metrics", {
        headers: { "X-Admin-Secret": secret },
      });
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json() as Promise<TelemetryMetrics>;
    },
    enabled: submitted && secret.length > 0,
    retry: false,
  });

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-xl font-semibold">管理员统计</h1>

      <div className="flex gap-2">
        <input
          type="password"
          value={secret}
          onChange={(e) => { setSecret(e.target.value); setSubmitted(false); }}
          placeholder="Admin secret"
          className="flex-1 text-sm border border-[var(--color-border)] rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
        />
        <button
          onClick={() => setSubmitted(true)}
          className="text-sm px-4 py-1.5 bg-[var(--color-primary)] text-white rounded hover:opacity-90"
        >
          查询
        </button>
      </div>

      {isLoading && <p className="text-sm text-[var(--color-muted)]">加载中...</p>}
      {error && (
        <p className="text-sm text-red-600">
          {(error as Error).message === "403" ? "密钥错误" :
           (error as Error).message === "503" ? "Admin 未配置" : "请求失败"}
        </p>
      )}

      {data && (
        <div className="grid grid-cols-2 gap-4">
          <StatCard label="注册用户" value={data.users} />
          <StatCard label="文档库文件" value={data.substrates} />
          <StatCard label="活跃会话" value={data.active_sessions} />
          <StatCard label="反馈提交" value={data.feedback_submissions} />
          <StatCard label="分享链接" value={data.share_tokens} />
        </div>
      )}

      {submitted && (
        <section className="space-y-3">
          <div>
            <h2 className="text-base font-semibold">WUKR · Weekly Useful Knowledge Reuse</h2>
            <p className="text-xs text-[var(--color-muted)]">
              过去 7 天至少发生一次有用知识复用的用户占活跃用户比例。
            </p>
          </div>
          {telemetryLoading && <p className="text-sm text-[var(--color-muted)]">加载 WUKR…</p>}
          {telemetryError && (
            <p className="text-sm text-[var(--color-muted)]">
              WUKR telemetry 暂不可用；不影响基础管理员统计。
            </p>
          )}
          {telemetry?.wukr && (
            <div className="grid grid-cols-3 gap-4">
              <StatCard label="WUKR" value={`${(telemetry.wukr.wukr * 100).toFixed(1)}%`} />
              <StatCard label="活跃用户（7天）" value={telemetry.wukr.active_users} />
              <StatCard label="有用复用用户" value={telemetry.wukr.useful_reuse_users} />
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="p-4 border border-[var(--color-border)] rounded-lg">
      <p className="text-xs text-[var(--color-muted)] mb-1">{label}</p>
      <p className="text-2xl font-semibold">{value.toLocaleString()}</p>
    </div>
  );
}
