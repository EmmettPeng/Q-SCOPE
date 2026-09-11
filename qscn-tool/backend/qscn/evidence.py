from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Iterable

from .schemas import DatabaseManifest


EVIDENCE_RULE_VERSION = "1.1"


BIO_RULES: dict[str, dict[str, Any]] = {
    "BIO-01": {
        "state": "signal_subtype_unresolved",
        "references": [
            "https://doi.org/10.1073/pnas.93.18.9505",
            "https://doi.org/10.1128/JB.183.12.3537-3547.2001",
            "https://doi.org/10.1111/j.1365-2958.2011.07548.x",
        ],
    },
    "BIO-02": {
        "state": "ligand_specificity_and_activity_unresolved",
        "references": [
            "https://doi.org/10.1046/j.1365-2958.2000.01684.x",
            "https://doi.org/10.1111/j.1365-2958.2011.07548.x",
            "https://doi.org/10.1021/bi400315s",
        ],
    },
    "BIO-03": {
        "state": "luxr_solo_candidate",
        "references": ["https://pubmed.ncbi.nlm.nih.gov/11544237/"],
    },
    "BIO-04": {
        "state": "metabolism_qs_ambiguity",
        "references": [
            "https://doi.org/10.1046/j.1365-2958.2001.02532.x",
            "https://doi.org/10.1128/JB.188.8.2885-2897.2006",
        ],
    },
    "BIO-05": {
        "state": "binding_transduction_substeps",
        "references": [
            "https://doi.org/10.1038/415545a",
            "https://doi.org/10.1016/j.cell.2006.07.032",
        ],
    },
    "BIO-06": {
        "state": "lsr_substep_role",
        "references": [
            "https://doi.org/10.1046/j.1365-2958.2001.02669.x",
            "https://doi.org/10.1046/j.1365-2958.2003.03781.x",
            "https://doi.org/10.1016/j.molcel.2004.07.020",
            "https://doi.org/10.1128/JB.187.1.238-248.2005",
            "https://doi.org/10.1128/JB.00014-07",
        ],
    },
    "BIO-07": {
        "state": "downstream_regulator_not_direct_receptor",
        "references": [
            "https://doi.org/10.1111/j.1365-2958.2006.05386.x",
            "https://doi.org/10.1073/pnas.1712524114",
        ],
    },
    "BIO-08": {
        "state": "family_hit_not_activity",
        "references": ["https://doi.org/10.1128/JB.187.5.1792-1798.2005"],
    },
    "BIO-09": {
        "state": "intracellular_second_messenger_context",
        "references": ["https://doi.org/10.1128/JB.01253-09"],
    },
    "BIO-10": {
        "state": "entry_step_not_product_specificity",
        "references": ["https://doi.org/10.1128/JB.01140-07"],
    },
    "BIO-11": {
        "state": "heterodimer_partner_required_context",
        "references": ["https://doi.org/10.1074/JBC.M115.708453"],
    },
    "BIO-12": {
        "state": "intermediate_step_not_pqs_proof",
        "references": [
            "https://doi.org/10.1074/JBC.M804555200",
            "https://doi.org/10.1021/bi9009055",
        ],
    },
    "BIO-13": {
        "state": "pqsE_biosynthesis_contribution_context_dependent",
        "references": [
            "https://doi.org/10.1128/JB.00753-08",
            "https://doi.org/10.1128/msystems.00194-20",
            "https://doi.org/10.1128/jb.00402-25",
        ],
    },
    "BIO-14": {
        "state": "precursor_source_not_universal_requirement",
        "references": [
            "https://doi.org/10.1128/JB.184.23.6472-6480.2002",
            "https://doi.org/10.1128/JB.00209-07",
        ],
    },
    "BIO-15": {
        "state": "pqs_conversion_not_hhq_requirement",
        "references": ["https://doi.org/10.1111/j.1365-2958.2010.07303.x"],
    },
}


