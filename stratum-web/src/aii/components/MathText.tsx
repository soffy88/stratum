'use client';

/**
 * MathText — 中文文本 + LaTeX 公式混排渲染(KaTeX)。
 * 数学 KU 的 natural_text_zh 里公式是 LaTeX 源码:
 *   行内 \(...\) 或 $...$ ;块级 \[...\] 或 $$...$$
 * 中文正常显示,公式段用 KaTeX 渲染成数学符号。无公式文本则原样显示(经济书不受影响)。
 */
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { useMemo } from 'react';

// 块级在前(\[...\] / $$...$$),再行内(\(...\) / $...$);非贪婪
const RE = /\\\[([\s\S]+?)\\\]|\$\$([\s\S]+?)\$\$|\\\(([\s\S]+?)\\\)|\$([^$\n]+?)\$/g;

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function render(text: string): string {
  if (!text) return '';
  let out = '';
  let last = 0;
  let m: RegExpExecArray | null;
  RE.lastIndex = 0;
  while ((m = RE.exec(text)) !== null) {
    out += escapeHtml(text.slice(last, m.index));
    const block = m[1] ?? m[2];
    const inline = m[3] ?? m[4];
    const tex = (block ?? inline ?? '').trim();
    try {
      out += katex.renderToString(tex, { displayMode: block != null, throwOnError: false });
    } catch {
      out += escapeHtml(m[0]);
    }
    last = m.index + m[0].length;
  }
  out += escapeHtml(text.slice(last));
  return out;
}

export function MathText({ text, className }: { text?: string | null; className?: string }) {
  const html = useMemo(() => render(text || ''), [text]);
  return (
    <div
      className={className}
      style={{ whiteSpace: 'pre-wrap' }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
