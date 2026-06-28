'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Search, Compass, FileText, Rss, Clock, Network, StickyNote,
  Highlighter, LayoutGrid, Share2, Sparkles, CheckSquare, User, Shield, Settings,
  Menu, PanelLeftClose, Brain, Layers, TrendingUp, ShieldCheck, Gauge, Sun, Moon,
  Library,
} from 'lucide-react';
import { create } from 'zustand';
import { getTheme, setTheme, type Theme } from '@/lib/theme';

/* Global collapsible-sidebar state — a module-level singleton so the (app) and
   (aii) layouts share one open/closed value across navigation. Persisted to
   localStorage; defaults open on desktop, closed on mobile. */
const SIDEBAR_KEY = 'stratum-sidebar-open';
export const useSidebarStore = create<{
  open: boolean;
  toggle: () => void;
  close: () => void;
  init: () => void;
}>((set) => ({
  open: true, // SSR default; corrected by init() on mount
  toggle: () => set((s) => {
    const open = !s.open;
    if (typeof window !== 'undefined') localStorage.setItem(SIDEBAR_KEY, open ? '1' : '0');
    return { open };
  }),
  close: () => {
    if (typeof window !== 'undefined') localStorage.setItem(SIDEBAR_KEY, '0');
    set({ open: false });
  },
  init: () => {
    if (typeof window === 'undefined') return;
    const saved = localStorage.getItem(SIDEBAR_KEY);
    set({ open: saved !== null ? saved === '1' : window.innerWidth >= 768 });
  },
}));

function ThemeToggle() {
  const [theme, setThemeState] = useState<Theme>('zen');
  useEffect(() => { setThemeState(getTheme()); }, []);
  const isDark = theme === 'dark';
  const toggle = () => {
    const next: Theme = isDark ? 'light' : 'dark';
    setTheme(next);
    setThemeState(next);
  };
  return (
    <button onClick={toggle}
      className="flex items-center gap-3 px-3 rounded-lg text-sm min-h-11 w-full text-foreground hover:bg-muted">
      {isDark ? <Sun className="w-4 h-4 shrink-0" /> : <Moon className="w-4 h-4 shrink-0" />}
      {isDark ? '亮色模式' : '暗色模式'}
    </button>
  );
}

interface NavItem { href: string; label: string; icon: React.ComponentType<{ className?: string }>; }
interface NavGroup { title?: string; items: NavItem[]; }

const NAV: NavGroup[] = [
  { items: [
    { href: '/search', label: '搜索', icon: Search },
    { href: '/discover', label: '发现', icon: Compass },
  ] },
  { title: '知识获取', items: [
    { href: '/documents', label: '文档', icon: FileText },
    { href: '/feeds', label: '订阅源', icon: Rss },
  ] },
  { title: '知识整理', items: [
    { href: '/highlights', label: '高亮', icon: Highlighter },
    { href: '/notes', label: '笔记', icon: StickyNote },
    { href: '/concepts', label: '概念', icon: Network },
    { href: '/graph', label: '知识图谱', icon: Share2 },  // 新增
  ] },
  { title: '视图', items: [
    { href: '/views', label: '视图', icon: LayoutGrid },
    { href: '/timeline', label: '时光机', icon: Clock },
  ] },
  { title: 'AI', items: [
    { href: '/ai', label: 'AI 助手', icon: Sparkles },
  ] },
  { title: 'AII 认知引擎', items: [
    { href: '/dashboard', label: '认知看板', icon: Gauge },
    { href: '/books', label: '书单元', icon: Library },
    { href: '/knowledge', label: '知识单元', icon: Brain },
    { href: '/clusters', label: '知识簇', icon: Layers },
    { href: '/evolution', label: '演化', icon: TrendingUp },
    { href: '/governance', label: '治理', icon: ShieldCheck },
  ] },
  { title: '系统', items: [
    { href: '/jobs', label: '定时任务', icon: CheckSquare },
    { href: '/profile', label: '我的', icon: User },
    { href: '/admin', label: '管理', icon: Shield },
    { href: '/settings', label: '设置', icon: Settings },
  ] },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-4 p-3">
      {NAV.map((group, gi) => (
        <div key={gi} className="flex flex-col gap-0.5">
          {group.title && (
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-3 mb-1">
              {group.title}
            </div>
          )}
          {group.items.map(item => {
            const active = pathname === item.href || pathname.startsWith(item.href + '/');
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} onClick={onNavigate}
                className={`flex items-center gap-3 px-3 rounded-lg text-sm min-h-11 transition-colors
                  ${active ? 'bg-primary/10 text-primary font-medium' : 'text-foreground hover:bg-muted'}`}>
                <Icon className="w-4 h-4 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export function Sidebar() {
  const { open, toggle, close, init } = useSidebarStore();

  // Resolve the persisted/screen-aware initial state once on mount.
  useEffect(() => { init(); }, [init]);

  // On mobile the sidebar is an overlay — close it after navigating.
  const handleNav = () => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) close();
  };

  return (
    <>
      {/* 打开按钮 — 仅在收起时显示,固定左上(桌面+移动都可用) */}
      {!open && (
        <button
          onClick={toggle}
          className="fixed top-3 left-3 z-50 p-2 rounded-lg bg-background border min-h-11 min-w-11 flex items-center justify-center shadow-sm"
          aria-label="打开侧栏"
        >
          <Menu className="w-5 h-5" />
        </button>
      )}

      {/* 移动端遮罩 */}
      {open && <div className="md:hidden fixed inset-0 bg-black/40 z-30" onClick={close} />}

      {/* 侧栏:移动端 fixed 浮层;桌面 static 占位(收起时整条消失,主内容铺满) */}
      <aside
        className={`${open ? 'translate-x-0' : '-translate-x-full md:hidden'}
          fixed md:static inset-y-0 left-0 z-40 w-72 md:w-60 shrink-0
          h-dvh border-r bg-card overflow-y-auto transition-transform duration-200`}
      >
        <div className="flex items-center justify-between px-5 py-4">
          <span className="font-bold text-lg">Stratum</span>
          <button
            onClick={toggle}
            className="p-2 min-h-11 min-w-11 flex items-center justify-center rounded-lg hover:bg-muted"
            aria-label="收起侧栏"
          >
            <PanelLeftClose className="w-5 h-5" />
          </button>
        </div>
        <NavLinks onNavigate={handleNav} />
        <div className="px-3 pb-4"><ThemeToggle /></div>
      </aside>
    </>
  );
}
