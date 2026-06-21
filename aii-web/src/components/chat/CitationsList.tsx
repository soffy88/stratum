/**
 * CitationsList — chat 回答下方的依据列表(REQ-003 R3)。
 *
 * 每条 citation = grade 徽标(OEpistemicBadge,1.9.0 双语 + 红线 #1 硬规范)+ snippet。
 *
 * 点击 citation 跳到 /query?ku=<id>(可选,后续 AII 填业务逻辑,starter 给一个 console.log 占位)。
 */
'use client';

import { OEpistemicBadge } from '@helios/blocks';
import { safeGrade } from '@/lib/grade';
import type { ChatCitation } from '@/types/api';

export function CitationsList({
  citations,
  onCitationClick,
}: {
  citations: ChatCitation[];
  onCitationClick?: (c: ChatCitation) => void;
}) {
  if (citations.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 mt-2 pt-3 border-t border-[color:var(--border-strong)]">
      <div className="text-[10px] uppercase tracking-wide text-[color:var(--text-secondary)] font-medium">
        依据 / Citations ({citations.length})
      </div>
      <ul className="flex flex-col gap-2">
        {citations.map((c) => {
          const inner = (
            <div className="flex items-start gap-2">
              <OEpistemicBadge grade={safeGrade(c.grade)} compact />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-mono text-[color:var(--text-secondary)] mb-0.5">
                  {c.ku_id}
                </div>
                <div className="text-sm leading-snug">{c.snippet}</div>
              </div>
            </div>
          );
          return (
            <li key={c.ku_id}>
              {onCitationClick ? (
                <button
                  type="button"
                  onClick={() => onCitationClick(c)}
                  className="w-full text-left p-2 rounded border border-transparent hover:border-[color:var(--border-strong)] hover:bg-[color:var(--bg-cell)] transition-colors"
                >
                  {inner}
                </button>
              ) : (
                <div className="p-2">{inner}</div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
