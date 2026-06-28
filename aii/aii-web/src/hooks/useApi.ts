/**
 * useApi — 调 API 的通用 hook。
 *
 * 红线 #6 实现:
 *   返回的 { degraded } 已经从 apiClient 包过,Page 只需 `if (state.degraded) ...`
 *   推荐用 <DegradedBanner /> 组件统一渲染(layout 已含)。
 *
 * 用法:
 *   const [state, run] = useApi(query);
 *   const onSubmit = () => run({ query: '...' });
 *   if (state.loading) ...
 *   if (state.error) ...
 *   if (state.data) ...
 *   {state.degraded && <DegradedBanner />}
 */
'use client';

import { useCallback, useState } from 'react';
import type { ApiResult } from '@/types/api';

export interface ApiState<T> {
  loading: boolean;
  data: T | null;
  error: string | null;
  /** warning === "degraded_no_provider" 时为 true */
  degraded: boolean;
}

const initial: ApiState<unknown> = {
  loading: false,
  data: null,
  error: null,
  degraded: false,
};

export function useApi<Req, Res>(
  fn: (req: Req) => Promise<ApiResult<Res>>
): [ApiState<Res>, (req: Req) => Promise<ApiResult<Res>>] {
  const [state, setState] = useState<ApiState<Res>>(initial as ApiState<Res>);

  const run = useCallback(
    async (req: Req) => {
      setState((s) => ({ ...s, loading: true, error: null }));
      const result = await fn(req);
      setState({
        loading: false,
        data: result.ok ? (result.data as Res) : null,
        error: result.ok ? null : result.error ?? 'Unknown error',
        degraded: result.degraded,
      });
      return result;
    },
    [fn]
  );

  return [state, run];
}

/**
 * 无参变体 — 给 GET 类(GraphHealth / Evolution)用。
 */
export function useApiNoArg<Res>(
  fn: () => Promise<ApiResult<Res>>
): [ApiState<Res>, () => Promise<ApiResult<Res>>] {
  const [state, setState] = useState<ApiState<Res>>(initial as ApiState<Res>);

  const run = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    const result = await fn();
    setState({
      loading: false,
      data: result.ok ? (result.data as Res) : null,
      error: result.ok ? null : result.error ?? 'Unknown error',
      degraded: result.degraded,
    });
    return result;
  }, [fn]);

  return [state, run];
}
