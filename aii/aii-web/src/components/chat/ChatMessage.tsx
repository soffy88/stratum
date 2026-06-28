'use client';

import type { ChatResponse, ChatCitation } from '@/types/api';
import { AIIResponse } from './AIIResponse';

export type ChatHistoryItem =
  | { role: 'user';        id: string; content: string }
  | { role: 'aii';         id: string; response: ChatResponse }
  | { role: 'aii-loading'; id: string }
  | { role: 'aii-error';   id: string; error: string };

export function ChatMessage({
  item,
  onCitationClick,
}: {
  item: ChatHistoryItem;
  onCitationClick?: (c: ChatCitation) => void;
}) {
  if (item.role === 'user') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <div className="aii-bubble-user">{item.content}</div>
      </div>
    );
  }

  if (item.role === 'aii-loading') {
    return (
      <div className="aii-skeleton">
        <div className="aii-skeleton-line" style={{ width: '80%' }} />
        <div className="aii-skeleton-line" style={{ width: '60%' }} />
        <div className="aii-skeleton-line" style={{ width: '70%' }} />
      </div>
    );
  }

  if (item.role === 'aii-error') {
    return (
      <div
        role="alert"
        className="aii-response-meta"
        style={{ color: 'var(--destructive)' }}
      >
        ⚠ {item.error}
      </div>
    );
  }

  return <AIIResponse response={item.response} onCitationClick={onCitationClick} />;
}