COMPONENT_RULES: dict[str, tuple[str, ...]] = {
    "LuxM": ("BIO-01",),
    "LuxI": ("BIO-01",),
    "RpfF": ("BIO-01",),
    "CqsA": ("BIO-01",),
    "LuxN": ("BIO-02",),
    "LuxR": ("BIO-02",),
    "RpfC": ("BIO-02",),
    "CqsS": ("BIO-02",),
    "PqsR": ("BIO-02",),
    "LuxS": ("BIO-04",),
    "RpfG": ("BIO-07",),
    "DGC": ("BIO-08",),
    "Clp": ("BIO-09",),
    "PqsA": ("BIO-10",),
    "PqsD": ("BIO-12",),
    "PqsE": ("BIO-13",),
    "PhnA": ("BIO-14",),
    "PhnB": ("BIO-14",),
    "PqsH": ("BIO-15",),
}


LSR_ROLES = {
    "LsrA": "transport_atp_binding",
    "LsrB": "binding",
    "LsrC": "transport_permease",
    "LsrD": "transport_permease",
    "LsrK": "processing",
    "LsrR": "regulation",
}


COMPONENT_REFERENCES: dict[tuple[str, str], list[str]] = {
    ("BIO-01", "LuxM"): [
        "https://doi.org/10.1111/j.1365-2958.1994.tb00422.x",
        "https://doi.org/10.1128/JB.183.12.3537-3547.2001",
    ],
    ("BIO-01", "LuxI"): [
        "https://doi.org/10.1073/pnas.93.18.9505",
        "https://doi.org/10.1111/j.1365-2958.2004.04211.x",
    ],
    ("BIO-01", "RpfF"): ["https://doi.org/10.1046/j.1365-2958.1997.3721736.x"],
    ("BIO-01", "CqsA"): [
        "https://doi.org/10.1021/cb1003652",
        "https://doi.org/10.1111/j.1365-2958.2011.07548.x",
    ],
    ("BIO-02", "LuxN"): [
        "https://doi.org/10.1046/j.1365-2958.2000.01684.x",
        "https://doi.org/10.1016/j.cell.2008.06.023",
    ],
    ("BIO-02", "LuxR"): [
        "https://doi.org/10.1093/emboj/cdf459",
        "https://doi.org/10.1128/mbio.00146-19",
    ],
    ("BIO-02", "RpfC"): ["https://doi.org/10.1371/journal.ppat.1006304"],
    ("BIO-02", "CqsS"): [
        "https://doi.org/10.1111/j.1365-2958.2011.07548.x",
        "https://doi.org/10.1111/j.1365-2958.2012.07992.x",
    ],
    ("BIO-02", "PqsR"): ["https://doi.org/10.1021/bi400315s"],
}


COMPONENT_DETAILS: dict[tuple[str, str], dict[str, Any]] = {
    ("BIO-07", "RpfG"): {
        "direct_receptor": False,
        "retracted_activity_reference_excluded": "https://doi.org/10.1073/pnas.0600345103",
        "retraction_notice": "https://doi.org/10.1073/pnas.1712524114",
    },
    ("BIO-15", "PqsH"): {
        "conversion": "HHQ_to_PQS",
        "oxygen_dependent": True,
    },
    ("BIO-13", "PqsE"): {
        "hhq_core_member": False,
        "downstream_rhlr_regulatory_support": True,
        "haq_biosynthesis_contribution": "strain_dependent",
    },
}


def _integrity_state(hit: dict[str, Any]) -> str:
    five = hit.get("partial_5prime")
    three = hit.get("partial_3prime")
    if five is None or three is None:
        return "unknown"
    if five and three:
        return "partial_both"
    if five:
        return "partial_5p"
    if three:
        return "partial_3p"
    return "complete_prediction"


