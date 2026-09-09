-- 030: keep evidence provenance valid when a substrate is removed.
-- Existing orphan rows are qualification debris; remove claim links first so
-- the foreign key can be installed without weakening provenance checks.

DELETE FROM stratum.claim_evidence ce
WHERE NOT EXISTS (
    SELECT 1 FROM stratum.evidence e WHERE e.id = ce.evidence_id
)
OR NOT EXISTS (
    SELECT 1 FROM stratum.knowledge_claims c WHERE c.id = ce.claim_id
);

DELETE FROM stratum.evidence e
WHERE NOT EXISTS (
    SELECT 1 FROM stratum.substrates s WHERE s.id = e.substrate_id
);

ALTER TABLE stratum.evidence
    ADD CONSTRAINT evidence_substrate_id_fkey
    FOREIGN KEY (substrate_id)
    REFERENCES stratum.substrates(id)
    ON DELETE CASCADE;
