-- 027_derivative_add_medium.sql
-- Add medium column to derivative table for illustration_agent schema compatibility.

ALTER TABLE derivative ADD COLUMN IF NOT EXISTS medium VARCHAR;
