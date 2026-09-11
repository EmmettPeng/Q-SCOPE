from __future__ import annotations

import hashlib
import json
import subprocess
import csv
from pathlib import Path
from typing import Any

from .config import settings
from .schemas import InputKind
from .schemas import HIT_RULE_VERSION
from .storage import write_json
from .execution import ExternalCommandError, run_external


class AnalysisError(RuntimeError):
    def __init__(self, message: str, code: str = "analysis_failed") -> None:
        super().__init__(message)
        self.code = code


def tool_version(command: str) -> str:
    try:
        completed = subprocess.run(
            [command, "-h"], capture_output=True, text=True, timeout=20
        )
        first = (completed.stdout or completed.stderr).splitlines()
        return first[0].lstrip("# ") if first else command
    except (OSError, subprocess.SubprocessError):
        return f"{command}: unavailable"


def parse_prodigal_gff(path: Path, sample_id: str) -> list[dict[str, Any]]:
    genes: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="strict") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9 or fields[2] != "CDS":
                continue
            attributes = {}
            for item in fields[8].split(";"):
                if "=" in item:
                    key, value = item.split("=", 1)
                    attributes[key] = value
            gene_id = attributes.get("ID")
            if not gene_id:
                raise AnalysisError(f"Prodigal GFF CDS lacks ID in {path.name}")
            partial = attributes.get("partial", "00")
            genes.append({
                "sample_id": sample_id,
                "gene_id": gene_id,
                "original_sequence_id": gene_id,
                "contig_id": fields[0],
                "start": int(fields[3]),
                "end": int(fields[4]),
                "strand": fields[6],
                "partial_5prime": len(partial) == 2 and partial[0] == "1",
                "partial_3prime": len(partial) == 2 and partial[1] == "1",
                "partial_code": partial,
            })
    return genes


def parse_prodigal_protein_headers(
    protein_path: Path,
    gff_path: Path,
    sample_id: str,
) -> list[dict[str, Any]]:
    """Map Prodigal's public FASTA IDs to its internal GFF IDs and coordinates."""
    gff_genes = {gene["gene_id"]: gene for gene in parse_prodigal_gff(gff_path, sample_id)}
    genes: list[dict[str, Any]] = []
    with protein_path.open("r", encoding="utf-8", errors="strict") as handle:
        for line in handle:
            if not line.startswith(">"):
                continue
            fields = line[1:].rstrip("\n").split(" # ", 4)
            if len(fields) != 5:
                raise AnalysisError(f"malformed Prodigal protein header in {protein_path.name}")
            sequence_id = fields[0].split()[0]
            attributes = {}
            for item in fields[4].split(";"):
                if "=" in item:
                    key, value = item.split("=", 1)
                    attributes[key] = value
            internal_id = attributes.get("ID")
            if not internal_id or internal_id not in gff_genes:
                raise AnalysisError(
                    f"Prodigal protein ID cannot be mapped to GFF in {protein_path.name}"
                )
            gff_gene = gff_genes[internal_id]
            partial = attributes.get("partial", gff_gene["partial_code"])
            strand = "+" if fields[3] == "1" else "-" if fields[3] == "-1" else gff_gene["strand"]
            genes.append({
                **gff_gene,
                "gene_id": sequence_id,
                "original_sequence_id": sequence_id,
                "prodigal_internal_id": internal_id,
                "start": int(fields[1]),
                "end": int(fields[2]),
                "strand": strand,
                "partial_5prime": len(partial) == 2 and partial[0] == "1",
                "partial_3prime": len(partial) == 2 and partial[1] == "1",
                "partial_code": partial,
            })
    if len(genes) != len(gff_genes):
        raise AnalysisError(
            f"Prodigal FASTA/GFF gene counts differ in {protein_path.name}: "
            f"{len(genes)} != {len(gff_genes)}"
        )
    return genes


