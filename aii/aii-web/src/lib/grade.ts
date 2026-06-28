import type { EpistemicGrade } from '@helios/blocks';

const _VALID_GRADES = new Set<string>([
  'proven', 'high', 'moderate', 'low', 'very_low',
  'unverified', 'contradicted', 'pending_verification',
]);

/** 将后端 grade 值规范化为合法 EpistemicGrade，未知值 fallback 到 'unverified'。 */
export function safeGrade(g: string | undefined | null): EpistemicGrade {
  return (g && _VALID_GRADES.has(g)) ? g as EpistemicGrade : 'unverified';
}
