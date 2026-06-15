-- 028_derivative_add_file_path.sql
-- Add file_path column to derivative table for illustration_agent schema compatibility.
-- illustration_agent._save_illustration_derivative writes (id, substrate_id, kind, medium, file_path, meta_json).

ALTER TABLE derivative ADD COLUMN IF NOT EXISTS file_path VARCHAR;
