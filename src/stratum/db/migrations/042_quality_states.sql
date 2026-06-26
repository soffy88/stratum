-- 042_quality_states.sql
-- quality_reason: 记录 quarantine 原因（file_missing / pdf_no_pages / epub_no_spine /
--                 pdf_open_failed / epub_open_failed / md_empty / md_too_short）
ALTER TABLE substrates ADD COLUMN IF NOT EXISTS quality_reason VARCHAR DEFAULT NULL;
