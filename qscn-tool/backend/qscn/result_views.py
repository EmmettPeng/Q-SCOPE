from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from . import db


def _selected_result_path(run_id: str, interpretation_id: str | None = None) -> Path:
    interpretations = db.list_rows("interpretations", "run_id=?", (run_id,))
    if not interpretations:
        raise ValueError("results not found")
    selected = next((item for item in interpretations if item["id"] == interpretation_id), None)
    if interpretation_id and selected is None:
        raise ValueError("interpretation not found for run")
    selected = selected or interpretations[0]
    return Path(selected["result_path"])


def load_result(run_id: str, interpretation_id: str | None = None) -> dict[str, Any]:
    return json.loads(_selected_result_path(run_id, interpretation_id).read_text(encoding="utf-8"))


def result_summary(payload: dict[str, Any]) -> dict[str, Any]:
    network = payload.get("network", {})
    return {
        **{key: value for key, value in payload.items() if key not in {
            "hits", "capabilities", "biological_annotations", "network",
        }},
        "hits": [],
        "capabilities": [],
        "biological_annotations": [],
        "network": {**network, "edges": []},
        "biological_rule_ids": sorted({
            item.get("rule_id")
            for item in payload.get("biological_annotations", [])
            if item.get("rule_id")
        }),
        "result_counts": {
            "hits": len(payload.get("hits", [])),
            "capabilities": len(payload.get("capabilities", [])),
            "biological_annotations": len(payload.get("biological_annotations", [])),
            "network_edges": len(network.get("edges", [])),
        },
    }


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.partial")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def materialize_result_views(result_path: Path, payload: dict[str, Any]) -> None:
    """Persist small view files so the web process never reparses results.json per tab."""
    target = result_path.parent
    _atomic_json(target / "summary.json", result_summary(payload))
    _atomic_json(target / "capabilities.json", payload.get("capabilities", []))
    _atomic_json(target / "biological_annotations.json", payload.get("biological_annotations", []))
    _atomic_json(target / "network_edges.json", payload.get("network", {}).get("edges", []))
    hits_path = result_path.parents[2] / "hits.ndjson"
    temporary = hits_path.with_name(f".{hits_path.name}.{os.getpid()}.partial")
    with temporary.open("w", encoding="utf-8") as handle:
        for hit in payload.get("hits", []):
            handle.write(json.dumps(hit, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(hits_path)


def _ensure_result_views(run_id: str, interpretation_id: str | None) -> Path:
    result_path = _selected_result_path(run_id, interpretation_id)
    if not (result_path.parent / "summary.json").exists():
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        materialize_result_views(result_path, payload)
    return result_path


def load_result_summary(run_id: str, interpretation_id: str | None = None) -> dict[str, Any]:
    result_path = _ensure_result_views(run_id, interpretation_id)
    return json.loads((result_path.parent / "summary.json").read_text(encoding="utf-8"))


def _load_view_items(result_path: Path, filename: str) -> list[dict[str, Any]]:
    return json.loads((result_path.parent / filename).read_text(encoding="utf-8"))


def _supporting_hits(result_path: Path, calls: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    wanted = {
        hit_id for call in calls
        for hit_id in (call.get("supporting_hit_ids") or [])
    }
    if not wanted:
        return {}
    found: dict[str, dict[str, Any]] = {}
    with (result_path.parents[2] / "hits.ndjson").open(encoding="utf-8") as handle:
        for line in handle:
            hit = json.loads(line)
            if hit.get("hit_id") in wanted:
                found[hit["hit_id"]] = hit
                if len(found) == len(wanted):
                    break
    return found


def _hit_matches(
    hit: dict[str, Any],
    min_hmm_coverage: float,
    min_sequence_coverage: float,
    include_partial: bool,
) -> bool:
    if float(hit.get("hmm_coverage") or 0) < min_hmm_coverage:
        return False
    if float(hit.get("sequence_coverage") or 0) < min_sequence_coverage:
        return False
    if not include_partial and str(hit.get("gene_integrity_state") or "").startswith("partial_"):
        return False
    return True


def _qualifying_profiles(
    call: dict[str, Any],
    hits_by_id: dict[str, dict[str, Any]],
    min_hmm_coverage: float,
    min_sequence_coverage: float,
    include_partial: bool,
) -> set[str]:
    mapped = call.get("component_hit_ids") or {}
    if not mapped:
        mapped = {}
        for hit_id in call.get("supporting_hit_ids") or []:
            hit = hits_by_id.get(hit_id)
            if hit and hit.get("profile_id") in (call.get("observed_components") or []):
                mapped.setdefault(hit["profile_id"], []).append(hit_id)
    return {
        profile
        for profile, hit_ids in mapped.items()
        if any(
            hit_id in hits_by_id
            and _hit_matches(
                hits_by_id[hit_id],
                min_hmm_coverage,
                min_sequence_coverage,
                include_partial,
            )
            for hit_id in hit_ids
        )
    }


def _capability_matches(
    call: dict[str, Any],
    hits_by_id: dict[str, dict[str, Any]],
    min_hmm_coverage: float,
    min_sequence_coverage: float,
    include_partial: bool,
    biological_rule_id: str = "",
) -> bool:
    if biological_rule_id and not any(
        item.get("rule_id") == biological_rule_id
        for item in call.get("biological_annotations") or []
    ):
        return False
    if min_hmm_coverage <= 0 and min_sequence_coverage <= 0 and include_partial:
        return True
    qualifying = _qualifying_profiles(
        call,
        hits_by_id,
        min_hmm_coverage,
        min_sequence_coverage,
        include_partial,
    )
    if not call.get("capable"):
        return bool(qualifying)
    required = call.get("required_profiles") or call.get("observed_components") or []
    return bool(required) and all(profile in qualifying for profile in required)


def filtered_capabilities(
    payload: dict[str, Any],
    min_hmm_coverage: float = 0,
    min_sequence_coverage: float = 0,
    include_partial: bool = True,
    biological_rule_id: str = "",
) -> dict[str, Any]:
    capabilities = payload.get("capabilities", [])
    hits_by_id = {item["hit_id"]: item for item in payload.get("hits", [])}
    items = [
        call for call in capabilities
        if _capability_matches(
            call,
            hits_by_id,
            min_hmm_coverage,
            min_sequence_coverage,
            include_partial,
            biological_rule_id,
        )
    ]
    return {"items": items, "total": len(items), "baseline": len(capabilities)}


def filtered_edges(
    payload: dict[str, Any],
    min_hmm_coverage: float = 0,
    min_sequence_coverage: float = 0,
    include_partial: bool = True,
    biological_rule_id: str = "",
) -> dict[str, Any]:
    network = payload.get("network", {})
    edges = network.get("edges", [])
    hits_by_id = {item["hit_id"]: item for item in payload.get("hits", [])}
    calls = {
        (call["sample_id"], call["pathway_id"], call["role"]): call
        for call in payload.get("capabilities", [])
    }
    items = []
    for edge in edges:
        if biological_rule_id and biological_rule_id not in (edge.get("biological_rule_ids") or []):
            continue
        sender = calls.get((edge["source_sample"], edge["pathway_id"], "sending"))
        receiver = calls.get((edge["target_sample"], edge["pathway_id"], "receiving"))
        if not sender or not receiver:
            continue
        if _capability_matches(
            sender, hits_by_id, min_hmm_coverage, min_sequence_coverage, include_partial,
        ) and _capability_matches(
            receiver, hits_by_id, min_hmm_coverage, min_sequence_coverage, include_partial,
        ):
            items.append(edge)
    return {"items": items, "total": len(items), "baseline": len(edges)}


def paged_hits(
    payload: dict[str, Any],
    offset: int,
    limit: int,
    profile_ids: Iterable[str] = (),
    min_hmm_coverage: float = 0,
    min_sequence_coverage: float = 0,
    include_partial: bool = True,
    biological_rule_id: str = "",
) -> dict[str, Any]:
    allowed_profiles = set(profile_ids)
    allowed_hit_ids: set[str] | None = None
    if biological_rule_id:
        allowed_hit_ids = {
            hit_id
            for annotation in payload.get("biological_annotations", [])
            if annotation.get("rule_id") == biological_rule_id
            for hit_id in annotation.get("supporting_hit_ids") or []
        }
    scoped = [
        hit for hit in payload.get("hits", [])
        if (not allowed_profiles or hit.get("profile_id") in allowed_profiles)
    ]
    items = [
        hit for hit in scoped
        if (allowed_hit_ids is None or hit.get("hit_id") in allowed_hit_ids)
        and _hit_matches(hit, min_hmm_coverage, min_sequence_coverage, include_partial)
    ]
    return {
        "items": items[offset:offset + limit],
        "record_ids": [item["hit_id"] for item in items],
        "total": len(items),
        "baseline": len(scoped),
        "offset": offset,
        "limit": limit,
    }


def run_capabilities(
    run_id: str, interpretation_id: str, min_hmm_coverage: float = 0,
    min_sequence_coverage: float = 0, include_partial: bool = True,
    biological_rule_id: str = "",
) -> dict[str, Any]:
    result_path = _ensure_result_views(run_id, interpretation_id)
    calls = _load_view_items(result_path, "capabilities.json")
    hits = {} if min_hmm_coverage <= 0 and min_sequence_coverage <= 0 and include_partial else _supporting_hits(result_path, calls)
    return filtered_capabilities(
        {"capabilities": calls, "hits": list(hits.values())}, min_hmm_coverage,
        min_sequence_coverage, include_partial, biological_rule_id,
    )


def run_edges(
    run_id: str, interpretation_id: str, min_hmm_coverage: float = 0,
    min_sequence_coverage: float = 0, include_partial: bool = True,
    biological_rule_id: str = "",
) -> dict[str, Any]:
    result_path = _ensure_result_views(run_id, interpretation_id)
    calls = _load_view_items(result_path, "capabilities.json")
    edges = _load_view_items(result_path, "network_edges.json")
    hits = {} if min_hmm_coverage <= 0 and min_sequence_coverage <= 0 and include_partial else _supporting_hits(result_path, calls)
    return filtered_edges(
        {"capabilities": calls, "hits": list(hits.values()), "network": {"edges": edges}},
        min_hmm_coverage, min_sequence_coverage, include_partial, biological_rule_id,
    )


def run_annotations(run_id: str, interpretation_id: str) -> dict[str, Any]:
    result_path = _ensure_result_views(run_id, interpretation_id)
    items = _load_view_items(result_path, "biological_annotations.json")
    return {"items": items, "total": len(items), "baseline": len(items)}


def run_paged_hits(
    run_id: str, interpretation_id: str, offset: int, limit: int,
    profile_ids: Iterable[str] = (), min_hmm_coverage: float = 0,
    min_sequence_coverage: float = 0, include_partial: bool = True,
    biological_rule_id: str = "",
) -> dict[str, Any]:
    result_path = _ensure_result_views(run_id, interpretation_id)
    profiles = set(profile_ids)
    allowed_hit_ids: set[str] | None = None
    if biological_rule_id:
        annotations = _load_view_items(result_path, "biological_annotations.json")
        allowed_hit_ids = {
            hit_id for annotation in annotations if annotation.get("rule_id") == biological_rule_id
            for hit_id in annotation.get("supporting_hit_ids") or []
        }
    baseline = total = 0
    page: list[dict[str, Any]] = []
    record_ids: list[str] = []
    with (result_path.parents[2] / "hits.ndjson").open(encoding="utf-8") as handle:
        for line in handle:
            hit = json.loads(line)
            if profiles and hit.get("profile_id") not in profiles:
                continue
            baseline += 1
            if allowed_hit_ids is not None and hit.get("hit_id") not in allowed_hit_ids:
                continue
            if not _hit_matches(hit, min_hmm_coverage, min_sequence_coverage, include_partial):
                continue
            record_ids.append(hit["hit_id"])
            if offset <= total < offset + limit:
                page.append(hit)
            total += 1
    return {
        "items": page, "record_ids": record_ids, "total": total, "baseline": baseline,
        "offset": offset, "limit": limit,
    }
