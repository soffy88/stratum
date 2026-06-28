/**
 * 轻量可信度标记 —— 视觉减负方案(AII-FRONTEND-BU-VISUAL-001)。
 *
 * 命门保留,但用更轻的方式表达:
 *   - GradeDot:小色点表达 grade 强弱(绿=强 / 灰=弱),hover 显示具体 grade,
 *     取代每条挂 OEpistemicBadge(图标+标签+框)。
 *   - stanceMeta:stance 立场 → 轻量文字前缀 + 左色条颜色,取代重标签框。
 *
 * 这些是否上提 blocks:GradeDot 这种"纯色点 + hover grade"很可能跨项目通用
 * (helivex SafeBadge 等),若 ≥2 项目要,再评估上提 blocks 的 OEpistemicBadge variant="dot"。
 * 本轮先落在 aii-web 页面层,不阻塞 BU 交付。
 */
import type { EpistemicGrade } from '@helios/blocks';

// grade → 颜色 + 中文标签(供 hover title)。色阶:强(绿/蓝)→ 弱(灰)→ 反证(红)。
const GRADE_META: Record<EpistemicGrade, { color: string; label: string }> = {
  proven:               { color: '#16a34a', label: '已证 proven' },
  high:                 { color: '#22c55e', label: '高 high' },
  moderate:             { color: '#0891b2', label: '中 moderate' },
  low:                  { color: '#d97706', label: '低 low' },
  very_low:             { color: '#a16207', label: '很低 very_low' },
  unverified:           { color: '#9ca3af', label: '未确证 unverified' },
  contradicted:         { color: '#dc2626', label: '被反证 contradicted' },
  pending_verification: { color: '#7c3aed', label: '待确证 pending' },
};

/** 行首小色点:绿=强 / 灰=弱 / 红=反证。hover 显示具体 grade。 */
export function GradeDot({ grade, size = 8 }: { grade: EpistemicGrade; size?: number }) {
  const m = GRADE_META[grade] ?? GRADE_META.unverified;
  return (
    <span
      role="img"
      aria-label={`可信度:${m.label}`}
      title={m.label}
      className="inline-block shrink-0 rounded-full align-middle"
      style={{ width: size, height: size, background: m.color }}
    />
  );
}

/** grade → 正文文字颜色(强论据正文更亮,弱论据更淡),做"颜色深浅"表达强弱的辅助。 */
export function gradeTextClass(grade: EpistemicGrade): string {
  switch (grade) {
    case 'proven':
    case 'high':
    case 'moderate':
      return 'text-[color:var(--foreground)]';            // 强:正常亮度
    case 'contradicted':
      return 'text-[color:var(--alert-error,#dc2626)]';   // 反证:红
    default:
      return 'text-[color:var(--text-secondary)]';        // 弱:偏淡
  }
}

/**
 * stance 立场 → 轻量表达:文字前缀 + 左色条颜色。
 * 不同 stance 用不同色条,读者一眼区分"书的主张" vs "事实" vs "观点"。
 * 从 stance_marker 文本推断类别(后端未来可给结构化 stance 字段,这里前向兼容)。
 */
export function stanceMeta(stanceMarker: string): { prefix: string; bar: string } {
  const s = stanceMarker || '';
  if (/主张|认为|提出|声称/.test(s)) {
    return { prefix: s.replace(/[:：]\s*$/, ''), bar: '#d97706' };  // 主张/观点 = 琥珀(提醒:这是立场)
  }
  if (/研究表明|实验|数据|证据/.test(s)) {
    return { prefix: s.replace(/[:：]\s*$/, ''), bar: '#0891b2' };  // 偏实证 = 青
  }
  if (/事实|定义|定理/.test(s)) {
    return { prefix: s.replace(/[:：]\s*$/, ''), bar: '#16a34a' };  // 事实/定义 = 绿
  }
  return { prefix: s, bar: 'var(--border)' };
}
