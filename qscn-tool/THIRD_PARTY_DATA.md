# Third-party database notice

The Apache-2.0 license in `LICENSE` applies to Q-SCOPE-authored software. It does
not grant rights in database files, source sequences, HMM profiles, database
labels, or references supplied by third parties.

## Bundled QSP profiles

The repository contains `QSPdatabase.hmm` and `QSPdatabase.json`. The project
owner confirmed on 2026-08-10 that these supplied copies may be redistributed
with Q-SCOPE (formerly QSCN). The HMM resource derives from the published QSP database:

- Dai, C. et al. *QSP: An open sequence database for quorum sensing related
  gene analysis with an automatic annotation pipeline*. Water Research 235,
  119814 (2023). https://doi.org/10.1016/j.watres.2023.119814
- Upstream repository: https://github.com/chunxiao-dcx/QSP

The publication describes 38 HMMs built from 4,024 seed sequences, with
profile-specific GA optimization, and evaluates the resource against 15,848
bacterial genomes and aquatic metagenomes. The publication and repository make
the database publicly downloadable, but the repository does not identify a
tagged release or an explicit license file. The exact upstream commit or
snapshot corresponding to the bundled HMM therefore remains to be verified.

`QSPdatabase.json` is Q-SCOPE's separate pathway-interpretation layer. Its eight
system definitions map a subset of the published QSP protein types into sending
and receiving roles; the QSP publication does not by itself validate Q-SCOPE's
capability rules or inferred communication edges. Checksums and known counts
are recorded in `databases/provenance.json`.

## Bundled KEGG-derived profiles

The repository contains `kegg_m02024.hmm` and `kegg_m02024.json`. The pathway
roles in the JSON were manually extracted from the KEGG `map02024` quorum
sensing reference pathway. In KEGG nomenclature, a `map` prefix denotes a
manually drawn reference pathway linked to KO entries; organism-specific maps
are separate computationally generated views that convert KOs to organism gene
identifiers. Organism names retained in Q-SCOPE pathway labels therefore identify
the model systems drawn on the reference map and do not restrict the pathway
architecture to those taxa.

The exact KEGG release/extraction date and the construction procedure for the
combined 281-profile HMM library remain **unconfirmed**. KEGG states that KEGG is a copyrighted
database product, restricts its API to academic use, and uses subscription or
licensing arrangements for other access and service-provider uses:

- https://www.kegg.jp/pathway/map02024
- https://www.kegg.jp/kegg/pathway.html
- https://www.kegg.jp/kegg/legal.html
- https://www.kegg.jp/kegg/download/
- https://www.kegg.jp/kegg/rest/

The project owner confirmed on 2026-08-10 that the supplied KEGG-derived files
may be redistributed with Q-SCOPE (formerly QSCN). This project-level confirmation does not change
their ownership, does not place them under Apache-2.0, and does not establish
that every downstream use is permitted. The exact upstream version and build
chain remain pending documentation. Recipients remain responsible for complying
with applicable KEGG terms for their intended use.

## Scientific limitations

The KEGG E-value defaults, short-peptide behavior, partial-gene behavior,
fragmented MAG behavior, and transfer of model-system reference architectures
to homologous proteins in other taxa have not been validated against an
independent positive/negative benchmark. Results are research evidence and
inference, not experimental proof or clinical output.
