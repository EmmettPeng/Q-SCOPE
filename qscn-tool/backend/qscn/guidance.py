from __future__ import annotations

from copy import deepcopy
from typing import Any


GUIDANCE_VERSION = "1.0"


QSP_INTERPRETATION_GUIDANCE: tuple[dict[str, Any], ...] = (
    {
        "endpoint_id": "qsp-lsr-transport",
        "pathway_id": "LsrABC_system", "role": "receiving",
        "name": "Transport machinery",
        "required_profiles": ["LsrA", "LsrC", "LsrD"],
        "optional_profiles": ["LsrB", "LsrK", "LsrR"],
        "wording": "Candidate encoding the Lsr ATP-binding and permease transport machinery",
        "boundary": "Does not establish AI-2 binding, intracellular phosphorylation, LsrR-mediated regulation or activity.",
        "evidence_ids": ["BIO-06"],
        "references": ["https://doi.org/10.1046/j.1365-2958.2001.02669.x", "https://doi.org/10.1128/JB.187.1.238-248.2005"],
    },
    {
        "endpoint_id": "qsp-lsr-binding-transport",
        "pathway_id": "LsrABC_system", "role": "receiving",
        "name": "Binding plus transport",
        "required_profiles": ["LsrA", "LsrB", "LsrC", "LsrD"],
        "optional_profiles": ["LsrK", "LsrR"],
        "wording": "Candidate encoding the LsrABCD binding-and-transport module",
        "boundary": "Does not establish intracellular phosphorylation, LsrR-mediated regulation or activity.",
        "evidence_ids": ["BIO-06"],
        "references": ["https://doi.org/10.1016/j.molcel.2004.07.020", "https://doi.org/10.1128/JB.187.1.238-248.2005"],
    },
    {
        "endpoint_id": "qsp-lsr-uptake-processing",
        "pathway_id": "LsrABC_system", "role": "receiving",
        "name": "Uptake and intracellular processing",
        "required_profiles": ["LsrA", "LsrB", "LsrC", "LsrD", "LsrK"],
        "optional_profiles": ["LsrR"],
        "wording": "Candidate encoding Lsr-mediated AI-2 binding, uptake and phosphorylation potential",
        "boundary": "Not a full local Lsr component-set call; does not establish LsrR-mediated response or activity.",
        "evidence_ids": ["BIO-06"],
        "references": ["https://doi.org/10.1128/JB.187.1.238-248.2005", "https://doi.org/10.1128/JB.00014-07"],
    },
    {
        "endpoint_id": "qsp-lsr-full-local-set",
        "pathway_id": "LsrABC_system", "role": "receiving",
        "name": "Full local component set",
        "required_profiles": ["LsrA", "LsrB", "LsrC", "LsrD", "LsrK", "LsrR"],
        "optional_profiles": [],
        "wording": "Genome containing the full local LsrA/B/C/D/K/R component set",
        "boundary": "Sequence evidence does not establish expression, uptake, phosphorylation or regulatory activity.",
        "evidence_ids": ["BIO-06"],
        "references": ["https://doi.org/10.1128/JB.187.1.238-248.2005", "https://doi.org/10.1128/JB.00014-07"],
    },
    {
        "endpoint_id": "qsp-luxpq-binding",
        "pathway_id": "LuxS_LuxPQ_system", "role": "receiving",
        "name": "AI-2-binding substep", "required_profiles": ["LuxP"],
        "optional_profiles": ["LuxQ"],
        "wording": "LuxP AI-2-binding-component evidence",
        "boundary": "Does not establish membrane transduction or complete AI-2 reception.",
        "evidence_ids": ["BIO-05"],
        "references": ["https://doi.org/10.1038/415545a", "https://doi.org/10.1016/j.cell.2006.07.032"],
    },
    {
        "endpoint_id": "qsp-luxpq-transduction",
        "pathway_id": "LuxS_LuxPQ_system", "role": "receiving",
        "name": "Membrane-transduction substep", "required_profiles": ["LuxQ"],
        "optional_profiles": ["LuxP"],
        "wording": "LuxQ transduction-component evidence",
        "boundary": "Does not establish LuxP-dependent ligand binding or AI-2-specific reception.",
        "evidence_ids": ["BIO-05"],
        "references": ["https://doi.org/10.1016/j.cell.2006.07.032"],
    },
    {
        "endpoint_id": "qsp-luxpq-complete-reception",
        "pathway_id": "LuxS_LuxPQ_system", "role": "receiving",
        "name": "Complete LuxPQ-mediated AI-2 reception",
        "required_profiles": ["LuxP", "LuxQ"], "optional_profiles": [],
        "wording": "Candidate encoding the LuxP-LuxQ binding-and-transduction pair",
        "boundary": "Sequence evidence does not establish expression, ligand availability or receptor activity.",
        "evidence_ids": ["BIO-05"],
        "references": ["https://doi.org/10.1038/415545a", "https://doi.org/10.1016/j.cell.2006.07.032"],
    },
    {
        "endpoint_id": "qsp-rpf-sensing-transduction",
        "pathway_id": "Rpf_system", "role": "receiving", "name": "DSF sensing and initial transduction",
        "required_profiles": ["RpfC"], "optional_profiles": ["RpfG"],
        "wording": "Candidate encoding RpfC-mediated DSF sensing and initial transduction potential",
        "boundary": "Downstream RpfG-mediated response, ligand specificity and activity remain unresolved.",
        "evidence_ids": ["BIO-02", "BIO-07"],
        "references": ["https://doi.org/10.1371/journal.ppat.1006304", "https://doi.org/10.1111/j.1365-2958.2006.05386.x"],
    },
    {
        "endpoint_id": "qsp-rpf-receptor-response",
        "pathway_id": "Rpf_system", "role": "receiving", "name": "Canonical receptor-response context",
        "required_profiles": ["RpfC", "RpfG"], "optional_profiles": [],
        "wording": "Candidate encoding the RpfC-RpfG receptor-and-response context",
        "boundary": "Does not establish ligand specificity, pathway activity or phenotype; RpfG alone is not DSF reception.",
        "evidence_ids": ["BIO-02", "BIO-07"],
        "references": ["https://doi.org/10.1371/journal.ppat.1006304", "https://doi.org/10.1111/j.1365-2958.2006.05386.x"],
    },
    {
        "endpoint_id": "qsp-pqs-hhq-core",
        "pathway_id": "Pqs_operon_system", "role": "sending", "name": "HHQ-core biosynthetic potential",
        "required_profiles": ["PqsA", "PqsB", "PqsC", "PqsD"],
        "optional_profiles": ["PhnA", "PhnB", "PqsH", "PqsE"],
        "wording": "Candidate encoding the PqsABCD HHQ-forming core",
        "boundary": "Does not establish PQS conversion, full regulatory output or product formation; PqsE contribution is strain-dependent.",
        "evidence_ids": ["BIO-10", "BIO-11", "BIO-12", "BIO-13", "BIO-14", "BIO-15"],
        "references": ["https://doi.org/10.1128/JB.01140-07", "https://doi.org/10.1074/JBC.M115.708453", "https://doi.org/10.1074/JBC.M804555200", "https://doi.org/10.1128/jb.00402-25"],
    },
    {
        "endpoint_id": "qsp-pqs-pqs-conversion",
        "pathway_id": "Pqs_operon_system", "role": "sending", "name": "PQS-conversion potential",
        "required_profiles": ["PqsA", "PqsB", "PqsC", "PqsD", "PqsH"],
        "optional_profiles": ["PhnA", "PhnB", "PqsE"],
        "wording": "Candidate encoding the PqsABCD HHQ core plus PqsH-mediated PQS-conversion potential",
        "boundary": "Requires suitable oxygen and substrate conditions; does not establish product formation or full regulatory output.",
        "evidence_ids": ["BIO-10", "BIO-11", "BIO-12", "BIO-13", "BIO-14", "BIO-15"],
        "references": ["https://doi.org/10.1128/JB.01140-07", "https://doi.org/10.1074/JBC.M115.708453", "https://doi.org/10.1074/JBC.M804555200", "https://doi.org/10.1111/j.1365-2958.2010.07303.x"],
    },
)


def guidance_for_database(database_id: str) -> dict[str, Any] | None:
    if database_id != "qsp":
        return None
    return {
        "format_version": "1.0",
        "version": GUIDANCE_VERSION,
        "endpoints": list(deepcopy(QSP_INTERPRETATION_GUIDANCE)),
    }
