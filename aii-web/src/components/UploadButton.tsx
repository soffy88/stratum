"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api-client";

interface FileProgress {
  name: string;
  percent: number;
  status: "uploading" | "done" | "error";
  error?: string;
}

function uploadFileXHR(
  file: File,
  token: string | null,
  onProgress: (pct: number) => void,
): Promise<{ substrate_id: string; medium: string }> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v1/inbox/submit");
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.withCredentials = true;

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };

    xhr.onload = () => {
      let data: { substrate_id?: string; medium?: string; detail?: string } = {};
      try { data = JSON.parse(xhr.responseText); } catch { /* empty */ }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve({ substrate_id: data.substrate_id ?? "", medium: data.medium ?? "unknown" });
      } else {
        reject(new Error(data.detail ?? `HTTP ${xhr.status}`));
      }
    };

    xhr.onerror = () => reject(new Error("网络错误"));
    xhr.ontimeout = () => reject(new Error("上传超时"));
    xhr.send(form);
  });
}

export function UploadButton({ onSuccess }: { onSuccess?: () => void }) {
  const [files, setFiles] = useState<FileProgress[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(fileList: FileList) {
    const token = apiClient.getAccessToken();
    const items = Array.from(fileList);
    setFiles(items.map((f) => ({ name: f.name, percent: 0, status: "uploading" })));

    for (let i = 0; i < items.length; i++) {
      const file = items[i]!;
      try {
        const result = await uploadFileXHR(file, token, (pct) => {
          setFiles((prev) =>
            prev.map((p, j) => (j === i ? { ...p, percent: pct } : p)),
          );
        });
        setFiles((prev) =>
          prev.map((p, j) => (j === i ? { ...p, percent: 100, status: "done" } : p)),
        );
        toast.success(`已入库：${file.name}（${result.medium}）`);
        onSuccess?.();
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setFiles((prev) =>
          prev.map((p, j) =>
            j === i ? { ...p, status: "error", error: msg } : p,
          ),
        );
        toast.error(`上传失败：${file.name} — ${msg}`);
      }
    }

    // Clear progress list after a short delay so user can read results
    setTimeout(() => setFiles([]), 3000);
    if (inputRef.current) inputRef.current.value = "";
  }

  const isUploading = files.some((f) => f.status === "uploading");

  return (
    <div className="space-y-2">
      <div
        className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:bg-[var(--color-border)]/10 transition"
        onDrop={(e) => {
          e.preventDefault();
          if (e.dataTransfer.files.length) void handleFiles(e.dataTransfer.files);
        }}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => !isUploading && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          onChange={(e) => {
            if (e.target.files?.length) void handleFiles(e.target.files);
          }}
        />
        <span className="select-none text-sm text-[var(--color-muted)]">
          {isUploading ? "上传中..." : "📁 点击上传 或拖拽文件到此处"}
        </span>
      </div>

      {files.length > 0 && (
        <ul className="space-y-1.5 text-xs">
          {files.map((f, i) => (
            <li key={i} className="flex items-center gap-2">
              <span className="truncate max-w-[180px] text-[var(--color-muted)]">
                {f.name}
              </span>
              {f.status === "uploading" && (
                <div className="flex-1 bg-[var(--color-border)] rounded-full h-1.5 overflow-hidden">
                  <div
                    className="h-full bg-[var(--color-primary)] transition-all"
                    style={{ width: `${f.percent}%` }}
                  />
                </div>
              )}
              {f.status === "done" && (
                <span className="text-green-600">✓</span>
              )}
              {f.status === "error" && (
                <span className="text-red-500 truncate">{f.error}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
