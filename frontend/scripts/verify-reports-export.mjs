// Frontend-only checks against an isolated Chromium DevTools browser and frontend preview.
// node scripts/verify-reports-export.mjs <debug URL> <frontend URL> [--close-browser]
import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { createDashboardWorkspace } from '../src/demo/dashboard.js'
import { money, transactionCsv } from '../src/finance/dashboard.js'
import { reportRangeOptions, resolveReportRange, selectReports } from '../src/finance/reports.js'

const debug = process.argv[2] ?? 'http://127.0.0.1:9336'
const base = process.argv[3] ?? 'http://127.0.0.1:5176'
const output = mkdtempSync(join('C:\\Users\\USER\\AppData\\Local\\Temp\\kilo', 'finset-reports-browser-'))
const workspace = createDashboardWorkspace()
const expected = (preset = 'this-month', custom = {}) => selectReports(workspace, resolveReportRange(workspace.asOf, preset, custom))
const target = await (await fetch(`${debug}/json/new?about:blank`, { method: 'PUT', signal: AbortSignal.timeout(15000) })).json()
const socket = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true })
  socket.addEventListener('error', reject, { once: true })
})
let sequence = 0
const pending = new Map()
const errors = []
const requests = []
const downloads = []
socket.addEventListener('message', ({ data }) => {
  const message = JSON.parse(data)
  if (message.id) {
    const call = pending.get(message.id)
    if (!call) return
    pending.delete(message.id)
    clearTimeout(call.timer)
    if (message.error) call.reject(new Error(message.error.message))
    else call.resolve(message.result)
  } else if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text)
  else if (message.method === 'Network.requestWillBeSent') requests.push(message.params.request.url)
  else if (message.method?.startsWith('Browser.download')) downloads.push({ method: message.method, ...message.params })
})

function send(method, params = {}) {
  const id = ++sequence
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)) }, ['Runtime.evaluate', 'Page.navigate'].includes(method) ? 60000 : 15000)
    pending.set(id, { resolve, reject, timer })
    socket.send(JSON.stringify({ id, method, params }))
  })
}

async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true, userGesture: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text)
  return result.result.value
}

async function waitFor(expression) {
  const deadline = Date.now() + 60000
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return
    await new Promise((resolve) => setTimeout(resolve, 50))
  }
  throw new Error(`UI condition not reached: ${expression}`)
}

async function click(label, selector = 'button') {
  const point = await evaluate(`(() => {
    const item = Array.from(document.querySelectorAll(${JSON.stringify(selector)})).find(el =>
      (el.querySelector('[id$="-label"]')?.textContent ?? el.textContent).trim() === ${JSON.stringify(label)} && el.getBoundingClientRect().width);
    if (!item || item.disabled) return false;
    item.focus(); item.scrollIntoView({ block: 'center' });
    const rect = item.getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  })()`)
  assert.ok(point, `Enabled control: ${label}`)
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 1 })
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 1 })
}

async function choose(preset) {
  await evaluate(`document.querySelector('.report-range-picker button').click()`)
  await waitFor(`!!document.querySelector('[role="menu"]')`)
  await click(reportRangeOptions.find((row) => row.id === preset).label, '[role="menuitemradio"]')
}

async function dates(from, to) {
  for (const [index, value] of [from, to].entries()) {
    await evaluate(`(() => {
      const input = document.querySelectorAll('.report-range-form input[type="date"]')[${index}];
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      setter.call(input, ${JSON.stringify(value)});
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    })()`)
  }
}

async function capture() {
  await evaluate(`(() => {
    window.exportRecords = [];
    window.exportBlobs = new Map();
    window.originalExportFetch = window.fetch;
    window.originalExportUrl = URL.createObjectURL;
    window.originalExportClick = HTMLAnchorElement.prototype.click;
    URL.createObjectURL = (blob) => {
      const url = window.originalExportUrl.call(URL, blob);
      window.exportBlobs.set(url, blob);
      return url;
    };
    HTMLAnchorElement.prototype.click = function () {
      if (this.download) window.exportRecords.push({ filename: this.download, blob: window.exportBlobs.get(this.href) });
      return window.originalExportClick.call(this);
    };
  })()`)
}

