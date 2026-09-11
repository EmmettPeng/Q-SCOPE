import assert from 'node:assert/strict'
import test from 'node:test'
import { build } from 'esbuild'

async function loadModule(entry) {
  const result = await build({ entryPoints: [entry], bundle: true, write: false, format: 'esm', platform: 'node' })
  return import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].contents).toString('base64')}`)
}

const { defaultEvidenceFilters, evidenceFilteredEdges, hitMatchesEvidence } = await loadModule('src/evidence.ts')

function capability(sample, role, profile, hitId) {
  return {
    sample_id: sample, pathway_id: 'p', role, capable: true, rule_strategy: 'all',
    required_hits: 1, required_profiles: [profile], observed_components: [profile],
    component_hit_ids: { [profile]: [hitId] }, biological_annotations: [],
  }
}

const results = {
  hits: [
    { hit_id: 'sender-hit', profile_id: 'send', hmm_coverage: 0.35, sequence_coverage: 0.9, gene_integrity_state: 'complete_prediction' },
    { hit_id: 'receiver-hit', profile_id: 'receive', hmm_coverage: 0.9, sequence_coverage: 0.9, gene_integrity_state: 'partial_3p' },
  ],
  capabilities: [capability('s', 'sending', 'send', 'sender-hit'), capability('r', 'receiving', 'receive', 'receiver-hit')],
  network: { edges: [{ id: 'edge', source_sample: 's', target_sample: 'r', pathway_id: 'p', biological_rule_ids: ['BIO-02'] }] },
}

test('default evidence view preserves every base edge', () => {
  assert.deepEqual(evidenceFilteredEdges(results, defaultEvidenceFilters()), results.network.edges)
})

test('coverage and partial settings filter the view without mutating base records', () => {
  const filters = { ...defaultEvidenceFilters(), minHmmCoverage: 0.5 }
  assert.deepEqual(evidenceFilteredEdges(results, filters), [])
  assert.equal(results.capabilities[0].capable, true)
  assert.equal(hitMatchesEvidence(results.hits[1], { ...defaultEvidenceFilters(), includePartial: false }), false)
})

test('legacy interpretations rebuild component mapping from supporting hit IDs', () => {
  const legacy = structuredClone(results)
  for (const call of legacy.capabilities) {
    call.supporting_hit_ids = Object.values(call.component_hit_ids).flat()
    delete call.component_hit_ids
  }
  assert.equal(evidenceFilteredEdges(legacy, { ...defaultEvidenceFilters(), minHmmCoverage: 0.3 }).length, 1)
  assert.equal(evidenceFilteredEdges(legacy, { ...defaultEvidenceFilters(), minHmmCoverage: 0.4 }).length, 0)
})

test('BIO selector uses edge annotations as an optional evidence view', () => {
  assert.equal(evidenceFilteredEdges(results, { ...defaultEvidenceFilters(), biologicalRuleId: 'BIO-02' }).length, 1)
  assert.equal(evidenceFilteredEdges(results, { ...defaultEvidenceFilters(), biologicalRuleId: 'BIO-15' }).length, 0)
})
