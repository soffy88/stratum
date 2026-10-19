/**
 * AII Notes 正文 wikilink 解析与渲染辅助。
 *
 * 语法：[[目标]] 或 [[目标|显示文字]]，其中目标是笔记 id，或笔记标题
 * （大小写不敏感）。解析规则与后端 knowledge_lint 对齐：id 优先，其次标题。
 * 代码围栏（```）内的 [[...]] 不解析。
 */

export interface ParsedWikilink {
  /** 原始 [[...]] 文本 */
  raw: string;
  /** 去掉别名后的目标（笔记 id 或标题） */
  target: string;
  /** [[目标|显示文字]] 中的显示文字（无别名时为 null） */
  label: string | null;
}

export interface ResolvedWikilinkTarget {
  id: string;
  title: string | null;
}

/** 按 ``` 围栏切分：围栏内的内容不做 wikilink 解析 */
function splitFencedBlocks(content: string): { text: string; code: boolean }[] {
  const parts = content.split(/(```[\s\S]*?(?:```|$))/g);
  return parts.map((text, i) => ({ text, code: i % 2 === 1 }));
}

function parseSegment(text: string): ParsedWikilink[] {
  const out: ParsedWikilink[] = [];
  const re = /\[\[([^[\]\n]+)\]\]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const inner = (m[1] ?? "").trim();
    if (!inner) continue;
    const pipe = inner.indexOf("|");
    const target = (pipe === -1 ? inner : inner.slice(0, pipe)).trim();
    const label = pipe === -1 ? null : inner.slice(pipe + 1).trim();
    if (!target) continue;
    out.push({ raw: m[0], target, label: label || null });
  }
  return out;
}

/** 解析正文中的全部 wikilink（按出现顺序，含重复） */
export function parseWikilinks(content: string): ParsedWikilink[] {
  const out: ParsedWikilink[] = [];
  for (const { text, code } of splitFencedBlocks(content ?? "")) {
    if (!code) out.push(...parseSegment(text));
  }
  return out;
}

/** 正文中的出链目标（去重，保持首次出现顺序） */
export function extractWikilinkTargets(content: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const w of parseWikilinks(content)) {
    if (!seen.has(w.target)) {
      seen.add(w.target);
      out.push(w.target);
    }
  }
  return out;
}

function escapeMarkdownLabel(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/\[/g, "\\[").replace(/\]/g, "\\]");
}

/**
 * 把正文里的 [[目标]] / [[目标|显示文字]] 改写为标准 markdown 链接
 * [显示文字](/notes/<id>)，以便 markdown 渲染器输出可点击链接。
 * resolve 返回 null 表示断链：保留原文不动。
 */
export function wikilinksToMarkdownLinks(
  content: string,
  resolve: (target: string) => ResolvedWikilinkTarget | null,
): string {
  return splitFencedBlocks(content ?? "")
    .map(({ text, code }) => {
      if (code) return text;
      return text.replace(/\[\[([^[\]\n]+)\]\]/g, (raw, inner: string) => {
        const t = String(inner).trim();
        if (!t) return raw;
        const pipe = t.indexOf("|");
        const target = (pipe === -1 ? t : t.slice(0, pipe)).trim();
        if (!target) return raw;
        const hit = resolve(target);
        if (!hit) return raw;
        const aliasLabel = pipe === -1 ? "" : t.slice(pipe + 1).trim();
        const label = aliasLabel || hit.title || target;
        return `[${escapeMarkdownLabel(label)}](/notes/${encodeURIComponent(hit.id)})`;
      });
    })
    .join("");
}
