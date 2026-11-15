// Frontend-only browser checks using installed Chromium's DevTools protocol.
// Start the frontend on 5175 and an isolated headless browser on 9334 first.
import assert from 'node:assert/strict'
import { writeFileSync } from 'node:fs'
import { join } from 'node:path'

const base = 'http://127.0.0.1:5175'
const debug = 'http://127.0.0.1:9334'
const target = await (await fetch(`${debug}/json/new?${encodeURIComponent(base)}`, { method: 'PUT' })).json()
const socket = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }) })
let sequence = 0
const pending = new Map()
const errors = []
const requests = []
socket.addEventListener('message', ({ data }) => {
  const message = JSON.parse(data)
  if (message.id) {
    const call = pending.get(message.id)
    if (!call) return
    pending.delete(message.id)
    clearTimeout(call.timeout)
    if (message.error) call.reject(new Error(message.error.message))
    else call.resolve(message.result)
  } else if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text)
  else if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') errors.push(message.params.args.map((item) => item.value ?? item.description).join(' '))
  else if (message.method === 'Network.requestWillBeSent') requests.push(message.params.request.url)
})

function send(method, params = {}) {
  const id = ++sequence
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)) }, 10000)
    pending.set(id, { resolve, reject, timeout })
    socket.send(JSON.stringify({ id, method, params }))
  })
}

async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text)
  return result.result.value
}

async function waitFor(expression) {
  const deadline = Date.now() + 7000
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return
    await new Promise((resolve) => setTimeout(resolve, 40))
  }
  throw new Error(`UI condition not reached: ${expression}`)
}

async function reloadPage() {
  const loaded = new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { socket.removeEventListener('message', listener); reject(new Error('Page load timeout')) }, 10000)
    const listener = ({ data }) => {
      if (JSON.parse(data).method === 'Page.loadEventFired') {
        clearTimeout(timeout)
        socket.removeEventListener('message', listener)
        resolve()
      }
    }
    socket.addEventListener('message', listener)
  })
  await send('Page.reload')
  await loaded
  await waitFor(`!!document.querySelector('button[aria-label="Change appearance"]') && !!document.querySelector('h1')`)
}

async function key(keyName) {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: keyName, code: keyName, windowsVirtualKeyCode: keyName === 'Escape' ? 27 : keyName === 'Enter' ? 13 : 40 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: keyName, code: keyName })
}

async function clickText(text, selector = 'button') {
  const done = await evaluate(`(() => { const item = Array.from(document.querySelectorAll(${JSON.stringify(selector)})).find(el => (el.querySelector('[id$="-label"]')?.textContent ?? el.textContent).trim() === ${JSON.stringify(text)} && el.getBoundingClientRect().width); if (!item) return false; item.focus(); item.click(); return true })()`)
  assert.ok(done, `Control exists: ${text}`)
}

async function chooseTheme(mode) {
  await evaluate(`document.querySelector('button[aria-label="Change appearance"]').click()`)
  await waitFor(`!!document.querySelector('[role="menu"]')`)
  await clickText(mode, '[role="menuitemradio"]')
  await waitFor(`document.documentElement.dataset.appearance === ${JSON.stringify(mode.toLowerCase())}`)
}

async function viewport(width, height, mobile = false) {
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile })
}

