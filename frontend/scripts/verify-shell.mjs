// Frontend-only browser checks using installed Chromium's DevTools protocol.
// Defaults: frontend on 5175, isolated browser on 9334. Optional args: debug URL, frontend URL.
import assert from 'node:assert/strict'
import { writeFileSync } from 'node:fs'
import { join } from 'node:path'

const base = process.argv[3] ?? 'http://127.0.0.1:5175'
const debug = process.argv[2] ?? 'http://127.0.0.1:9334'
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

async function key(keyName, shift = false) {
  const codes = { Escape: 27, Enter: 13, ArrowDown: 40, Tab: 9 }
  const modifiers = shift ? 8 : 0
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: keyName, code: keyName, windowsVirtualKeyCode: codes[keyName], modifiers })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: keyName, code: keyName, modifiers })
}

async function clickAt(x, y) {
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 })
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 })
}

async function openNavigation() {
  await evaluate(`document.querySelector('.mobile-navigation-toggle').focus(); document.querySelector('.mobile-navigation-toggle').click()`)
  await waitFor(`document.querySelector('.mobile-navigation-drawer').matches(':modal') && Math.abs(document.querySelector('.mobile-navigation-drawer').getBoundingClientRect().left) < 0.5`)
  assert.equal(await evaluate(`document.querySelector('.mobile-navigation-toggle').getAttribute('aria-expanded')`), 'true')
  assert.equal(await evaluate(`document.activeElement.getAttribute('aria-label')`), 'Close navigation')
  assert.equal(await evaluate(`document.body.style.overflow`), 'hidden')
  assert.equal(await evaluate(`document.documentElement.style.overflow`), 'hidden')
}

