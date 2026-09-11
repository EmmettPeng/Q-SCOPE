import { expect, test } from '@playwright/test'
import { writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { inflateRawSync } from 'node:zlib'

function crc32(data: Buffer): number {
  let crc = 0xffffffff
  for (const byte of data) {
    crc ^= byte
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1))
  }
  return (crc ^ 0xffffffff) >>> 0
}

function storedZip(name: string, content: string): Buffer {
  const filename = Buffer.from(name)
  const data = Buffer.from(content)
  const crc = crc32(data)
  const local = Buffer.alloc(30)
  local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(20, 4)
  local.writeUInt32LE(crc, 14); local.writeUInt32LE(data.length, 18); local.writeUInt32LE(data.length, 22)
  local.writeUInt16LE(filename.length, 26)
  const central = Buffer.alloc(46)
  central.writeUInt32LE(0x02014b50, 0); central.writeUInt16LE(20, 4); central.writeUInt16LE(20, 6)
  central.writeUInt32LE(crc, 16); central.writeUInt32LE(data.length, 20); central.writeUInt32LE(data.length, 24)
  central.writeUInt16LE(filename.length, 28)
  const offset = local.length + filename.length + data.length
  const end = Buffer.alloc(22)
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(1, 8); end.writeUInt16LE(1, 10)
  end.writeUInt32LE(central.length + filename.length, 12); end.writeUInt32LE(offset, 16)
  return Buffer.concat([local, filename, data, central, filename, end])
}

function zipEntries(archive: Buffer): Map<string, Buffer> {
  const entries = new Map<string, Buffer>()
  let offset = 0
  while (offset + 30 <= archive.length && archive.readUInt32LE(offset) === 0x04034b50) {
    const method = archive.readUInt16LE(offset + 8)
    const compressedSize = archive.readUInt32LE(offset + 18)
    const filenameLength = archive.readUInt16LE(offset + 26)
    const extraLength = archive.readUInt16LE(offset + 28)
    const filename = archive.subarray(offset + 30, offset + 30 + filenameLength).toString()
    const dataStart = offset + 30 + filenameLength + extraLength
    const compressed = archive.subarray(dataStart, dataStart + compressedSize)
    entries.set(filename, method === 8 ? inflateRawSync(compressed) : compressed)
    offset = dataStart + compressedSize
  }
  return entries
}

async function fullExportEntries(page: import('@playwright/test').Page, runId: string, interpretationId: string) {
  const query = `interpretation_id=${interpretationId}&mode=full`
  const started = await page.request.post(`/api/runs/${runId}/exports?${query}`)
  expect(started.ok()).toBeTruthy()
  await expect.poll(async () => {
    const response = await page.request.get(`/api/runs/${runId}/exports/status?${query}`)
    return (await response.json()).status
  }, { timeout: 120_000 }).toBe('complete')
  const download = await page.request.get(`/api/runs/${runId}/exports/download?${query}`)
  expect(download.ok()).toBeTruthy()
  return zipEntries(await download.body())
}