def annotate_hit_quality(hits: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add QH evidence without applying coverage cutoffs or changing hit pass state."""
    copied = [dict(hit) for hit in hits]
    profiles_by_protein: dict[tuple[str, str], set[str]] = defaultdict(set)
    for hit in copied:
        sequence_id = hit.get("sequence_id", hit["hit_id"])
        profiles_by_protein[(hit["sample_id"], sequence_id)].add(hit["profile_id"])
    for hit in copied:
        sequence_id = hit.get("sequence_id", hit["hit_id"])
        profiles = sorted(profiles_by_protein[(hit["sample_id"], sequence_id)])
        hit["gene_integrity_state"] = _integrity_state(hit)
        hit["competing_profile_hits"] = [profile for profile in profiles if profile != hit["profile_id"]]
        hit["evidence_rule_version"] = EVIDENCE_RULE_VERSION
    return copied


def _annotation(
    rule_id: str,
    call: dict[str, Any],
    components: list[str],
    component_hit_ids: dict[str, list[str]],
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rule = BIO_RULES[rule_id]
    supporting_hit_ids = sorted({
        hit_id for component in components for hit_id in component_hit_ids.get(component, [])
    })
    signature = "|".join((
        rule_id, call["sample_id"], call["pathway_id"], call["role"], *sorted(components)
    ))
    digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:16]
    references = list(dict.fromkeys(
        reference
        for component in components
        for reference in COMPONENT_REFERENCES.get((rule_id, component), rule["references"])
    ))
    return {
        "annotation_id": f"annotation:{digest}",
        "rule_id": rule_id,
        "rule_version": EVIDENCE_RULE_VERSION,
        "category": "boundary",
        "state": rule["state"],
        "sample_id": call["sample_id"],
        "pathway_id": call["pathway_id"],
        "role": call["role"],
        "components": sorted(components),
        "supporting_hit_ids": supporting_hit_ids,
        "details": details or {},
        "references": references,
        "affects_base_capability": False,
    }


def biological_annotations(
    manifest: DatabaseManifest,
    capabilities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return QSP-only BIO annotations. Custom and KEGG manifests get none."""
    if manifest.database_id != "qsp":
        return []
    calls = {(call["sample_id"], call["pathway_id"], call["role"]): call for call in capabilities}
    annotations: list[dict[str, Any]] = []
    for call in capabilities:
        observed = set(call["observed_components"])
        if not observed:
            continue
        hit_ids = call.get("component_hit_ids", {})
        for component in sorted(observed):
            for rule_id in COMPONENT_RULES.get(component, ()):
                annotations.append(_annotation(
                    rule_id, call, [component], hit_ids,
                    COMPONENT_DETAILS.get((rule_id, component)),
                ))

        if call["pathway_id"] == "LuxI_LuxR_system" and call["role"] == "receiving" and "LuxR" in observed:
            sending = calls.get((call["sample_id"], call["pathway_id"], "sending"))
            if not sending or "LuxI" not in sending["observed_components"]:
                annotations.append(_annotation("BIO-03", call, ["LuxR"], hit_ids))

        if call["pathway_id"] == "LuxS_LuxPQ_system" and call["role"] == "receiving":
            components = sorted(observed & {"LuxP", "LuxQ"})
            if components:
                annotations.append(_annotation(
                    "BIO-05", call, components, hit_ids,
                    {"substep_roles": {"LuxP": "binding", "LuxQ": "transduction"},
                     "represented_substeps": [
                         role for component, role in (("LuxP", "binding"), ("LuxQ", "transduction"))
                         if component in observed
                     ]},
                ))

        if call["pathway_id"] == "LsrABC_system" and call["role"] == "receiving":
            components = sorted(observed & set(LSR_ROLES))
            if components:
                annotations.append(_annotation(
                    "BIO-06", call, components, hit_ids,
                    {"component_roles": {component: LSR_ROLES[component] for component in components}},
                ))

        if call["pathway_id"] == "c-di-GMP_pathway":
            components = sorted(observed & {"DGC", "Clp"})
            if components:
                annotations.append(_annotation("BIO-09", call, components, hit_ids))

        if call["pathway_id"] == "Pqs_operon_system" and call["role"] == "sending":
            partners = sorted(observed & {"PqsB", "PqsC"})
            if partners:
                annotations.append(_annotation(
                    "BIO-11", call, partners, hit_ids,
                    {"partner_state": "complete" if len(partners) == 2 else "partner_missing",
                     "missing_partners": sorted({"PqsB", "PqsC"} - observed)},
                ))

    unique = {annotation["annotation_id"]: annotation for annotation in annotations}
    return [unique[key] for key in sorted(unique)]


def attach_annotations(
    capabilities: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
) -> None:
    by_call: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for annotation in annotations:
        by_call[(annotation["sample_id"], annotation["pathway_id"], annotation["role"])].append(
            annotation
        )
    for call in capabilities:
        call["biological_annotations"] = by_call.get(
            (call["sample_id"], call["pathway_id"], call["role"]), []
        )
