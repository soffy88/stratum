"use client";

import type { KeyboardEvent } from "react";
import type { OutgoingLink } from "@/lib/adapters/notes";

interface OutgoingLinksPanelProps {
  /** 已解析的出链（这篇笔记链向谁） */
  links: OutgoingLink[];
  /** 点击出链 */
  onSelect?: (noteId: string) => void;
  /** 空状态文案 */
  emptyText?: string;
}

/**
 * 出链面板（"这篇笔记链向谁"）：视觉对标 OBacklinkPanel。
 */
export function OutgoingLinksPanel({ links, onSelect, emptyText }: OutgoingLinksPanelProps) {
  const handleKey = (e: KeyboardEvent, id: string | null) => {
    if ((e.key === "Enter" || e.key === " ") && id) {
      e.preventDefault();
      onSelect?.(id);
    }
  };

  return (
    <aside className="flex flex-col gap-2 w-full" aria-label="出链">
      <header className="flex items-center gap-2">
        <svg
          aria-hidden="true"
          width="1em"
          height="1em"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M7 17 17 7" />
          <path d="M8 7h9v9" />
        </svg>
        <h3 className="text-sm font-bold text-[var(--color-foreground)] tracking-[-0.01em]">
          出链
        </h3>
        <span className="text-xs text-[var(--color-muted)] font-mono">({links.length})</span>
      </header>
      <p className="-mt-1 text-[11px] text-[var(--color-muted)]">这篇笔记链向谁</p>
      {links.length === 0 ? (
        <div className="px-3 py-6 text-center text-xs text-[var(--color-muted)] border border-dashed border-[var(--color-border)] rounded-md">
          {emptyText ?? "暂无出链"}
        </div>
      ) : (
        <ul className="flex flex-col gap-1.5 list-none p-0 m-0" aria-label={`出链 ${links.length} 条`}>
          {links.map((link) => (
            <li key={link.id ?? link.target}>
              <button
                type="button"
                onClick={() => link.id && onSelect?.(link.id)}
                onKeyDown={(e) => handleKey(e, link.id)}
                className="flex flex-col gap-1 px-3 py-2 rounded-md text-left w-full bg-[var(--color-card)] hover:bg-[var(--color-muted)]/20 border border-[var(--color-border)] transition-colors cursor-pointer focus:outline-none focus-visible:ring-2"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-[var(--color-foreground)] truncate flex-1">
                    {link.title || link.target}
                  </span>
                </div>
                <div className="text-[10px] font-mono text-[var(--color-primary)] truncate">
                  [[{link.target}]]
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
