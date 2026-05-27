"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/auth";
import { setTheme, getTheme, type Theme } from "@/lib/theme";
import { apiClient } from "@/lib/api-client";
import type { SessionItem, SessionListResponse } from "@/lib/types";

type Tab = "profile" | "theme" | "sessions";

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("profile");

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">设置</h1>

      <div className="flex gap-4 border-b border-[var(--color-border)] mb-6">
        <TabBtn active={tab === "profile"} onClick={() => setTab("profile")}>个人资料</TabBtn>
        <TabBtn active={tab === "theme"} onClick={() => setTab("theme")}>主题</TabBtn>
        <TabBtn active={tab === "sessions"} onClick={() => setTab("sessions")}>会话管理</TabBtn>
      </div>

      {tab === "profile" && <ProfileTab />}
      {tab === "theme" && <ThemeTab />}
      {tab === "sessions" && <SessionsTab />}
    </div>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={`pb-2 px-1 text-sm font-medium border-b-2 ${active ? "border-[var(--color-primary)]" : "border-transparent text-[var(--color-muted)]"}`}>
      {children}
    </button>
  );
}

function ProfileTab() {
  const { user } = useAuthStore();
  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm text-[var(--color-muted)]">用户名</label>
        <p className="font-medium">{user?.username}</p>
      </div>
      <div>
        <label className="text-sm text-[var(--color-muted)]">邮箱</label>
        <p className="font-medium">{user?.email}</p>
      </div>
      <p className="text-xs text-[var(--color-muted)]">编辑功能将在后续版本提供</p>
    </div>
  );
}

function ThemeTab() {
  const [current, setCurrent] = useState<Theme>(getTheme());
  const themes: { value: Theme; label: string }[] = [
    { value: "zen", label: "Zen (默认)" },
    { value: "light", label: "Light" },
    { value: "dark", label: "Dark" },
  ];

  const handleChange = (t: Theme) => {
    setTheme(t);
    setCurrent(t);
  };

  return (
    <div className="space-y-2">
      {themes.map((t) => (
        <button
          key={t.value}
          onClick={() => handleChange(t.value)}
          className={`w-full text-left p-3 border rounded ${current === t.value ? "border-[var(--color-primary)] bg-[var(--color-border)]/30" : "border-[var(--color-border)]"}`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

function SessionsTab() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => apiClient.get<SessionListResponse>("/api/users/me/sessions"),
  });

  const revoke = useMutation({
    mutationFn: (sessionId: string) =>
      apiClient.delete<{ status: string }>(`/api/users/me/sessions/${sessionId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  if (isLoading) return <p className="text-sm text-[var(--color-muted)]">加载中...</p>;
  if (error) return <p className="text-sm text-red-600">无法加载会话列表</p>;

  const sessions: SessionItem[] = data?.items ?? [];

  return (
    <div className="space-y-3">
      <p className="text-xs text-[var(--color-muted)]">以下为当前活跃的登录会话</p>
      {sessions.length === 0 && (
        <p className="text-sm text-[var(--color-muted)]">暂无活跃会话</p>
      )}
      {sessions.map((s) => (
        <div
          key={s.id}
          className="flex items-start justify-between p-3 border border-[var(--color-border)] rounded text-sm"
        >
          <div className="space-y-0.5">
            <p className="font-mono text-xs text-[var(--color-muted)]">
              {s.ip_address ?? "未知 IP"}
            </p>
            <p className="text-xs text-[var(--color-muted)] truncate max-w-xs">
              {s.user_agent ?? "未知设备"}
            </p>
            {s.is_current && (
              <span className="text-xs text-green-600 font-medium">当前会话</span>
            )}
          </div>
          {!s.is_current && (
            <button
              onClick={() => revoke.mutate(s.id)}
              disabled={revoke.isPending}
              className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50 ml-4 shrink-0"
            >
              撤销
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