async function record(index) {
  await waitFor(`window.exportRecords.length > ${index}`)
  return evaluate(`(async () => {
    const record = window.exportRecords[${index}];
    const bytes = new Uint8Array(await record.blob.arrayBuffer());
    return { filename: record.filename, type: record.blob.type, size: bytes.length, prefix: Array.from(bytes.slice(0, 4)), text: record.blob.type.startsWith('text/csv') ? await record.blob.text() : null };
  })()`)
}

async function summary(report) {
  await waitFor(`document.querySelector('.report-context strong')?.textContent === ${JSON.stringify(report.range.label)}`)
  const values = await evaluate(`Array.from(document.querySelectorAll('.report-summary-value'), el => el.textContent)`)
  assert.deepEqual(values, [money(report.summary.income, true), money(report.summary.expenses, true), `${report.summary.net > 0 ? '+' : ''}${money(report.summary.net, true)}`])
}

async function downloaded(filename) {
  const deadline = Date.now() + 15000
  const path = join(output, filename)
  while (Date.now() < deadline) {
    try { return readFileSync(path) } catch (error) { if (error.code !== 'ENOENT') throw error }
    await new Promise((resolve) => setTimeout(resolve, 50))
  }
  throw new Error(`Download did not complete: ${filename}; browser events: ${JSON.stringify(downloads)}`)
}

async function reload() {
  await send('Page.reload', { ignoreCache: true })
  await waitFor(`!!document.querySelector('.report-context') && !window.exportRecords`)
  await capture()
}

