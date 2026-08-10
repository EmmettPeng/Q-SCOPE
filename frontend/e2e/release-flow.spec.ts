import { expect, test } from '@playwright/test'
import { writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

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

test('public v0.4.0 workflow: upload, real worker run, reinterpret, views, downloads, delete', async ({ page }) => {
  const archive = join(tmpdir(), `qscn-e2e-${Date.now()}.zip`)
  const projectName = `v0.4.0 browser E2E ${Date.now()}`
  const databaseName = `TSV browser E2E ${Date.now()}`
  const pathwayTable = join(tmpdir(), `qscn-pathways-${Date.now()}.tsv`)
  writeFileSync(archive, storedZip('tiny-proteome.faa', '>protein_1\nMPEPTIDEWLFQH\n'))
  writeFileSync(pathwayTable,
    'Pathway\tSignal_type\tSignal_Sending\tSignal_Receiving\tReferences\n' +
    'LuxM_LuxN_system\tHSLs\tLuxM\tLuxN\thttps://doi.org/10.1128/jb.183.12.3537-3547.2001\n' +
    'LuxI_LuxR_system\tHSLs\tLuxI\tLuxR\thttps://doi.org/10.1007/s10867-010-9186-4\n')

  await page.goto('/')
  await expect(page).toHaveTitle('Quorum Sensing Communication Network Analysis')
  await expect(page.getByText('QSCN v0.4.0 · For research use only')).toBeVisible()
  await page.getByRole('button', { name: 'Import custom database' }).click()
  const templateDownload = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Download TSV template' }).click()
  await expect((await templateDownload).suggestedFilename()).toBe('qscn-pathways-template.tsv')
  await page.getByLabel('Database name').fill(databaseName)
  await page.getByLabel('Version').fill('1.0')
  await page.getByLabel('Threshold policy').selectOption('ga')
  await page.locator('.file-picker input[accept=".hmm"]').setInputFiles(resolve('..', 'databases', 'QSPdatabase.hmm'))
  await page.locator('.file-picker input[accept=".tsv,.txt"]').setInputFiles(pathwayTable)
  await page.getByRole('button', { name: 'Import database' }).click()
  const importedDatabase = page.locator('.db-mini').filter({ hasText: databaseName })
  await expect(importedDatabase).toBeVisible({ timeout: 60_000 })
  page.once('dialog', dialog => dialog.accept())
  await importedDatabase.getByLabel('Delete database').click()
  await expect(importedDatabase).not.toBeVisible()

  await page.getByLabel('Project name').fill(projectName)
  await page.locator('.dropzone input[type=file]').setInputFiles(archive)
  await page.getByRole('button', { name: 'Upload and validate' }).click()
  await expect(page.getByRole('heading', { name: 'Validated samples' })).toBeVisible()

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

  await page.getByRole('button', { name: 'Potential network' }).click()
  await page.getByRole('button', { name: 'Group by signal' }).click()
  await page.getByRole('button', { name: 'One edge per Pathway' }).click()
  await page.getByRole('button', { name: 'Summary' }).click()

  await page.getByRole('button', { name: 'HMM evidence' }).click()
  const exportDownload = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Download complete result package' }).click()
  await expect((await exportDownload).suggestedFilename()).toMatch(/^qscn-.*\.zip$/)

  page.once('dialog', dialog => dialog.accept())
  await page.locator('.project-item.active').getByLabel('Delete project').click()
  await expect(page.getByRole('heading', { name: projectName, exact: true })).not.toBeVisible()
})
