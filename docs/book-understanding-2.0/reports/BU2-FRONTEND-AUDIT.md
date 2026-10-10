# BU2-FRONTEND-INTEGRATION-001: Frontend Audit

## 1. Frontend Framework
- **Framework**: Next.js 14 (App Router) with React 18
- **Language**: TypeScript
- **UI Components**: Custom components + `@helios/blocks` (external component library)
- **State Management**: Zustand (stores in `src/stores/`)
- **Data Fetching**: Custom `useApi` hook + `apiClient` (Axios-like wrapper)
- **Auth**: JWT access token + httpOnly refresh cookie

## 2. Frontend Entry Points
- **App Root**: `src/app/layout.tsx` → providers (Auth, QueryClient, UI)
- **Route Groups**: 
  - `(aii)` — AII-specific pages (books, knowledge, chat, etc.)
  - `(app)` — General app pages (documents, notes, graph, etc.)
  - `(auth)` — Auth pages

## 3. Router
- **File-based routing** (Next.js App Router)
- **Existing BU-related routes**:
  - `/books` — `src/app/(aii)/books/page.tsx` (Book Understanding list + detail panel)
  - `/knowledge` — `src/app/(aii)/knowledge/page.tsx` (Knowledge graph, KU, KC)
  - No chapter-level BU page
  - No cross-book (P14) pages

## 4. API Client
- **Location**: `src/lib/api-client.ts` + `src/lib/apiClient.ts`
- **Base URL**: `NEXT_PUBLIC_AII_API_BASE` (defaults to `/api`)
- **Auth**: Bearer token in memory, refresh via `/api/auth/refresh`
- **Error Handling**: `ApiResult<T>` envelope with `ok`, `data`, `error`, `degraded`, `warning`
- **Mock Mode**: `NEXT_PUBLIC_USE_MOCK=true` uses `mock-data.ts`

## 5. Book Understanding Page (`/books`)
**Current State** (`src/app/(aii)/books/page.tsx`):
- ✅ Lists BUs from `/api/bu/list` (mock: 11 items)
- ✅ Detail panel from `/api/bu/{id}` (mock: claims, arguments, structure, concepts)
- ✅ Grade dots, stance markers, evidence grades
- ✅ LearningLayer component (paths + deep cards)
- ❌ **Backend APIs not implemented** — all mock data
- ❌ Chapter-level BU detail missing
- ❌ P13 synthesis missing
- ❌ Provenance tracing missing

## 6. Existing BU UI Components
| Component | Status |
|-----------|--------|
| `BuDetailPanel` | Mock-only, in books/page.tsx |
| `GradeDot` / `GradeMarkers` | ✅ Reusable |
| `LearningLayer` | ✅ Reusable (paths + cards) |
| `StanceMeta` | ✅ Reusable |
| `OEmptyState` / `OLoadingState` / `OErrorState` | ✅ From `@helios/blocks` |

## 7. BU2 API (Backend)
**Current State**: 
- **NO dedicated BU2 API routes** in `src/stratum/api/routers/`
- **BU2 Service Layer**: `BU2Query` in `src/stratum/services/bu_v2_query.py` — reads from `book_understandings_v2` + `book_syntheses`
- **BU2 Entrypoint**: `BU2Runner` in `src/stratum/services/bu_v2_entrypoint.py` — runs full P10 pipeline
- **Cross-Book (P14)**: `BU2P14Runner` in `src/stratum/services/bu_v2_crossbook_entrypoint.py`
- **Expression Generator**: `BU2CrossBookExpressionGenerator` in `src/stratum/services/bu_v2_crossbook_expression.py`

**Database Tables**:
- `stratum.book_understandings_v2` (BU2 authority)
- `stratum.book_syntheses` (P13 synthesis)
- `stratum.chapter_understandings` (P12 chapter results)
- `stratum.crossbook_understandings` (P14 derived authority)

## 8. P14 API (Backend)
**Current State**:
- **NO dedicated P14 API routes**
- **P14 Service Layer**: Complete pipeline in `bu_v2_crossbook_entrypoint.py`
- **Query Interface**: `BU2CrossBookQuery` in `src/stratum/services/bu_v2_crossbook_query.py`

## 9. Missing Routes (Backend API)
| Route | Purpose | Status |
|-------|---------|--------|
| `GET /api/v1/bu/list` | List all BUs | ❌ Missing |
| `GET /api/v1/bu/{run_id}` | BU detail | ❌ Missing |
| `GET /api/v1/bu/{run_id}/chapters` | Chapter list | ❌ Missing |
| `GET /api/v1/bu/{run_id}/chapters/{chapter_id}` | Chapter detail | ❌ Missing |
| `GET /api/v1/bu/{run_id}/synthesis` | P13 synthesis | ❌ Missing |
| `GET /api/v1/cross-books/{collection_id}` | Cross-book overview | ❌ Missing |
| `GET /api/v1/cross-books/{collection_id}/concepts` | Concept relations | ❌ Missing |
| `GET /api/v1/cross-books/{collection_id}/theses` | Thesis relations | ❌ Missing |
| `GET /api/v1/cross-books/{collection_id}/arguments` | Argument relations | ❌ Missing |
| `GET /api/v1/cross-books/{collection_id}/contradictions` | Contradictions | ❌ Missing |
| `GET /api/v1/cross-books/{collection_id}/gaps` | Knowledge gaps | ❌ Missing |
| `GET /api/v1/cross-books/{collection_id}/synthesis` | Cross-book synthesis | ❌ Missing |
| `GET /api/v1/cross-books/{collection_id}/expression` | Human-readable expression | ❌ Missing |
| `GET /api/v1/cross-books/{collection_id}/pairwise` | Pairwise comparison | ❌ Missing |

## 10. Missing Frontend Pages
| Page | Route | Status |
|------|-------|--------|
| Chapter BU Detail | `/books/[id]/chapters/[chapterId]` | ❌ Missing |
| Cross-Book Overview | `/cross-books/[collectionId]` | ❌ Missing |
| Cross-Book Concepts | `/cross-books/[collectionId]/concepts` | ❌ Missing |
| Cross-Book Contradictions | `/cross-books/[collectionId]/contradictions` | ❌ Missing |
| Cross-Book Gaps | `/cross-books/[collectionId]/gaps` | ❌ Missing |
| Cross-Book Query | `/cross-books/[collectionId]/query` | ❌ Missing |

## 11. Auth Boundary
- All API routes use `jwt_auth` dependency
- Frontend sends `Authorization: Bearer <token>`
- User ownership checked at DB level (`user_id` + `hash_user_id`)

## 12. Summary
**Frontend is ready** (components, hooks, routing) but **backend APIs are missing**. The BU2/P14 service layer exists and is tested (244 BU2 tests + 17 P14 tests pass). Need to create:
1. **API adapter routes** (thin layer over existing services)
2. **Frontend pages** for chapter BU + cross-book
3. **E2E verification** with real data

**No duplicate authority** — all services read from `book_understandings_v2` and P14 derived tables.
