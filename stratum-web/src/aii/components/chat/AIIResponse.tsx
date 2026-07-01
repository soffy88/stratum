/**
 * AIIResponse v2 — REQ-004 精简信息层级
 *
 * chitchat:    回答文本 + 底部一行小字
 * grounded:    回答文本 + ConfidenceMeter(紧凑) + citations + disclaimer(仅金融)
 * no_knowledge:回答文本 + 一行黄色警示
 *
 * 删掉:ModeTag(grounded 是正常模式不需标注) / confidence_basis 重复文字 / 
 *       no_knowledge 的 0% 可信度条
 * 红线保留:
 *   #1 grade→color 硬规范(OEpistemicBadge 内部)
 *   #2 defeaters 强制显示(OEpistemicCard 内部)
 *   #3 ORadarChart 无目标线(API 层)
 *   #6 降级不静默(DegradedBanner 在 ChatPage 层)
 */
'use client';

import type { ChatResponse, ChatCitation } from '@/aii/types/api';
import { OConfidenceMeter } from '@helios/blocks';
import { CitationsList } from './CitationsList';

export function AIIResponse({
  response,
  onCitationClick,
}: {
  response: ChatResponse;
  onCitationClick?: (c: ChatCitation) => void;
}) {
  const { mode, answer, epistemic_confidence, citations, disclaimer } = response;

  return (
    <div className={`aii-bubble-aii aii-response-${mode}`}>
      {/* 回答正文 — 所有 mode 都有 */}
      <p className="aii-response-text">{answer}</p>

      {/* grounded: 可信度条(紧凑) + citations */}
      {mode === 'grounded' && (
        <>
          <OConfidenceMeter
            value={epistemic_confidence}
            compact
            hideBasis
          />
          {citations.length > 0 && (
            <CitationsList citations={citations} onCitationClick={onCitationClick} />
          )}
          {disclaimer && (
            <div className="aii-response-disclaimer">
              <span aria-hidden>⚠</span>
              <span>{disclaimer}</span>
            </div>
          )}
        </>
      )}

      {/* chitchat: 底部一行小字 */}
      {mode === 'chitchat' && (
        <div className="aii-response-meta">
          一般性回答 · 非来自确证知识库
        </div>
      )}

      {/* no_knowledge: 黄色一行警示 */}
      {mode === 'no_knowledge' && (
        <div className="aii-response-meta" style={{ color: 'var(--warning, oklch(0.70 0.15 80))' }}>
          ⚠ 知识库未覆盖此问题
        </div>
      )}
    </div>
  );
}
