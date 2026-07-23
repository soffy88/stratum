"use client";

import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useState } from "react";

interface Props {
  noteId: string;
}

export function ShareNoteButton({ noteId }: Props) {
  const [copied, setCopied] = useState(false);

  const createShare = useMutation({
    mutationFn: () =>
      apiClient.post<{ token: string; share_url: string }>(`/api/share/note/${noteId}`, {
        allow_anonymous: true,
      }),
    onSuccess: (data) => {
      const url = `${window.location.origin}${data.share_url}`;
      navigator.clipboard.writeText(url).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    },
  });

  return (
    <button
      onClick={() => createShare.mutate()}
      disabled={createShare.isPending}
      className="px-3 py-1.5 text-sm border border-[var(--color-border)] rounded hover:bg-[var(--color-border)]/30 disabled:opacity-50"
    >
      {copied ? "已复制链接 ✓" : createShare.isPending ? "生成中..." : "分享"}
    </button>
  );
}
