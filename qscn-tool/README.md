# Q-SCOPE — v1.0.0

Q-SCOPE (Quorum-Sensing Communication Link Predictor) is a locally deployed,
Docker-based web application for annotating quorum-sensing components in
microbial genomes or protein sets and predicting potential communication links.

Current release: **Q-SCOPE v1.0.0** (`1.0.0`). It is not a clinical tool,
and its network edges are biological inferences rather than experimentally
validated interactions. Short peptides, partial genes, fragmented MAGs,
KEGG thresholds, and the transfer of model-system reference architectures to
other taxa have not completed an independent biological calibration.

Run source-build,
development, test and release commands from this directory. The separate
`../qscn-research/` directory contains analysis and manuscript artifacts and is
not part of the Docker build context.

## Read-only GitHub Pages demo

The public demo at <https://emmettpeng.github.io/Q-SCOPE/> renders a
precomputed PD10 analysis with the production React interface. It has no API,
upload, analysis worker, persistent storage, cookies, or analytics. Mutating
controls remain visible but disabled so visitors can see which capabilities are
available in the local application.

Regenerate and validate its versioned snapshot from this directory:

```bash
python scripts/generate_demo_snapshot.py
python scripts/check_demo_snapshot.py
cd frontend && npm test && npm run build:demo
```

The generator requires the locked backend dependencies (the release container
is the recommended runtime). The published artifact contains result JSON only;
it excludes the PD10 input ZIP, predicted sequences, HMM files, SQLite, Redis,
and analysis intermediates.

## Install on Windows, macOS, or Linux

