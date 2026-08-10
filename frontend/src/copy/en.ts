const humanize = (value: string): string => {
  const normalized = value.replaceAll('_', ' ')
  return normalized ? normalized[0].toUpperCase() + normalized.slice(1) : normalized
}

const roleLabels: Record<string, string> = { sending: 'Sending', receiving: 'Receiving' }
const statusLabels: Record<string, string> = {
  uploaded: 'Uploaded', validating: 'Validating', ready: 'Ready', queued: 'Queued',
  running: 'Running', complete: 'Complete', failed: 'Failed', cancelled: 'Cancelled',
}
const strategyLabels: Record<string, string> = {
  all: 'All defined components', minimum_count: 'Minimum component count', required_profiles: 'Specific required components',
}
const evidenceLevelLabels: Record<string, string> = { potential_communication: 'Potential communication' }
const modeLabels: Record<string, string> = { minimal: 'Summary', signal: 'Group by signal', pathway: 'One edge per Pathway' }
const redistributionLabels: Record<string, string> = { confirmed: 'Confirmed', restricted: 'Restricted', unconfirmed: 'Unconfirmed' }

export const displayRole = (role: string): string => roleLabels[role] ?? humanize(role)
export const displayStatus = (status: string): string => statusLabels[status] ?? humanize(status)
export const displayRuleStrategy = (strategy: string): string => strategyLabels[strategy] ?? humanize(strategy)
export const displayEvidenceLevel = (level: string): string => evidenceLevelLabels[level] ?? humanize(level)
export const displayNetworkMode = (mode: string): string => modeLabels[mode] ?? humanize(mode)
export const displayRedistributionStatus = (status: string): string => redistributionLabels[status] ?? humanize(status)

