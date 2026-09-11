import type { NetworkEdge, NetworkNode, NodeMetric } from './types'
import { copy } from './copy/en'

export type NetworkViewMode = 'minimal' | 'signal' | 'pathway'

export interface SignalCount { signal_name: string; pathway_count: number }
export interface DirectionBucket { pathway_count: number; signals: SignalCount[] }
export interface DirectionSummary {
  total_pathways: number
  forward: DirectionBucket
  reverse: DirectionBucket
  bidirectional: DirectionBucket
  self: DirectionBucket
}

export interface DisplayEdge extends NetworkEdge {
  pathway_ids: string[]
  pathway_names: string[]
  signal_names: string[]
  evidence_edge_count: number
  evidence_edges: NetworkEdgeEvidence[]
  bidirectional: boolean
  source_arrow_shape: 'none' | 'triangle'
  target_arrow_shape: 'none' | 'triangle'
  direction_summary?: DirectionSummary
}

export interface NetworkEdgeEvidence {
  edge_id: string
  pathway_id: string
  pathway_name: string
  signal_name: string
  source_sample: string
  source_label: string
  target_sample: string
  target_label: string
  sender_components: string[]
  receiver_components: string[]
  sender_component_labels?: string[]
  receiver_component_labels?: string[]
  references: string[]
  evidence_level: string
  biological_rule_ids?: string[]
  biological_states?: string[]
  boundary_references?: string[]
}

function unique(values: string[]): string[] { return [...new Set(values)] }

function edgeEvidence(edge: NetworkEdge): NetworkEdgeEvidence {
  return {
    edge_id: edge.id, pathway_id: edge.pathway_id, pathway_name: edge.pathway_name,
    signal_name: edge.signal_name, source_sample: edge.source_sample, source_label: edge.source_label,
    target_sample: edge.target_sample, target_label: edge.target_label,
    sender_components: [...edge.sender_components], receiver_components: [...edge.receiver_components],
    ...(edge.sender_component_labels ? { sender_component_labels: [...edge.sender_component_labels] } : {}),
    ...(edge.receiver_component_labels ? { receiver_component_labels: [...edge.receiver_component_labels] } : {}),
    references: [...edge.references], evidence_level: edge.evidence_level,
    ...(edge.biological_rule_ids?.length ? { biological_rule_ids: [...edge.biological_rule_ids] } : {}),
    ...(edge.biological_states?.length ? { biological_states: [...edge.biological_states] } : {}),
    ...(edge.boundary_references?.length ? { boundary_references: [...edge.boundary_references] } : {}),
  }
}

function initialDisplayEdge(edge: NetworkEdge): DisplayEdge {
  return {
    ...edge, pathway_ids: [edge.pathway_id], pathway_names: [edge.pathway_name],
    signal_names: [edge.signal_name], evidence_edge_count: 1, evidence_edges: [edgeEvidence(edge)],
    bidirectional: false, source_arrow_shape: 'none', target_arrow_shape: 'triangle',
  }
}

function appendEdge(target: DisplayEdge, edge: NetworkEdge): void {
  target.pathway_ids = unique([...target.pathway_ids, edge.pathway_id])
  target.pathway_names = unique([...target.pathway_names, edge.pathway_name])
  target.signal_names = unique([...target.signal_names, edge.signal_name])
  target.sender_components = unique([...target.sender_components, ...edge.sender_components])
  target.receiver_components = unique([...target.receiver_components, ...edge.receiver_components])
  if (target.sender_component_labels || edge.sender_component_labels) target.sender_component_labels = unique([...(target.sender_component_labels ?? target.sender_components), ...(edge.sender_component_labels ?? edge.sender_components)])
  if (target.receiver_component_labels || edge.receiver_component_labels) target.receiver_component_labels = unique([...(target.receiver_component_labels ?? target.receiver_components), ...(edge.receiver_component_labels ?? edge.receiver_components)])
  target.references = unique([...target.references, ...edge.references])
  target.evidence_edge_count += 1
  target.evidence_edges.push(edgeEvidence(edge))
}

function appendDisplayEdge(target: DisplayEdge, edge: DisplayEdge): void {
  target.pathway_ids = unique([...target.pathway_ids, ...edge.pathway_ids])
  target.pathway_names = unique([...target.pathway_names, ...edge.pathway_names])
  target.signal_names = unique([...target.signal_names, ...edge.signal_names])
  target.sender_components = unique([...target.sender_components, ...edge.sender_components])
  target.receiver_components = unique([...target.receiver_components, ...edge.receiver_components])
  if (target.sender_component_labels || edge.sender_component_labels) target.sender_component_labels = unique([...(target.sender_component_labels ?? target.sender_components), ...(edge.sender_component_labels ?? edge.sender_components)])
  if (target.receiver_component_labels || edge.receiver_component_labels) target.receiver_component_labels = unique([...(target.receiver_component_labels ?? target.receiver_components), ...(edge.receiver_component_labels ?? edge.receiver_components)])
  target.references = unique([...target.references, ...edge.references])
  target.evidence_edge_count += edge.evidence_edge_count
  target.evidence_edges.push(...edge.evidence_edges)
}

