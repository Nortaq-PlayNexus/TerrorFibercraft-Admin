// Visual/functional verification of the NexusX frontend.
// Drives the installed Chrome, screenshots every panel, and checks for
// console errors. Run: node scripts/verify.mjs
import puppeteer from 'puppeteer-core'
import { mkdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE = 'http://localhost:5199'
const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'screenshots')
mkdirSync(OUT, { recursive: true })

// panel id -> nav button title (label shown in the sidebar)
const PANELS = {
  dashboard: 'Dashboard',
  macro: 'Macro Studio',
  agents: 'Agents',
  schedule: 'Scheduler',
  breeding: 'Breeding',
  vision: 'Vision',
  scripts: 'NexusScript',
  devices: 'Devices',
  market: 'Marketplace',
  kb: 'Knowledge DB',
  telemetry: 'Telemetry',
  settings: 'Settings',
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu'],
  defaultViewport: { width: 1400, height: 900 },
})

const page = await browser.newPage()
const consoleErrors = []
page.on('console', (m) => {
  if (m.type() === 'error') consoleErrors.push(m.text())
})
page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`))

await page.goto(BASE, { waitUntil: 'networkidle2', timeout: 30000 })
await new Promise((r) => setTimeout(r, 1500))

let failures = 0
const results = []

for (const [panel, label] of Object.entries(PANELS)) {
  const clicked = await page.evaluate((lbl) => {
    const btn = [...document.querySelectorAll('.nav-item')].find((b) => b.title === lbl)
    if (btn) { btn.click(); return true }
    return false
  }, label)
  await new Promise((r) => setTimeout(r, 900))

  const shot = join(OUT, `${panel}.png`)
  await page.screenshot({ path: shot })

  // verify the panel actually rendered content (non-empty main area)
  const contentLen = await page.evaluate(() => {
    const main = document.querySelector('main.content')
    return main ? main.textContent.trim().length : 0
  })
  const ok = contentLen > 20 && clicked
  if (!ok) failures += 1
  results.push(`${panel.padEnd(10)} nav=${clicked} content=${String(contentLen).padStart(5)} ${ok ? 'OK' : 'EMPTY'}`)
}

// kill-switch interaction test
await page.evaluate(() => document.querySelector('.kill-switch').click())
await new Promise((r) => setTimeout(r, 300))
const modeText = await page.evaluate(() => document.querySelector('.mode-pill').textContent)
results.push(`kill-switch mode=${modeText.trim()} ${modeText.includes('EMERGENCY') ? 'OK' : 'FAIL'}${modeText.includes('EMERGENCY') ? '' : (failures += 1, '')}`)

console.log(results.join('\n'))
console.log(`\nconsole errors: ${consoleErrors.length}`)
consoleErrors.slice(0, 10).forEach((e) => console.log('  ERR:', e))

await browser.close()
process.exit(failures === 0 && consoleErrors.length === 0 ? 0 : 1)
