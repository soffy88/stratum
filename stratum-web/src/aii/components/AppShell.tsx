/**
 * AppShell v3 — 三态 sidebar:展开 / 折叠(图标栏) / 隐藏
 *
 * Topbar 左侧按钮循环切换:
 *   隐藏 → 点击 → 展开
 *   展开 → 点击 → 折叠
 *   折叠 → 点击 → 隐藏
 *
 * Sidebar 右边缘 resize handle:拖动自由调整宽度(oui 1.0.0 新增)
 */
'use client';

import { useState, useCallback, type ReactNode } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { OAppShell, type SideBarNavItem } from '@helios/oui';
import { ENV_BADGE, USE_MOCK } from '@/aii/lib/env';

const NAV_ITEMS: SideBarNavItem[] = [
  { id: 'dashboard',  label: '概览',   icon: '📊', href: '/dashboard' },
  { id: 'knowledge',  label: '知识库', icon: '📚', href: '/knowledge' },
  { id: 'graph',      label: '图谱',   icon: '🕸️', href: '/graph' },
  { id: 'clusters',   label: '知识簇', icon: '🧩', href: '/clusters' },
  { id: 'books',      label: '书级理解', icon: '📖', href: '/book' },
  { id: 'chat',       label: '对话',   icon: '💬', href: '/chat' },
  { id: 'query',      label: '查询',   icon: '🔍', href: '/query' },
  { id: 'ingest',     label: '摄入',   icon: '📥', href: '/ingest' },
  { id: 'health',     label: '图健康', icon: '💚', href: '/health' },
  { id: 'diagnose',   label: '诊断',   icon: '🔬', href: '/diagnose' },
  { id: 'evolution',  label: '进化',   icon: '🧬', href: '/evolution' },
  { id: 'governance', label: '治理',   icon: '⚖️', href: '/governance' },
];

function activeId(pathname: string) {
  return pathname.split('/').filter(Boolean)[0] ?? 'chat';
}

type SidebarState = 'full' | 'collapsed' | 'hidden';

export function AppShell({ children }: { children: ReactNode }) {
  const router   = useRouter();
  const pathname = usePathname() ?? '/chat';

  // 三态
  const [state, setState] = useState<SidebarState>('full');

  const cycleState = useCallback(() => {
    setState(s =>
      s === 'full'      ? 'collapsed' :
      s === 'collapsed' ? 'hidden'    : 'full'
    );
  }, []);

  const collapsed = state === 'collapsed';
  const hidden    = state === 'hidden';

  // 图标
  const menuIcon = hidden ? '▶' : state === 'collapsed' ? '▶' : '☰';
  const menuTitle =
    hidden    ? '展开侧栏' :
    collapsed ? '隐藏侧栏' : '折叠侧栏';

  return (
    <OAppShell
      topbarProps={{
        title: 'AII',
        logo: (
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2, 8px)' }}>
            <button
              type="button"
              onClick={cycleState}
              title={menuTitle}
              aria-label={menuTitle}
              style={{
                display: 'flex', flexDirection: 'column', justifyContent: 'center',
                gap: '4px', padding: '6px',
                background: 'none', border: 'none', cursor: 'pointer',
                borderRadius: 'var(--radius, 0.5rem)',
                color: 'var(--muted-foreground)',
                transition: 'background var(--duration-fast, 100ms), color var(--duration-fast, 100ms)',
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--muted)'; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'none'; }}
            >
              {[0,1,2].map(i => (
                <span key={i} style={{ display: 'block', width: '18px', height: '2px', background: 'currentColor', borderRadius: '1px' }} />
              ))}
            </button>
            <span style={{ fontWeight: 700, fontSize: 'var(--text-sm)', letterSpacing: 'var(--ls-snug)' }}>
              AII
            </span>
          </div>
        ),
        actionsSlot: (
          <span
            className={[
              'text-xs px-2 py-0.5 rounded-full border font-medium',
              USE_MOCK
                ? 'border-warning text-warning'
                : 'border-border text-muted-foreground',
            ].join(' ')}
          >
            {ENV_BADGE}
          </span>
        ),
      }}
      sidebarProps={{
        items: NAV_ITEMS,
        activeId: activeId(pathname),
        onItemClick: (item) => item.href && router.push(item.href),
      }}
      sidebarCollapsed={collapsed}
      sidebarHidden={hidden}
      onSidebarCollapsedChange={(v) => setState(v ? 'collapsed' : 'full')}
      onSidebarHiddenChange={(v) => setState(v ? 'hidden' : 'full')}
    >
      {children}
    </OAppShell>
  );
}
