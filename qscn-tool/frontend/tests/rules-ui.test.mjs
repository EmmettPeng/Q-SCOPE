import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const appSource = await readFile(new URL('../src/App.tsx', import.meta.url), 'utf8')
const typeSource = await readFile(new URL('../src/types.ts', import.meta.url), 'utf8')

test('capability rule UI exposes only all and selected-component strategies', () => {
  assert.doesNotMatch(appSource, /minimum_count|allowOneMissing|Allow one component/)
  assert.match(typeSource, /RuleStrategy = 'all' \| 'required_profiles'/)
})

test('database guidance can be applied and manual edits clear its provenance', () => {
  assert.match(appSource, /GuidanceCards/)
  assert.match(appSource, /endpoint\.evidence_ids/)
  assert.match(appSource, /guidance_endpoint_id: endpoint\.endpoint_id/)
  assert.match(appSource, /guidance_endpoint_id: null, guidance_version: null/)
  assert.match(appSource, /guidance_file/)
  assert.match(appSource, /databases\/guidance-template/)
})

test('standalone evidence guide is removed while evidence filters remain', () => {
  assert.doesNotMatch(appSource, /EvidenceGuidePage|setTab\('evidence'\)|tab === 'evidence'/)
  assert.match(appSource, /EvidenceFilterControls/)
})

test('project page renders the saved database-run-interpretation tree', () => {
  assert.match(appSource, /AnalysisHistory/)
  assert.match(appSource, /analysis-tree/)
  assert.match(appSource, /interpretation_id=/)
})
