import { PDFDocument, StandardFonts, rgb } from 'pdf-lib'

interface PdfLegendItem { label: string; color: string }
interface PdfHeader { title: string; meta: string; legend: PdfLegendItem[] }

function pdfColor(hex: string) {
  const value = hex.replace('#', '')
  return rgb(...([0, 2, 4].map((index) => Number.parseInt(value.slice(index, index + 2), 16) / 255) as [number, number, number]))
}

export async function jpegDataUrlToPdf(dataUrl: string, width: number, height: number, header?: PdfHeader): Promise<Blob> {
  const encoded = dataUrl.split(',', 2)[1]
  if (!encoded) throw new Error('Invalid network image data.')

  const pdf = await PDFDocument.create()
  const landscape = width >= height
  const pageWidth = landscape ? 842 : 595
  const pageHeight = landscape ? 595 : 842
  const page = pdf.addPage([pageWidth, pageHeight])
  const font = await pdf.embedFont(StandardFonts.Helvetica)
  const jpeg = await pdf.embedJpg(Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0)))

  const legendRows: Array<Array<PdfLegendItem>> = []
  if (header?.legend.length) {
    let row: PdfLegendItem[] = []
    let used = 0
    header.legend.forEach((item) => {
      const itemWidth = 24 + font.widthOfTextAtSize(item.label, 8)
      if (row.length && used + itemWidth > pageWidth - 64) { legendRows.push(row); row = []; used = 0 }
      row.push(item); used += itemWidth
    })
    if (row.length) legendRows.push(row)
  }

  const headerHeight = header ? 66 + legendRows.length * 18 : 0
  const availableHeight = pageHeight - headerHeight - 24
  const scale = Math.min((pageWidth - 32) / width, availableHeight / height)
  const drawWidth = width * scale
  const drawHeight = height * scale
  const x = (pageWidth - drawWidth) / 2
  const y = 16 + Math.max(0, (availableHeight - drawHeight) / 2)
  page.drawImage(jpeg, { x, y, width: drawWidth, height: drawHeight })

  if (header) {
    page.drawText(header.title, { x: 32, y: pageHeight - 30, size: 18, font })
    page.drawText(header.meta, { x: 32, y: pageHeight - 49, size: 10, font, color: rgb(0.35, 0.35, 0.35) })
    legendRows.forEach((row, rowIndex) => {
      let legendX = 32
      const legendY = pageHeight - 68 - rowIndex * 18
      row.forEach((item) => {
        page.drawRectangle({ x: legendX, y: legendY, width: 8, height: 8, color: pdfColor(item.color) })
        page.drawText(item.label, { x: legendX + 12, y: legendY + 1, size: 8, font })
        legendX += 24 + font.widthOfTextAtSize(item.label, 8)
      })
    })
  }

  return new Blob([await pdf.save()], { type: 'application/pdf' })
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = filename; link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
}
