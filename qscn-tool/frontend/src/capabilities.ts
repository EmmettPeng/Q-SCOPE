import type { Capability } from './types'

export type CapabilityCall = 'capable' | 'partial' | 'not_detected'
export type CapabilitySortKey = 'sample' | 'pathway' | 'role' | 'completeness' | 'rule' | 'call'
export type SortDirection = 'asc' | 'desc'

export interface CapabilityFilters {
  query: string
  sampleId: string
  pathwayId: string
  role: string
  call: string
}

export interface CapabilitySort {
  key: CapabilitySortKey
  direction: SortDirection
}

export function capabilityCall(item: Capability): CapabilityCall {
  if (item.capable) return 'capable'
  return item.status === 'component_evidence' ? 'partial' : 'not_detected'
}

export function filterAndSortCapabilities(
  capabilities: Capability[],
  sampleNames: Map<string, string>,
  filters: CapabilityFilters,
  sort: CapabilitySort,
): Capability[] {
  const query = filters.query.trim().toLocaleLowerCase()
  const callRank: Record<CapabilityCall, number> = { capable: 0, partial: 1, not_detected: 2 }
  const text = (value: string) => value.toLocaleLowerCase()
  const valueFor = (item: Capability): string | number => {
    if (sort.key === 'sample') return sampleNames.get(item.sample_id) ?? item.sample_id
    if (sort.key === 'pathway') return `${item.pathway_name}\u0000${item.signal_name}`
    if (sort.key === 'role') return item.role === 'sending' ? 0 : 1
    if (sort.key === 'completeness') return item.completeness
    if (sort.key === 'rule') return item.rule_strategy
    return callRank[capabilityCall(item)]
  }
  const stableKey = (item: Capability) => [
    sampleNames.get(item.sample_id) ?? item.sample_id,
    item.pathway_name,
    item.role === 'sending' ? '0' : '1',
    item.sample_id,
    item.pathway_id,
  ].join('\u0000')
  return capabilities
    .filter((item) => {
      if (filters.sampleId && item.sample_id !== filters.sampleId) return false
      if (filters.pathwayId && item.pathway_id !== filters.pathwayId) return false
      if (filters.role && item.role !== filters.role) return false
      if (filters.call && capabilityCall(item) !== filters.call) return false
      if (!query) return true
      const searchable = [
        item.sample_id, sampleNames.get(item.sample_id) ?? '', item.pathway_id,
        item.pathway_name, item.signal_name, ...item.observed_components,
        ...item.missing_components, ...(item.observed_components_labels ?? []),
        ...(item.missing_components_labels ?? []),
      ].map(text).join(' ')
      return searchable.includes(query)
    })
    .sort((left, right) => {
      const leftValue = valueFor(left)
      const rightValue = valueFor(right)
      const primary = typeof leftValue === 'number' && typeof rightValue === 'number'
        ? leftValue - rightValue
        : String(leftValue).localeCompare(String(rightValue), undefined, { sensitivity: 'base' })
      if (primary) return sort.direction === 'asc' ? primary : -primary
      return stableKey(left).localeCompare(stableKey(right), undefined, { sensitivity: 'base' })
    })
}
