"use client";

// AII 学习助手模块 — 学习档案列表/新建。数据来自 AII 后端 /api/learning/profiles。
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface Profile {
  profile_id: number;
  subject: string;
  goal: string;
  main_textbook: string;
  created_at: string;
}

export default function LearningListPage() {
  const router = useRouter();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [err, setErr] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [subject, setSubject] = useState("");
  const [mainTextbook, setMainTextbook] = useState("");
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    fetch("/api/aii/api/learning/profiles")
      .then((r) => r.json())
      .then((d) => { setProfiles(d?.data ?? []); setErr(false); })
      .catch(() => setErr(true));
  }, []);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!subject.trim() || !mainTextbook.trim()) return;
    setBusy(true);
    try {
      const r = await fetch("/api/aii/api/learning/profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject, main_textbook: mainTextbook, goal }),
      });
      const d = await r.json();
      if (d?.data?.profile_id) router.push(`/learning/${d.data.profile_id}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-bold">学习助手</h1>
        <button
          onClick={() => setShowNew((v) => !v)}
          className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white"
        >
          {showNew ? "取消" : "+ 新建学习档案"}
        </button>
      </div>
      <p className="text-sm text-[var(--color-muted)] mb-4">
        持续记忆(C仓) + 不能撒谎的裁判——诊断真实起点、生成学习计划、独立推导/代码判定掌握程度、间隔重复防遗忘。
      </p>

      {err && <p className="text-sm text-red-600 mb-3">无法连接 AII 后端 /api/learning/profiles</p>}

      {showNew && (
        <div className="border border-[var(--color-border)] rounded-lg p-4 mb-4 space-y-3">
          <div>
            <label className="block text-xs text-[var(--color-muted)] mb-1">学科/主题</label>
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="如: An Introduction to Mathematical Analysis for Economic Theory..."
              className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-transparent"
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--color-muted)] mb-1">
              主教材文件名(不含.md, 需已在 books/MD 或高级数学经济专用 文件夹里)
            </label>
            <input
              value={mainTextbook}
              onChange={(e) => setMainTextbook(e.target.value)}
              placeholder="如: An_Introduction_to_Mathematical_Analysis_01KVAJVD"
              className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-transparent font-mono"
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--color-muted)] mb-1">目标(到什么水平)</label>
            <input
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="如: 能独立推导简单增长模型的稳态性质"
              className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-transparent"
            />
          </div>
          <button
            disabled={busy || !subject.trim() || !mainTextbook.trim()}
            onClick={create}
            className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white disabled:opacity-40"
          >
            {busy ? "创建中…" : "创建并开始诊断"}
          </button>
        </div>
      )}

      <div className="space-y-2">
        {profiles.map((p) => (
          <Link
            key={p.profile_id}
            href={`/learning/${p.profile_id}`}
            className="block border border-[var(--color-border)] rounded-lg p-4 hover:border-[var(--color-primary)] transition-colors"
          >
            <div className="font-medium truncate">{p.subject}</div>
            {p.goal && <div className="text-sm text-[var(--color-muted)] mt-1 truncate">{p.goal}</div>}
            <div className="text-xs text-[var(--color-muted)] mt-1 font-mono truncate">{p.main_textbook}</div>
          </Link>
        ))}
        {!profiles.length && !err && (
          <p className="text-[var(--color-muted)] text-sm">还没有学习档案，点右上角新建一个。</p>
        )}
      </div>
    </div>
  );
}
