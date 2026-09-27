"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/auth";
import { setTheme, getTheme, type Theme } from "@/lib/theme";
import { apiClient } from "@/lib/api-client";
import { resetOnboardingTour } from "@/components/OnboardingTour";
import type { SessionItem, SessionListResponse } from "@/lib/types";

type Tab = "profile" | "theme" | "sessions" | "usage" | "sync";

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("profile");

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">设置</h1>

      <div className="flex gap-4 border-b border-[var(--color-border)] mb-6">
        <TabBtn active={tab === "profile"} onClick={() => setTab("profile")}>个人资料</TabBtn>
        <TabBtn active={tab === "theme"} onClick={() => setTab("theme")}>主题</TabBtn>
        <TabBtn active={tab === "sessions"} onClick={() => setTab("sessions")}>会话管理</TabBtn>
        <TabBtn active={tab === "usage"} onClick={() => setTab("usage")}>用量</TabBtn>
        <TabBtn active={tab === "sync"} onClick={() => setTab("sync")}>Obsidian</TabBtn>
      </div>

      {tab === "profile" && <ProfileTab />}
      {tab === "theme" && <ThemeTab />}
      {tab === "sessions" && <SessionsTab />}
      {tab === "usage" && <UsageTab />}
      {tab === "sync" && <ObsidianSyncTab />}
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
      <div className="pt-2 border-t border-[var(--color-border)]">
        <button
          onClick={() => {
            resetOnboardingTour();
            window.location.reload();
          }}
          className="text-sm text-[var(--color-primary)] hover:underline"
        >
          重看引导教程
        </button>
      </div>
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

  const convSessionsLink = (
    <div className="mb-4 p-3 border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/5 rounded-lg">
      <p className="text-sm">
        对话与上下文管理请前往{' '}
        <a href="/sessions" className="text-[var(--color-primary)] font-medium hover:underline">
          会话管理 →
        </a>
      </p>
      <p className="text-xs text-[var(--color-muted)] mt-1">
        查看对话历史、上下文窗口、记忆提取
      </p>
    </div>
  );

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
      {convSessionsLink}
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

interface CreditSnapshot {
  period: string;
  tier: string;
  allowances: Record<string, number>;
  unit_costs: Record<string, number>;
  credits_used: number;
  credits_remaining: number;
}

function UsageTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["creditSnapshot"],
    queryFn: () => apiClient.get<CreditSnapshot>("/api/v1/billing/credits"),
  });

  if (isLoading) return <p className="text-sm text-[var(--color-muted)]">加载用量中...</p>;
  if (error || !data) return <p className="text-sm text-red-600">无法加载 credits 用量</p>;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-3">
        <UsageCard label="当前套餐" value={data.tier.toUpperCase()} />
        <UsageCard label="本月已用" value={data.credits_used} />
        <UsageCard label="剩余 credits" value={data.credits_remaining} />
      </div>
      <p className="text-xs text-[var(--color-muted)]">计费周期：{data.period}</p>
      <div>
        <h2 className="text-sm font-semibold mb-2">能力单价</h2>
        <div className="space-y-1.5 text-sm">
          {Object.entries(data.unit_costs).map(([capability, cost]) => (
            <div key={capability} className="flex justify-between border-b border-[var(--color-border)] pb-1.5">
              <span>{capability}</span>
              <span className="tabular-nums text-[var(--color-muted)]">{cost} credits / 次</span>
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-[var(--color-muted)]">
        套餐额度由服务端策略决定；客户端只展示账本快照，不自行计算或修改余额。
      </p>
    </div>
  );
}

function UsageCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="p-3 border border-[var(--color-border)] rounded-lg">
      <p className="text-xs text-[var(--color-muted)] mb-1">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

interface ObsidianSyncResult {
  status: string;
  connector?: string;
  export?: { files_written?: number };
  import?: { created?: number; updated?: number; skipped?: number; errors?: string[] };
}

function ObsidianSyncTab() {
  const [path, setPath] = useState("");
  const [mode, setMode] = useState<"export" | "import" | "both">("both");
  const [result, setResult] = useState<ObsidianSyncResult | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { data: roots, isLoading: rootsLoading } = useQuery({
    queryKey: ["vaultRoots"],
    queryFn: () => apiClient.get<{ roots: string[] }>("/api/v1/sync/vault/roots"),
  });

  const sync = useMutation({
    mutationFn: () => apiClient.post<ObsidianSyncResult>("/api/v1/sync/obsidian", { path, mode }),
    onSuccess: (value) => { setResult(value); setSubmitError(null); },
    onError: (error) => { setSubmitError(error instanceof Error ? error.message : "同步失败"); },
  });

  const submit = () => {
    if (!path.trim()) { setSubmitError("请输入 Obsidian vault 路径"); return; }
    setResult(null);
    sync.mutate();
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-sm font-semibold">Obsidian 双向同步</h2>
        <p className="text-xs text-[var(--color-muted)] mt-1">
          使用 Markdown frontmatter 的稳定 id 做 upsert；路径必须位于服务端允许的根目录内。
        </p>
      </div>
      <label className="block space-y-1" htmlFor="obsidian-path">
        <span className="text-sm">Vault 路径</span>
        <input
          id="obsidian-path"
          aria-label="Vault 路径"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          list="obsidian-roots"
          placeholder={roots?.roots[0] ?? "/allowed/vault"}
          className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm"
        />
        <datalist id="obsidian-roots">
          {(roots?.roots ?? []).map((root) => <option key={root} value={root} />)}
        </datalist>
        {rootsLoading && <span className="text-xs text-[var(--color-muted)]">读取允许目录…</span>}
      </label>
      <div className="flex items-center gap-3">
        <label className="text-sm" htmlFor="obsidian-mode">模式</label>
        <select
          id="obsidian-mode"
          value={mode}
          onChange={(e) => setMode(e.target.value as typeof mode)}
          className="border border-[var(--color-border)] rounded px-3 py-2 text-sm"
        >
          <option value="both">双向</option>
          <option value="export">导出到 Obsidian</option>
          <option value="import">从 Obsidian 导入</option>
        </select>
        <button
          type="button"
          onClick={submit}
          disabled={sync.isPending}
          className="ml-auto px-4 py-2 rounded bg-[var(--color-primary)] text-white text-sm disabled:opacity-50"
        >
          {sync.isPending ? "同步中…" : "开始同步"}
        </button>
      </div>
      {submitError && <p className="text-sm text-red-600">{submitError}</p>}
      {result && (
        <div className="p-3 rounded-lg border border-green-500/30 bg-green-500/5 text-sm space-y-1">
          <p className="font-medium">同步完成（{result.connector ?? "vault"}）</p>
          {result.export && <p className="text-xs">导出文件：{result.export.files_written ?? 0}</p>}
          {result.import && (
            <p className="text-xs">
              导入：新建 {result.import.created ?? 0} · 更新 {result.import.updated ?? 0} ·
              跳过 {result.import.skipped ?? 0}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
