import { jsPDF } from 'jspdf'
import { autoTable } from 'jspdf-autotable'
import { money, monthName } from '../finance/dashboard.js'
import { downloadFile } from './download.js'

const title = 'FinSet \u2014 Financial Statement'
const fontName = 'NunitoSans'
const colors = {
  brand: '#6037a2', text: '#262032', muted: '#6b6378', border: '#e9e5ef',
  soft: '#fbfafe', income: '#27714f', expense: '#b3334a',
}
// Original OFL-licensed static fonts from google/fonts revision 67c396223bad0bfb69801c5c28e410f50fe35274.
const fontUrls = [
  new URL('../assets/NunitoSans-Regular.ttf', import.meta.url),
  new URL('../assets/NunitoSans-Bold.ttf', import.meta.url),
]
let fontsPromise

async function loadFonts() {
  if (!fontsPromise) {
    fontsPromise = Promise.all(fontUrls.map(async (url) => {
      const response = await fetch(url)
      if (!response.ok) throw new Error('The statement font could not be loaded.')
      const bytes = new Uint8Array(await response.arrayBuffer())
      let binary = ''
      for (const byte of bytes) binary += String.fromCharCode(byte)
      return btoa(binary)
    })).catch((error) => {
      fontsPromise = undefined
      throw error
    })
  }
  return fontsPromise
}

export function statementFilename(range) {
  const period = ['this-month', 'last-month'].includes(range.preset)
    ? monthName(range.from.slice(0, 7)).replaceAll(' ', '-')
    : range.from === range.to ? range.from : `${range.from}-to-${range.to}`
  return `FinSet-Financial-Statement-${period}.pdf`
}

