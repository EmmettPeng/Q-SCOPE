from __future__ import annotations

import csv
import json
import shutil
import uuid
import zipfile
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from . import SCHEMA_VERSION, __release__, __version__
from . import db
from .analysis import run_hmmscan, run_prodigal, tool_version
from .completeness import calculate_capabilities, validate_rules
from .config import settings
from .databases import get_database, load_manifest
from .network import build_network
from .schemas import ANALYSIS_SCOPE_VERSION, CAPABILITY_RULE_VERSION, HIT_RULE_VERSION, CapabilityRule, InputKind
from .scope import normalize_scope
from .storage import directory_size, ensure_storage_budget, read_json, write_json


def project_dir(project_id: str) -> Path:
    return settings.projects_dir / project_id


def run_dir(run_id: str, project_id: str) -> Path:
    return project_dir(project_id) / "runs" / run_id


def _public_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in sample.items() if key != "fasta_path"}
        for sample in samples
    ]


def _update_run(
    run_id: str,
    stage: str,
    progress: float,
    status: str = "running",
    error: str | None = None,
    error_code: str | None = None,
) -> None:
    db.update(
        "runs",
        run_id,
        {
            "stage": stage,
            "progress": max(0.0, min(progress, 1.0)),
            "status": status,
            "error": error,
            "error_code": error_code,
            "error_params_json": "{}" if error_code else None,
        },
    )


