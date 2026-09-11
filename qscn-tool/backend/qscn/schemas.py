from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CAPABILITY_RULE_VERSION = "3.0"
HIT_RULE_VERSION = "1.0"
ANALYSIS_SCOPE_VERSION = "1.0"


class InputKind(str, Enum):
    protein = "protein"
    genome = "genome"


class ComponentDefinition(BaseModel):
    profile_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)


class PathwayDefinition(BaseModel):
    pathway_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    signal_name: str = Field(min_length=1)
    sending_profiles: list[str] = Field(default_factory=list)
    receiving_profiles: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_roles(self) -> "PathwayDefinition":
        self.sending_profiles = list(dict.fromkeys(self.sending_profiles))
        self.receiving_profiles = list(dict.fromkeys(self.receiving_profiles))
        self.references = list(dict.fromkeys(self.references))
        if not self.sending_profiles and not self.receiving_profiles:
            raise ValueError("a pathway must define at least one role")
        return self


class ThresholdPolicy(BaseModel):
    type: Literal["ga", "evalue"]
    default_evalue: float | None = Field(default=None, gt=0)
    default_full_evalue: float | None = Field(default=None, gt=0)
    default_domain_i_evalue: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def evalue_required(self) -> "ThresholdPolicy":
        if self.type == "evalue":
            full = self.default_full_evalue or self.default_evalue
            domain = self.default_domain_i_evalue or self.default_evalue
            if full is None or domain is None:
                raise ValueError(
                    "evalue policy requires default_full_evalue and "
                    "default_domain_i_evalue"
                )
            self.default_full_evalue = full
            self.default_domain_i_evalue = domain
            # Retained in the internal schema for stored interpretation records.
            self.default_evalue = full
        elif any(
            value is not None
            for value in (
                self.default_evalue,
                self.default_full_evalue,
                self.default_domain_i_evalue,
            )
        ):
            raise ValueError("ga policy cannot define E-value thresholds")
        return self


class DatabaseProvenance(BaseModel):
    source_url: str | None = None
    source_version: str = "unconfirmed"
    build_date: str = "unconfirmed"
    build_method: str = "unconfirmed"
    license: str = "unconfirmed"
    redistribution_status: Literal["confirmed", "restricted", "unconfirmed"] = "unconfirmed"
    profile_count: int | None = Field(default=None, ge=0)
    metadata_reference_count: int | None = Field(default=None, ge=0)
    hmm_sha256: str | None = None
    metadata_sha256: str | None = None
    component_metadata_sha256: str | None = None
    guidance_sha256: str | None = None
    guidance_version: str | None = None


class HitThresholds(BaseModel):
    full_evalue_max: float = Field(gt=0)
    domain_i_evalue_max: float = Field(gt=0)


class AnalysisScopeRequest(BaseModel):
    version: Literal["1.0"] = ANALYSIS_SCOPE_VERSION
    mode: Literal["all", "pathways", "signals"] = "all"
    requested_values: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_values(self) -> "AnalysisScopeRequest":
        self.requested_values = list(dict.fromkeys(value.strip() for value in self.requested_values))
        if any(not value for value in self.requested_values):
            raise ValueError("analysis scope values cannot be empty")
        if self.mode == "all" and self.requested_values:
            raise ValueError("all scope cannot define requested values")
        if self.mode != "all" and not self.requested_values:
            raise ValueError("scoped analysis requires requested values")
        return self


class InterpretationGuidanceEndpoint(BaseModel):
    endpoint_id: str = Field(min_length=1, max_length=120)
    pathway_id: str = Field(min_length=1)
    role: Literal["sending", "receiving"]
    name: str = Field(min_length=1, max_length=200)
    required_profiles: list[str] = Field(min_length=1)
    optional_profiles: list[str] = Field(default_factory=list)
    wording: str = Field(min_length=1, max_length=2000)
    boundary: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_lists(self) -> "InterpretationGuidanceEndpoint":
        self.required_profiles = list(dict.fromkeys(self.required_profiles))
        self.optional_profiles = list(dict.fromkeys(self.optional_profiles))
        self.evidence_ids = list(dict.fromkeys(self.evidence_ids))
        self.references = list(dict.fromkeys(self.references))
        if set(self.required_profiles) & set(self.optional_profiles):
            raise ValueError("required and optional profiles must not overlap")
        return self


