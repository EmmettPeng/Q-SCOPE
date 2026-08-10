import assert from 'node:assert/strict'
import test from 'node:test'
import { build } from 'esbuild'

const result = await build({ entryPoints: ['src/copy/en.ts'], bundle: true, write: false, format: 'esm', platform: 'node' })
const module = await import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].contents).toString('base64')}`)

test('known API error codes and fallback resolve to centralized copy', () => {
  assert.equal(module.errorMessage('project_not_found'), module.copy.errors.project_not_found)
  assert.match(module.errorMessage('database_table_invalid', { row: 4 }), /row 4/)
  assert.match(module.errorMessage('database_profile_mismatch', { profiles: ['LuxI', 'LuxR'] }), /LuxI, LuxR/)
  assert.equal(module.errorMessage('not-a-code'), module.copy.errors.unexpected)
  assert.ok(Object.keys(module.copy.errors).length >= 20)
})

test('machine values receive stable human-readable display labels', () => {
  assert.equal(module.displayRole('sending'), 'Sending')
  assert.equal(module.displayStatus('ready'), 'Ready')
  assert.equal(module.displayRuleStrategy('required_profiles'), 'Specific required components')
  assert.equal(module.displayEvidenceLevel('potential_communication'), 'Potential communication')
  assert.equal(module.displayNetworkMode('minimal'), 'Summary')
  assert.equal(module.displayRedistributionStatus('unconfirmed'), 'Unconfirmed')
  assert.equal(module.displayStatus('custom_state'), 'Custom state')
})

test('sequence counts use the selected biological unit', () => {
  assert.equal(module.copy.overview.residues(1200, 'protein'), '1,200 amino acids')
  assert.equal(module.copy.overview.residues(1200, 'genome'), '1,200 nucleotides')
})