try {
  await send('Runtime.enable')
  await send('Page.enable')
  await send('Network.enable')
  await send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: output, eventsEnabled: true })
  assert.equal(await evaluate('1 + 1'), 2)
  console.log('PASS: Isolated browser runtime is responsive')
  await send('Page.bringToFront')
  await send('Page.navigate', { url: `${base}/#/reports` })
  await waitFor(`document.querySelector('h1')?.textContent === 'Reports' && !!document.querySelector('.report-context')`)
  await summary(expected())
  await capture()

  for (const width of [1440, 800, 390, 320]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: width <= 390 })
    await waitFor(`window.innerWidth === ${width} && document.documentElement.scrollWidth <= window.innerWidth + 1`)
    assert.ok(await evaluate(`document.documentElement.scrollWidth <= window.innerWidth + 1`), `No horizontal overflow at ${width}px`)
    assert.equal(await evaluate(`Array.from(document.querySelectorAll('.report-header-controls button')).filter(el => el.getBoundingClientRect().width > 0).length`), 3)
    const screenshot = await send('Page.captureScreenshot', { format: 'png' })
    writeFileSync(join(output, `reports-${width}.png`), Buffer.from(screenshot.data, 'base64'))
  }
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  console.log('PASS: Reports summary and desktop/tablet/mobile viewport layouts')

  await click('Export CSV')
  const csv = await record(0)
  assert.equal(csv.filename, 'finset-2026-11-01-to-2026-11-13-transactions.csv')
  assert.deepEqual(csv.prefix.slice(0, 3), [239, 187, 191])
  assert.equal(csv.text, transactionCsv(expected().transactions))
  const csvFile = await downloaded(csv.filename)
  assert.deepEqual(Array.from(csvFile.subarray(0, 3)), [239, 187, 191])
  assert.equal(csvFile.subarray(3).toString('utf8'), transactionCsv(expected().transactions))
  console.log('PASS: Real CSV download, BOM, columns, filename and all eligible records')

  await evaluate(`(() => {
    window.fontWaiters = [];
    window.fetch = (url, ...args) => String(url).includes('NunitoSans-')
      ? new Promise((resolve, reject) => window.fontWaiters.push(() => window.originalExportFetch(url, ...args).then(resolve, reject)))
      : window.originalExportFetch(url, ...args);
  })()`)
  await click('Export PDF')
  await waitFor(`window.fontWaiters.length === 2`)
  assert.ok(await evaluate(`Array.from(document.querySelectorAll('.report-header-controls button')).some(el => el.disabled && el.getAttribute('aria-busy') === 'true' && el.textContent.includes('Preparing PDF'))`))
  await evaluate(`Array.from(document.querySelectorAll('.report-header-controls button')).find(el => el.textContent.includes('Preparing PDF')).click()`)
  await choose('last-month')
  await summary(expected('last-month'))
  await evaluate(`window.fetch = window.originalExportFetch; window.fontWaiters.forEach(release => release())`)
  const pdf = await record(1)
  assert.equal(pdf.filename, 'FinSet-Financial-Statement-November-2026.pdf')
  assert.equal(pdf.type, 'application/pdf')
  assert.deepEqual(pdf.prefix, [37, 80, 68, 70])
  assert.ok(pdf.size > 5000)
  assert.ok((await downloaded(pdf.filename)).subarray(0, 8).toString().startsWith('%PDF-'))
  await waitFor(`document.querySelector('.ui-toast-title')?.textContent === 'PDF export ready' && !!Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim() === 'Export PDF' && !el.disabled)`)
  assert.ok(await evaluate(`document.querySelector('.ui-toast-message').textContent.includes(${JSON.stringify(expected().range.label)})`))
  assert.equal(await evaluate(`window.exportRecords.length`), 2)
  console.log('PASS: Real PDF download, disabled loading action, duplicate-click protection and period snapshot')

  await choose('custom')
  await dates('2026-11-12', '2026-11-13')
  await summary(expected('last-month'))
  await click('Export CSV')
  assert.equal((await record(2)).text, transactionCsv(expected('last-month').transactions))
  await click('Apply range')
  const custom = expected('custom', { from: '2026-11-12', to: '2026-11-13' })
  await summary(custom)
  await click('Export CSV')
  assert.equal((await record(3)).text, transactionCsv(custom.transactions))
  await click('Export PDF')
  assert.equal((await record(4)).filename, 'FinSet-Financial-Statement-2026-11-12-to-2026-11-13.pdf')
  await dates('2026-11-13', '2026-11-12')
  await click('Apply range')
  await waitFor(`!!document.querySelector('.report-range-error')`)
  await summary(custom)
  console.log('PASS: Draft dates do not change exports; applied custom ranges and invalid-range preservation')

  await dates('2026-08-01', '2026-08-31')
  await click('Apply range')
  await summary(expected('custom', { from: '2026-08-01', to: '2026-08-31' }))
  assert.ok(await evaluate(`Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim() === 'Export CSV').disabled`))
  await click('Export PDF')
  const empty = await record(5)
  assert.equal(empty.filename, 'FinSet-Financial-Statement-2026-08-01-to-2026-08-31.pdf')
  assert.ok((await downloaded(empty.filename)).subarray(0, 8).toString().startsWith('%PDF-'))
  console.log('PASS: Empty period has zero summary, disabled CSV and a real PDF statement')

  await reload()
  await evaluate(`window.fetch = (url, ...args) => String(url).includes('NunitoSans-') ? Promise.resolve(new Response('', { status: 503 })) : window.originalExportFetch(url, ...args)`)
  await click('Export PDF')
  await waitFor(`document.querySelector('.ui-toast-title')?.textContent === 'PDF export failed' && !!Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim() === 'Export PDF' && !el.disabled)`)
  assert.equal(await evaluate(`window.exportRecords.length`), 0)
  await evaluate(`window.fetch = window.originalExportFetch`)
  await click('Export PDF')
  assert.equal((await record(0)).type, 'application/pdf')
  await waitFor(`document.querySelector('.ui-toast-title')?.textContent === 'PDF export ready'`)
  console.log('PASS: Font failure shows feedback, clears loading and retries successfully')

  await evaluate(`window.workingExportUrl = URL.createObjectURL; URL.createObjectURL = () => { throw new Error('Simulated blocked download') }`)
  await click('Export PDF')
  await waitFor(`document.querySelector('.ui-toast-title')?.textContent === 'PDF export failed' && !!Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim() === 'Export PDF' && !el.disabled)`)
  assert.equal(await evaluate(`window.exportRecords.length`), 1)
  await evaluate(`URL.createObjectURL = window.workingExportUrl`)
  assert.deepEqual(errors, [])
  assert.ok(!requests.some((url) => new URL(url).pathname.startsWith('/api/')))
  console.log('PASS: Blocked download feedback and recovery; no uncaught errors or backend requests')
  console.log(`Artifacts: ${output}`)
} finally {
  if (process.argv.includes('--close-browser')) await send('Browser.close').catch(() => {})
  else await fetch(`${debug}/json/close/${target.id}`).catch(() => {})
  for (const call of pending.values()) { clearTimeout(call.timer); call.reject(new Error('Browser test closed')) }
  pending.clear()
  socket.close()
}