try {
  await send('Runtime.enable')
  await send('Page.enable')
  await send('Network.enable')
  await waitFor(`!!document.querySelector('h1')`)
  await viewport(1440, 1000)
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] })
  await evaluate(`localStorage.removeItem('finset.appearance'); location.hash = '/dashboard'`)
  await reloadPage()
  await waitFor(`document.documentElement.dataset.theme === 'light' && !!document.querySelector('h1') && document.title === 'FinSet | Dashboard'`)
  assert.equal(await evaluate(`document.title`), 'FinSet | Dashboard')
  console.log('PASS light is default even on a dark system')

  for (const width of [320, 390, 640, 641, 768, 1024, 1199, 1200, 1440]) {
    await viewport(width, 1000, width <= 640)
    assert.ok(await evaluate(`document.documentElement.scrollWidth <= innerWidth`), `No overflow at ${width}px`)
    const navSelector = width <= 640 ? '.bottom-navigation' : '.sidebar'
    assert.ok(await evaluate(`getComputedStyle(document.querySelector('${navSelector}')).display !== 'none'`), `Navigation visible at ${width}px`)
  }
  console.log('PASS responsive overflow/navigation checks at nine widths')

  await viewport(1440, 1000)
  for (const id of ['transactions', 'budgets', 'financial-planning', 'reports', 'settings', 'dashboard']) {
    await evaluate(`document.querySelector('.sidebar a[href="#/${id}"]').click()`)
    await waitFor(`location.hash === '#/${id}' && document.querySelector('.sidebar [aria-current="page"]').getAttribute('href') === '#/${id}'`)
  }
  await evaluate(`history.back()`)
  await waitFor(`location.hash === '#/settings' && document.title === 'FinSet | Settings'`)
  await evaluate(`history.forward()`)
  await waitFor(`location.hash === '#/dashboard'`)
  await evaluate(`document.querySelector('.skip-link').click()`)
  assert.equal(await evaluate(`location.hash`), '#/dashboard')
  assert.equal(await evaluate(`document.activeElement.id`), 'main-content')
  console.log('PASS six routes, active states, browser back/forward')

  await chooseTheme('Dark')
  assert.equal(await evaluate(`document.documentElement.dataset.theme`), 'dark')
  await reloadPage()
  await waitFor(`document.documentElement.dataset.theme === 'dark' && !!document.querySelector('h1') && document.title === 'FinSet | Dashboard'`)
  await chooseTheme('System')
  await waitFor(`document.documentElement.dataset.theme === 'dark'`)
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] })
  await waitFor(`document.documentElement.dataset.theme === 'light'`)
  console.log('PASS dark persistence and live system preference updates')

  await evaluate(`document.querySelector('button[aria-label="Change appearance"]').focus()`)
  await key('ArrowDown')
  await waitFor(`!!document.querySelector('[role="menu"]') && document.activeElement.getAttribute('role') === 'menuitemradio'`)
  await key('Escape')
  await waitFor(`!document.querySelector('[role="menu"]') && document.activeElement.getAttribute('aria-label') === 'Change appearance'`)
  await evaluate(`document.querySelector('button[aria-label="Change appearance"]').click()`)
  await evaluate(`document.querySelector('h1').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))`)
  await waitFor(`!document.querySelector('[role="menu"]')`)
  console.log('PASS dropdown keyboard, Escape/focus return, outside dismissal')

  await clickText('Shell guide')
  await waitFor(`!!document.querySelector('dialog[open]')`)
  assert.equal(await evaluate(`document.body.style.overflow`), 'hidden')
  await key('Escape')
  await waitFor(`!document.querySelector('dialog[open]')`)
  assert.equal(await evaluate(`document.activeElement.textContent.trim()`), 'Shell guide')
  await evaluate(`document.querySelector('button[aria-label="Edit workspace preferences"]').click()`)
  await waitFor(`!!document.querySelector('dialog input')`)
  await evaluate(`(() => { const input=document.querySelector('dialog input'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,''); input.dispatchEvent(new Event('input',{bubbles:true})); })()`)
  await evaluate(`document.querySelector('dialog form').requestSubmit()`)
  await waitFor(`document.querySelector('dialog input').getAttribute('aria-invalid') === 'true'`)
  await evaluate(`(() => { const input=document.querySelector('dialog input'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'Stage one workspace'); input.dispatchEvent(new Event('input',{bubbles:true})); })()`)
  await clickText('Save label')
  await waitFor(`!document.querySelector('dialog[open]') && !!document.querySelector('[role="status"]')`)
  assert.equal(await evaluate(`document.querySelector('.sidebar-profile-copy strong').textContent`), 'Stage one workspace')
  await evaluate(`document.querySelector('button[aria-label="Dismiss notification"]').click()`)
  await waitFor(`!document.querySelector('[role="status"]')`)
  console.log('PASS modal lifecycle, input validation, local label, toast dismissal')

  await clickText('Preview loading state')
  await waitFor(`!!document.querySelector('.loading-preview')`)
  assert.ok(await evaluate(`document.querySelector('.loading-preview-button').disabled`))
  await waitFor(`!document.querySelector('.loading-preview')`)
  console.log('PASS loading skeleton preview and disabled state')

  const temp = join(process.env.LOCALAPPDATA, 'Temp', 'kilo')
  for (const [name, width, height, theme] of [['desktop', 1440, 1000, 'Light'], ['tablet', 768, 1024, 'Dark'], ['mobile', 390, 844, 'Light']]) {
    await viewport(width, height, width < 640)
    await chooseTheme(theme)
    await evaluate(`new Promise(resolve => setTimeout(resolve, 200))`)
    if (name === 'mobile') {
      await evaluate(`document.querySelector('.bottom-navigation a[href="#/budgets"]').click()`)
      await waitFor(`location.hash === '#/budgets'`)
      assert.ok(await evaluate(`Array.from(document.querySelectorAll('.bottom-navigation a')).every(el => el.getBoundingClientRect().height >= 44)`))
    }
    const screenshot = await send('Page.captureScreenshot', { format: 'png' })
    writeFileSync(join(temp, `finset-stage1-${name}.png`), Buffer.from(screenshot.data, 'base64'))
  }
  assert.deepEqual(errors, [], `No application console/runtime errors: ${errors.join('; ')}`)
  assert.ok(!requests.some((url) => url.includes('/api/')), 'No API requests')
  console.log('PASS mobile navigation/touch targets; screenshots captured; no application errors or API calls')
  console.log('BROWSER VALIDATION PASS')
} finally {
  socket.close()
}
