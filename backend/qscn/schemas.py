from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


CAPABILITY_RULE_VERSION = "2.0"
HIT_RULE_VERSION = "1.0"
ANALYSIS_SCOPE_VERSION = "1.0"


class InputKind(str, Enum):
    protein = "protein"
    genome = "genome"


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
            # Kept in v0.2.x for older clients and manifests.
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


class DatabaseManifest(BaseModel):
    database_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source: str = Field(min_length=1)
    classification_scheme: str = Field(min_length=1)
    threshold_policy: ThresholdPolicy
    pathways: list[PathwayDefinition] = Field(min_length=1)
    provenance: DatabaseProvenance = Field(default_factory=DatabaseProvenance)

    @model_validator(mode="after")
    def unique_pathways(self) -> "DatabaseManifest":
        ids = [pathway.pathway_id for pathway in self.pathways]
        if len(ids) != len(set(ids)):
            raise ValueError("pathway_id values must be unique")
        return self


class CapabilityRule(BaseModel):
    pathway_id: str = Field(min_length=1)
    role: Literal["sending", "receiving"]
    strategy: Literal["all", "minimum_count", "required_profiles"] = "all"
    minimum_count: int | None = Field(default=None, ge=1)
    required_profiles: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def strategy_fields(self) -> "CapabilityRule":
        self.required_profiles = list(dict.fromkeys(self.required_profiles))
        if self.strategy == "minimum_count":
            if self.minimum_count is None:
                raise ValueError("minimum_count strategy requires minimum_count")
            if self.required_profiles:
                raise ValueError("minimum_count strategy cannot define required_profiles")
        elif self.strategy == "required_profiles":
            if not self.required_profiles:
                raise ValueError("required_profiles strategy requires at least one profile")
            if self.minimum_count is not None:
                raise ValueError("required_profiles strategy cannot define minimum_count")
        elif self.minimum_count is not None or self.required_profiles:
            raise ValueError("all strategy cannot define minimum_count or required_profiles")
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
    capability_rules: list[CapabilityRule] | None = None
    analysis_scope: AnalysisScopeRequest | None = None


class RenameSampleRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