def run_prodigal(sample: dict[str, Any], kind: InputKind, output_dir: Path) -> dict[str, str]:
    if kind != InputKind.genome:
        raise AnalysisError("Prodigal is only used for genome input")
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_id = sample["sample_id"]
    protein_path = output_dir / f"{sample_id}.faa"
    cds_path = output_dir / f"{sample_id}.fna"
    gff_path = output_dir / f"{sample_id}.gff"
    mode = "single"
    command = [
        "prodigal",
        "-i",
        sample["fasta_path"],
        "-a",
        str(protein_path),
        "-d",
        str(cds_path),
        "-o",
        str(gff_path),
        "-f",
        "gff",
        "-p",
        mode,
        "-q",
    ]
    try:
        completed = run_external(command, timeout=settings.worker_ttl)
    except ExternalCommandError as error:
        raise AnalysisError(str(error), error.code) from error
    if completed.returncode != 0:
        raise AnalysisError(f"Prodigal failed for {sample['display_name']}: {completed.stderr[-1500:]}")
    genes = parse_prodigal_protein_headers(protein_path, gff_path, sample["sample_id"])
    genes_path = output_dir / f"{sample_id}.predicted_genes.json"
    write_json(genes_path, genes)
    genes_tsv = output_dir / f"{sample_id}.predicted_genes.tsv"
    with genes_tsv.open("w", encoding="utf-8", newline="") as handle:
        columns = [
            "sample_id", "gene_id", "original_sequence_id", "contig_id", "start", "end",
            "strand", "partial_5prime", "partial_3prime", "partial_code",
            "prodigal_internal_id",
        ]
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(genes)
    write_json(
        output_dir / f"{sample_id}.prodigal.json",
        {
            "command": command, "mode": mode, "stderr": completed.stderr[-4000:],
            "wall_seconds": completed.wall_seconds, "peak_rss_kb": completed.peak_rss_kb,
            "predicted_gene_count": len(genes),
        },
    )
    return {
        "protein_path": str(protein_path), "cds_path": str(cds_path), "gff_path": str(gff_path),
        "genes_path": str(genes_path), "genes_tsv_path": str(genes_tsv),
    }


