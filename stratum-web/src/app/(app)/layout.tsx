"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";
import { Sidebar } from "@/components/layout/Sidebar";
import { FeedbackWidget } from "@/components/shared/FeedbackWidget";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading, loadCurrentUser } = useAuthStore();
  const router = useRouter();

  useEffect(() => { loadCurrentUser(); }, [loadCurrentUser]);

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
