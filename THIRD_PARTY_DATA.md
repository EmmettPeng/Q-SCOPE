# Third-party database notice

The Apache-2.0 license in `LICENSE` applies to QSCN-authored software. It does
not grant rights in database files, source sequences, HMM profiles, database
labels, or references supplied by third parties.

## Bundled QSP profiles

The repository contains `QSPdatabase.hmm` and `QSPdatabase.json`. The project
owner confirmed on 2026-08-10 that these supplied copies may be redistributed
with QSCN. Their exact upstream source, construction procedure, and upstream
license still require fuller documentation. Checksums and known counts are
recorded in `databases/provenance.json`.

## Bundled KEGG-derived profiles

The repository contains `kegg_m02024.hmm` and `kegg_m02024.json`. They are
described as KEGG-derived, but their exact source version and construction
procedure remain **unconfirmed**. KEGG states that KEGG is a copyrighted
database product, restricts its API to academic use, and uses subscription or
licensing arrangements for other access and service-provider uses:

- https://www.kegg.jp/kegg/legal.html
- https://www.kegg.jp/kegg/download/
- https://www.kegg.jp/kegg/rest/

The project owner confirmed on 2026-08-10 that the supplied KEGG-derived files
may be redistributed with QSCN. This project-level confirmation does not change
their ownership, does not place them under Apache-2.0, and does not establish
that every downstream use is permitted. The exact upstream version and build
chain remain pending documentation. Recipients remain responsible for complying
with applicable KEGG terms for their intended use.

## Scientific limitations

The KEGG E-value defaults, short-peptide behavior, partial-gene behavior,
fragmented MAG behavior, and species-specific pathway labels have not been
validated against an independent positive/negative benchmark. Results are
research evidence and inference, not experimental proof or clinical output.
