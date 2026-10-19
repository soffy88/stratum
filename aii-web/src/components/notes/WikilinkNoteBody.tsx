"use client";

import { useMemo } from "react";
import { OMarkdownRenderer } from "@helios/blocks";
import { wikilinksToMarkdownLinks } from "@/lib/wikilink";
import type { OutgoingLink } from "@/lib/adapters/notes";

interface WikilinkNoteBodyProps {
  /** 笔记正文 markdown */
  content: string;
  /** 出链解析结果（由 useOutgoingLinks 提供） */
  links: OutgoingLink[];
}

/**
 * 笔记正文渲染：把 [[笔记id]] / [[标题]] / [[目标|显示文字]] 改写为可点击的
 * 站内笔记链接，其余 markdown 原样渲染。断链保留原文不动。
 */
export function WikilinkNoteBody({ content, links }: WikilinkNoteBodyProps) {
  const markdown = useMemo(() => {
    const byTarget = new Map(links.map((l) => [l.target, l]));
    return wikilinksToMarkdownLinks(content, (target) => {
      const hit = byTarget.get(target);
      if (!hit || !hit.id) return null;
      return { id: hit.id, title: hit.title };
    });
  }, [content, links]);

  return (
    <div className="wikilink-note-body rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] px-5 py-4">
      <OMarkdownRenderer content={markdown} gfm />
    </div>
  );
}
