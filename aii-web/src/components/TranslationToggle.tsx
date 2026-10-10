"use client";
import { useState } from "react";

interface Props {
  substrateId: string;
}

export function TranslationToggle({ substrateId }: Props) {
  const [showTranslation, setShowTranslation] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [done, setDone] = useState(false);

  async function toggle() {
    if (!showTranslation && !done) {
      setTranslating(true);
      const res = await fetch(`/api/v1/translate/substrate/${substrateId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_lang: "zh", provider: "qwen3" }),
        credentials: "include",
      });
      if (res.ok) setDone(true);
      setTranslating(false);
    }
    setShowTranslation((v) => !v);
  }

  return (
    <button
      onClick={toggle}
      disabled={translating}
      className="px-3 py-1 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-border)]/20 disabled:opacity-50"
    >
      {translating ? "翻译中…" : showTranslation ? "显示原文" : "中英对照"}
    </button>
  );
}