function directedPathwayKey(edge: NetworkEdge): string {
  return [edge.database_version_id, edge.source, edge.target, edge.pathway_id, edge.signal_name].join('\u0000')
}

function reciprocalPathwayEdges(edges: NetworkEdge[]): DisplayEdge[] {
  const displayed: DisplayEdge[] = []
  const unmatched = new Map<string, DisplayEdge[]>()
  for (const edge of edges) {
    const reverseKey = [edge.database_version_id, edge.target, edge.source, edge.pathway_id, edge.signal_name].join('\u0000')
    const reverseQueue = edge.source === edge.target ? undefined : unmatched.get(reverseKey)
    const reverse = reverseQueue?.shift()
    if (reverse) {
      appendEdge(reverse, edge); reverse.bidirectional = true; reverse.source_arrow_shape = 'triangle'
      const endpoints = [reverse.source_sample, reverse.target_sample].sort().join(':')
      reverse.id = `pathway:bidirectional:${endpoints}:${edge.pathway_id}`
      continue
    }
    const displayEdge = initialDisplayEdge(edge)
    displayed.push(displayEdge)
    const key = directedPathwayKey(edge)
    const queue = unmatched.get(key) ?? []
    queue.push(displayEdge); unmatched.set(key, queue)
  }
  return displayed
}

function sameSignalKey(edge: DisplayEdge): string {
  if (edge.bidirectional) {
    const endpoints = [edge.source, edge.target].sort()
    return [edge.database_version_id, 'both', ...endpoints, edge.signal_name].join('\u0000')
  }
  return [edge.database_version_id, 'directed', edge.source, edge.target, edge.signal_name].join('\u0000')
}

function signalEdges(edges: NetworkEdge[]): DisplayEdge[] {
  const groups = new Map<string, DisplayEdge>()
  for (const edge of reciprocalPathwayEdges(edges)) {
    const key = sameSignalKey(edge)
    const existing = groups.get(key)
    if (existing) appendDisplayEdge(existing, edge)
    else groups.set(key, {
      ...edge, id: `signal:${edge.bidirectional ? 'both' : 'directed'}:${edge.source_sample}:${edge.target_sample}:${edge.signal_name}`,
      pathway_ids: [...edge.pathway_ids], pathway_names: [...edge.pathway_names], signal_names: [...edge.signal_names],
      sender_components: [...edge.sender_components], receiver_components: [...edge.receiver_components],
      ...(edge.sender_component_labels ? { sender_component_labels: [...edge.sender_component_labels] } : {}),
      ...(edge.receiver_component_labels ? { receiver_component_labels: [...edge.receiver_component_labels] } : {}),
      references: [...edge.references], evidence_edges: [...edge.evidence_edges],
    })
  }
  return [...groups.values()]
}

function bucket(pathways: Array<{ signal: string }>): DirectionBucket {
  const counts = new Map<string, number>()
  pathways.forEach(({ signal }) => counts.set(signal, (counts.get(signal) ?? 0) + 1))
  return { pathway_count: pathways.length, signals: [...counts].map(([signal_name, pathway_count]) => ({ signal_name, pathway_count })) }
}

