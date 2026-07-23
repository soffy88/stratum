import { NextResponse, type NextRequest } from 'next/server';

// AII merge P3.2: inject the AII backend's X-API-Key server-side for the
// /api/aii/* proxy. Keeping the key in a plain server env (AII_API_KEY, NOT a
// NEXT_PUBLIC_* var) means it never reaches the browser bundle — more secure
// than AII's own client-exposed key.
export function middleware(req: NextRequest) {
  if (req.nextUrl.pathname.startsWith('/api/aii/')) {
    const key = process.env.AII_API_KEY ?? '';
    if (key) {
      const headers = new Headers(req.headers);
      headers.set('X-API-Key', key);
      return NextResponse.next({ request: { headers } });
    }
  }
  return NextResponse.next();
}

export const config = { matcher: '/api/aii/:path*' };