Q-SCOPE is distributed as a local, container-first application. Release bundles
are available from [GitHub Releases](https://github.com/EmmettPeng/Q-SCOPE/releases).
The same digest-pinned `linux/amd64` and `linux/arm64` image supports Windows
x64, Intel and Apple Silicon Macs, and amd64/arm64 Linux hosts. Q-SCOPE binds only
to localhost and stores projects in local Docker volumes.

### Windows 10/11 x64

1. Install and start [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
   with its WSL 2 Linux-container backend. Docker Desktop does not require a
   separate Ubuntu distribution for Q-SCOPE.
2. Download and extract `Q-SCOPE-v1.0.0-windows.zip`.
3. Double-click `windows\Q-SCOPE.cmd`.

### macOS

1. Install and start [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/).
2. Download and extract `Q-SCOPE-v1.0.0-macos.zip`.
3. On first launch, control-click `macos/Q-SCOPE.command` and choose **Open**.

### Ubuntu Linux

1. Install [Docker Engine and Docker Compose v2](https://docs.docker.com/engine/install/ubuntu/).
2. Download and extract `Q-SCOPE-v1.0.0-linux.tar.gz`.
3. Run `./linux/Q-SCOPE.sh`.

The launchers pull the release image, wait for SQLite, Redis, Worker, QSP, and
KEGG readiness, then open `http://127.0.0.1:8000`. Ubuntu 22.04 and 24.04 LTS
on amd64/arm64 are the tested Linux hosts; other distributions with a compatible
Linux Docker Engine and Compose v2 may work but are not in the v1.0.0 host matrix.

Recommended host resources are 4 CPU, 16 GB memory, and 40 GB free disk space.
The package provides `start`, `stop`, `status`, `logs`, `update`, `backup`, and
confirmed `restore` commands. Normal stop and update operations never delete
the stable `qscope_data` and `qscope_redis` volumes.

## Build from source

Requirements: Docker with Docker Compose v2. Q-SCOPE binds only to localhost.

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

Project inputs and results remain in the `qscope_data` volume until the user
explicitly deletes them. The application never deletes a Docker volume.

## Schema 5 and stable volumes

Q-SCOPE v1.0.0 uses application schema 5 and the named Docker volumes
`qscope_data` and `qscope_redis`. A volume with an incompatible schema is refused
without modification.

Inspect volumes before any cleanup:

```bash
docker volume ls
docker volume inspect qscope_data
docker volume inspect qscope_redis
```

Only after independently confirming that an old volume is no longer needed may
the user remove that exact volume. Do not use `docker compose down -v` as an
upgrade step.

## Inputs and safety limits

- Upload one ZIP; every visible FASTA represents one sample and must use the
  declared sequence type.
- Protein FASTA is scanned directly. Nucleotide genome FASTA uses Prodigal
  `single`, with CDS, GFF, contig coordinates, strand, and partial flags saved.
  Validated predictions are cached per project and reused across database and
  repeat runs; every run still receives a complete linked or copied prediction
  set for audit and full export.
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
- Hit rule `1.0`, capability rule `3.0`, and analysis scope `1.0` are used by
  Q-SCOPE v1.0.0. Capability criteria allow only all defined components or an
  explicit selected component set; minimum-count criteria are not accepted.
  Changing hit thresholds creates a new run; changing pathway rules or
  scope creates an interpretation from saved hits without rerunning HMMER.
- Projects retain a database → run → interpretation history. QSP multicomponent
  criteria expose versioned database guidance endpoints for Lsr, LuxPQ, Rpf,
  and Pqs; applying a guide is an explicit user choice recorded with the
  interpretation and does not rewrite HMM evidence. QH/BIO annotations remain
  result evidence and filters, but there is no standalone Evidence Guide page.
- QSP and KEGG retain independent native classifications and are never combined
  into a cross-database pathway or network edge.

Built-in database metadata uses a versioned component catalog. `profile_id`
remains the immutable HMM and rule identifier, while `display_name` is
presentation metadata. KEGG components are rendered as
`display_name(profile_id)` (for example, `LuxA(K00494)`); QSP identity names are
rendered once (`LuxI`). Blank curated KEGG names are explicit `NA` values.
Exports retain every original profile ID and add parallel display-name/label
fields.

## Built-in database provenance and semantics

- QSP is the published quorum-sensing-related protein database described by
  Dai et al. in *Water Research* 235, 119814 (2023),
  https://doi.org/10.1016/j.watres.2023.119814. It contains 38 protein-type
  HMMs built from 4,024 seed sequences and uses profile-specific GA thresholds.
  The upstream resource is available at https://github.com/chunxiao-dcx/QSP.
- `QSPdatabase.json` is a separate Q-SCOPE interpretation layer that maps 29 of
  those protein types into eight sending/receiving system definitions. The
  published QSP resource supports sequence annotation; it does not independently
  validate Q-SCOPE's pathway-completion rules or potential communication edges.
- The KEGG pathway definitions were manually extracted from the `map02024`
  quorum sensing reference pathway. Organism names retained in pathway labels
  denote the model systems drawn on the KEGG reference map; they are not claims
  that the corresponding architecture exists only in that organism.
- QSP and KEGG remain independently constructed evidence sources. Q-SCOPE preserves
  each database's native profiles and labels and does not assemble a capability
  or network edge from components found in different databases.

## Results

Complete exports contain the run manifest, candidate and passing hits, HMMER
outputs, pathway capabilities, network JSON/TSV/SIF, and for genome runs the
Prodigal FAA/CDS/GFF plus predicted-gene JSON/TSV mapping. Every run records
software/build versions, input and database checksums, thresholds, scope,
wall-clock time, peak child-process memory, and output size.

## Custom databases

Use **Import custom database** to select one combined `.hmm` and one UTF-8,
tab-separated `.tsv` or `.txt` Pathway table. An optional component-name TSV
defines the display name for every HMM profile; an optional guidance TSV defines
versioned interpretation endpoints for multi-component roles. Download all three
templates from the import dialog. The Pathway table columns are
`Pathway`, `Signal_type`,
`Signal_Sending`, `Signal_Receiving`, and `References`; separate multiple
profiles or references with semicolons. Q-SCOPE validates exact HMM `NAME` values,
creates an internal normalized manifest, retains both original files, and builds
fresh indexes with its bundled HMMER. Guidance is explanatory only: its
Evidence IDs are source labels and never execute BIO/QH rules or change hits.
Do not upload `.h3*` files.

The component-name table has exactly `Profile_ID` and `Display_Name` columns and
must define every HMM profile exactly once with a non-empty display name. If it is
omitted, tabular imports receive an identity component catalog
(`display_name = profile_id`). A ZIP `manifest.json` may also provide explicit
schema-2.0 `components` entries. New manual imports should use the tabular
workflow. Unconfirmed provenance and licensing fields remain explicitly reported
as `unconfirmed`.

## Licensing and release status

Q-SCOPE-authored code is Apache-2.0. QSP and KEGG-related data remain third-party
data rather than Apache-2.0 code; the project owner confirmed on 2026-08-10
that the supplied copies may be distributed with Q-SCOPE. Their known provenance,
remaining upstream-version details, and applicable terms are recorded in
`THIRD_PARTY_DATA.md` and `databases/provenance.json`.

Release history is recorded in `CHANGELOG.md`; automated build and release
gates are defined in the workspace-level `../.github/workflows/` directory.

## Development checks

```bash
docker compose build
docker run --rm -v "$PWD":/workspace:ro -w /workspace \
  -e PYTHONPATH=/workspace/backend qscn:1.0.0 \
  python -m unittest discover -s tests -v
cd frontend && npm test && npm run build && npm audit
./scripts/benchmark_demo.sh
```