function minimalEdges(edges: NetworkEdge[]): DisplayEdge[] {
  const pairGroups = new Map<string, NetworkEdge[]>()
  for (const edge of edges) {
    const endpoints = [edge.source_sample, edge.target_sample].sort()
    const key = [edge.database_version_id, ...endpoints].join('\u0000')
    pairGroups.set(key, [...(pairGroups.get(key) ?? []), edge])
  }
  return [...pairGroups.values()].map((group) => {
    const samples = [group[0].source_sample, group[0].target_sample].sort()
    const forwardSample = samples[0]
    const reverseSample = samples[1]
    const byPathway = new Map<string, { signal: string; forward: boolean; reverse: boolean; self: boolean }>()
    group.forEach((edge) => {
      const item = byPathway.get(edge.pathway_id) ?? { signal: edge.signal_name, forward: false, reverse: false, self: false }
      if (edge.source_sample === edge.target_sample) item.self = true
      else if (edge.source_sample === forwardSample) item.forward = true
      else item.reverse = true
      byPathway.set(edge.pathway_id, item)
    })
    const pathways = [...byPathway.values()]
    const forward = pathways.filter((item) => item.forward && !item.reverse)
    const reverse = pathways.filter((item) => item.reverse && !item.forward)
    const bidirectional = pathways.filter((item) => item.forward && item.reverse)
    const self = pathways.filter((item) => item.self)
    const first = group[0]
    const sourceEdge = group.find((edge) => edge.source_sample === forwardSample) ?? first
    const targetEdge = group.find((edge) => edge.target_sample === reverseSample) ?? first
    const display = initialDisplayEdge(first)
    display.id = `minimal:${samples.join(':')}`
    display.source_sample = forwardSample
    display.target_sample = reverseSample
    display.source = `genome:${forwardSample}`
    display.target = `genome:${reverseSample}`
    display.source_label = sourceEdge.source_sample === forwardSample ? sourceEdge.source_label : sourceEdge.target_label
    display.target_label = targetEdge.target_sample === reverseSample ? targetEdge.target_label : targetEdge.source_label
    display.pathway_ids = unique(group.map((edge) => edge.pathway_id))
    display.pathway_names = unique(group.map((edge) => edge.pathway_name))
    display.signal_names = unique(group.map((edge) => edge.signal_name))
    display.signal_name = display.signal_names.length === 1 ? display.signal_names[0] : copy.network.multipleSignals
    display.color = '#70766f'
    display.sender_components = unique(group.flatMap((edge) => edge.sender_components))
    display.receiver_components = unique(group.flatMap((edge) => edge.receiver_components))
    if (group.some((edge) => edge.sender_component_labels)) display.sender_component_labels = unique(group.flatMap((edge) => edge.sender_component_labels ?? edge.sender_components))
    if (group.some((edge) => edge.receiver_component_labels)) display.receiver_component_labels = unique(group.flatMap((edge) => edge.receiver_component_labels ?? edge.receiver_components))
    display.references = unique(group.flatMap((edge) => edge.references))
    display.evidence_edges = group.map(edgeEvidence)
    display.evidence_edge_count = group.length
    display.bidirectional = bidirectional.length > 0 || (forward.length > 0 && reverse.length > 0)
    display.source_arrow_shape = reverse.length > 0 || bidirectional.length > 0 ? 'triangle' : 'none'
    display.target_arrow_shape = forward.length > 0 || bidirectional.length > 0 || self.length > 0 ? 'triangle' : 'none'
    if (self.length) display.source_arrow_shape = 'none'
    display.direction_summary = {
      total_pathways: byPathway.size, forward: bucket(forward), reverse: bucket(reverse),
      bidirectional: bucket(bidirectional), self: bucket(self),
    }
    return display
  })
}

export function displayEdges(edges: NetworkEdge[], mode: NetworkViewMode): DisplayEdge[] {
  if (mode === 'minimal') return minimalEdges(edges)
  if (mode === 'signal') return signalEdges(edges)
  return reciprocalPathwayEdges(edges)
}

export function networkMetrics(nodes: NetworkNode[], edges: NetworkEdge[]) {
  const metrics = new Map<string, NodeMetric>()
  const neighbors = new Map<string, Set<string>>()
  nodes.forEach((node) => {
    metrics.set(node.sample_id, { sample_id: node.sample_id, display_name: node.label, in_degree: 0, out_degree: 0, total_degree: 0, unique_neighbors: 0, self_edge_count: 0 })
    neighbors.set(node.sample_id, new Set())
  })
  edges.forEach((edge) => {
    const source = metrics.get(edge.source_sample); const target = metrics.get(edge.target_sample)
    if (!source || !target) return
    source.out_degree += 1; target.in_degree += 1
    if (edge.self_communication) source.self_edge_count += 1
    else { neighbors.get(edge.source_sample)?.add(edge.target_sample); neighbors.get(edge.target_sample)?.add(edge.source_sample) }
  })
  metrics.forEach((item, sampleId) => { item.total_degree = item.in_degree + item.out_degree; item.unique_neighbors = neighbors.get(sampleId)?.size ?? 0 })
  const rows = nodes.map((node) => metrics.get(node.sample_id)!)
  return { rows, bySample: metrics, summary: { total_nodes: nodes.length, isolated_nodes: rows.filter((item) => item.total_degree === 0).length, total_edges: edges.length, self_edges: edges.filter((edge) => edge.self_communication).length, pathway_count: new Set(edges.map((edge) => edge.pathway_id)).size, signal_count: new Set(edges.map((edge) => edge.signal_name)).size } }
}
