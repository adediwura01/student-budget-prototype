import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createDashboardWorkspace } from '../src/demo/dashboard.js'
import { money, selectDashboard, transactionCsv } from '../src/finance/dashboard.js'
import { resolveReportRange, selectReports } from '../src/finance/reports.js'
import { createFinancialStatement, downloadFinancialStatement, statementFilename } from '../src/utils/financialStatement.js'
import { downloadFile } from '../src/utils/download.js'

const fonts = ['Regular', 'Bold'].map((weight) => readFileSync(new URL(`../src/assets/NunitoSans-${weight}.ttf`, import.meta.url)).toString('base64'))
const generatedAt = new Date(2026, 10, 16, 12)
const workspace = createDashboardWorkspace()
const reportFor = (data = workspace, preset = 'this-month', custom = {}) => selectReports(data, resolveReportRange(data.asOf, preset, custom))
const pdfFor = (report) => createFinancialStatement(report, fonts, generatedAt)

// Decode the actual text drawing operations using the embedded fonts' Unicode maps.
function pageText(doc, textX) {
  const maps = Object.fromEntries(['normal', 'bold'].map((style) => {
    const font = doc.getFont('NunitoSans', style)
    return [font.id, font.metadata.toUnicode]
  }))
  return doc.internal.pages.slice(1).map((commands) => commands.flatMap((command) => {
    const font = /\/(F\d+) [\d.]+ Tf/.exec(command)?.[1]
    if (!maps[font]) return []
    if (textX !== undefined) {
      const position = /([-\d.]+) [-\d.]+ Td/.exec(command)
      if (!position || Math.abs(Number(position[1]) - textX) > 0.1) return []
    }
    return [...command.matchAll(/<([\da-f]+)>\s*Tj/gi)].map((match) =>
      match[1].match(/.{4}/g).map((glyph) => String.fromCharCode(maps[font][parseInt(glyph, 16)])).join(''))
  }))
}

function mockDownload(t, { clickError = false } = {}) {
  const calls = []
  const timers = []
  const blobs = []
  const link = {
    click() { calls.push('click'); if (clickError) throw new Error('Download blocked') },
    remove() { calls.push('remove') },
  }
  const oldDocument = globalThis.document
  globalThis.document = {
    createElement(tag) { assert.equal(tag, 'a'); return link },
    body: { append(item) { assert.equal(item, link); calls.push('append') } },
  }
  t.after(() => {
    if (oldDocument === undefined) delete globalThis.document
    else globalThis.document = oldDocument
  })
  t.mock.method(URL, 'createObjectURL', (blob) => { blobs.push(blob); calls.push('create'); return 'blob:financial-statement' })
  t.mock.method(URL, 'revokeObjectURL', (url) => { assert.equal(url, 'blob:financial-statement'); calls.push('revoke') })
  t.mock.method(globalThis, 'setTimeout', (callback, delay) => { timers.push({ callback, delay }); return 1 })
  return { calls, timers, blobs, link }
}

test('statement filenames identify month presets and exact applied custom periods', () => {
  assert.equal(statementFilename(reportFor().range), 'FinSet-Financial-Statement-November-2026.pdf')
  assert.equal(statementFilename(reportFor(workspace, 'last-month').range), 'FinSet-Financial-Statement-October-2026.pdf')
  assert.equal(statementFilename(reportFor(workspace, 'last-3-months').range), 'FinSet-Financial-Statement-2026-09-01-to-2026-11-13.pdf')
  assert.equal(statementFilename(reportFor(workspace, 'custom', { from: '2026-11-12', to: '2026-11-13' }).range), 'FinSet-Financial-Statement-2026-11-12-to-2026-11-13.pdf')
  assert.equal(statementFilename(reportFor(workspace, 'custom', { from: '2026-11-13', to: '2026-11-13' }).range), 'FinSet-Financial-Statement-2026-11-13.pdf')
})