export const copy = {
  common: {
    product: 'QSCN', release: 'QSCN v0.3.2 · For research use only', dismissError: 'Dismiss error',
    unknown: '—', notDetected: 'No qualifying evidence detected',
    unexpectedError: 'Something went wrong. Try again. If the problem continues, restart the local QSCN services.',
  },
  navigation: {
    newAnalysis: 'New analysis', localProjects: 'Local projects', databases: 'Databases',
    importDatabase: 'Import custom database', localOnly: 'Processed locally · Data stays on this machine',
    projectSummary: (samples: number, status: string) => `${samples} samples · ${displayStatus(status)}`,
    databaseSummary: (profiles: number, pathways: number) => `${profiles} profiles · ${pathways} pathways`,
    tabs: { overview: 'Project', capabilities: 'Pathway evidence', network: 'Potential network', hits: 'HMM evidence' },
  },
  header: {
    eyebrow: 'QUORUM-SENSING EVIDENCE',
    homeTitle: 'Explore potential quorum-sensing communication in a microbial community',
    evidenceFirst: 'Evidence-first analysis',
  },
  upload: {
    eyebrow: 'INPUT', title: 'Upload a sequence collection',
    description: 'Each FASTA file represents one sample. All FASTA files in the ZIP must contain the selected sequence type.',
    projectName: 'Project name', projectPlaceholder: 'For example: Gut consortium A',
    protein: 'Protein sequences', genome: 'Nucleotide sequences', chooseZip: 'Choose a ZIP archive',
    limits: 'Up to 100 samples · 2 GB compressed', submit: 'Upload and validate',
    chooseFirst: 'Choose a ZIP archive before uploading.',
    workflowEyebrow: 'WORKFLOW', workflowTitle: 'From sequences to potential communication',
    workflow: [
      'Secure archive extraction and sequence validation',
      'Gene prediction for nucleotide inputs',
      'HMM profile scanning',
      'Sending- and receiving-role interpretation',
      'Pathway-scoped potential communication network',
    ],
  },
  overview: {
    samplesEyebrow: 'SAMPLES', samplesTitle: 'Validated samples',
    sequences: (n: number) => `${n.toLocaleString()} sequences`,
    residues: (n: number, kind: 'protein' | 'genome') => kind === 'protein'
      ? `${n.toLocaleString()} amino acids`
      : `${n.toLocaleString()} nucleotides`,
    analysisEyebrow: 'ANALYSIS', analysisTitle: 'Configure analysis', database: 'Profile database',
    pathways: (n: number) => `${n} pathways`, ga: 'Profile-specific GA thresholds',
    evalue: 'Full-sequence E-value and domain i-Evalue thresholds',
    fullEvalue: 'Maximum full-sequence E-value', domainIEvalue: 'Maximum domain i-Evalue',
    configureRules: 'Configure capability rules', start: 'Start analysis',
    background: 'This analysis can continue in the background.', cancel: 'Cancel analysis', retry: 'Start a new run',
    ruleSummary: (strict: number, total: number) => `${strict} of ${total} roles require all defined components.`,
    provenance: (status: string) => `Redistribution status: ${displayRedistributionStatus(status)}`,
    legacy: 'This result uses an unsupported schema from before v0.3. Export it with QSCN v0.2.2, then create a new v0.3 project.',
  },
  rules: {
    eyebrow: 'CAPABILITY RULES · VERSION 2.0', title: 'Capability criteria by Pathway',
    setupDescription: 'Sending and receiving roles are evaluated independently. These criteria will be applied after HMM scanning.',
    description: 'Sending and receiving roles are evaluated independently. Changing these criteria reuses saved HMM evidence and does not run HMMER again.',
    close: 'Close capability criteria', strict: 'Require all components', allowMissing: 'Allow one component to be missing',
    all: 'Require all defined components', minimum: 'Require a minimum component count', profiles: 'Require specific components',
    locked: 'Roles with one defined component always require that component.', required: 'Minimum required',
    of: (n: number) => `of ${n} defined components`,
    strategyLabel: (pathway: string, role: string) => `Criteria for the ${role} role in ${pathway}`,
    chooseProfile: 'Select at least one required component.', use: 'Save criteria',
  },
  interpretation: {
    eyebrow: 'INTERPRETATION SETTINGS', title: 'Interpretation settings',
    description: 'Change the scope and capability criteria together. Applying the settings creates one new interpretation from the saved HMM evidence without rescanning.',
    cancel: 'Cancel', close: 'Close interpretation settings',
    applyFailed: 'The settings could not be applied. Your changes are still available in this dialog; review the error and try again.',
  },
  scope: {
    eyebrow: 'ANALYSIS SCOPE · VERSION 1.0', title: 'Choose the interpretation scope',
    description: 'HMMER scans the complete selected database. This scope limits which Pathways are evaluated and included in networks and interpretation artifacts. You can change it later without rescanning.',
    close: 'Close scope settings', configure: 'Configure scope', edit: 'Edit scope', use: 'Save scope',
    modes: { all: 'All Pathways', pathways: 'Select Pathways', signals: 'Select signals' },
    chooseOne: 'Select at least one Pathway or signal.',
    pathwayCount: (n: number) => `${n} Pathway${n === 1 ? '' : 's'}`,
    summary: (mode: string, count: number) => mode === 'all'
      ? 'All Pathways in the selected database will be evaluated.'
      : `${count} selected ${mode === 'signals' ? 'signal' : 'Pathway'}${count === 1 ? '' : 's'} will be evaluated.`,
  },
  databaseGuide: {
    eyebrow: 'CUSTOM DATABASE', title: 'Import a custom database',
    description: 'Choose a combined HMM profile library and a UTF-8 tab-separated Pathway table. QSCN creates the normalized manifest for you.',
    close: 'Close custom database import', name: 'Database name', version: 'Version', source: 'Source (optional)',
    classification: 'Classification scheme (optional)', threshold: 'Threshold policy', ga: 'Profile-specific GA', evalue: 'E-value thresholds',
    fullEvalue: 'Maximum full-sequence E-value', domainIEvalue: 'Maximum domain i-Evalue',
    hmmFile: 'HMM profile library', pathwayFile: 'Pathway table', chooseHmm: 'Choose .hmm file', chooseTable: 'Choose .tsv or .txt file',
    template: 'Download TSV template', format: 'Table format',
    notes: [
      'Combine individual profile HMMs into one file before upload.',
      'Use exactly five tab-separated columns: Pathway, Signal_type, Signal_Sending, Signal_Receiving, and References.',
      'Separate multiple profiles or references with a semicolon (;).',
      'QSCN validates profile names and builds fresh indexes with its bundled HMMER.',
    ],
    choose: 'Import database', required: 'Choose both files and complete the required fields.', importing: 'Importing database…',
  },
  capabilities: {
    eyebrow: 'PATHWAY EVIDENCE', title: 'Sending- and receiving-role evidence', edit: 'Edit criteria', apply: 'Apply settings',
    download: 'Pathway evidence TSV', filter: 'Search samples, Pathways, signals, or components',
    headers: ['Sample', 'Pathway / signal', 'Role', 'Component evidence', 'Applied criteria', 'Interpretation'],
    required: (profiles: string[]) => `Required components: ${profiles.join(', ')}`,
    threshold: (n: number) => `Minimum components: ${n}`,
    capable: (role: string) => `${displayRole(role)} criteria met`, partial: 'Component evidence; criteria not met',
    sampleFilter: 'Filter by sample', pathwayFilter: 'Filter by Pathway', roleFilter: 'Filter by role',
    callFilter: 'Filter by interpretation', allSamples: 'All samples', allPathways: 'All Pathways',
    allRoles: 'All roles', allCalls: 'All interpretations', capableCall: 'Criteria met',
    clear: 'Clear filters',
    count: (shown: number, total: number) => `Showing ${shown.toLocaleString()} of ${total.toLocaleString()} rows`,
    sortBy: (label: string) => `Sort by ${label}`,
  },
  progress: {
    queued: 'Queued', preparing: 'Preparing inputs', predicting: 'Predicting genes', scanning: 'Scanning HMM profiles',
    interpreting: 'Interpreting and preparing results', complete: 'Complete', cancelled: 'Cancelled',
    sample: (current: number, total: number, name: string) => `Sample ${current} of ${total}: ${name}`,
  },
  network: {
    eyebrow: 'POTENTIAL COMMUNICATION', title: 'Sample-to-sample network',
    showSelf: 'Show within-sample potential communication',
    modes: { minimal: 'Summary', signal: 'Group by signal', pathway: 'One edge per Pathway' }, multipleSignals: 'Multiple signals',
    stats: ['Samples', 'Pathway evidence edges', 'Displayed connections', 'Samples without edges', 'Within-sample edges', 'Pathways', 'Signals'],
    headers: ['Sample', 'Incoming evidence edges', 'Outgoing evidence edges', 'Total evidence-edge degree', 'Connected samples', 'Within-sample edges'],
    disclaimer: 'Edges are pathway-scoped hypotheses of potential communication based on HMM evidence, the selected database, and the current interpretation criteria. They are not experimentally validated interactions. Absence of an edge does not establish absence of communication. Short peptides and partial genes have not been independently calibrated.',
    layout: 'Recalculate layout', canvasLabel: 'Network of potential quorum-sensing communication between samples', inspector: 'EVIDENCE INSPECTOR',
    evidence: 'Potential communication evidence',
    emptyInspector: 'Select a sample or edge to inspect its Pathway-level evidence.', tooltipPathways: 'Pathways',
    tooltipTotal: (n: number) => `${n} Pathway${n === 1 ? '' : 's'}`,
    tooltipDirected: (n: number, source: string, target: string) => `${n} directed Pathway${n === 1 ? '' : 's'} · ${source} → ${target}`,
    tooltipBidirectional: (n: number) => `${n} bidirectional Pathway${n === 1 ? '' : 's'}`,
    tooltipSelf: (n: number) => `${n} within-sample Pathway${n === 1 ? '' : 's'}`,
    pathwayEvidence: 'Pathway-level evidence', bidirectional: 'Evidence in both directions', directed: 'Evidence in one direction',
    edgeDirection: (source: string, target: string) => `${source} → ${target}`,
    fields: {
      source: 'Sending sample', target: 'Receiving sample', signal: 'Signal', database: 'Source database',
      evidenceEdges: 'Pathway evidence edges', senderComponents: 'Observed sending components',
      receiverComponents: 'Observed receiving components', references: 'Database references',
      evidenceLevel: 'Evidence classification', direction: 'Evidence direction',
      inDegree: 'Incoming evidence edges', outDegree: 'Outgoing evidence edges',
      totalDegree: 'Total evidence-edge degree', uniqueNeighbors: 'Connected samples', selfEdges: 'Within-sample edges',
    },
    pdfTitle: 'QSCN · Potential communication network',
    pdfMeta: (mode: string, evidence: number, displayed: number) => `${displayNetworkMode(mode)} · ${evidence} Pathway evidence edges · ${displayed} displayed connections`,
    downloads: { pdf: 'Export current view (PDF)', sif: 'Cytoscape SIF', edges: 'Edge evidence TSV', metrics: 'Node metrics TSV' },
  },
  hits: {
    eyebrow: 'HMM EVIDENCE', title: 'HMM hit evidence', export: 'Download complete result package',
    headers: ['Sample / sequence', 'HMM profile', 'Threshold assessment', 'Full-sequence E-value', 'Domain i-Evalue', 'Domain c-Evalue', 'Full-sequence score', 'Domain score', 'Applied threshold'],
    passed: 'Meets threshold', failed: 'Below threshold', showAll: 'Include hits outside the interpretation scope',
    truncated: (shown: number, total: number) => `Showing the first ${shown} of ${total.toLocaleString()} HMM hit records. Download the complete result package to access all records.`,
  },
  confirmations: {
    deleteDatabase: (name: string, version: string) => `Delete custom database “${name}” version ${version}? This cannot be undone.`,
    deleteProject: (name: string) => `Delete project “${name}” and all of its analysis results? This cannot be undone.`,
    deleteProjectLabel: 'Delete project', deleteDatabaseLabel: 'Delete database',
  },
  errors: {
    project_zip_required: 'Choose a project archive in ZIP format.',
    upload_too_large: 'This archive exceeds the upload size limit. Choose a smaller archive or increase the local limit.',
    project_not_found: 'This project is no longer available. Return to Local projects and choose another project.',
    input_validation_failed: 'The archive could not be validated. Check the FASTA contents and ZIP structure, then upload it again.',
    invalid_sample_name: 'A sample name is invalid. Use a non-empty name without path characters.',
    active_run_blocks_delete: 'Cancel the active analysis before deleting this project.',
    project_not_ready: 'Validate the project successfully before starting an analysis.',
    input_kind_mismatch: 'The selected sequence type does not match the validated input. Create a new project with the correct sequence type.',
    database_not_found: 'The selected database is no longer available. Choose another database.',
    ga_override_not_allowed: 'This database uses profile-specific GA thresholds. Remove the E-value overrides and try again.',
    conflicting_threshold_overrides: 'Conflicting threshold settings were provided. Use the current full-sequence and domain thresholds only.',
    invalid_capability_rules: 'The capability criteria are invalid. Review the highlighted role settings and try again.',
    run_not_found: 'This analysis run is no longer available. Return to the project and choose another run.',
    run_not_active: 'This analysis is no longer active, so it cannot be cancelled. Refresh the project to see its current status.',
    worker_unavailable: 'The local analysis worker is unavailable. Restart the QSCN services, then try again.',
    run_not_complete: 'Wait for the analysis to complete before changing interpretation settings.',
    results_not_found: 'No results are available for this analysis. Confirm that it completed successfully or start a new run.',
    interpretation_not_found: 'This interpretation is no longer available. Refresh the project to load the latest results.',
    artifact_not_found: 'This result file is unavailable. Refresh the results and try the download again.',
    database_zip_required: 'Choose a custom database bundle in ZIP format.',
    database_files_required: 'Choose one .hmm file and one tab-separated .tsv or .txt Pathway table.',
    database_metadata_invalid: 'Enter a database name and version, then choose a valid threshold policy.',
    database_table_invalid: 'The Pathway table is invalid. Check its five-column header and row values.',
    database_profile_mismatch: 'One or more table components do not exactly match an HMM profile NAME.',
    database_threshold_invalid: 'The threshold settings are invalid. GA requires GA values on every profile; E-value thresholds must be positive.',
    database_version_conflict: 'A database with this name-derived ID and version already exists with different content. Change the version or delete the unused database.',
    database_bundle_too_large: 'This database bundle exceeds the upload size limit. Choose a smaller bundle or increase the local limit.',
    database_import_failed: 'The custom database could not be imported. Check the HMM file and Pathway table, then try again.',
    database_delete_blocked: 'This database cannot be deleted because it is built in or referenced by an existing analysis.',
    invalid_request: 'Some required values are missing or invalid. Review the form and try again.',
    analysis_failed: 'The analysis stopped before completion. Review the run diagnostics in the result package, then correct the input or settings and start a new run.',
    invalid_analysis_scope: 'The selected Pathway or signal is not available in this database. Review the scope and try again.',
    archive_compression_ratio_exceeded: 'The ZIP archive contains a highly compressed entry that cannot be processed safely. Recreate the archive without nested or unusually compressed files.',
    archive_resource_limit_exceeded: 'The archive exceeds a local limit for files, sequences, sequence length, or extracted size. Reduce the archive or adjust the local limits.',
    sample_name_conflict: 'Two FASTA files produce the same sample name. Rename one file and upload the archive again.',
    ambiguous_sequence_alphabet: 'The selected protein input contains only nucleotide symbols. Select Nucleotide sequences or provide an unambiguous protein FASTA.',
    disk_space_insufficient: 'The analysis stopped because there is not enough allowed disk space. Free local disk space or increase the configured run limit, then start a new run.',
    analysis_timeout: 'An analysis step exceeded its time limit. Increase the local timeout for this dataset or start a new run with a smaller input.',
    incompatible_schema: 'This data volume uses an unsupported schema from before v0.3. Export it with QSCN v0.2.2, then use a new v0.3 data volume.',
    analysis_interrupted: 'The analysis was interrupted when QSCN restarted. Start a new run; saved inputs remain available.',
    legacy_run_failed: 'This analysis from an earlier QSCN release did not complete. Start a new run with the current release.',
    unexpected: 'Something went wrong. Try again. If the problem continues, restart the local QSCN services.',
  },
} as const

export type ErrorCode = keyof typeof copy.errors

export function errorMessage(code: string | undefined, params?: Record<string, unknown>): string {
  const base = code && code in copy.errors ? copy.errors[code as ErrorCode] : copy.errors.unexpected
  if (code === 'database_table_invalid' && typeof params?.row === 'number') return `${base} Review row ${params.row}.`
  if ((code === 'database_profile_mismatch' || code === 'database_threshold_invalid') && Array.isArray(params?.profiles) && params.profiles.length) {
    return `${base} Profiles: ${params.profiles.join(', ')}.`
  }
  return base
}
