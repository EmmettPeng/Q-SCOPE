import assert from 'node:assert/strict'
import test from 'node:test'
import { build } from 'esbuild'

async function loadModule(entry) {
  const result = await build({ entryPoints: [entry], bundle: true, write: false, format: 'esm', platform: 'node' })
  return import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].contents).toString('base64')}`)
}

const { capabilityCall, filterAndSortCapabilities } = await loadModule('src/capabilities.ts')

function capability(sample, pathway, role, completeness, status, components = []) {
  return {
    sample_id: sample, pathway_id: pathway, pathway_name: pathway.toUpperCase(), signal_name: `signal-${pathway}`,
    role, completeness, status, capable: status.endsWith('_capable'), observed_components: components,
    missing_components: [], rule_strategy: 'all', total_components: 2, required_profiles: [],
    missing_required_profiles: [], required_hits: 2, supporting_hit_ids: [], references: [],
  }
}

const rows = [
  capability('b', 'p2', 'receiving', 0, 'not_detected'),
  capability('a', 'p1', 'sending', 1, 'sending_capable', ['LuxI']),
  capability('a', 'p2', 'receiving', 0.5, 'component_evidence', ['LuxR']),
]
const names = new Map([['a', 'Alpha'], ['b', 'Beta']])
const empty = { query: '', sampleId: '', pathwayId: '', role: '', call: '' }

test('combined filters and component search narrow capability rows', () => {
  const filtered = filterAndSortCapabilities(rows, names, { ...empty, sampleId: 'a', role: 'receiving', query: 'luxr' }, { key: 'sample', direction: 'asc' })
  assert.deepEqual(filtered.map(item => item.pathway_id), ['p2'])
})

test('call status and completeness sorting use biological display order', () => {
  assert.deepEqual(rows.map(capabilityCall), ['not_detected', 'capable', 'partial'])
  const byCall = filterAndSortCapabilities(rows, names, empty, { key: 'call', direction: 'asc' })
  assert.deepEqual(byCall.map(capabilityCall), ['capable', 'partial', 'not_detected'])
  const byCompleteness = filterAndSortCapabilities(rows, names, empty, { key: 'completeness', direction: 'desc' })
  assert.deepEqual(byCompleteness.map(item => item.completeness), [1, 0.5, 0])
})

test('default ties remain deterministic by sample, pathway and role', () => {
  const sorted = filterAndSortCapabilities([...rows].reverse(), names, empty, { key: 'sample', direction: 'asc' })
  assert.deepEqual(sorted.map(item => `${item.sample_id}:${item.pathway_id}:${item.role}`), ['a:p1:sending', 'a:p2:receiving', 'b:p2:receiving'])
})
