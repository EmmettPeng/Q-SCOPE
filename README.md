# QSCN — v0.3.1

QSCN is a local, evidence-first research tool for annotating quorum-sensing
components in microbial genomes or protein sets and reconstructing potential
microorganism-to-microorganism communication networks.

Current release: **QSCN v0.3.1** (`0.3.1`). It is not a clinical tool,
and its network edges are biological inferences rather than experimentally
validated interactions. Short peptides, partial genes, fragmented MAGs,
KEGG thresholds, and species-specific pathway labels have not completed an
independent biological calibration.

## Start locally

Requirements: Docker with Docker Compose v2. QSCN binds only to localhost.

```bash
cp .env.example .env
QSCN_BUILD_REVISION=$(git rev-parse HEAD) \
QSCN_BUILD_TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
docker compose build
docker compose up -d
```

Open `http://localhost:8000`. Confirm both endpoints before analysis:

```bash
curl --fail http://localhost:8000/api/health
curl --fail http://localhost:8000/api/readiness
```

Project inputs and results remain in the `qscn_v03_data` volume until the user
explicitly deletes them. The application never deletes a Docker volume.

## Required fresh install from v0.2

v0.3 deliberately does not migrate v0.2 SQLite data. Before upgrading, start
v0.2.2 and export every result that must be retained. The renamed v0.3 app and
Redis volumes leave the old volumes untouched. If an old SQLite file is mounted manually,
v0.3 refuses startup without changing it.

Inspect volumes before any cleanup:

```bash
docker volume ls
docker volume inspect qscn_qscn_data
docker volume inspect qscn_qscn_v03_data
```

Only after independently confirming that an old volume is no longer needed may
the user remove that exact volume. Do not use `docker compose down -v` as an
upgrade step.

## Inputs and safety limits

- Upload one ZIP; every visible FASTA represents one sample and must use the
  declared sequence type.
- Protein FASTA is scanned directly. Nucleotide genome FASTA uses Prodigal
  `single`, with CDS, GFF, contig coordinates, strand, and partial flags saved.
- Sample names must remain unique after safe-ID normalization. Sequence IDs are
  unique within a sample; the same sequence ID may occur in different samples.
- ZIP path traversal, links, special/encrypted entries, case-conflicting paths,
  excessive compression ratios, and configured resource-limit violations are
  rejected before analysis.
- All limits are configurable through `.env.example`. Raising them also raises
  denial-of-service and disk-exhaustion risk.

## Analysis rules

- QSP uses profile-specific sequence/domain GA thresholds (`--cut_ga`).
- KEGG and E-value custom databases require both full-sequence E-value and best
  domain i-Evalue, defaulting to `1e-5`.
- Hit rule `1.0`, capability rule `2.0`, and analysis scope `1.0` remain frozen.
  Changing hit thresholds creates a new run; changing pathway rules or
  scope creates an interpretation from saved hits without rerunning HMMER.
- QSP and KEGG retain independent native classifications and are never combined
  into a cross-database pathway or network edge.

## Results

Complete exports contain the run manifest, candidate and passing hits, HMMER
outputs, pathway capabilities, network JSON/TSV/SIF, and for genome runs the
Prodigal FAA/CDS/GFF plus predicted-gene JSON/TSV mapping. Every run records
software/build versions, input and database checksums, thresholds, scope,
wall-clock time, peak child-process memory, and output size.

## Custom databases

Use **Import custom database** to select one combined `.hmm` and one UTF-8,
tab-separated `.tsv` or `.txt` Pathway table. Download the table template from
the import dialog. Its five columns are `Pathway`, `Signal_type`,
`Signal_Sending`, `Signal_Receiving`, and `References`; separate multiple
profiles or references with semicolons. QSCN validates exact HMM `NAME` values,
creates an internal normalized manifest, retains both original files, and builds
fresh indexes with its bundled HMMER. Do not upload `.h3*` files.

The previous ZIP format containing one `.hmm` and one `manifest.json` remains
accepted by the API for compatibility. New manual imports should use the
two-file workflow. Unconfirmed provenance and licensing fields remain explicitly
reported as `unconfirmed`.

## Licensing and release status

QSCN-authored code is Apache-2.0. This does not license bundled third-party
data. Read `THIRD_PARTY_DATA.md`, `THIRD_PARTY_SOFTWARE.md`, and
`databases/provenance.json` before redistributing or using the databases.

Release history is recorded in `CHANGELOG.md`; automated build and release
gates are defined in `.github/workflows/` when present.

## Development checks

```bash
docker compose build
docker run --rm -v "$PWD":/workspace:ro -w /workspace \
  -e PYTHONPATH=/workspace/backend qscn:0.3.1 \
  python -m unittest discover -s tests -v
cd frontend && npm test && npm run build && npm audit
./scripts/benchmark_demo.sh
```
