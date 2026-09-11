import assert from 'node:assert/strict'
import test from 'node:test'
import { build } from 'esbuild'

const result = await build({
  entryPoints: ['src/demo-api.ts'], bundle: true, write: false, format: 'esm', platform: 'node',
  define: { 'import.meta.env.BASE_URL': JSON.stringify('/Q-SCOPE/') },
})
const moduleUrl = `data:text/javascript;base64,${Buffer.from(result.outputFiles[0].contents).toString('base64')}`

const hit = { hit_id: 'h1', profile_id: 'LuxI', hmm_coverage: .8, sequence_coverage: .9, gene_integrity_state: 'complete_prediction' }
const capability = { sample_id: 's1', pathway_id: 'p1', role: 'sending', capable: true, required_profiles: ['LuxI'], observed_components: ['LuxI'], component_hit_ids: { LuxI: ['h1'] }, supporting_hit_ids: ['h1'], biological_annotations: [] }
const snapshot = {
  metadata: {}, projects: [{ id: 'project' }], databases: [{ version_id: 'db' }], examples: [],
  analysis_tree: { project_id: 'project', databases: [{ runs: [{ id: 'run' }] }] },
  run: { id: 'run', project_id: 'project', interpretations: [{ id: 'interpretation' }] },
  results: { run_id: 'run', interpretation_id: 'interpretation', hits: [hit], capabilities: [capability], biological_annotations: [], samples: [], network: { edges: [], nodes: [], summary: {}, node_metrics: [], legend: [] } },
  profiles: { db: [{ profile_id: 'LuxI', display_name: 'LuxI' }, { profile_id: 'LuxR', display_name: 'LuxR' }] },
}

globalThis.fetch = async (url) => {
  assert.equal(url, '/Q-SCOPE/demo/demo-snapshot.json')
  return { ok: true, json: async () => structuredClone(snapshot) }
}
const demo = await import(moduleUrl)

test('serves projects, result summaries, filtering and pagination without an API request', async () => {
  assert.deepEqual(await demo.demoRequest('/api/projects'), snapshot.projects)
  const summary = await demo.demoRequest('/api/runs/run/results?summary=true&interpretation_id=interpretation')
  assert.equal(summary.hits.length, 0)
  assert.equal(summary.result_counts.hits, 1)
  const hits = await demo.demoRequest('/api/runs/run/results/hits?offset=0&limit=1&min_hmm_coverage=.7&include_partial=true')
  assert.equal(hits.total, 1)
  assert.deepEqual(hits.record_ids, ['h1'])
  const filtered = await demo.demoRequest('/api/runs/run/results/capabilities?min_hmm_coverage=.9')
  assert.equal(filtered.total, 0)
})

test('supports profile search and rejects unknown or mutating requests', async () => {
  const profiles = await demo.demoRequest('/api/databases/db/profiles?query=luxr&offset=0&limit=50')
  assert.deepEqual(profiles.items.map((item) => item.profile_id), ['LuxR'])
  await assert.rejects(() => demo.demoRequest('/api/missing'), /not available/)
  await assert.rejects(() => demo.demoRequest('/api/projects', { method: 'POST' }), /Read-only demo/)
})
