# LEGACY_PATH_MAP

- **`stratum-api` (:9302)**
  - Still used? YES.
  - Production traffic? YES (Auth, Search fallback).
  - DB writes? YES (Old endpoints).
  - Replacement? `stratum-sl` (:9304).
  - Safe to freeze? NOT YET. Must deploy E2E testing to ensure 9304 covers all legacy functionality.

- **`aii.bu_onto` Old 7 Fields (soul, positioning, question, skeleton, thinking, for_whom, boundary)**
  - Still used? NO (Superseded by `facets_grounded`).
  - Production traffic? Read-only fallback for old UI.
  - DB writes? Generated as legacy stub.
  - Replacement? `facets_grounded`.
  - Safe to freeze? YES.

- **`aii_context` Single-tenant C仓 tables**
  - Still used? YES.
  - DB writes? YES.
  - Replacement? `stratum.personal_states` and `stratum.learning_events` with proper `user_id`.
  - Safe to freeze? NOT YET. Real identity migration needed.

- **DeepCard `localStorage` Mastery**
  - Still used? YES.
  - Production traffic? YES (Frontend reads/writes).
  - DB writes? NO (local only).
  - Replacement? Canonical `learning_events`.
  - Safe to freeze? NO. Users will lose progress if frozen before migration.

- **`aii/scripts/generate_bu.py` 60 KU limit**
  - Still used? YES.
  - DB writes? YES.
  - Replacement? Whole-book sliding window or ChapterDelta synthesis.
  - Safe to freeze? YES. Should be replaced by true Book Understanding 2.0 generation.