async function closedNavigation(focus = 'trigger') {
  await waitFor(`!document.querySelector('.mobile-navigation-drawer').open && getComputedStyle(document.querySelector('.mobile-navigation-drawer')).display === 'none'`)
  assert.equal(await evaluate(`document.querySelector('.mobile-navigation-toggle').getAttribute('aria-expanded')`), 'false')
  assert.equal(await evaluate(`document.body.style.overflow`), '')
  assert.equal(await evaluate(`document.documentElement.style.overflow`), '')
  assert.equal(await evaluate(focus === 'trigger' ? `document.activeElement === document.querySelector('.mobile-navigation-toggle')` : `document.activeElement.id === 'main-content'`), true)
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
  await evaluate(`new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))`)
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

  for (const width of [320, 360, 390, 430, 640, 641, 768, 1024, 1199, 1200, 1440]) {
    await viewport(width, 1000, width <= 640)
    assert.ok(await evaluate(`document.documentElement.scrollWidth <= innerWidth`), `No overflow at ${width}px`)
    const navSelector = width <= 640 ? '.mobile-navigation-toggle' : '.sidebar'
    assert.ok(await evaluate(`getComputedStyle(document.querySelector('${navSelector}')).display !== 'none'`), `Navigation visible at ${width}px`)
    assert.equal(await evaluate(`document.querySelector('.bottom-navigation')`), null)
    if (width > 640) assert.equal(await evaluate(`getComputedStyle(document.querySelector('.mobile-navigation-toggle')).display`), 'none')
  }
  console.log('PASS responsive overflow/navigation checks at eleven widths; no bottom navigation')

  await viewport(1440, 1000)
  await evaluate(`document.querySelector('.mobile-navigation-toggle').click()`)
  await evaluate(`new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))`)
  assert.equal(await evaluate(`document.querySelector('.mobile-navigation-drawer').open`), false)
  assert.equal(await evaluate(`document.querySelector('.mobile-navigation-toggle').getAttribute('aria-expanded')`), 'false')
  assert.equal(await evaluate(`document.body.style.overflow`), '')
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

  await evaluate(`document.querySelector('button[aria-label="Edit workspace preferences"]').click()`)
  await waitFor(`!!document.querySelector('dialog input')`)
  await evaluate(`(() => { const input=document.querySelector('dialog input'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,''); input.dispatchEvent(new Event('input',{bubbles:true})); })()`)
  await evaluate(`document.querySelector('dialog form').requestSubmit()`)
  await waitFor(`document.querySelector('dialog input').getAttribute('aria-invalid') === 'true'`)
  await evaluate(`(() => { const input=document.querySelector('dialog input'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'Stage one workspace'); input.dispatchEvent(new Event('input',{bubbles:true})); })()`)
  await clickText('Save label')
  await waitFor(`!!document.querySelector('.ui-toast') && document.querySelector('.sidebar-profile-copy strong').textContent === 'Stage one workspace'`)
  assert.equal(await evaluate(`document.querySelector('.sidebar-profile-copy strong').textContent`), 'Stage one workspace')
  await clickText('Cancel')
  await waitFor(`!document.querySelector('dialog[open]')`)
  await evaluate(`document.querySelector('button[aria-label="Dismiss notification"]').click()`)
  await waitFor(`!document.querySelector('.ui-toast')`)
  console.log('PASS modal lifecycle, input validation, local label, toast dismissal')

  const temp = join(process.env.LOCALAPPDATA, 'Temp', 'kilo')

  const routes = [
    ['dashboard', 'Dashboard'], ['transactions', 'Transactions'], ['budgets', 'Budgets'],
    ['financial-planning', 'Financial Planning'], ['reports', 'Reports'], ['settings', 'Settings'],
  ]
  for (const theme of ['Light', 'Dark']) {
    await chooseTheme(theme)
    for (const width of [320, 360, 390, 430]) {
      await viewport(width, 900, true)
      await openNavigation()
      assert.equal(await evaluate(`document.querySelector('.mobile-navigation-drawer').getAttribute('aria-modal')`), 'true')
      assert.equal(await evaluate(`document.querySelector('.mobile-navigation-toggle').getAttribute('aria-haspopup')`), 'dialog')
      assert.equal(await evaluate(`document.querySelector('.mobile-navigation-toggle').getAttribute('aria-controls')`), 'mobile-navigation-drawer')
      assert.ok(await evaluate(`document.querySelector('.mobile-navigation-toggle use').getAttribute('href').endsWith('#list')`))
      assert.ok(await evaluate(`Array.from(document.querySelectorAll('.mobile-primary-navigation a')).every(el => el.getBoundingClientRect().height >= 52 && parseFloat(getComputedStyle(el).fontSize) >= 15)`))
      assert.ok(await evaluate(`document.documentElement.scrollWidth <= innerWidth && document.querySelector('.mobile-navigation-drawer').getBoundingClientRect().right <= innerWidth`))
      assert.ok(await evaluate(`Array.from(document.querySelectorAll('.mobile-primary-navigation a > span')).every(el => el.getBoundingClientRect().height <= parseFloat(getComputedStyle(el).lineHeight) * 2)`), 'Readable complete navigation labels')
      const tree = await send('Accessibility.getFullAXTree')
      const dialogNode = tree.nodes.find((node) => node.role?.value === 'dialog' && node.name?.value === 'FinSet navigation')
      assert.ok(dialogNode?.properties.some((property) => property.name === 'modal' && property.value.value === true))
      for (const [, label] of routes) assert.ok(tree.nodes.some((node) => node.role?.value === 'link' && node.name?.value === label && !node.ignored), `Accessible ${label} link`)
      const screenshot = await send('Page.captureScreenshot', { format: 'png' })
      writeFileSync(join(temp, `finset-navigation-${theme.toLowerCase()}-${width}.png`), Buffer.from(screenshot.data, 'base64'))
      await key('Escape')
      await closedNavigation()

      for (const [id, label] of routes) {
        await openNavigation()
        await evaluate(`document.querySelector('.mobile-primary-navigation a[href="#/${id}"]').click()`)
        await waitFor(`location.hash === '#/${id}' && document.title === ${JSON.stringify(`FinSet | ${label}`)}`)
        await closedNavigation('main')
        await openNavigation()
        assert.equal(await evaluate(`document.querySelector('.mobile-primary-navigation [aria-current="page"]').getAttribute('href')`), `#/${id}`)
        assert.equal(await evaluate(`document.querySelectorAll('.mobile-primary-navigation [aria-current="page"]').length`), 1)
        await key('Escape')
        await closedNavigation()
      }
      console.log(`PASS ${theme} ${width}px: six routes, labels, active states, touch targets, ARIA and Escape/focus`)
    }
    await viewport(768, 1000)
    assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar')).width`), '82px')
    assert.equal(await evaluate(`getComputedStyle(document.querySelector('.brand-wordmark')).display`), 'none')
    assert.equal(await evaluate(`getComputedStyle(document.querySelector('.mobile-navigation-toggle')).display`), 'none')
    for (const [id] of routes) {
      await evaluate(`document.querySelector('.sidebar a[href="#/${id}"]').click()`)
      await waitFor(`location.hash === '#/${id}' && document.querySelector('.sidebar [aria-current="page"]').getAttribute('href') === '#/${id}'`)
    }
    await evaluate(`Promise.all(Array.from(document.querySelectorAll('.sidebar .nav-link')).flatMap(el => el.getAnimations().map(animation => animation.finished)))`)
    const screenshot = await send('Page.captureScreenshot', { format: 'png' })
    writeFileSync(join(temp, `finset-navigation-${theme.toLowerCase()}-768.png`), Buffer.from(screenshot.data, 'base64'))
    console.log(`PASS ${theme} 768px: compact sidebar and six destinations preserved`)
  }

  await viewport(390, 700, true)
  await evaluate(`location.hash = '/reports'`)
  await waitFor(`document.title === 'FinSet | Reports'`)
  await evaluate(`window.scrollTo({ top: 400, behavior: 'instant' })`)
  const scrollY = await evaluate(`window.scrollY`)
  assert.ok(scrollY > 0)
  await openNavigation()
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 380, y: 350, deltaX: 0, deltaY: 500 })
  assert.equal(await evaluate(`window.scrollY`), scrollY, 'Backdrop cannot scroll the page')
  for (let index = 0; index < 12; index += 1) {
    await key('Tab')
    assert.ok(await evaluate(`document.querySelector('.mobile-navigation-drawer').contains(document.activeElement)`))
  }
  await evaluate(`document.querySelector('.mobile-navigation-drawer .brand').focus()`)
  await key('Tab', true)
  assert.equal(await evaluate(`document.activeElement.getAttribute('href')`), '#/settings')
  await key('Tab')
  assert.equal(await evaluate(`document.activeElement.getAttribute('aria-label')`), 'FinSet dashboard')
  await clickAt(380, 350)
  await closedNavigation()
  assert.equal(await evaluate(`window.scrollY`), scrollY, 'Backdrop dismissal preserves scroll position')
  await openNavigation()
  await evaluate(`document.querySelector('button[aria-label="Close navigation"]').click()`)
  await closedNavigation()
  await openNavigation()
  await evaluate(`document.querySelector('.mobile-navigation-drawer .brand').click()`)
  await waitFor(`location.hash === '#/dashboard'`)
  await closedNavigation('main')
  console.log('PASS backdrop, close control, branding link, scroll lock and keyboard focus containment')

  await openNavigation()
  await evaluate(`location.hash = '/reports'`)
  await waitFor(`document.title === 'FinSet | Reports'`)
  await closedNavigation('main')
  await openNavigation()
  await viewport(641, 900)
  await closedNavigation('main')
  await viewport(390, 900, true)
  assert.equal(await evaluate(`document.querySelector('.mobile-navigation-drawer').open`), false)
  console.log('PASS external route changes and resize close the drawer without reopening or scroll locks')

  await viewport(320, 400, true)
  await openNavigation()
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 200, y: 300, deltaX: 0, deltaY: 500 })
  await waitFor(`document.querySelector('.mobile-navigation-drawer').scrollTop > 0`)
  await key('Escape')
  await closedNavigation()
  await openNavigation()
  assert.equal(await evaluate(`document.querySelector('.mobile-navigation-drawer').scrollTop`), 0)
  await key('Escape')
  await closedNavigation()
  console.log('PASS short-viewport internal scrolling and visible initial focus on reopen')

  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
  await openNavigation()
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.mobile-navigation-drawer')).transitionDuration`), '0s')
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.mobile-navigation-drawer'), '::backdrop').transitionDuration`), '0s')
  await key('Escape')
  await closedNavigation()
  console.log('PASS reduced-motion preference disables drawer and backdrop transitions')

  assert.deepEqual(errors, [], `No application console/runtime errors: ${errors.join('; ')}`)
  assert.ok(!requests.some((url) => url.includes('/api/')), 'No API requests')
  console.log('PASS screenshots captured; no application errors or API calls')
  console.log('BROWSER VALIDATION PASS')
} finally {
  if (socket.readyState !== WebSocket.CLOSED) {
    await new Promise((resolve) => {
      socket.addEventListener('close', resolve, { once: true })
      if (socket.readyState === WebSocket.OPEN) socket.close()
    })
  }
  await fetch(`${debug}/json/close/${target.id}`)
}