test('PDF prints the actual Reports summary, period and generation date, not cumulative balance', () => {
  const report = reportFor()
  const doc = pdfFor(report)
  const text = pageText(doc)[0]
  assert.ok(text.includes('FinSet \u2014 Financial Statement'))
  assert.ok(text.includes(report.range.label))
  assert.ok(text.includes('16 November 2026'))
  for (const [label, value] of [['Total Income', money(report.summary.income, true)], ['Total Expenses', money(report.summary.expenses, true)], ['Net Cash Flow', `+${money(report.summary.net, true)}`]]) {
    assert.equal(text[text.indexOf(label) + 1], value)
  }
  assert.ok(!text.includes(money(selectDashboard(workspace, '2026-11').money.balance, true)))
  const bytes = Buffer.from(doc.output('arraybuffer'))
  assert.ok(bytes.toString('ascii', 0, 8).startsWith('%PDF-'))
  assert.ok(bytes.includes(Buffer.from('/ToUnicode')))
  assert.ok(bytes.includes(Buffer.from('%%EOF')))
})

test('embedded fonts render the naira symbol, punctuation and accented descriptions', () => {
  const copy = createDashboardWorkspace()
  copy.transactions.push({ id: 'accent', name: 'Caf\u00e9 \u2014 \u1ecd\u1eb9 market', type: 'expense', category: 'food', amount: 101, date: copy.asOf, confirmed: true })
  const doc = pdfFor(reportFor(copy))
  for (const style of ['normal', 'bold']) assert.ok(doc.getFont('NunitoSans', style).metadata.characterToGlyph(0x20a6) > 0)
  assert.ok(pageText(doc).flat().includes('Caf\u00e9 \u2014 \u1ecd\u1eb9 market'))
  assert.ok(pageText(doc).flat().includes(money(-101, true)))
})

test('unsupported characters fail explicitly instead of silently dropping transaction text', () => {
  const copy = createDashboardWorkspace()
  copy.transactions = [{ id: 'unsupported', name: 'Record \u4f60\u597d', type: 'expense', category: 'food', amount: 101, date: copy.asOf, confirmed: true }]
  const report = reportFor(copy)
  assert.throws(() => pdfFor(report), (error) => error.code === 'FINSET_PDF_UNSUPPORTED_TEXT')
  assert.ok(transactionCsv(report.transactions).includes('Record \u4f60\u597d'))
})

test('tabs and line breaks remain readable without truncating description text', () => {
  const copy = createDashboardWorkspace()
  copy.transactions = [{ id: 'whitespace', name: 'Tuition\tfees\nPayment record', type: 'expense', category: 'food', amount: 101, date: copy.asOf, confirmed: true }]
  const report = reportFor(copy)
  const doc = pdfFor(report)
  assert.equal(doc.lastAutoTable.body[0].raw[1], 'Tuition fees\nPayment record')
  const text = pageText(doc).flat()
  assert.ok(text.includes('Tuition fees'))
  assert.ok(text.includes('Payment record'))
  assert.ok(transactionCsv(report.transactions).includes('Tuition\tfees\nPayment record'))
})

test('PDF and CSV export every eligible transaction in the same order for each applied range', () => {
  for (const [preset, custom] of [['this-month', {}], ['last-month', {}], ['last-3-months', {}], ['custom', { from: '2026-11-12', to: '2026-11-13' }]]) {
    const report = reportFor(workspace, preset, custom)
    const doc = pdfFor(report)
    assert.equal(doc.lastAutoTable.body.length, report.summary.count)
    assert.deepEqual(doc.lastAutoTable.body.map((row) => row.raw), report.transactions.map((row) => [row.dateLabel, row.name, row.categoryName, row.typeLabel, money(row.type === 'expense' ? -row.amount : row.amount, true)]))
    const csvRows = transactionCsv(report.transactions).split('\r\n').slice(1).map((line) => line.match(/"(?:[^"]|"")*"/g).map((cell) => cell.slice(1, -1).replaceAll('""', '"')))
    assert.deepEqual(csvRows.map((row) => row[1]), doc.lastAutoTable.body.map((row) => row.raw[1]))
    assert.deepEqual(csvRows.map((row) => row[3]), doc.lastAutoTable.body.map((row) => row.raw[2]))
  }
})

