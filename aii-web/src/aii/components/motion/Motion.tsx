/**
 * Motion 接入(基于 @helios/oui/motion,底层 anime.js v4,可选依赖)。
 *
 * 降级安全:未装 animejs 或 prefers-reduced-motion 时,
 *   - AnimatedNumber 直接显示终值(无滚动)
 *   - useStaggerReveal no-op(元素本就可见)
 * 不报错、不阻塞。装了 animejs 才启用动画。
 */
'use client';

import { useEffect, useRef } from 'react';
import { animateValue, staggerReveal } from '@helios/oui/motion';

/** KPI 数字滚动。未装 animejs / reduced-motion 时直接显示终值。 */
export function AnimatedNumber({
  value,
  duration = 1200,
  className,
}: {
  value: number;
  duration?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // animateValue 内部已处理 reduced-motion 与未装降级(直接 setText 终值)
    void animateValue(el, { from: 0, to: value, duration });
  }, [value, duration]);
  // SSR / 首帧:先放终值(千分位),避免闪烁;动画接管后覆盖
  return <span ref={ref} className={className}>{Math.round(value).toLocaleString()}</span>;
}

/**
 * 容器内子元素交错入场。传选择器(相对 document)或在 ref 容器上调用。
 * 未装 animejs / reduced-motion 时 no-op(元素保持可见)。
 */
export function useStaggerReveal(
  selector: string,
  deps: unknown[] = [],
  opts?: { delay?: number; translateY?: number },
) {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>(selector));
    if (els.length === 0) return;
    void staggerReveal(els, { delay: opts?.delay ?? 60, translateY: opts?.translateY ?? 12 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