class InterpretationGuidance(BaseModel):
    format_version: Literal["1.0"] = "1.0"
    version: str = Field(min_length=1, max_length=120)
    endpoints: list[InterpretationGuidanceEndpoint] = Field(min_length=1)
    source_sha256: str | None = None

    @model_validator(mode="after")
    def unique_endpoints(self) -> "InterpretationGuidance":
        ids = [endpoint.endpoint_id for endpoint in self.endpoints]
        if len(ids) != len(set(ids)):
            raise ValueError("guidance endpoint IDs must be unique")
        return self


class DatabaseManifest(BaseModel):
    schema_version: Literal["1.0", "2.0"] = "1.0"
    database_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source: str = Field(min_length=1)
    classification_scheme: str = Field(min_length=1)
    threshold_policy: ThresholdPolicy
    components: list[ComponentDefinition] = Field(default_factory=list)
    pathways: list[PathwayDefinition] = Field(min_length=1)
    provenance: DatabaseProvenance = Field(default_factory=DatabaseProvenance)
    interpretation_guidance: InterpretationGuidance | None = None

    @model_validator(mode="after")
    def unique_pathways(self) -> "DatabaseManifest":
        component_ids = [component.profile_id for component in self.components]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("component profile_id values must be unique")
        ids = [pathway.pathway_id for pathway in self.pathways]
        if len(ids) != len(set(ids)):
            raise ValueError("pathway_id values must be unique")
        pathways = {pathway.pathway_id: pathway for pathway in self.pathways}
        if self.interpretation_guidance:
            for endpoint in self.interpretation_guidance.endpoints:
                pathway = pathways.get(endpoint.pathway_id)
                if pathway is None:
                    raise ValueError("guidance references an unknown pathway")
                profiles = (
                    pathway.sending_profiles
                    if endpoint.role == "sending"
                    else pathway.receiving_profiles
                )
                if len(profiles) <= 1:
                    raise ValueError("guidance endpoints require a multi-component role")
                unknown = (
                    set(endpoint.required_profiles)
                    | set(endpoint.optional_profiles)
                ) - set(profiles)
                if unknown:
                    raise ValueError("guidance references profiles outside its pathway role")
        return self


class CapabilityRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pathway_id: str = Field(min_length=1)
    role: Literal["sending", "receiving"]
    strategy: Literal["all", "required_profiles"] = "all"
    required_profiles: list[str] = Field(default_factory=list)
    guidance_endpoint_id: str | None = None
    guidance_version: str | None = None

    @model_validator(mode="after")
    def strategy_fields(self) -> "CapabilityRule":
        self.required_profiles = list(dict.fromkeys(self.required_profiles))
        if self.strategy == "required_profiles":
            if not self.required_profiles:
                raise ValueError("required_profiles strategy requires at least one profile")
        elif self.required_profiles:
            raise ValueError("all strategy cannot define required_profiles")
        if bool(self.guidance_endpoint_id) != bool(self.guidance_version):
            raise ValueError("guidance endpoint ID and version must be provided together")
        if self.guidance_endpoint_id and self.strategy != "required_profiles":
            raise ValueError("guidance can only accompany required_profiles")
        return self


class PreflightRequest(BaseModel):
    input_kind: InputKind


class RunRequest(BaseModel):
    input_kind: InputKind
    database_version_id: str
    capability_rules: list[CapabilityRule] | None = None
    sequence_evalue_override: float | None = Field(default=None, gt=0)
    hit_thresholds_override: HitThresholds | None = None
    analysis_scope: AnalysisScopeRequest | None = None


class InterpretationRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    capability_rules: list[CapabilityRule] | None = None
    analysis_scope: AnalysisScopeRequest | None = None


class RenameInterpretationRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def normalize_name(self) -> "RenameInterpretationRequest":
        self.name = self.name.strip() if self.name else None
        return self


class RenameSampleRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