def _write_tsv(path: Path, rows: Iterable[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            rendered = {
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            }
            writer.writerow(rendered)


def _sif_interaction_type(pathway_id: str) -> str:
    return f"potential_communication__pathway={quote(pathway_id, safe='._-')}"


def _write_sif(
    path: Path,
    nodes: Iterable[dict[str, Any]],
    edges: Iterable[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    unique_edges = {
        (edge["source_sample"], edge["target_sample"], edge["pathway_id"]): edge
        for edge in edges
    }
    ordered_edges = [unique_edges[key] for key in sorted(unique_edges)]
    connected = {
        sample_id
        for edge in ordered_edges
        for sample_id in (edge["source_sample"], edge["target_sample"])
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        for edge in ordered_edges:
            handle.write(
                f"{edge['source_sample']}\t{_sif_interaction_type(edge['pathway_id'])}"
                f"\t{edge['target_sample']}\n"
            )
        for node in sorted(nodes, key=lambda item: item["sample_id"]):
            if node["sample_id"] not in connected:
                handle.write(f"{node['sample_id']}\n")


def create_interpretation(
    run_id: str,
    rules: Iterable[CapabilityRule | dict[str, Any]] | None = None,
    analysis_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run = db.get("runs", run_id)
    if not run:
        raise ValueError("run not found")
    project = db.get("projects", run["project_id"])
    if not project:
        raise ValueError("project not found")
    base = run_dir(run_id, run["project_id"])
    hits = read_json(base / "hits.json")
    samples = json.loads(project["samples_json"] or "[]")
    database_row = get_database(run["database_version_id"])
    manifest = load_manifest(database_row)
    interpretation_id = str(uuid.uuid4())
    normalized_rules = validate_rules(manifest, rules)
    normalized_scope = normalize_scope(manifest, analysis_scope)
    scoped_pathways = (
        None if normalized_scope["mode"] == "all"
        else set(normalized_scope["resolved_pathway_ids"])
    )
    capabilities = calculate_capabilities(
        manifest, hits, [sample["sample_id"] for sample in samples], normalized_rules,
        pathway_ids=scoped_pathways,
    )
    network = build_network(
        run["database_version_id"],
        database_row["source"],
        {sample["sample_id"]: sample["display_name"] for sample in samples},
        capabilities,
    )
    payload = {
        "interpretation_id": interpretation_id,
        "run_id": run_id,
        "capability_rule_version": CAPABILITY_RULE_VERSION,
        "hit_rule_version": run.get("hit_rule_version") or "legacy-0.2",
        "capability_rules": [rule.model_dump(mode="json") for rule in normalized_rules],
        "analysis_scope": normalized_scope,
        "database": {
            "version_id": database_row["version_id"],
            "database_id": database_row["database_id"],
            "name": database_row["name"],
            "version": database_row["version"],
            "source": database_row["source"],
            "checksum": database_row["checksum"],
            "classification_scheme": database_row["classification_scheme"],
            "provenance": manifest.provenance.model_dump(mode="json"),
            "redistribution_status": manifest.provenance.redistribution_status,
        },
        "samples": _public_samples(samples),
        "hits": hits,
        "capabilities": capabilities,
        "network": network,
    }
    target = base / "interpretations" / interpretation_id
    result_path = target / "results.json"
    write_json(result_path, payload)
    _write_tsv(
        target / "pathway_capabilities.tsv",
        capabilities,
        [
            "sample_id", "pathway_id", "pathway_name", "signal_name", "references", "role",
            "rule_strategy", "total_components", "observed_components", "missing_components",
            "required_profiles", "missing_required_profiles", "required_hits", "completeness",
            "capable", "status", "supporting_hit_ids",
        ],
    )
    _write_tsv(
        target / "network_edges.tsv",
        network["edges"],
        [
            "id", "source_sample", "source_label", "target_sample", "target_label",
            "pathway_id", "pathway_name", "signal_name", "database_version_id",
            "database_source", "self_communication", "evidence_level", "sender_components",
            "receiver_components", "references",
        ],
    )
    _write_tsv(
        target / "network_nodes.tsv",
        network["nodes"],
        ["id", "kind", "sample_id", "label"],
    )
    _write_tsv(
        target / "network_node_metrics.tsv",
        network["node_metrics"],
        [
            "sample_id", "display_name", "in_degree", "out_degree", "total_degree",
            "unique_neighbors", "self_edge_count",
        ],
    )
    _write_tsv(
        target / "network_summary.tsv",
        [{"metric": key, "value": value} for key, value in network["summary"].items()],
        ["metric", "value"],
    )
    _write_sif(target / "network.sif", network["nodes"], network["edges"])
    db.insert(
        "interpretations",
        {
            "id": interpretation_id,
            "run_id": run_id,
            "completeness_mode": "v2",
            "capability_rule_version": CAPABILITY_RULE_VERSION,
            "capability_rules_json": json.dumps(
                [rule.model_dump(mode="json") for rule in normalized_rules], ensure_ascii=False
            ),
            "analysis_scope_version": ANALYSIS_SCOPE_VERSION,
            "analysis_scope_json": json.dumps(normalized_scope, ensure_ascii=False),
            "result_path": str(result_path),
            "created_at": db.now(),
        },
    )
    return payload


def execute_run(run_id: str) -> str:
    run = db.get("runs", run_id)
    if not run:
        raise ValueError("run not found")
    project = db.get("projects", run["project_id"])
    if not project:
        raise ValueError("project not found")
    samples = json.loads(project["samples_json"] or "[]")
    if not samples:
        raise ValueError("project has not passed preflight")
    database_row = get_database(run["database_version_id"])
    target = run_dir(run_id, project["id"])
    target.mkdir(parents=True, exist_ok=True)
    raw_dir = target / "hmmer"
    prediction_dir = target / "predictions"
    all_hits: list[dict[str, Any]] = []
    scan_metadata: list[dict[str, Any]] = []
    started_at = db.now()
    started_clock = time.monotonic()
    last_stage = "queued"
    last_progress = float(run.get("progress", 0))

    def update_progress(stage: str, progress: float, status: str = "running") -> None:
        nonlocal last_stage, last_progress
        last_stage = stage
        last_progress = max(last_progress, progress)
        _update_run(run_id, stage, last_progress, status)

    try:
        ensure_storage_budget(settings.data_dir, target)
        update_progress("preparing", 0.03)
        kind = InputKind(run["input_kind"])
        if run.get("hit_thresholds_json"):
            hit_thresholds = json.loads(run["hit_thresholds_json"])
        elif run.get("sequence_evalue"):
            hit_thresholds = {
                "full_evalue_max": run["sequence_evalue"],
                "domain_i_evalue_max": run["sequence_evalue"],
            }
        else:
            hit_thresholds = None

        protein_paths: dict[str, Path] = {}
        predicted_genes: dict[str, dict[str, dict[str, Any]]] = {}
        if kind == InputKind.genome:
            for index, sample in enumerate(samples):
                sample_id = sample["sample_id"]
                update_progress(f"predicting:{sample_id}", 0.05 + 0.25 * index / len(samples))
                predicted = run_prodigal(sample, kind, prediction_dir)
                protein_paths[sample_id] = Path(predicted["protein_path"])
                predicted_genes[sample_id] = {
                    item["gene_id"]: item
                    for item in read_json(Path(predicted["genes_path"]))
                }
                update_progress(
                    f"predicting:{sample_id}", 0.05 + 0.25 * (index + 1) / len(samples)
                )
                ensure_storage_budget(settings.data_dir, target)
        else:
            protein_paths = {
                sample["sample_id"]: Path(sample["fasta_path"])
                for sample in samples
            }

        scan_start = 0.30 if kind == InputKind.genome else 0.05
        scan_span = 0.55 if kind == InputKind.genome else 0.80
        for index, sample in enumerate(samples):
            sample_id = sample["sample_id"]
            update_progress(
                f"scanning:{sample_id}", scan_start + scan_span * index / len(samples)
            )
            hits, metadata = run_hmmscan(
                sample_id,
                protein_paths[sample_id],
                Path(database_row["hmm_path"]),
                raw_dir,
                database_row["threshold_type"],
                hit_thresholds,
            )
            if kind == InputKind.genome:
                genes = predicted_genes[sample_id]
                for hit in hits:
                    gene = genes.get(hit["sequence_id"], {})
                    hit.update({
                        "original_sequence_id": gene.get("original_sequence_id", hit["sequence_id"]),
                        "contig_id": gene.get("contig_id"),
                        "gene_start": gene.get("start"),
                        "gene_end": gene.get("end"),
                        "gene_strand": gene.get("strand"),
                        "partial_5prime": gene.get("partial_5prime"),
                        "partial_3prime": gene.get("partial_3prime"),
                    })
            else:
                for hit in hits:
                    hit.update({
                        "original_sequence_id": hit["sequence_id"], "contig_id": None,
                        "gene_start": None, "gene_end": None, "gene_strand": None,
                        "partial_5prime": None, "partial_3prime": None,
                    })
            all_hits.extend(hits)
            scan_metadata.append(metadata)
            update_progress(
                f"scanning:{sample_id}", scan_start + scan_span * (index + 1) / len(samples)
            )
            ensure_storage_budget(settings.data_dir, target)
        write_json(target / "hits.json", all_hits)
        _write_tsv(
            target / "hits.tsv",
            all_hits,
            [
                "hit_id", "sample_id", "sequence_id", "original_sequence_id", "contig_id",
                "gene_start", "gene_end", "gene_strand", "partial_5prime", "partial_3prime",
                "profile_id", "full_evalue", "full_score",
                "domain_evalue", "domain_i_evalue", "domain_c_evalue", "domain_score",
                "hmm_from", "hmm_to", "ali_from", "ali_to", "hmm_coverage",
                "sequence_coverage", "pass", "failure_reasons", "hit_rule_version",
                "applied_thresholds", "threshold_rule", "description",
            ],
        )
        manifest_payload = {
                "qscn_version": __version__,
                "qscn_release": __release__,
                "schema_version": SCHEMA_VERSION,
                "build_revision": settings.build_revision,
                "build_timestamp": settings.build_timestamp,
                "run_id": run_id,
                "project_id": project["id"],
                "input_kind": kind.value,
                "prodigal_mode": "single" if kind == InputKind.genome else None,
                "capability_rule_version": CAPABILITY_RULE_VERSION,
                "hit_rule_version": run.get("hit_rule_version") or HIT_RULE_VERSION,
                "capability_rules": json.loads(run["capability_rules_json"]),
                "analysis_scope": json.loads(run["analysis_scope_json"]),
                "database_version_id": database_row["version_id"],
                "database_checksum": database_row["checksum"],
                "database_provenance": load_manifest(database_row).provenance.model_dump(mode="json"),
                "threshold_type": database_row["threshold_type"],
                "hit_thresholds": hit_thresholds,
                "sequence_evalue": hit_thresholds.get("full_evalue_max") if hit_thresholds else None,
                "archive_sha256": project["archive_sha256"],
                "samples": _public_samples(samples),
                "tools": {"hmmscan": tool_version("hmmscan"), "prodigal": tool_version("prodigal")},
                "scans": scan_metadata,
                "started_at": started_at,
                "completed_at": None,
                "wall_seconds": None,
                "peak_rss_kb": max((item.get("peak_rss_kb", 0) for item in scan_metadata), default=0),
                "output_bytes": None,
            }
        write_json(target / "run_manifest.json", manifest_payload)
        update_progress("interpreting", 0.9)
        result = create_interpretation(
            run_id,
            json.loads(run["capability_rules_json"]),
            json.loads(run["analysis_scope_json"]),
        )
        manifest_payload.update({
            "completed_at": db.now(),
            "wall_seconds": time.monotonic() - started_clock,
            "output_bytes": directory_size(target),
        })
        write_json(target / "run_manifest.json", manifest_payload)
        update_progress("complete", 1.0, "complete")
        return result["interpretation_id"]
    except Exception as error:
        error_code = getattr(error, "code", None) or (
            "disk_space_insufficient"
            if isinstance(error, OSError) and str(error) in {"disk_free_space_below_limit", "run_output_size_exceeded"}
            else "analysis_failed"
        )
        _update_run(
            run_id,
            last_stage,
            last_progress,
            "failed",
            str(error)[:4000],
            error_code,
        )
        raise


def build_export(run_id: str, interpretation_id: str) -> Path:
    run = db.get("runs", run_id)
    interpretation = db.get("interpretations", interpretation_id)
    if not run or not interpretation or interpretation["run_id"] != run_id:
        raise ValueError("interpretation not found for run")
    base = run_dir(run_id, run["project_id"])
    export_dir = base / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"qscn-{run_id[:8]}-{interpretation_id[:8]}.zip"
    selected = [base / "run_manifest.json", base / "hits.json", base / "hits.tsv"]
    selected.extend(path for path in (base / "hmmer").glob("*") if path.is_file())
    if (base / "predictions").exists():
        selected.extend(path for path in (base / "predictions").glob("*") if path.is_file())
    interpretation_dir = Path(interpretation["result_path"]).parent
    selected.extend(path for path in interpretation_dir.glob("*") if path.is_file())
    with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in selected:
            if path.exists():
                archive.write(path, path.relative_to(base))
    return export_path


ARTIFACTS = {
    "pathway-capabilities.tsv": "pathway_capabilities.tsv",
    "network.sif": "network.sif",
    "network-nodes.tsv": "network_nodes.tsv",
    "network-edges.tsv": "network_edges.tsv",
    "network-summary.tsv": "network_summary.tsv",
    "network-node-metrics.tsv": "network_node_metrics.tsv",
}


def get_interpretation_artifact(run_id: str, interpretation_id: str, artifact: str) -> Path:
    if artifact not in ARTIFACTS:
        raise ValueError("unknown interpretation artifact")
    interpretation = db.get("interpretations", interpretation_id)
    if not interpretation or interpretation["run_id"] != run_id:
        raise ValueError("interpretation not found for run")
    path = Path(interpretation["result_path"]).parent / ARTIFACTS[artifact]
    if not path.is_file():
        raise ValueError("interpretation artifact is unavailable")
    return path
