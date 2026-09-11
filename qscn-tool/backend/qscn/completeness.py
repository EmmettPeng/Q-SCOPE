from __future__ import annotations

from typing import Any, Iterable

from .schemas import CapabilityRule, DatabaseManifest, PathwayDefinition


ROLES = ("sending", "receiving")


def _profiles_for(pathway: PathwayDefinition, role: str) -> list[str]:
    return pathway.sending_profiles if role == "sending" else pathway.receiving_profiles


def strict_rules(manifest: DatabaseManifest) -> list[CapabilityRule]:
    return [
        CapabilityRule(pathway_id=pathway.pathway_id, role=role, strategy="all")
        for pathway in manifest.pathways
        for role in ROLES
        if _profiles_for(pathway, role)
    ]


def validate_rules(
    manifest: DatabaseManifest,
    rules: Iterable[CapabilityRule | dict[str, Any]] | None,
) -> list[CapabilityRule]:
    normalized = strict_rules(manifest) if rules is None else [
        rule if isinstance(rule, CapabilityRule) else CapabilityRule.model_validate(rule)
        for rule in rules
    ]
    expected = {
        (pathway.pathway_id, role)
        for pathway in manifest.pathways
        for role in ROLES
        if _profiles_for(pathway, role)
    }
    keys = [(rule.pathway_id, rule.role) for rule in normalized]
    if len(keys) != len(set(keys)):
        raise ValueError("capability rules contain duplicate pathway roles")
    missing = sorted(expected - set(keys))
    extra = sorted(set(keys) - expected)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing rules: {missing}")
        if extra:
            details.append(f"unknown rules: {extra}")
        raise ValueError("; ".join(details))

    pathways = {pathway.pathway_id: pathway for pathway in manifest.pathways}
    for rule in normalized:
        profiles = _profiles_for(pathways[rule.pathway_id], rule.role)
        if len(profiles) == 1 and rule.strategy != "all":
            raise ValueError(f"single-component role {rule.pathway_id}/{rule.role} must use all")
        unknown = sorted(set(rule.required_profiles) - set(profiles))
        if unknown:
            raise ValueError(
                f"required profiles are not part of {rule.pathway_id}/{rule.role}: {', '.join(unknown)}"
            )
        if rule.guidance_endpoint_id:
            guidance = manifest.interpretation_guidance
            endpoint = next(
                (
                    item
                    for item in (guidance.endpoints if guidance else [])
                    if item.endpoint_id == rule.guidance_endpoint_id
                ),
                None,
            )
            if (
                guidance is None
                or rule.guidance_version != guidance.version
                or endpoint is None
                or endpoint.pathway_id != rule.pathway_id
                or endpoint.role != rule.role
                or endpoint.required_profiles != rule.required_profiles
            ):
                raise ValueError("guidance endpoint does not match the database capability rule")
    return normalized


def _role_call(
    sample_id: str,
    pathway: PathwayDefinition,
    role: str,
    profiles: list[str],
    observed_profiles: set[str],
    supporting_hits: dict[str, list[str]],
    rule: CapabilityRule,
) -> dict[str, Any]:
    profile_set = set(profiles)
    observed = sorted(profile_set & observed_profiles)
    missing = sorted(profile_set - observed_profiles)
    if rule.strategy == "all":
        required_profiles = list(profiles)
        required_hits = len(profiles)
        missing_required = sorted(set(required_profiles) - observed_profiles)
        capable = not missing_required and bool(observed)
    else:
        required_profiles = list(rule.required_profiles)
        required_hits = len(required_profiles)
        missing_required = sorted(set(required_profiles) - observed_profiles)
        capable = not missing_required and bool(observed)
    hit_ids = sorted({hit_id for profile in observed for hit_id in supporting_hits.get(profile, [])})
    component_hit_ids = {
        profile: sorted(supporting_hits.get(profile, [])) for profile in observed
    }
    return {
        "sample_id": sample_id,
        "pathway_id": pathway.pathway_id,
        "pathway_name": pathway.name,
        "signal_name": pathway.signal_name,
        "references": pathway.references,
        "role": role,
        "rule_strategy": rule.strategy,
        "total_components": len(profiles),
        "observed_components": observed,
        "missing_components": missing,
        "required_profiles": required_profiles,
        "missing_required_profiles": missing_required,
        "required_hits": required_hits,
        "completeness": len(observed) / len(profiles),
        "capable": capable,
        "status": f"{role}_capable" if capable else ("component_evidence" if observed else "not_detected"),
        "supporting_hit_ids": hit_ids,
        "component_hit_ids": component_hit_ids,
    }


def calculate_capabilities(
    manifest: DatabaseManifest,
    hits: Iterable[dict[str, Any]],
    sample_ids: Iterable[str],
    rules: Iterable[CapabilityRule | dict[str, Any]] | None = None,
    pathway_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    rules = validate_rules(manifest, rules)
    rule_map = {(rule.pathway_id, rule.role): rule for rule in rules}
    observed_by_sample: dict[str, set[str]] = {sample_id: set() for sample_id in sample_ids}
    ids_by_sample_profile: dict[str, dict[str, list[str]]] = {
        sample_id: {} for sample_id in sample_ids
    }
    for hit in hits:
        if not hit.get("pass", True):
            continue
        sample_id = hit["sample_id"]
        profile = hit["profile_id"]
        observed_by_sample.setdefault(sample_id, set()).add(profile)
        ids_by_sample_profile.setdefault(sample_id, {}).setdefault(profile, []).append(hit["hit_id"])

    calls: list[dict[str, Any]] = []
    for sample_id in observed_by_sample:
        for pathway in manifest.pathways:
            if pathway_ids is not None and pathway.pathway_id not in pathway_ids:
                continue
            for role in ROLES:
                profiles = _profiles_for(pathway, role)
                if not profiles:
                    continue
                calls.append(
                    _role_call(
                        sample_id,
                        pathway,
                        role,
                        profiles,
                        observed_by_sample[sample_id],
                        ids_by_sample_profile[sample_id],
                        rule_map[(pathway.pathway_id, role)],
                    )
                )
    return calls
