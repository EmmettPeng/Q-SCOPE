export type InputKind = 'protein' | 'genome'
export type RuleRole = 'sending' | 'receiving'
export type RuleStrategy = 'all' | 'required_profiles'

export interface AnalysisScope {
  version: '1.0'
  mode: 'all' | 'pathways' | 'signals'
  requested_values: string[]
  resolved_pathway_ids: string[]
}

export interface CapabilityRule {
  pathway_id: string
  role: RuleRole
  strategy: RuleStrategy
  required_profiles: string[]
  guidance_endpoint_id?: string | null
  guidance_version?: string | null
}

export interface InterpretationGuidanceEndpoint {
  endpoint_id: string
  pathway_id: string
  role: RuleRole
  name: string
  required_profiles: string[]
  optional_profiles: string[]
  wording: string
  boundary: string
  evidence_ids: string[]
  references: string[]
}

export interface InterpretationGuidance {
  format_version: '1.0'
  version: string
  endpoints: InterpretationGuidanceEndpoint[]
  source_sha256?: string | null
}

export interface Sample {
  sample_id: string
  display_name: string
  original_path: string
  sequence_count: number
  total_residues: number
  input_kind: InputKind
}

export interface Project {
  id: string
  name: string
  status: string
  input_kind?: InputKind
  samples: Sample[]
  created_at: string
  origin?: 'user' | 'bundled_example'
  example_id?: string | null
}

export interface BundledExample {
  example_id: string
  name: string
  description: string
  available: boolean
  installed: boolean
  project_id?: string | null
  sample_count: number
}

export interface HmmProfileSummary {
  profile_id: string
  display_name: string
  display_label: string
  model_length?: number | null
  ga_sequence?: number | null
  ga_domain?: number | null
  pathway_roles: Array<{ pathway_id: string; pathway_name: string; role: RuleRole }>
}

export interface PathwayInfo {
  pathway_id: string
  name: string
  signal_name: string
  sending_count: number
  receiving_count: number
  sending_profiles: string[]
  receiving_profiles: string[]
  references: string[]
}

export interface ComponentDefinition {
  profile_id: string
  display_name: string
  display_label?: string
}

export interface DatabaseInfo {
  version_id: string
  database_id: string
  name: string
  version: string
  source: string
  classification_scheme: string
  checksum: string
  threshold_type: 'ga' | 'evalue'
  default_evalue?: number
  threshold_policy: {
    type: 'ga' | 'evalue'
    default_evalue?: number | null
    default_full_evalue?: number | null
    default_domain_i_evalue?: number | null
  }
  builtin: boolean
  pathway_count: number
  profile_count: number
  redistribution_status: 'confirmed' | 'restricted' | 'unconfirmed'
  provenance: {
    source_url?: string | null
    source_version: string
    build_date: string
    build_method: string
    license: string
    redistribution_status: 'confirmed' | 'restricted' | 'unconfirmed'
    guidance_sha256?: string | null
    component_metadata_sha256?: string | null
    guidance_version?: string | null
  }
  pathways: PathwayInfo[]
  components: ComponentDefinition[]
  interpretation_guidance?: InterpretationGuidance | null
}

export interface InterpretationInfo {
  id: string
  run_id: string
  name?: string | null
  display_name: string
  automatic_summary: string
  capability_rule_version: string
  capability_rules: CapabilityRule[]
  analysis_scope: AnalysisScope
  created_at: string
  updated_at: string
}

export interface Run {
  id: string
  project_id: string
  database_version_id: string
  input_kind: InputKind
  capability_rule_version: string
  capability_rules: CapabilityRule[]
  sequence_evalue?: number
  hit_rule_version?: string
  hit_thresholds?: { full_evalue_max: number; domain_i_evalue_max: number } | null
  analysis_scope: AnalysisScope
  status: string
  stage: string
  progress: number
  created_at: string
  updated_at: string
  progress_detail?: {
    phase: string
    phase_progress: number
    current_sample_id: string | null
    completed_samples: number
    total_samples: number
  }
  error_code?: string
  error_params?: Record<string, unknown>
  interpretations?: InterpretationInfo[]
}

export interface AnalysisTreeDatabase {
  database_version_id: string
  database_id: string
  name: string
  version: string
  runs: Run[]
}

export interface AnalysisTree {
  project_id: string
  databases: AnalysisTreeDatabase[]
}

