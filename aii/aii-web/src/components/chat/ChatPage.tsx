/**
 * ChatPage v2 — REQ-004 布局修复
 * aii-chat-layout: flex column, 高度 = 100dvh - topbar
 * aii-chat-history: flex-1 overflow-y-auto (滚动区)
 * aii-chat-input-bar: flex-shrink-0 fixed bottom (始终可见)
 */
'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import * as api from '@/lib/api-client';
import type { ChatCitation } from '@/types/api';
import { DegradedBanner } from '@/components/DegradedBanner';
import { ChatMessage, type ChatHistoryItem } from './ChatMessage';
import { ChatInput } from './ChatInput';

let seq = 0;
const uid = () => `m${++seq}-${Date.now().toString(36)}`;

export function ChatPage() {
  const router   = useRouter();
  const [history,  setHistory]  = useState<ChatHistoryItem[]>([]);
  const [degraded, setDegraded] = useState(false);
  const [inFlight, setInFlight] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [history]);

  const send = useCallback(async (message: string) => {
    const uid1 = uid(), uid2 = uid();
    setHistory(h => [...h, { role: 'user', id: uid1, content: message }, { role: 'aii-loading', id: uid2 }]);
    setInFlight(true);
    const result = await api.chat({ message });
    setDegraded(result.degraded);
    setHistory(h => h.map(it => it.id !== uid2 ? it
      : result.ok && result.data
        ? { role: 'aii',       id: it.id, response: result.data }
        : { role: 'aii-error', id: it.id, error: result.error ?? '请求失败' }
    ));
    setInFlight(false);
  }, []);

  const onCitationClick = useCallback((c: ChatCitation) => {
    router.push(`/query?ku=${encodeURIComponent(c.ku_id)}`);
  }, [router]);

  return (
    <div className="aii-chat-layout">

      {/* 降级 banner */}
      {degraded && (
        <div style={{ padding: 'var(--space-3, 12px) 0 0' }}>
          <DegradedBanner />
        </div>
      )}

      {/* 滚动历史区 */}
      <div className="aii-chat-history" role="log" aria-live="polite">
        {history.length === 0 && (
          <div style={{
            flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--muted-foreground)', fontSize: 'var(--text-sm)',
            textAlign: 'center', padding: 'var(--space-12, 48px) 0',
          }}>
            <div>
              <div style={{ fontSize: '2rem', marginBottom: 'var(--space-3)' }}>◎</div>
              <div style={{ fontWeight: 600, marginBottom: 'var(--space-1)' }}>AII 认识论外脑</div>
              <div style={{ opacity: 0.7, fontSize: 'var(--text-xs)' }}>每个回答都告诉你"这有多可信、基于什么"</div>
            </div>
          </div>
        )}
        {history.map(item => (
          <ChatMessage key={item.id} item={item} onCitationClick={onCitationClick} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* 固定底部输入框 */}
      <div className="aii-chat-input-bar">
        <ChatInput onSubmit={send} disabled={inFlight} />
      </div>

    </div>
  );
}