test('public v1.0.0 workflow: upload, real worker run, reinterpret, views, downloads, delete', async ({ page }) => {
  const archive = join(tmpdir(), `qscn-e2e-${Date.now()}.zip`)
  const projectName = `v1.0.0 browser E2E ${Date.now()}`
  const databaseName = `TSV browser E2E ${Date.now()}`
  const pathwayTable = join(tmpdir(), `qscn-pathways-${Date.now()}.tsv`)
  const guidanceTable = join(tmpdir(), `qscn-guidance-${Date.now()}.tsv`)
  writeFileSync(archive, storedZip('tiny-proteome.faa', '>protein_1\nMPEPTIDEWLFQH\n'))
  writeFileSync(pathwayTable,
    'Pathway\tSignal_type\tSignal_Sending\tSignal_Receiving\tReferences\n' +
    'Custom_guided_system\tHSLs\tLuxM;LuxI\tLuxN\thttps://doi.org/10.1128/jb.183.12.3537-3547.2001\n')
  writeFileSync(guidanceTable,
    'Format_version\tGuidance_version\tEndpoint_ID\tPathway\tRole\tName\tRequired_profiles\tOptional_profiles\tRecommended_wording\tInterpretation_boundary\tEvidence_IDs\tReferences\n' +
    '1.0\tcustom-e2e-1\tcustom-luxm-core\tCustom_guided_system\tsending\tLuxM core\tLuxM\tLuxI\tCandidate LuxM core\tSequence evidence does not establish signal production.\tCUSTOM-EVIDENCE-1\thttps://doi.org/10.1128/jb.183.12.3537-3547.2001\n')

  await page.goto('/')
  await expect(page).toHaveTitle('Q-SCOPE · Quorum-Sensing Communication Link Predictor')
  await expect(page.getByRole('button', { name: 'Quorum-Sensing Communication Link Predictor (Q-SCOPE)' })).toBeVisible()
  await expect(page.getByAltText('Q-SCOPE logo')).toBeVisible()
  await expect(page.getByText('Q-SCOPE v1.0.0 · For research use only')).toBeVisible()
  await page.getByRole('button', { name: 'Import custom database' }).click()
  const templateDownload = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Download Pathway template' }).click()
  await expect((await templateDownload).suggestedFilename()).toBe('qscn-pathways-template.tsv')
  const componentDownload = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Download component-name template' }).click()
  await expect((await componentDownload).suggestedFilename()).toBe('qscn-component-names-template.tsv')
  const guidanceDownload = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Download guidance template' }).click()
  await expect((await guidanceDownload).suggestedFilename()).toBe('qscn-interpretation-guidance-template.tsv')
  await page.getByLabel('Database name').fill(databaseName)
  await page.getByLabel('Version').fill('1.0')
  await page.getByLabel('Threshold policy').selectOption('ga')
  await page.locator('.file-picker input[accept=".hmm"]').setInputFiles(resolve('..', 'databases', 'QSPdatabase.hmm'))
  await page.locator('.file-picker input[accept=".tsv,.txt"]').nth(0).setInputFiles(pathwayTable)
  await page.locator('.file-picker input[accept=".tsv,.txt"]').nth(2).setInputFiles(guidanceTable)
  await page.getByRole('button', { name: 'Import database' }).click()
  const importedDatabase = page.getByRole('row', { name: new RegExp(databaseName) })
  await expect(importedDatabase).toBeVisible({ timeout: 60_000 })

  await page.getByLabel('Project name').fill(projectName)
  await page.getByLabel('Choose a ZIP archive').setInputFiles(archive)
  await page.getByRole('button', { name: 'Upload and validate' }).click()
  await expect(page.getByRole('heading', { name: 'Validated samples' })).toBeVisible()

  await page.getByLabel('Profile database').selectOption({ label: `${databaseName} · 1.0` })
  await page.getByRole('button', { name: 'Configure capability rules' }).click()
  await page.getByLabel('Criteria for the sending role in Custom_guided_system').selectOption('required_profiles')
  await expect(page.getByText('CUSTOM-EVIDENCE-1')).toBeVisible()
  await page.getByRole('button', { name: 'Apply endpoint' }).click()
  await page.getByRole('button', { name: 'Save criteria' }).click()

  await page.getByRole('button', { name: 'Start analysis' }).click()
  await expect(page.getByRole('heading', { name: 'Sending- and receiving-role evidence' })).toBeVisible({ timeout: 240_000 })
  await page.getByRole('button', { name: 'Interpretation settings' }).click()
  await page.getByRole('button', { name: 'Select Pathways' }).click()
  await page.locator('.interpretation-modal .scope-options input').first().check()
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(page.getByText('All Pathways in the selected database will be evaluated.')).toBeVisible()
  await page.getByRole('button', { name: 'Interpretation settings' }).click()
  await page.getByRole('button', { name: 'Select Pathways' }).click()
  await page.locator('.interpretation-modal .scope-options input').first().check()
  await page.getByRole('button', { name: 'Apply settings' }).click()
  await expect(page.getByText(/1 selected Pathway will be evaluated/)).toBeVisible()

  await page.getByRole('button', { name: 'Network', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Quorum-sensing communication network (potential)' })).toBeVisible()
  await page.getByRole('button', { name: 'Interpretation settings' }).click()
  await page.getByRole('button', { name: 'All Pathways' }).click()
  await page.getByRole('button', { name: 'Apply settings' }).click()
  await expect(page.getByRole('heading', { name: 'Quorum-sensing communication network (potential)' })).toBeVisible()
  await page.getByRole('button', { name: 'Group by signal' }).click()
  await page.getByRole('button', { name: 'One edge per Pathway' }).click()
  await page.getByRole('button', { name: 'Summary' }).click()

  await page.getByRole('button', { name: 'Evidence', exact: true }).click()
  await page.getByRole('button', { name: 'HMM evidence' }).click()
  await page.getByRole('button', { name: 'Prepare analysis package' }).click()
  const analysisDownloadLink = page.getByRole('link', { name: 'Download analysis package' })
  await expect(analysisDownloadLink).toBeVisible({ timeout: 60_000 })
  const exportDownload = page.waitForEvent('download')
  await analysisDownloadLink.click()
  await expect((await exportDownload).suggestedFilename()).toMatch(/^qscn-.*\.zip$/)

  await page.getByRole('button', { name: 'Projects', exact: true }).click()
  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('article', { name: projectName }).getByLabel('Delete project').click()
  await expect(page.getByRole('heading', { name: projectName, exact: true })).not.toBeVisible()
  page.once('dialog', dialog => dialog.accept())
  await importedDatabase.getByLabel('Delete database').click()
  await expect(importedDatabase).not.toBeVisible()
})

test('analysis tree preserves two QSP interpretations and a KEGG run with exact artifact links', async ({ page }) => {
  const archive = join(tmpdir(), `qscn-history-e2e-${Date.now()}.zip`)
  const projectName = `v1.0.0 history E2E ${Date.now()}`
  writeFileSync(archive, storedZip('tiny-proteome.faa', '>protein_1\nMPEPTIDEWLFQH\n'))

  await page.goto('/')
  await page.getByLabel('Project name').fill(projectName)
  await page.getByLabel('Choose a ZIP archive').setInputFiles(archive)
  await page.getByRole('button', { name: 'Upload and validate' }).click()
  await expect(page.getByRole('heading', { name: 'Validated samples' })).toBeVisible()

  const project = (await (await page.request.get('/api/projects')).json() as Array<{ id: string; name: string }>).find((item) => item.name === projectName)
  expect(project).toBeTruthy()

  await page.getByLabel('Profile database').selectOption({ label: 'QSP published profiles · builtin-v2' })
  await page.getByRole('button', { name: 'Start analysis' }).click()
  await expect(page.getByRole('heading', { name: 'Sending- and receiving-role evidence' })).toBeVisible({ timeout: 240_000 })

  await page.getByRole('button', { name: 'Interpretation settings' }).click()
  await page.getByRole('button', { name: 'Select Pathways' }).click()
  await page.locator('.interpretation-modal .scope-options input').first().check()
  await page.getByRole('button', { name: 'Apply settings' }).click()
  await expect(page.getByText(/1 selected Pathway will be evaluated/)).toBeVisible()

  let tree = await (await page.request.get(`/api/projects/${project!.id}/analysis-tree`)).json() as {
    databases: Array<{ name: string; runs: Array<{ id: string; interpretations: Array<{ id: string }> }> }>
  }
  const qspNode = tree.databases.find((database) => database.name === 'QSP published profiles')
  expect(qspNode?.runs).toHaveLength(1)
  expect(qspNode?.runs[0].interpretations).toHaveLength(2)

  await page.getByRole('button', { name: 'Project', exact: true }).click()
  await page.getByLabel('Profile database').selectOption({ label: 'KEGG map02024 QS profiles · m02024-display-v2' })
  await page.getByRole('button', { name: 'Start analysis' }).click()
  await expect(page.getByRole('heading', { name: 'Sending- and receiving-role evidence' })).toBeVisible({ timeout: 240_000 })

  tree = await (await page.request.get(`/api/projects/${project!.id}/analysis-tree`)).json()
  expect(tree.databases).toHaveLength(2)
  expect(tree.databases.find((database) => database.name === 'QSP published profiles')?.runs[0].interpretations).toHaveLength(2)
  expect(tree.databases.find((database) => database.name === 'KEGG map02024 QS profiles')?.runs[0].interpretations).toHaveLength(1)

  const saved = tree.databases.flatMap((database) => database.runs.flatMap((run) =>
    run.interpretations.map((interpretation, index) => ({
      runId: run.id,
      interpretationId: interpretation.id,
      name: `${database.name.startsWith('QSP') ? 'QSP' : 'KEGG'} saved ${index + 1}`,
    })),
  ))
  for (const item of saved) {
    const response = await page.request.patch(`/api/runs/${item.runId}/interpretations/${item.interpretationId}`, { data: { name: item.name } })
    expect(response.ok()).toBeTruthy()
  }

  await page.reload()
  await page.getByRole('article', { name: projectName }).getByRole('button').first().click()
  await expect(page.getByRole('heading', { name: 'Evidence', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Project', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Analysis history' })).toBeVisible()
  await expect(page.locator('.analysis-history').getByText('QSP published profiles', { exact: true })).toBeVisible()
  await expect(page.locator('.analysis-history').getByText('KEGG map02024 QS profiles', { exact: true })).toBeVisible()

  for (const item of saved) {
    await page.locator('.analysis-history button[title="Open interpretation"]').filter({ hasText: item.name }).click()
    await page.getByRole('button', { name: 'HMM evidence', exact: true }).click()
    await expect(page.getByRole('link', { name: 'Hit-quality evidence TSV' })).toHaveAttribute(
      'href',
      `/api/runs/${item.runId}/interpretations/${item.interpretationId}/artifacts/hit-quality-evidence.tsv`,
    )
    await page.getByRole('button', { name: 'Project', exact: true }).click()
  }

  await page.getByRole('button', { name: 'Projects', exact: true }).click()
  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('article', { name: projectName }).getByLabel('Delete project').click()
  await expect(page.getByRole('heading', { name: projectName, exact: true })).not.toBeVisible()
})

test('genome project reuses one Prodigal prediction cache across QSP and KEGG runs', async ({ page }) => {
  const archive = join(tmpdir(), `qscn-genome-e2e-${Date.now()}.zip`)
  const projectName = `v1.0.0 genome cache E2E ${Date.now()}`
  const codons = ['GCT', 'GAA', 'CCA', 'TTT', 'AAG', 'GGT']
  const orfs = Array.from({ length: 36 }, (_, index) => {
    const body = Array.from({ length: 280 }, (_, offset) => codons[(index + offset) % codons.length]).join('')
    return `ATG${body}TAA${'C'.repeat(45)}`
  })
  writeFileSync(archive, storedZip('synthetic-genome.fna', `>synthetic_contig\n${orfs.join('')}\n`))

  await page.goto('/')
  await page.getByRole('button', { name: 'Nucleotide sequences' }).click()
  await page.getByLabel('Project name').fill(projectName)
  await page.getByLabel('Choose a ZIP archive').setInputFiles(archive)
  await page.getByRole('button', { name: 'Upload and validate' }).click()
  await expect(page.getByRole('heading', { name: 'Validated samples' })).toBeVisible()
  const project = (await (await page.request.get('/api/projects')).json() as Array<{ id: string; name: string }>).find((item) => item.name === projectName)!

  await page.getByLabel('Profile database').selectOption({ label: 'QSP published profiles · builtin-v2' })
  await page.getByRole('button', { name: 'Start analysis' }).click()
  await expect(page.getByRole('heading', { name: 'Sending- and receiving-role evidence' })).toBeVisible({ timeout: 240_000 })
  let tree = await (await page.request.get(`/api/projects/${project.id}/analysis-tree`)).json() as {
    databases: Array<{ name: string; runs: Array<{ id: string; interpretations: Array<{ id: string }> }> }>
  }
  const firstRun = tree.databases.find((database) => database.name === 'QSP published profiles')!.runs[0]

  await page.getByRole('button', { name: 'Project', exact: true }).click()
  await page.getByLabel('Profile database').selectOption({ label: 'KEGG map02024 QS profiles · m02024-display-v2' })
  await page.getByRole('button', { name: 'Start analysis' }).click()
  await expect(page.getByRole('heading', { name: 'Sending- and receiving-role evidence' })).toBeVisible({ timeout: 240_000 })
  tree = await (await page.request.get(`/api/projects/${project.id}/analysis-tree`)).json()
  const secondRun = tree.databases.find((database) => database.name === 'KEGG map02024 QS profiles')!.runs[0]

  const firstExport = await fullExportEntries(page, firstRun.id, firstRun.interpretations[0].id)
  const secondExport = await fullExportEntries(page, secondRun.id, secondRun.interpretations[0].id)
  const firstManifest = JSON.parse(firstExport.get('run_manifest.json')!.toString())
  const secondManifest = JSON.parse(secondExport.get('run_manifest.json')!.toString())
  expect(firstManifest.gene_prediction.reused).toBe(false)
  expect(secondManifest.gene_prediction.reused).toBe(true)
  expect(secondManifest.gene_prediction.source).toBe('project_cache')
  expect(secondManifest.gene_prediction.cache_key).toBe(firstManifest.gene_prediction.cache_key)
  expect([...firstExport.keys()].some((name) => name.startsWith('predictions/') && name.endsWith('.faa'))).toBeTruthy()
  expect([...secondExport.keys()].some((name) => name.startsWith('predictions/') && name.endsWith('.gff'))).toBeTruthy()

  await page.getByRole('button', { name: 'Projects', exact: true }).click()
  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('article', { name: projectName }).getByLabel('Delete project').click()
  await expect(page.getByRole('heading', { name: projectName, exact: true })).not.toBeVisible()
})
