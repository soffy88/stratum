"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/stores/auth";

const NAV_ITEMS = [
  { href: "/search", label: "搜索" },
  { href: "/discover", label: "发现" },
  { href: "/documents", label: "文档" },
  { href: "/feeds", label: "订阅源" },
  { href: "/timeline", label: "时光机" },
  { href: "/concepts", label: "概念" },
  { href: "/notes", label: "笔记" },
  { href: "/highlights", label: "高亮" },
  { href: "/views", label: "视图" },
  { href: "/ai", label: "AI" },
  { href: "/jobs", label: "任务" },
  { href: "/profile", label: "我的" },
  { href: "/admin", label: "管理" },
  { href: "/settings", label: "设置" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();

  return (
    <aside className="w-56 border-r border-[var(--color-border)] flex flex-col h-full">
      <div className="p-4 font-semibold text-lg">Stratum</div>
      <nav className="flex-1 px-2 space-y-1">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`block px-3 py-2 rounded text-sm ${
              pathname?.startsWith(item.href) ? "bg-[var(--color-border)] font-medium" : "hover:bg-[var(--color-border)]/50"
            }`}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="p-4 border-t border-[var(--color-border)] text-sm">
        <div className="text-[var(--color-muted)]">{user?.username}</div>
        <button onClick={() => logout()} className="text-[var(--color-muted)] hover:underline mt-1">
          退出
        </button>
      </div>
    </aside>
  );
}
