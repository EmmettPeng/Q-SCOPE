# Q-SCOPE — v1.0.0

Q-SCOPE (**Q**uorum-**S**ensing **CO**mmunication Link **P**r**E**dictor) is a local,
container-first research application for annotating quorum-sensing components
in microbial genomes or protein sets and reconstructing potential communication
links.

The application reports evidence before biological inference. Predicted network
edges are hypotheses, not experimentally validated interactions, and Q-SCOPE is
not a clinical or diagnostic tool.

## Install

Download the package for Windows, macOS, or Linux from
[GitHub Releases](https://github.com/EmmettPeng/Q-SCOPE/releases). All packages
use the same digest-pinned multi-architecture container image.

- Windows 10/11 x64: extract `Q-SCOPE-v1.0.0-windows.zip`, then open
  `windows/Q-SCOPE.cmd`.
- macOS: extract `Q-SCOPE-v1.0.0-macos.zip`, then control-click
  `macos/Q-SCOPE.command` and choose **Open**.
- Linux: extract `Q-SCOPE-v1.0.0-linux.tar.gz`, then run `./linux/Q-SCOPE.sh`.

Docker Desktop or Docker Engine with Compose v2 is required. Q-SCOPE binds to
`127.0.0.1:8000` by default and stores projects in local Docker volumes.
Recommended resources are 4 CPU cores, 16 GB memory, and 40 GB free disk space.

## Capabilities

- Protein and nucleotide FASTA input with defensive ZIP validation.
- Prodigal gene prediction and HMMER profile scanning.
- Bundled QSP `builtin-v2` and KEGG `m02024-display-v2` databases.
- Auditable hits, thresholds, coverage, coordinates, checksums, and provenance.
- Independent sending and receiving capability interpretation.
- Evidence tables, manifests, pathway capabilities, and potential networks.
- Custom HMM database import and a restorable PD10 example project.

QSP and KEGG are independent evidence sources and are never combined to create a
single pathway or network edge. A component hit does not by itself demonstrate a
complete quorum-sensing system.

## Build from source

The software source is under `qscn-tool/`. Manuscript and case-study materials
are maintained separately under `qscn-research/` and are excluded from the
application image.

```bash
cd qscn-tool
cp .env.example .env
docker compose up -d --build
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/readiness
```

See [qscn-tool/README.md](qscn-tool/README.md) for analysis semantics, custom
database formats, exports, security limits, and development checks.

## License and third-party data

Q-SCOPE-authored code is licensed under Apache-2.0. Bundled QSP and KEGG-derived
resources are third-party data and are not covered by the software license. See
`qscn-tool/THIRD_PARTY_DATA.md` and `qscn-tool/databases/provenance.json`.

## Citation

The manuscript is under submission and review.
