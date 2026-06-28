/**
 * ModeTag — 把 chat mode 视觉化(REQ-003 R2)。
 *
 * 红线护栏:
 *   - 3 种 mode 必须视觉可区分(chitchat 不能看起来像 grounded)
 *   - mode→style 硬编码,不接 variant 覆盖
 *
 * grounded     → 中性 neutral tag(不抢眼,跟正文协调)
 * chitchat     → 灰色 label(明显非确证)
 * no_knowledge → 警示色(让用户立即知道这是 fallback)
 */
'use client';

import type { ChatMode } from '@/types/api';

const STYLE: Record<ChatMode, { label: { zh: string; en: string }; bg: string; fg: string; border: string }> = {
  grounded: {
    label: { zh: '基于知识库', en: 'Grounded' },
    bg: 'var(--bg-cell, #f0fdf4)',
    fg: 'var(--alert-success-fg, #166534)',
    border: 'var(--alert-success, #16a34a)',
  },
  chitchat: {
    label: { zh: '一般性回答 · 非来自确证知识库', en: 'General reply · not from knowledge base' },
    bg: 'var(--bg-cell, #f3f4f6)',
    fg: 'var(--text-secondary, #4b5563)',
    border: 'var(--border-strong, #9ca3af)',
  },
  no_knowledge: {
    label: { zh: '知识库未覆盖此问题', en: 'No knowledge base coverage' },
    bg: 'var(--alert-warn-bg, #fef3c7)',
    fg: 'var(--alert-warn-fg, #78350f)',
    border: 'var(--alert-warn, #d97706)',
  },
};

export function ModeTag({ mode }: { mode: ChatMode }) {
  const s = STYLE[mode];
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border"
      style={{ background: s.bg, color: s.fg, borderColor: s.border }}
      aria-label={`mode: ${mode}`}
    >
      {s.label.zh} / {s.label.en}
    </span>
  );
}
