import { NextResponse, type NextRequest } from 'next/server';

// AII merge P3.2: inject the AII backend's X-API-Key server-side for the
// /api/aii/* proxy. Keeping the key in a plain server env (AII_API_KEY, NOT a
// NEXT_PUBLIC_* var) means it never reaches the browser bundle.
//
// Security audit 2026-10-17 (🔴1): the key is an admin key, so it is injected
// ONLY for a logged-in user. Login is verified against the auth backend
// (stratum-api): a Bearer access token via /api/auth/me, or the httpOnly
// refresh_token cookie via /api/auth/refresh (validates the session row:
// not revoked, not expired, user exists). Anonymous requests get 401.
// Destructive / operational endpoints are admin-only at the BFF layer; admin
// = X-Admin-Secret matching ADMIN_SECRET (same mechanism as /api/admin/*).
// If ADMIN_SECRET is unset in this container they are simply refused (403).

const AUTH_CACHE_TTL_MS = 60_000;
const AUTH_CACHE_MAX = 5_000;
const authCache = new Map<string, number>(); // sha256(credential) -> expiry ms

/** [method, pattern] pairs that require admin at the BFF layer. */
const ADMIN_ONLY: ReadonlyArray<readonly [string, RegExp]> = [
  ['DELETE', /^\/api\/aii\/api\/source(\/|$)/],
  ['DELETE', /^\/api\/aii\/api\/ku(\/|$)/],
  ['POST', /^\/api\/aii\/api\/pipelines\/[^/]+\/(start|stop)\/?$/],
  ['PUT', /^\/api\/aii\/api\/classify\/config\/?$/],
];

/** Decode + collapse slashes + resolve dot segments so encodings can't dodge ADMIN_ONLY. */
export function normalizePath(pathname: string): string {
  let p = pathname;
  for (let i = 0; i < 3; i++) {
    try {
      const d = decodeURIComponent(p);
      if (d === p) break;
      p = d;
    } catch {
      break;
    }
  }
  p = p.replace(/\\/g, '/').replace(/\/{2,}/g, '/');
  const out: string[] = [];
  for (const seg of p.split('/')) {
    if (seg === '..') out.pop();
    else if (seg !== '.') out.push(seg);
  }
  const joined = out.join('/');
  return (joined.startsWith('/') ? joined : `/${joined}`).toLowerCase();
}

export function requiresAdmin(method: string, pathname: string): boolean {
  const m = method.toUpperCase();
  const p = normalizePath(pathname);
  return ADMIN_ONLY.some(([am, re]) => am === m && re.test(p));
}

function safeEqual(a: string, b: string): boolean {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function isAdmin(req: NextRequest): boolean {
  const secret = process.env['ADMIN_SECRET'] ?? '';
  return safeEqual(req.headers.get('x-admin-secret') ?? '', secret);
}

async function sha256(s: string): Promise<string> {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('');
}

function authBase(): string {
  return (process.env['STRATUM_API_BASE'] || 'http://stratum-api:9302').replace(/\/$/, '');
}

/** True when the request carries a valid login (fail-closed on any error). */
export async function isLoggedIn(req: NextRequest): Promise<boolean> {
  const bearer = req.headers.get('authorization') ?? '';
  const refresh = req.cookies.get('refresh_token')?.value ?? '';
  const hasBearer = /^Bearer\s+\S+/i.test(bearer);
  if (!hasBearer && !refresh) return false;

  const cacheKey = await sha256(hasBearer ? `b:${bearer}` : `r:${refresh}`);
  const now = Date.now();
  const exp = authCache.get(cacheKey);
  if (exp && exp > now) return true;
  if (exp) authCache.delete(cacheKey);

  let ok = false;
  try {
    const res = hasBearer
      ? await fetch(`${authBase()}/api/auth/me`, {
          headers: { Authorization: bearer },
          cache: 'no-store',
        })
      : await fetch(`${authBase()}/api/auth/refresh`, {
          method: 'POST',
          headers: { Cookie: `refresh_token=${refresh}` },
          cache: 'no-store',
        });
    ok = res.ok;
  } catch {
    ok = false;
  }
  if (ok) {
    if (authCache.size >= AUTH_CACHE_MAX) authCache.clear();
    authCache.set(cacheKey, now + AUTH_CACHE_TTL_MS);
  }
  return ok;
}

/** Test hook. */
export function _clearAuthCache(): void {
  authCache.clear();
}

function deny(status: 401 | 403, detail: string): NextResponse {
  return NextResponse.json({ detail }, { status });
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  // Next route matching is case-insensitive by default, so compare that way too.
  if (!/^\/api\/aii(\/|$)/i.test(normalizePath(pathname))) return NextResponse.next();

  if (!(await isLoggedIn(req))) return deny(401, 'Authentication required');
  if (requiresAdmin(req.method, pathname) && !isAdmin(req)) {
    return deny(403, 'Admin only');
  }

  const headers = new Headers(req.headers);
  headers.delete('x-admin-secret');
  const key = process.env['AII_API_KEY'] ?? '';
  if (key) headers.set('X-API-Key', key);
  else headers.delete('x-api-key');
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: '/api/aii/:path*' };