def parse_domtblout(path: Path, sample_id: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split(maxsplit=22)
            if len(fields) < 22:
                raise AnalysisError(f"malformed HMMER domtblout line in {path.name}")
            profile_id, _, hmm_length = fields[0], fields[1], int(fields[2])
            sequence_id, _, sequence_length = fields[3], fields[4], int(fields[5])
            full_evalue, full_score = float(fields[6]), float(fields[7])
            domain_number, domain_count = int(fields[9]), int(fields[10])
            conditional_evalue, domain_evalue, domain_score = (
                float(fields[11]),
                float(fields[12]),
                float(fields[13]),
            )
            hmm_from, hmm_to = int(fields[15]), int(fields[16])
            ali_from, ali_to = int(fields[17]), int(fields[18])
            signature = ":".join(
                map(str, (sample_id, sequence_id, profile_id, domain_number, hmm_from, ali_from))
            )
            hit_id = "hit:" + hashlib.sha1(signature.encode()).hexdigest()[:20]
            hits.append(
                {
                    "hit_id": hit_id,
                    "sample_id": sample_id,
                    "sequence_id": sequence_id,
                    "profile_id": profile_id,
                    "hmm_length": hmm_length,
                    "sequence_length": sequence_length,
                    "full_evalue": full_evalue,
                    "full_score": full_score,
                    "domain_number": domain_number,
                    "domain_count": domain_count,
                    "conditional_evalue": conditional_evalue,
                    "domain_c_evalue": conditional_evalue,
                    "domain_evalue": domain_evalue,
                    "domain_i_evalue": domain_evalue,
                    "domain_score": domain_score,
                    "hmm_from": hmm_from,
                    "hmm_to": hmm_to,
                    "ali_from": ali_from,
                    "ali_to": ali_to,
                    "hmm_coverage": (hmm_to - hmm_from + 1) / hmm_length,
                    "sequence_coverage": (ali_to - ali_from + 1) / sequence_length,
                    "description": fields[22] if len(fields) == 23 else "",
                }
            )
    return hits


def parse_ga_thresholds(path: Path) -> dict[str, dict[str, float]]:
    thresholds: dict[str, dict[str, float]] = {}
    current_profile: str | None = None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("NAME"):
                current_profile = line.split(maxsplit=1)[1].strip()
            elif line.startswith("GA") and current_profile:
                values = line.split(maxsplit=1)[1].rstrip(";\n ").split()
                if not values:
                    continue
                sequence_score = float(values[0])
                domain_score = float(values[1]) if len(values) > 1 else sequence_score
                thresholds[current_profile] = {
                    "full_score_min": sequence_score,
                    "domain_score_min": domain_score,
                }
    return thresholds


def apply_hit_rule(
    hits: list[dict[str, Any]],
    threshold_type: str,
    thresholds: dict[str, float] | None,
    ga_thresholds: dict[str, dict[str, float]] | None = None,
) -> list[dict[str, Any]]:
    for hit in hits:
        reasons: list[str] = []
        if threshold_type == "ga":
            applied = {"type": "ga", **(ga_thresholds or {}).get(hit["profile_id"], {})}
            passed = True  # --cut_ga already applies both model-specific cutoffs.
            rule = "profile_ga"
        else:
            if not thresholds:
                raise AnalysisError("an evalue database requires hit thresholds")
            full_max = thresholds["full_evalue_max"]
            domain_max = thresholds["domain_i_evalue_max"]
            if hit["full_evalue"] > full_max:
                reasons.append("full_evalue")
            if hit["domain_i_evalue"] > domain_max:
                reasons.append("domain_i_evalue")
            passed = not reasons
            applied = {
                "type": "evalue",
                "full_evalue_max": full_max,
                "domain_i_evalue_max": domain_max,
            }
            rule = f"full_evalue<={full_max:g};domain_i_evalue<={domain_max:g}"
        hit.update(
            {
                "pass": passed,
                "failure_reasons": reasons,
                "hit_rule_version": HIT_RULE_VERSION,
                "applied_thresholds": applied,
                "threshold_rule": rule,
            }
        )
    return hits


def run_hmmscan(
    sample_id: str,
    protein_path: Path,
    hmm_path: Path,
    output_dir: Path,
    threshold_type: str,
    thresholds: dict[str, float] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    domtblout = output_dir / f"{sample_id}.domtblout"
    tblout = output_dir / f"{sample_id}.tblout"
    stdout_path = output_dir / f"{sample_id}.hmmscan.txt"
    command = [
        "hmmscan",
        "--noali",
        "--tblout",
        str(tblout),
        "--domtblout",
        str(domtblout),
    ]
    if threshold_type == "ga":
        command.append("--cut_ga")
        rule = "profile_ga"
    else:
        if not thresholds or any(value <= 0 for value in thresholds.values()):
            raise AnalysisError("an evalue database requires positive hit thresholds")
        command.extend(["-E", str(thresholds["full_evalue_max"]), "--domE", "10"])
        rule = (
            f"full_evalue<={thresholds['full_evalue_max']:g};"
            f"domain_i_evalue<={thresholds['domain_i_evalue_max']:g}"
        )
    command.extend([str(hmm_path), str(protein_path)])
    with stdout_path.open("w", encoding="utf-8") as stdout:
        try:
            completed = run_external(command, stdout=stdout, timeout=settings.worker_ttl)
        except ExternalCommandError as error:
            raise AnalysisError(str(error), error.code) from error
    if completed.returncode != 0:
        raise AnalysisError(f"hmmscan failed for {sample_id}: {completed.stderr[-1500:]}")
    hits = parse_domtblout(domtblout, sample_id)
    hits = apply_hit_rule(
        hits,
        threshold_type,
        thresholds,
        parse_ga_thresholds(hmm_path) if threshold_type == "ga" else None,
    )
    metadata = {
        "sample_id": sample_id,
        "command": command,
        "threshold_rule": rule,
        "candidate_hit_count": len(hits),
        "passing_hit_count": sum(hit["pass"] for hit in hits),
        "stderr": completed.stderr[-4000:],
        "wall_seconds": completed.wall_seconds,
        "peak_rss_kb": completed.peak_rss_kb,
        "files": {
            "domtblout": str(domtblout),
            "tblout": str(tblout),
            "stdout": str(stdout_path),
        },
    }
    write_json(output_dir / f"{sample_id}.hmmscan.json", metadata)
    return hits, metadata
