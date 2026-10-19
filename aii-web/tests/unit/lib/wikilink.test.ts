import { describe, it, expect } from "vitest";
import {
  parseWikilinks,
  extractWikilinkTargets,
  wikilinksToMarkdownLinks,
} from "@/lib/wikilink";

describe("parseWikilinks", () => {
  it("parses [[id]] and [[target|label]]", () => {
    const ws = parseWikilinks("见 [[abc123]] 和 [[标题|别名]]");
    expect(ws).toHaveLength(2);
    expect(ws[0]).toMatchObject({ raw: "[[abc123]]", target: "abc123", label: null });
    expect(ws[1]).toMatchObject({ raw: "[[标题|别名]]", target: "标题", label: "别名" });
  });

  it("skips fenced code blocks", () => {
    const ws = parseWikilinks("```\n[[abc]]\n```\n正文 [[def]]");
    expect(ws.map((w) => w.target)).toEqual(["def"]);
  });

  it("ignores empty brackets", () => {
    expect(parseWikilinks("[[ ]]")).toHaveLength(0);
  });

  it("does not match across newlines", () => {
    expect(parseWikilinks("[[a\nb]]")).toHaveLength(0);
  });
});

describe("extractWikilinkTargets", () => {
  it("dedupes preserving first-seen order", () => {
    expect(extractWikilinkTargets("[[a]] [[b]] [[a]]")).toEqual(["a", "b"]);
  });

  it("strips alias part", () => {
    expect(extractWikilinkTargets("[[abc|点我]]")).toEqual(["abc"]);
  });

  it("returns empty for no wikilinks", () => {
    expect(extractWikilinkTargets("纯文本")).toEqual([]);
  });
});

describe("wikilinksToMarkdownLinks", () => {
  const resolve = (target: string) =>
    target === "abc" ? { id: "abc", title: "目标笔记" } : null;

  it("rewrites resolved links and keeps broken ones as-is", () => {
    const out = wikilinksToMarkdownLinks("见 [[abc]] 与 [[missing]]", resolve);
    expect(out).toBe("见 [目标笔记](/notes/abc) 与 [[missing]]");
  });

  it("prefers the alias label when present", () => {
    const out = wikilinksToMarkdownLinks("[[abc|点我]]", resolve);
    expect(out).toBe("[点我](/notes/abc)");
  });

  it("falls back to the raw target when the title is missing", () => {
    const out = wikilinksToMarkdownLinks("[[abc]]", () => ({ id: "abc", title: null }));
    expect(out).toBe("[abc](/notes/abc)");
  });

  it("escapes brackets in labels", () => {
    const out = wikilinksToMarkdownLinks("[[abc]]", () => ({
      id: "abc",
      title: "a[b]c",
    }));
    expect(out).toBe("[a\\[b\\]c](/notes/abc)");
  });

  it("leaves fenced code blocks untouched", () => {
    const out = wikilinksToMarkdownLinks("```\n[[abc]]\n```", resolve);
    expect(out).toBe("```\n[[abc]]\n```");
  });
});
