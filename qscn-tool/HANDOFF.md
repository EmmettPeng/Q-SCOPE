# Q-SCOPE engineering handoff

Last updated: 2026-09-11

Current release candidate: `Q-SCOPE v1.0.0`
Internal version: `1.0.0`
Application schema: `5`

## Release state

The source tree is prepared as the initial public Q-SCOPE release. Software,
tests, Docker context, packaging, and engineering documentation live here.
Manuscript analyses and paper artifacts live in `../qscn-research/` and must not
enter the application image or bundled databases.

The built-in registry contains only the current metadata editions:

- QSP `builtin-v2`: 38 HMM profiles with curated GA thresholds.
- KEGG `m02024-display-v2`: 281 HMM profiles with display-name metadata and
  default sequence/domain E-value thresholds of `1e-5`.

Database files, manifests, hits, capabilities, interpretations, and exports
preserve their source and native classification. Cross-database completion or
network inference is prohibited.

## Required verification

- Confirm version consistency across source, API health, OCI labels, Compose,
  UI, tests, and packages.
- Run all backend tests inside the release image.
- Run frontend tests, production build, and high-severity dependency audit.
- Build amd64 and arm64 images; verify tools, profiles, indexes, and readiness.
- Run the complete browser release flow and PD10 restoration flow.
- Inspect all platform packages and `SHA256SUMS`.
- Audit the Git index for research data, caches, credentials, and large files.

## Scientific boundaries

HMM hits are evidence, not proof of a complete system. Sending and receiving are
reported separately. Missing hits are reported as not detected, particularly for
short peptides, partial genes, and fragmented MAGs. KEGG model-organism labels
are not taxonomic restrictions. Results must remain traceable to their input,
database, thresholds, rules, software build, and raw HMM evidence.

## Open release risks

- Database provenance and applicable terms must remain explicit in
  `THIRD_PARTY_DATA.md` and `databases/provenance.json`.
- Short-peptide, fragmented-MAG, KEGG-threshold, and cross-taxon pathway transfer
  behavior has not received independent biological calibration.
- The Vite production build may emit a non-blocking large-chunk warning.
