# Q-SCOPE changelog

## Q-SCOPE v1.0.0 — 2026-09-11

Initial public release of Q-SCOPE, a local, container-first application for
evidence-first annotation of quorum-sensing components and reconstruction of
potential microbial communication links.

### Included

- Protein and nucleotide FASTA ingestion with defensive ZIP validation.
- Prodigal gene prediction with reusable, auditable prediction artifacts.
- HMMER scanning against QSP `builtin-v2` and KEGG `m02024-display-v2`.
- Versioned hit, capability, guidance, evidence, and analysis-scope rules.
- Project, run, and interpretation history; custom HMM database import; evidence
  tables; interactive network views; machine-readable exports.
- Restorable PD10 example and database profile/pathway/guidance inspection.
- Local Docker deployment, stable volumes, multi-architecture images, and
  Windows, macOS, and Linux packages.

### Compatibility and scope

- Application schema: `5`.
- QSP uses profile-specific GA thresholds. KEGG and E-value custom databases use
  full-sequence and best-domain E-value thresholds, defaulting to `1e-5`.
- Sending and receiving capabilities are evaluated independently. Databases are
  not combined into cross-database pathways or network edges.
- Network edges are inferences rather than experimentally validated
  interactions. Q-SCOPE is for research use only.
