import { expect, test } from '@playwright/test'

test('read-only Pages demo browses PD10 without backend API traffic', async ({ page }) => {
  const apiRequests: string[] = []
  page.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url())
  })

  await page.goto('/Q-SCOPE/')
  await expect(page.getByText('Read-only demo · Precomputed PD10 results')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Upload and validate' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Delete project' })).toBeDisabled()

  await page.getByRole('article', { name: 'PD10' }).getByRole('button').first().click()
  await expect(page.getByRole('heading', { name: 'Validated samples' })).toBeVisible()
  await page.locator('.analysis-history button[title="Open interpretation"]').click()
  await expect(page.getByRole('heading', { name: 'Sending- and receiving-role evidence' })).toBeVisible()

  await page.getByRole('button', { name: 'Interpretation settings' }).click()
  await expect(page.getByText('Read-only preview.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Apply settings' })).toBeDisabled()
  await page.getByRole('button', { name: 'Close interpretation settings' }).click()

  await page.getByRole('button', { name: 'HMM evidence' }).click()
  await expect(page.locator('.hit-row').nth(1)).toBeVisible()
  await page.getByRole('button', { name: 'Network', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Quorum-sensing communication network (potential)' })).toBeVisible()
  await page.getByRole('button', { name: 'Interpretation settings' }).click()
  await expect(page.getByRole('button', { name: 'Apply settings' })).toBeDisabled()
  await page.getByRole('button', { name: 'Close interpretation settings' }).click()
  await expect(page.locator('.stat-cards')).toContainText('128')
  expect(apiRequests).toEqual([])
})
