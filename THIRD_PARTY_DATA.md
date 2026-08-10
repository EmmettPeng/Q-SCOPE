# Third-party database notice

The Apache-2.0 license in `LICENSE` applies to QSCN-authored software. It does
not grant rights in database files, source sequences, HMM profiles, database
labels, or references supplied by third parties.

## Bundled QSP profiles

The repository contains `QSPdatabase.hmm` and `QSPdatabase.json`. Their exact
upstream source, construction procedure, license, and redistribution permission
remain **unconfirmed** for RC1. Checksums and known counts are recorded in
`databases/provenance.json`.

## Bundled KEGG-derived profiles

The repository contains `kegg_m02024.hmm` and `kegg_m02024.json`. They are
described as KEGG-derived, but their exact source version and construction
procedure remain **unconfirmed**. KEGG states that KEGG is a copyrighted
database product, restricts its API to academic use, and uses subscription or
licensing arrangements for other access and service-provider uses:

- https://www.kegg.jp/kegg/legal.html
- https://www.kegg.jp/kegg/download/
- https://www.kegg.jp/kegg/rest/

QSCN RC1 does not claim that redistribution permission has been granted. The
project owner has chosen to retain these files in the RC distribution while
the provenance and permission audit remains open. Recipients are responsible
for determining whether their intended use is permitted.

## Scientific limitations

The KEGG E-value defaults, short-peptide behavior, partial-gene behavior,
fragmented MAG behavior, and species-specific pathway labels have not been
validated against an independent positive/negative benchmark. Results are
research evidence and inference, not experimental proof or clinical output.