export interface Capability {
  sample_id: string
  pathway_id: string
  pathway_name: string
  signal_name: string
  references: string[]
  role: RuleRole
  rule_strategy: RuleStrategy
  total_components: number
  observed_components: string[]
  observed_components_labels?: string[]
  missing_components: string[]
  missing_components_labels?: string[]
  required_profiles: string[]
  required_profiles_labels?: string[]
  missing_required_profiles: string[]
  missing_required_profiles_labels?: string[]
  required_hits: number
  completeness: number
  capable: boolean
  status: string
  supporting_hit_ids: string[]
  component_hit_ids: Record<string, string[]>
  biological_annotations: BiologicalAnnotation[]
}

export interface BiologicalAnnotation {
  annotation_id: string
  rule_id: string
  rule_version: string
  category: 'boundary'
  state: string
  sample_id: string
  pathway_id: string
  role: RuleRole
  components: string[]
  supporting_hit_ids: string[]
  details: Record<string, unknown>
  references: string[]
  affects_base_capability: false
}

export interface Hit {
  hit_id: string
  sample_id: string
  sequence_id: string
  original_sequence_id: string
  contig_id?: string | null
  gene_start?: number | null
  gene_end?: number | null
  gene_strand?: string | null
  partial_5prime?: boolean | null
  partial_3prime?: boolean | null
  profile_id: string
  profile_display_name?: string
  profile_display_label?: string
  full_evalue: number
  full_score: number
  domain_evalue: number
  domain_i_evalue?: number
  domain_c_evalue?: number
  domain_score: number
  hmm_coverage: number
  sequence_coverage: number
  threshold_rule: string
  pass?: boolean
  failure_reasons?: string[]
  hit_rule_version?: string
  applied_thresholds?: Record<string, string | number>
  gene_integrity_state?: 'complete_prediction' | 'partial_5p' | 'partial_3p' | 'partial_both' | 'unknown'
  competing_profile_hits?: string[]
  competing_profile_labels?: string[]
  evidence_rule_version?: string
}

export interface NetworkNode {
  id: string
  kind: 'genome'
  sample_id: string
  label: string
}

export interface NetworkEdge {
  id: string
  source: string
  target: string
  kind: 'potential_communication'
  pathway_id: string
  pathway_name: string
  signal_name: string
  color: string
  database_version_id: string
  database_source: string
  source_sample: string
  source_label: string
  target_sample: string
  target_label: string
  self_communication: boolean
  evidence_level: string
  sender_components: string[]
  receiver_components: string[]
  sender_component_labels?: string[]
  receiver_component_labels?: string[]
  references: string[]
  annotation_ids: string[]
  biological_rule_ids: string[]
  biological_states: string[]
  boundary_references: string[]
}

export interface NetworkSummary {
  total_nodes: number
  isolated_nodes: number
  total_edges: number
  self_edges: number
  non_self_edges: number
  pathway_count: number
  signal_count: number
}

export interface NodeMetric {
  sample_id: string
  display_name: string
  in_degree: number
  out_degree: number
  total_degree: number
  unique_neighbors: number
  self_edge_count: number
}

export interface Results {
  interpretation_id: string
  run_id: string
  capability_rule_version: string
  hit_rule_version?: string
  evidence_rule_version?: string
  interpretation_guidance_version?: string
  capability_rules: CapabilityRule[]
  analysis_scope: AnalysisScope
  database: DatabaseInfo
  samples: Sample[]
  component_definitions: Record<string, ComponentDefinition>
  hits: Hit[]
  capabilities: Capability[]
  biological_annotations: BiologicalAnnotation[]
  biological_rule_ids?: string[]
  result_counts?: {
    hits: number
    capabilities: number
    biological_annotations: number
    network_edges: number
  }
  network: {
    nodes: NetworkNode[]
    edges: NetworkEdge[]
    summary: NetworkSummary
    node_metrics: NodeMetric[]
    legend: Array<{ signal_name: string; color: string; pathway_ids: string[] }>
  }
}

export interface ResultCollection<T> {
  items: T[]
  record_ids?: string[]
  total: number
  baseline: number
  offset?: number
  limit?: number
}

export interface ExportStatus {
  mode: 'analysis' | 'full'
  status: 'not_started' | 'queued' | 'running' | 'complete' | 'failed'
  progress: number
  completed_files?: number
  total_files?: number
  filename?: string
  size_bytes?: number
  sha256?: string
  error?: string
  download_ready: boolean
}
