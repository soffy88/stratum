"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/stores/auth";
import { useMediaQuery } from "@/hooks/use-media-query";

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

function NavLinks({
  pathname,
  onClick,
}: {
  pathname: string | null;
  onClick?: () => void;
}) {
  return (
    <>
      {NAV_ITEMS.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          onClick={onClick}
          className={`block px-3 py-2.5 rounded text-sm min-h-[44px] flex items-center ${
            pathname?.startsWith(item.href)
              ? "bg-[var(--color-border)] font-medium"
              : "hover:bg-[var(--color-border)]/50"
          }`}
        >
          {item.label}
        </Link>
      ))}
    </>
  );
}

function MobileSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Top bar */}
      <header className="fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-4 h-12 bg-[var(--color-background)] border-b border-[var(--color-border)]">
        <span className="font-semibold text-base">Stratum</span>
        <button
          onClick={() => setOpen(true)}
          className="min-h-[44px] min-w-[44px] flex items-center justify-center text-xl"
          aria-label="打开菜单"
        >
          ☰
        </button>
      </header>

      {/* Spacer for fixed header */}
      <div className="h-12" />

      {/* Drawer overlay */}
      {open && (
        <div
          className="fixed inset-0 z-50 flex"
          onClick={() => setOpen(false)}
        >
          {/* Backdrop */}
          <div className="flex-1 bg-black/50" />
          {/* Drawer panel */}
          <div
            className="w-64 bg-[var(--color-background)] h-full flex flex-col overflow-y-auto shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-[var(--color-border)]">
              <span className="font-semibold">Stratum</span>
              <button
                onClick={() => setOpen(false)}
                className="text-xl min-h-[44px] min-w-[44px] flex items-center justify-center"
              >
                ×
              </button>
            </div>
            <nav className="flex-1 px-2 py-2 space-y-0.5">
              <NavLinks pathname={pathname} onClick={() => setOpen(false)} />
            </nav>
            <div className="p-4 border-t border-[var(--color-border)] text-sm">
              <div className="text-[var(--color-muted)]">{user?.username}</div>
              <button
                onClick={() => logout()}
                className="text-[var(--color-muted)] hover:underline mt-1 min-h-[44px] flex items-center"
              >
                退出
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function DesktopSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();

  return (
    <aside className="w-56 border-r border-[var(--color-border)] flex flex-col h-full">
      <div className="p-4 font-semibold text-lg">Stratum</div>
      <nav className="flex-1 px-2 space-y-0.5 overflow-y-auto">
        <NavLinks pathname={pathname} />
      </nav>
      <div className="p-4 border-t border-[var(--color-border)] text-sm">
        <div className="text-[var(--color-muted)]">{user?.username}</div>
        <button
          onClick={() => logout()}
          className="text-[var(--color-muted)] hover:underline mt-1"
        >
          退出
        </button>
      </div>
    </aside>
  );
}

export function Sidebar() {
  const isMobile = useMediaQuery("(max-width: 768px)");
  return isMobile ? <MobileSidebar /> : <DesktopSidebar />;
}
