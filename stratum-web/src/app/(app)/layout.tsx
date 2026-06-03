"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth";
import { Sidebar } from "@/components/layout/Sidebar";
import { FeedbackWidget } from "@/components/shared/FeedbackWidget";
import { wsClient } from "@/lib/ws-client";
import { apiClient } from "@/lib/api-client";

const WS_TOAST_MESSAGES: Record<string, string> = {
  note_create: "笔记已创建",
  note_update: "笔记已更新",
  note_delete: "笔记已删除",
  substrate_pin: "已置顶",
  substrate_unpin: "已取消置顶",
  concept_create: "概念已创建",
  concept_update: "概念已更新",
  concept_delete: "概念已删除",
  agent_run_completed: "Agent 执行完成",
  agent_run_failed: "Agent 执行失败",
  highlight_create: "高亮已创建",
  highlight_delete: "高亮已删除",
  view_create: "视图已创建",
  view_default_changed: "默认视图已切换",
};

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading, loadCurrentUser } = useAuthStore();
  const router = useRouter();

  useEffect(() => { loadCurrentUser(); }, [loadCurrentUser]);

  useEffect(() => {
    if (!user) return;
    const token = apiClient.getAccessToken();
    if (!token) return;

    wsClient.connect(token);
    const unsub = wsClient.on("*", (event) => {
      const message = WS_TOAST_MESSAGES[event.event_type] ?? `事件: ${event.event_type}`;
      if (event.event_type === "agent_run_failed") {
        toast.error(message);
      } else {
        toast.success(message);
      }
    });

    return () => {
      unsub();
      wsClient.disconnect();
    };
  }, [user]);

  if (isLoading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>;
  }
  if (!user) {
    router.replace("/login");
    return null;
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6">{children}</main>
      <FeedbackWidget />
    </div>
  );
}
