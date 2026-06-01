"use client";
import { useState } from "react";

export function UploadButton() {
  const [uploading, setUploading] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  async function handleFiles(files: FileList) {
    setUploading(true);
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/v1/inbox/submit", {
        method: "POST",
        body: form,
        credentials: "include",
      });
      const data = await res.json();
      if (res.ok) {
        setLastResult(`✅ ${data.substrate_id} (${data.medium})`);
      } else {
        setLastResult(`❌ ${data.detail || "Upload failed"}`);
      }
    }
    setUploading(false);
  }

  return (
    <div
      className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:bg-[var(--color-border)]/10 transition"
      onDrop={(e) => {
        e.preventDefault();
        if (e.dataTransfer.files) handleFiles(e.dataTransfer.files);
      }}
      onDragOver={(e) => e.preventDefault()}
    >
      <input
        type="file"
        multiple
        hidden
        id="upload-input"
        onChange={(e) => {
          if (e.target.files) handleFiles(e.target.files);
        }}
      />
      <label htmlFor="upload-input" className="cursor-pointer select-none">
        {uploading ? "⏳ 上传中..." : "📁 点击上传 或拖拽文件到此处"}
      </label>
      {lastResult && (
        <p className="mt-2 text-sm text-[var(--color-muted)]">{lastResult}</p>
      )}
    </div>
  );
}