test('unconfirmed, deleted, future, outside-range and planned records do not leak into either export', () => {
  const copy = createDashboardWorkspace()
  const row = { name: 'EXCLUDED_RECORD', type: 'expense', category: 'food', amount: 999, date: copy.asOf, confirmed: true }
  copy.transactions.push(
    { ...row, id: 'unconfirmed', confirmed: false },
    { ...row, id: 'truthy-confirmed', confirmed: 'true' },
    { ...row, id: 'deleted', deleted: true },
    { ...row, id: 'future', date: '2026-11-14' },
    { ...row, id: 'outside', date: '2026-10-31' },
    { ...row, id: 'transfer', type: 'transfer' },
  )
  copy.plans.push({ id: 'pending', name: 'EXCLUDED_PLAN', type: 'income', amount: 999999, date: copy.asOf, status: 'pending' })
  const report = reportFor(copy)
  assert.deepEqual(report.summary, reportFor().summary)
  assert.deepEqual(report.transactions, reportFor().transactions)
  assert.ok(!pageText(pdfFor(report)).flat().join(' ').includes('EXCLUDED'))
  assert.ok(!transactionCsv(report.transactions).includes('EXCLUDED'))
})

test('empty reporting periods produce a real one-page statement with zero totals and an empty-state table', () => {
  const report = reportFor(workspace, 'custom', { from: '2026-08-01', to: '2026-08-31' })
  const doc = pdfFor(report)
  const text = pageText(doc)[0]
  assert.equal(doc.getNumberOfPages(), 1)
  assert.equal(text.filter((value) => value === money(0, true)).length, 3)
  assert.ok(text.includes('0 confirmed transactions'))
  assert.ok(text.includes('No confirmed transactions in this reporting period.'))
  assert.equal(transactionCsv(report.transactions).split('\r\n').length, 1)
})

test('one-kobo amounts and a negative net cash flow retain their signs and precision', () => {
  const copy = createDashboardWorkspace()
  copy.transactions = [
    { id: 'income', name: 'One kobo received', type: 'income', category: 'allowance', amount: 1, date: copy.asOf, confirmed: true },
    { id: 'expense', name: 'Two kobo spent', type: 'expense', category: 'food', amount: 2, date: copy.asOf, confirmed: true },
  ]
  const report = reportFor(copy)
  assert.deepEqual(report.summary, { income: 1, expenses: 2, net: -1, count: 2 })
  const text = pageText(pdfFor(report)).flat()
  assert.ok(text.includes(money(1, true)))
  assert.ok(text.includes(money(-2, true)))
  assert.equal(text[text.indexOf('Net Cash Flow') + 1], money(-1, true))
})

test('large safe-kobo values remain readable within right-aligned amount cells', () => {
  const copy = createDashboardWorkspace()
  copy.transactions = [{ id: 'large', name: 'Large amount', type: 'income', category: 'allowance', amount: Number.MAX_SAFE_INTEGER, date: copy.asOf, confirmed: true }]
  const doc = pdfFor(reportFor(copy))
  const amount = doc.lastAutoTable.body[0].cells[4]
  assert.equal(amount.styles.halign, 'right')
  assert.equal(doc.lastAutoTable.head[0].cells[4].styles.halign, 'right')
  assert.equal(amount.text.length, 1)
  assert.ok(pageText(doc).flat().includes(money(Number.MAX_SAFE_INTEGER, true)))
  assert.ok(amount.x + amount.width <= doc.internal.pageSize.getWidth() - 40 + 0.1)
})

test('multi-page tables repeat headers, keep normal rows inside margins, and number every page correctly', () => {
  const copy = createDashboardWorkspace()
  copy.transactions = Array.from({ length: 120 }, (_, index) => ({ id: `row-${String(index).padStart(3, '0')}`, name: `Transaction ${index}: ${'A readable long description '.repeat(6)}`, type: index % 2 ? 'income' : 'expense', category: index % 2 ? 'allowance' : 'food', amount: index + 1, date: copy.asOf, confirmed: true }))
  const report = reportFor(copy)
  const before = structuredClone(report)
  const doc = pdfFor(report)
  const pages = pageText(doc)
  assert.ok(pages.length >= 3)
  assert.equal(doc.lastAutoTable.body.length, 120)
  assert.equal(doc.lastAutoTable.settings.rowPageBreak, 'avoid')
  assert.equal(doc.lastAutoTable.settings.showHead, 'everyPage')
  pages.forEach((text, index) => {
    for (const header of ['Date', 'Description', 'Category', 'Type', 'Amount']) assert.ok(text.includes(header))
    assert.ok(text.includes(`Page ${index + 1} of ${pages.length}`))
    assert.ok(text.includes('This statement represents records entered into FinSet, not independently verified bank activity.'))
    if (index > 0) assert.ok(!text.includes('Total Income'))
  })
  for (const row of doc.lastAutoTable.body) {
    for (const cell of Object.values(row.cells)) {
      assert.ok(cell.y >= 80)
      assert.ok(cell.y + cell.height <= doc.internal.pageSize.getHeight() - 76 + 0.1)
      assert.ok(cell.x >= 40)
      assert.ok(cell.x + cell.width <= doc.internal.pageSize.getWidth() - 40 + 0.1)
    }
    assert.ok(row.cells[1].text.length > 1)
    doc.setFont('NunitoSans', 'normal').setFontSize(8.5)
    for (const line of row.cells[1].text) assert.ok(doc.getTextWidth(line) <= row.cells[1].width - 12 + 0.1)
  }
  assert.deepEqual(report, before)
})

