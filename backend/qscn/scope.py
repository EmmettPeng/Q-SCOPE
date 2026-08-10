from __future__ import annotations

from typing import Any

from .schemas import ANALYSIS_SCOPE_VERSION, AnalysisScopeRequest, DatabaseManifest


def all_scope() -> dict[str, Any]:
    return {
        "version": ANALYSIS_SCOPE_VERSION,
        "mode": "all",
        "requested_values": [],
        "resolved_pathway_ids": [],
    }


def normalize_scope(
    manifest: DatabaseManifest,
    scope: AnalysisScopeRequest | dict[str, Any] | None,
) -> dict[str, Any]:
    if scope is None:
        return {**all_scope(), "resolved_pathway_ids": [pathway.pathway_id for pathway in manifest.pathways]}
    requested = scope if isinstance(scope, AnalysisScopeRequest) else AnalysisScopeRequest.model_validate(scope)
    if requested.mode == "all":
        return {**all_scope(), "resolved_pathway_ids": [pathway.pathway_id for pathway in manifest.pathways]}

    pathway_ids = [pathway.pathway_id for pathway in manifest.pathways]
    if requested.mode == "pathways":
        unknown = sorted(set(requested.requested_values) - set(pathway_ids))
        if unknown:
            raise ValueError(f"unknown pathway IDs: {', '.join(unknown)}")
        selected = set(requested.requested_values)
        resolved = [pathway_id for pathway_id in pathway_ids if pathway_id in selected]
    else:
        signal_names = list(dict.fromkeys(pathway.signal_name for pathway in manifest.pathways))
        unknown = sorted(set(requested.requested_values) - set(signal_names))
        if unknown:
            raise ValueError(f"unknown signal names: {', '.join(unknown)}")
        selected = set(requested.requested_values)
        resolved = [
            pathway.pathway_id for pathway in manifest.pathways if pathway.signal_name in selected
        ]
    if not resolved:
        raise ValueError("analysis scope resolved to no pathways")
    ordered_requested = (
        [value for value in pathway_ids if value in set(requested.requested_values)]
        if requested.mode == "pathways"
        else [value for value in signal_names if value in set(requested.requested_values)]
    )
    return {
        "version": ANALYSIS_SCOPE_VERSION,
        "mode": requested.mode,
        "requested_values": ordered_requested,
        "resolved_pathway_ids": resolved,
    }
