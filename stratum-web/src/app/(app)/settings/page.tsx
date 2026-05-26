"use client";

import { useState } from "react";
import { useAuthStore } from "@/stores/auth";
import { setTheme, getTheme, type Theme } from "@/lib/theme";

type Tab = "profile" | "theme";

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("profile");

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">设置</h1>

      <div className="flex gap-4 border-b border-[var(--color-border)] mb-6">
        <TabBtn active={tab === "profile"} onClick={() => setTab("profile")}>个人资料</TabBtn>
        <TabBtn active={tab === "theme"} onClick={() => setTab("theme")}>主题</TabBtn>
      </div>

      {tab === "profile" && <ProfileTab />}
      {tab === "theme" && <ThemeTab />}
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