test('an exceptionally tall description continues across pages without losing its final text or following rows', () => {
  const copy = createDashboardWorkspace()
  const longName = `BEGIN_DESCRIPTION ${'LongDescriptionWithoutSpaces'.repeat(500)} END_DESCRIPTION`
  copy.transactions = [
    { id: 'a', name: longName, type: 'expense', category: 'food', amount: 101, date: copy.asOf, confirmed: true },
    { id: 'b', name: 'FOLLOWING_TRANSACTION', type: 'income', category: 'allowance', amount: 201, date: copy.asOf, confirmed: true },
  ]
  const doc = pdfFor(reportFor(copy))
  const text = pageText(doc).flat().join(' ')
  assert.ok(doc.getNumberOfPages() > 1)
  assert.ok(text.includes('BEGIN_DESCRIPTION'))
  assert.ok(text.includes('END_DESCRIPTION'))
  assert.ok(text.includes('FOLLOWING_TRANSACTION'))
  const descriptions = pageText(doc, doc.lastAutoTable.body[0].cells[1].x + 6).flat().join(' ')
  assert.ok(descriptions.replaceAll(/\s/g, '').includes(longName.replaceAll(/\s/g, '')))
})

test('the shared download helper preserves CSV content and releases its object URL after the click', (t) => {
  const state = mockDownload(t)
  const report = reportFor()
  const blob = new Blob([`\uFEFF${transactionCsv(report.transactions)}`], { type: 'text/csv;charset=utf-8' })
  downloadFile(blob, 'finset-2026-11-01-to-2026-11-13-transactions.csv')
  assert.equal(state.blobs[0], blob)
  assert.equal(state.link.download, 'finset-2026-11-01-to-2026-11-13-transactions.csv')
  assert.deepEqual(state.calls, ['create', 'append', 'click', 'remove'])
  assert.equal(state.timers[0].delay, 1000)
  state.timers[0].callback()
  assert.equal(state.calls.at(-1), 'revoke')
})

test('a blocked download propagates the failure while still removing its link and releasing resources', (t) => {
  const state = mockDownload(t, { clickError: true })
  assert.throws(() => downloadFile(new Blob(['test']), 'test.pdf'), /Download blocked/)
  assert.equal(state.calls.at(-1), 'remove')
  state.timers[0].callback()
  assert.equal(state.calls.at(-1), 'revoke')
})

test('font loading failures can be retried; successful PDF downloads cache local fonts and produce real PDF blobs', async (t) => {
  const state = mockDownload(t)
  let fail = true
  let requests = 0
  t.mock.method(globalThis, 'fetch', async (url) => {
    requests += 1
    assert.ok(url.pathname.endsWith('.ttf'))
    if (fail) return new Response('', { status: 503 })
    const font = url.pathname.includes('Regular') ? fonts[0] : fonts[1]
    return new Response(Buffer.from(font, 'base64'))
  })
  await assert.rejects(downloadFinancialStatement(reportFor()), /font could not be loaded/)
  assert.equal(state.blobs.length, 0)
  fail = false
  await downloadFinancialStatement(reportFor())
  assert.equal(requests, 4)
  assert.equal(state.link.download, 'FinSet-Financial-Statement-November-2026.pdf')
  assert.equal(state.blobs[0].type, 'application/pdf')
  assert.ok((await state.blobs[0].text()).startsWith('%PDF-'))
  await downloadFinancialStatement(reportFor())
  assert.equal(requests, 4)
  assert.equal(state.blobs.length, 2)
})
