"use client";

interface Props {
  contentId: string;
  children: string;
}

const COLORS = ["yellow", "green", "blue", "red"] as const;

export function TextHighlighter({ contentId, children }: Props) {
  async function handleMouseUp() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.toString().trim()) return;

    const text = sel.toString();
    const color = window.prompt(
      `高亮颜色 (${COLORS.join(" / ")})`,
      "yellow"
    );
    if (!color) return;
    const note = window.prompt("附注（可选）") ?? undefined;

    await fetch("/api/v1/highlights", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content_id: contentId,
        anchor: { char_start: 0, char_end: text.length, text },
        color,
        note: note || undefined,
      }),
      credentials: "include",
    });
  }

  return (
    <div onMouseUp={handleMouseUp} className="prose cursor-text select-text">
      {children}
    </div>
  );
}
