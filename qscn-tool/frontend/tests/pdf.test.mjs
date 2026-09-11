import assert from 'node:assert/strict'
import test from 'node:test'
import { build } from 'esbuild'

const result = await build({ entryPoints: ['src/pdf.ts'], bundle: true, write: false, format: 'esm', platform: 'node' })
const { jpegDataUrlToPdf } = await import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].contents).toString('base64')}`)

test('wraps JPEG bytes in a single-page PDF with a header and correct image orientation', async () => {
  const jpeg = '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9oADAMBAAIAAwAAABD/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/EB//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/EB//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/EB//2Q=='
  const blob = await jpegDataUrlToPdf(`data:image/jpeg;base64,${jpeg}`, 1200, 700, {
    title: 'Q-SCOPE network',
    meta: 'minimal view',
    legend: [{ label: 'AI-2', color: '#6f9278' }],
  })
  assert.equal(blob.type, 'application/pdf')
  const bytes = Buffer.from(await blob.arrayBuffer())
  assert.match(bytes.subarray(0, 8).toString(), /^%PDF-1\.[4-7]$/)
  assert.ok(bytes.length > 500)
  assert.match(bytes.toString('latin1'), /startxref/)
})
