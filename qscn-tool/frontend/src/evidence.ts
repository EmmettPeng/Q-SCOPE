import type { Capability, Hit, NetworkEdge, Results } from './types'

export interface EvidenceFilters {
  minHmmCoverage: number
  minSequenceCoverage: number
  includePartial: boolean
  biologicalRuleId: string
}

export const defaultEvidenceFilters = (): EvidenceFilters => ({
  minHmmCoverage: 0,
  minSequenceCoverage: 0,
  includePartial: true,
  biologicalRuleId: '',
})

export function evidenceFiltersActive(filters: EvidenceFilters): boolean {
  return filters.minHmmCoverage > 0 || filters.minSequenceCoverage > 0
    || !filters.includePartial || Boolean(filters.biologicalRuleId)
}

export function hitMatchesEvidence(hit: Hit, filters: EvidenceFilters): boolean {
  if ((hit.hmm_coverage ?? 0) < filters.minHmmCoverage) return false
  if ((hit.sequence_coverage ?? 0) < filters.minSequenceCoverage) return false
  if (!filters.includePartial && hit.gene_integrity_state?.startsWith('partial_')) return false
  return true
}

function qualifyingProfiles(call: Capability, hitsById: Map<string, Hit>, filters: EvidenceFilters): Set<string> {
  const mappedHitIds = Object.keys(call.component_hit_ids ?? {}).length
    ? call.component_hit_ids
    : (call.supporting_hit_ids ?? []).reduce<Record<string, string[]>>((byProfile, id) => {
      const hit = hitsById.get(id)
      if (hit && call.observed_components.includes(hit.profile_id)) {
        const profileHitIds = byProfile[hit.profile_id] ??= []
        profileHitIds.push(id)
      }
      return byProfile
    }, {})
  return new Set(Object.entries(mappedHitIds ?? {})
    .filter(([, hitIds]) => hitIds.some((id) => {
      const hit = hitsById.get(id)
      return Boolean(hit && hitMatchesEvidence(hit, filters))
    }))
    .map(([profile]) => profile))
}

export function capabilityMatchesEvidence(
  call: Capability,
  hitsById: Map<string, Hit>,
  filters: EvidenceFilters,
): boolean {
  if (filters.biologicalRuleId && !(call.biological_annotations ?? [])
    .some((annotation) => annotation.rule_id === filters.biologicalRuleId)) return false
  if (!evidenceFiltersActive({ ...filters, biologicalRuleId: '' })) return true
  const qualifying = qualifyingProfiles(call, hitsById, filters)
  if (!call.capable) return qualifying.size > 0
  const required = call.required_profiles.length ? call.required_profiles : call.observed_components
  return required.length > 0 && required.every((profile) => qualifying.has(profile))
}

export function evidenceFilteredEdges(results: Results, filters: EvidenceFilters): NetworkEdge[] {
  const hitsById = new Map(results.hits.map((hit) => [hit.hit_id, hit]))
  const calls = new Map(results.capabilities.map((call) => [
    `${call.sample_id}\u0000${call.pathway_id}\u0000${call.role}`, call,
  ]))
  return results.network.edges.filter((edge) => {
    if (filters.biologicalRuleId && !edge.biological_rule_ids?.includes(filters.biologicalRuleId)) return false
    const sender = calls.get(`${edge.source_sample}\u0000${edge.pathway_id}\u0000sending`)
    const receiver = calls.get(`${edge.target_sample}\u0000${edge.pathway_id}\u0000receiving`)
    if (!sender || !receiver) return false
    const coverageFilters = { ...filters, biologicalRuleId: '' }
    return capabilityMatchesEvidence(sender, hitsById, coverageFilters)
      && capabilityMatchesEvidence(receiver, hitsById, coverageFilters)
  })
}