export function createFinancialStatement(report, fonts, generatedAt = new Date()) {
  const doc = new jsPDF({ unit: 'pt', format: 'a4', putOnlyUsedFonts: true, compress: true })
  for (const [index, style] of ['normal', 'bold'].entries()) {
    const filename = `NunitoSans-${style}.ttf`
    doc.addFileToVFS(filename, fonts[index])
    doc.addFont(filename, fontName, style)
  }
  doc.setFont(fontName, 'normal')
  doc.setCreationDate(generatedAt)
  doc.setProperties({ title, author: 'FinSet', creator: 'FinSet', subject: `Financial records for ${report.range.label}` })

  const width = doc.internal.pageSize.getWidth()
  const height = doc.internal.pageSize.getHeight()
  const margin = 40
  const right = width - margin
  const contentWidth = width - margin * 2
  const generatedDate = new Intl.DateTimeFormat('en-NG', { day: 'numeric', month: 'long', year: 'numeric' }).format(generatedAt)
  const countLabel = `${report.summary.count} confirmed ${report.summary.count === 1 ? 'transaction' : 'transactions'}`

  doc.setFillColor(colors.brand)
  doc.roundedRect(margin, 34, 30, 30, 8, 8, 'F')
  doc.setFillColor('#ffffff')
  doc.rect(margin + 9, 42, 3, 16, 'F')
  doc.rect(margin + 9, 42, 13, 3, 'F')
  doc.rect(margin + 9, 48, 10, 3, 'F')
  doc.setFont(fontName, 'bold').setFontSize(21).setTextColor(colors.text)
  doc.text('FinSet', margin + 42, 53)
  doc.setFont(fontName, 'normal').setFontSize(8).setTextColor(colors.muted)
  doc.text('Student Budget & Expense Tracker', margin + 42, 67)

  doc.setFont(fontName, 'bold').setFontSize(22).setTextColor(colors.text)
  doc.text(title, margin, 106)
  doc.setFontSize(8).setTextColor(colors.muted)
  doc.text('REPORTING PERIOD', margin, 130)
  doc.text('GENERATED ON', right, 130, { align: 'right' })
  doc.setFont(fontName, 'normal').setFontSize(10).setTextColor(colors.text)
  doc.text(report.range.label, margin, 146)
  doc.text(generatedDate, right, 146, { align: 'right' })
  doc.setDrawColor(colors.border).setLineWidth(0.7)
  doc.line(margin, 160, right, 160)

  const summary = [
    { label: 'Total Income', value: report.summary.income, color: colors.income, note: 'Confirmed money received' },
    { label: 'Total Expenses', value: report.summary.expenses, color: colors.expense, note: 'Confirmed money spent' },
    { label: 'Net Cash Flow', value: report.summary.net, color: colors.brand, note: 'Income minus expenses', signed: true },
  ]
  const gap = 12
  const cardWidth = (contentWidth - gap * 2) / 3
  summary.forEach((cell, index) => {
    const x = margin + index * (cardWidth + gap)
    doc.setFillColor(colors.soft).setDrawColor(colors.border)
    doc.roundedRect(x, 177, cardWidth, 76, 6, 6, 'FD')
    doc.setFont(fontName, 'normal').setFontSize(9).setTextColor(colors.muted)
    doc.text(cell.label, x + 12, 197)
    const value = `${cell.signed && cell.value > 0 ? '+' : ''}${money(cell.value, true)}`
    doc.setFont(fontName, 'bold').setFontSize(17)
    const valueSize = Math.min(17, 17 * (cardWidth - 24) / doc.getTextWidth(value))
    doc.setFontSize(valueSize).setTextColor(cell.value < 0 ? colors.expense : cell.color)
    doc.text(value, x + 12, 222)
    doc.setFont(fontName, 'normal').setFontSize(7.5).setTextColor(colors.muted)
    doc.text(cell.note, x + 12, 240)
  })

  doc.setFont(fontName, 'bold').setFontSize(13).setTextColor(colors.text)
  doc.text('Transaction Details', margin, 285)
  doc.setFont(fontName, 'normal').setFontSize(9).setTextColor(colors.muted)
  doc.text(countLabel, right, 285, { align: 'right' })
  doc.setFontSize(8)
  doc.text('All amounts are in Nigerian naira (NGN). Expenses are shown as negative amounts.', margin, 302)

  // Presentation only: the same complete, eligible ledger and kobo totals as Reports and CSV.
  const rows = report.transactions.map((row) => [
    row.dateLabel, row.name.replaceAll('\t', ' '), row.categoryName.replaceAll('\t', ' '), row.typeLabel,
    money(row.type === 'expense' ? -row.amount : row.amount, true),
  ])
  const font = doc.getFont(fontName, 'normal')
  for (const row of rows) {
    for (const text of row) {
      for (const character of text) {
        if ('\r\n'.includes(character)) continue
        if (character.length > 1 || !font.metadata.characterToGlyph(character.charCodeAt(0))) {
          const error = new Error('The statement contains text that cannot be rendered with the PDF font.')
          error.code = 'FINSET_PDF_UNSUPPORTED_TEXT'
          throw error
        }
      }
    }
  }
  doc.setFont(fontName, 'bold').setFontSize(8.5)
  const amountWidth = rows.reduce((maximum, row) => Math.max(maximum, doc.getTextWidth(row[4]) + 16), 100)
  autoTable(doc, {
    startY: 316,
    margin: { top: 80, right: margin, bottom: 76, left: margin },
    tableWidth: contentWidth,
    head: [['Date', 'Description', 'Category', 'Type', { content: 'Amount', styles: { halign: 'right' } }]],
    body: rows.length ? rows : [[{ content: 'No confirmed transactions in this reporting period.', colSpan: 5, styles: { halign: 'center', cellPadding: 22, textColor: colors.muted } }]],
    theme: 'striped',
    showHead: 'everyPage',
    rowPageBreak: 'avoid',
    styles: {
      font: fontName, fontStyle: 'normal', fontSize: 8.5, textColor: colors.text,
      overflow: 'linebreak', valign: 'top', cellPadding: 6, minCellHeight: 24,
      lineColor: colors.border, lineWidth: { bottom: 0.4 },
    },
    headStyles: { fillColor: colors.brand, textColor: '#ffffff', fontStyle: 'bold', cellPadding: 8 },
    alternateRowStyles: { fillColor: colors.soft },
    columnStyles: {
      0: { cellWidth: 72 },
      1: { cellWidth: contentWidth - 72 - 92 - 58 - amountWidth },
      2: { cellWidth: 92 },
      3: { cellWidth: 58 },
      4: { cellWidth: amountWidth, halign: 'right', fontStyle: 'bold' },
    },
    didParseCell(data) {
      if (data.section === 'body' && rows.length && [3, 4].includes(data.column.index)) {
        data.cell.styles.textColor = report.transactions[data.row.index].type === 'income' ? colors.income : colors.expense
      }
    },
    willDrawPage({ pageNumber }) {
      if (pageNumber === 1) return
      doc.setFont(fontName, 'bold').setFontSize(10).setTextColor(colors.brand)
      doc.text(title, margin, 39)
      doc.setFont(fontName, 'normal').setFontSize(8.5).setTextColor(colors.muted)
      doc.text(report.range.label, margin, 55)
      doc.text(`Generated ${generatedDate}`, right, 55, { align: 'right' })
      doc.setDrawColor(colors.border).setLineWidth(0.7)
      doc.line(margin, 65, right, 65)
    },
  })

  // Add footers after layout, when the final page count is known.
  const pages = doc.getNumberOfPages()
  for (let page = 1; page <= pages; page += 1) {
    doc.setPage(page)
    doc.setDrawColor(colors.border).setLineWidth(0.7)
    doc.line(margin, height - 58, right, height - 58)
    doc.setFont(fontName, 'normal').setFontSize(7.5).setTextColor(colors.muted)
    doc.text('This statement represents records entered into FinSet, not independently verified bank activity.', margin, height - 43)
    doc.setFontSize(8)
    doc.text('FinSet | Financial Statement', margin, height - 25)
    doc.text(`Page ${page} of ${pages}`, right, height - 25, { align: 'right' })
  }
  return doc
}

export async function downloadFinancialStatement(report) {
  const generatedAt = new Date()
  const fonts = await loadFonts()
  const doc = createFinancialStatement(report, fonts, generatedAt)
  downloadFile(doc.output('blob'), statementFilename(report.range))
}
