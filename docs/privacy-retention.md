# AII privacy and retention

Authenticated identity is the ownership boundary. Source, Fragment, Evidence,
projection, Artifact and retrieval reads are filtered at the backend boundary;
UI filtering is not a privacy control.

- Store only data required for the requested workflow.
- Keep secrets in a secret manager or untracked environment and never log them.
- Raw files, extracted text, embeddings and provider payloads leave the system
  only when the configured provider is explicitly enabled.
- Source deletion hides the Source from normal retrieval while retaining
  auditable internal provenance; hard purge is a separate authenticated,
  audited operation governed by the retention policy.
- Logs, traces, backups and temporary provider payloads use operator-configured
  retention. Backups inherit the same access and retention controls.

Export and deletion requests must be owner-scoped and tested for cross-user
denial before release.
