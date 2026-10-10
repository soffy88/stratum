-- ============================================================================
-- 0013_library_catalog.sql — 图书馆目录 (BookOrbit 内化 Phase 4)
--
-- Renumbered from 0009 to avoid colliding with 0009_bu_skill_embedding.sql.
--
-- 新表:
--   aii.book_metadata        — Phase 1 oskill/book_metadata pipeline 的结果
--   aii.collections          — 书架/收藏夹 (BookOrbit collections)
--   aii.shelves              — 智能筛选书架 (BookOrbit smart scopes)
--   aii.reading_progress     — 阅读进度 (Kobo/KOReader sync)
--   aii.book_shelf_join      — 书与书架的多对多关系
--   aii.book_collection_join — 书与收藏夹的多对多关系
-- ============================================================================

-- ── 1. book_metadata (Phase 1 pipeline 结果) ──────────────────────
CREATE TABLE IF NOT EXISTS aii.book_metadata (
  title text PRIMARY KEY,
  author text,
  authors text[],
  isbn10 text,
  isbn13 text,
  publisher text,
  published_year integer,
  page_count integer,
  language text,
  cover_url text,
  source_url text,
  community_rating numeric(3,1),
  community_rating_count integer,
  genres text[],
  description text,
  provider text,
  provider_id text,
  fetched_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_book_metadata_isbn10 ON aii.book_metadata (isbn10);
CREATE INDEX IF NOT EXISTS idx_book_metadata_isbn13 ON aii.book_metadata (isbn13);
CREATE INDEX IF NOT EXISTS idx_book_metadata_publisher ON aii.book_metadata (publisher);
CREATE INDEX IF NOT EXISTS idx_book_metadata_cover ON aii.book_metadata (cover_url);

-- ── 2. collections (收藏夹) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS aii.collections (
  id serial PRIMARY KEY,
  name text NOT NULL,
  description text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- ── 3. shelves (智能书架) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS aii.shelves (
  id serial PRIMARY KEY,
  name text NOT NULL,
  filter_sql text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- ── 4. book_shelf_join (书 ↔ 书架) ──────────────────────────────
CREATE TABLE IF NOT EXISTS aii.book_shelf_join (
  book_title text,
  shelf_id integer REFERENCES aii.shelves (id) ON DELETE CASCADE,
  added_at timestamptz DEFAULT now(),
  PRIMARY KEY (book_title, shelf_id)
);

-- ── 5. book_collection_join (书 ↔ 收藏夹) ────────────────────────
CREATE TABLE IF NOT EXISTS aii.book_collection_join (
  book_title text,
  collection_id integer REFERENCES aii.collections (id) ON DELETE CASCADE,
  added_at timestamptz DEFAULT now(),
  PRIMARY KEY (book_title, collection_id)
);

-- ── 6. reading_progress (阅读进度) ──────────────────────────────
CREATE TABLE IF NOT EXISTS aii.reading_progress (
  book_title text PRIMARY KEY,
  last_chapter text,
  last_position_percent numeric(5,2),
  last_cfi text,
  last_page integer,
  last_read_at timestamptz DEFAULT now(),
  total_read_seconds integer DEFAULT 0,
  device_id text,
  updated_at timestamptz DEFAULT now()
);

-- ── 7. 预置书架 ──────────────────────────────────────────────────
INSERT INTO aii.shelves (name, filter_sql) VALUES
  ('数学', 'subject = ''数学'''),
  ('经济学', 'subject = ''经济学'''),
  ('计算机', 'subject = ''计算机'''),
  ('哲学', 'subject = ''哲学'''),
  ('心理学', 'subject = ''心理学'''),
  ('其他', 'subject = ''其他''')
ON CONFLICT DO NOTHING;

-- ── 8. 预置收藏夹 ────────────────────────────────────────────────
INSERT INTO aii.collections (name, description) VALUES
  ('已读', '已完成阅读的书'),
  ('在读', '正在阅读的书'),
  ('待读', '计划阅读的书'),
  ('收藏', '手动收藏的书')
ON CONFLICT DO NOTHING;
