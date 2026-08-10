export type InputKind = 'protein' | 'genome'
export type RuleRole = 'sending' | 'receiving'
export type RuleStrategy = 'all' | 'minimum_count' | 'required_profiles'

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
  minimum_count?: number | null
  required_profiles: string[]
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

export interface DatabaseInfo {
  version_id: string
  database_id: string
  name: string
  version: string
  source: string
  classification_scheme: string
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
  }
  pathways: PathwayInfo[]
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
  progress_detail?: {
    phase: string
    phase_progress: number
    current_sample_id: string | null
    completed_samples: number
    total_samples: number
  }
  error_code?: string
  error_params?: Record<string, unknown>
  interpretations?: Array<{ id: string; capability_rule_version: string; capability_rules: CapabilityRule[]; analysis_scope: AnalysisScope; created_at: string }>
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
  missing_components: string[]
  required_profiles: string[]
  missing_required_profiles: string[]
  required_hits: number
  completeness: number
  capable: boolean
  status: string
  supporting_hit_ids: string[]
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
  references: string[]
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
  capability_rules: CapabilityRule[]
  analysis_scope: AnalysisScope
  database: DatabaseInfo
  samples: Sample[]
  hits: Hit[]
  capabilities: Capability[]
  network: {
    nodes: NetworkNode[]
    edges: NetworkEdge[]
    summary: NetworkSummary
    node_metrics: NodeMetric[]
    legend: Array<{ signal_name: string; color: string; pathway_ids: string[] }>
  }
}
