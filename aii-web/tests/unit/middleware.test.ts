// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { _clearAuthCache, middleware, normalizePath, requiresAdmin } from '@/middleware';

const BASE = 'https://aiinote.com';

function req(path: string, init: { method?: string; headers?: Record<string, string> } = {}) {
  return new NextRequest(new URL(path, BASE), { method: init.method ?? 'GET', headers: init.headers });
}

describe('aii BFF middleware (security audit 🔴1)', () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    _clearAuthCache();
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
    process.env.AII_API_KEY = 'admin-key';
    process.env.STRATUM_API_BASE = 'http://auth.test';
    delete process.env.ADMIN_SECRET;
  });
  afterEach(() => vi.unstubAllGlobals());

  it('anonymous request gets 401 and no key, without calling the auth backend', async () => {
    const res = await middleware(req('/api/aii/api/stats/overview'));
    expect(res.status).toBe(401);
    expect(res.headers.get('x-middleware-request-x-api-key')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('upper-case path variant is also guarded', async () => {
    const res = await middleware(req('/API/AII/api/stats/overview'));
    expect(res.status).toBe(401);
  });

  it('invalid refresh cookie gets 401', async () => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 401 }));
    const res = await middleware(req('/api/aii/api/chat', { method: 'POST', headers: { cookie: 'refresh_token=bad' } }));
    expect(res.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledWith('http://auth.test/api/auth/refresh', expect.objectContaining({ method: 'POST' }));
  });

  it('auth backend error fails closed', async () => {
    fetchMock.mockRejectedValue(new Error('down'));
    const res = await middleware(req('/api/aii/api/stats/overview', { headers: { cookie: 'refresh_token=x' } }));
    expect(res.status).toBe(401);
  });

  it('valid session injects the key', async () => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));
    const res = await middleware(req('/api/aii/api/stats/overview', { headers: { cookie: 'refresh_token=good', 'x-api-key': 'spoof' } }));
    expect(res.status).toBe(200);
    expect(res.headers.get('x-middleware-request-x-api-key')).toBe('admin-key');
  });

  it('valid bearer token is checked via /api/auth/me', async () => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));
    const res = await middleware(req('/api/aii/api/ku/list', { headers: { authorization: 'Bearer tok' } }));
    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith('http://auth.test/api/auth/me', expect.anything());
  });

  it.each([
    ['DELETE', '/api/aii/api/source/abc?dry_run=false'],
    ['DELETE', '/api/aii/api/ku/123'],
    ['DELETE', '/api/aii//api/%73ource/abc'],
    ['POST', '/api/aii/api/pipelines/p1/start'],
    ['POST', '/api/aii/api/pipelines/p1/stop'],
    ['PUT', '/api/aii/api/classify/config'],
  ])('logged-in non-admin %s %s gets 403', async (method, path) => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));
    const res = await middleware(req(path, { method, headers: { cookie: 'refresh_token=good' } }));
    expect(res.status).toBe(403);
  });

  it('admin secret unlocks admin-only routes when ADMIN_SECRET is configured', async () => {
    process.env.ADMIN_SECRET = 's3cret';
    fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));
    const res = await middleware(req('/api/aii/api/ku/1', { method: 'DELETE', headers: { cookie: 'refresh_token=good', 'x-admin-secret': 's3cret' } }));
    expect(res.status).toBe(200);
    const wrong = await middleware(req('/api/aii/api/ku/1', { method: 'DELETE', headers: { cookie: 'refresh_token=good', 'x-admin-secret': 'nope!!' } }));
    expect(wrong.status).toBe(403);
  });

  it('path helpers', () => {
    expect(normalizePath('/api/aii/api/x/../source/1')).toBe('/api/aii/api/source/1');
    expect(requiresAdmin('GET', '/api/aii/api/source/1')).toBe(false);
    expect(requiresAdmin('delete', '/api/aii/api/source/1')).toBe(true);
  });
});
