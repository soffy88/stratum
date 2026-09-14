-- Normalize nullable user flags so the HTTP auth contract returns booleans.
-- Existing NULLs are legacy rows; this is a non-destructive, idempotent fix.
UPDATE stratum.users
SET email_verified = COALESCE(email_verified, FALSE),
    is_active = COALESCE(is_active, TRUE),
    is_suspended = COALESCE(is_suspended, FALSE)
WHERE email_verified IS NULL
   OR is_active IS NULL
   OR is_suspended IS NULL;

ALTER TABLE stratum.users
    ALTER COLUMN email_verified SET DEFAULT FALSE,
    ALTER COLUMN is_active SET DEFAULT TRUE,
    ALTER COLUMN is_suspended SET DEFAULT FALSE;
