/**
 * Capture the report's UI screenshots from the locally running VibeShift app.
 *
 * Requires the API (127.0.0.1:8000) and the Vite dev server (127.0.0.1:5180) to be
 * running, plus playwright-core + a Chrome install:
 *
 *     npm i playwright-core
 *     node report/capture_screenshots.js <run-id>
 *
 * Images land in report/assets/.
 */
const path = require('path')
const fs = require('fs')

const { chromium } = require(path.resolve(
  process.env.PW_ROOT || 'C:/Users/PC-15/shots',
  'node_modules/playwright-core',
))

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE = process.env.APP_BASE || 'http://127.0.0.1:5180'
const RUN = process.argv[2]
const OUT = path.resolve(__dirname, 'assets')

if (!RUN) {
  console.error('usage: node capture_screenshots.js <run-id>')
  process.exit(1)
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function main() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true })
  const page = await browser.newPage({
    viewport: { width: 1440, height: 980 },
    deviceScaleFactor: 2,
  })
  fs.mkdirSync(OUT, { recursive: true })
  const errors = []
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('response', (r) => {
    if (r.status() >= 400) errors.push(`HTTP ${r.status()} ${r.url()}`)
  })

  /** Screenshot the top `maxH` px of an element, centred in the viewport. */
  async function shotEl(name, locator, maxH = 1120) {
    const el = typeof locator === 'string' ? page.locator(locator).first() : locator
    await el.scrollIntoViewIfNeeded()
    await sleep(450)
    const box = await el.boundingBox()
    if (!box) throw new Error(`no box for ${name}`)
    const height = Math.min(box.height, maxH)
    await page.screenshot({
      path: path.join(OUT, name),
      clip: {
        x: Math.max(0, box.x),
        y: Math.max(0, box.y),
        width: Math.min(box.width, 1440),
        height,
      },
    })
    console.log('wrote', name, `${Math.round(box.width)}x${Math.round(height)}`)
  }

  /** Screenshot a region starting at an element's top-left, `height` px tall. */
  async function shotFromHere(name, locator, height = 900) {
    const el = typeof locator === 'string' ? page.locator(locator).first() : locator
    await el.scrollIntoViewIfNeeded()
    await sleep(450)
    const box = await el.boundingBox()
    if (!box) throw new Error(`no box for ${name}`)
    await page.screenshot({
      path: path.join(OUT, name),
      clip: { x: Math.max(0, box.x), y: Math.max(0, box.y), width: Math.min(box.width, 1440), height },
    })
    console.log('wrote', name, `${Math.round(box.width)}x${height}`)
  }

  const card = (text) => page.locator('section.card', { hasText: text }).first()

  // ---------------------------------------------------------------- dashboard
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.getByText('Run configuration').first().waitFor({ timeout: 30000 })
  await sleep(1200)
  await shotEl('shot_dashboard.png', 'main', 1250)
  // dataset + engine + run configuration live side by side in one grid row
  await shotEl('shot_status_grid.png', page.locator('div.grid').first(), 620)
  await shotEl('shot_run_config.png', card('Run configuration'), 900)
  await shotEl('shot_run_history.png', card('Run history'), 760)

  // ------------------------------------------------------------------ results
  await page.goto(`${BASE}/runs/${RUN}`, { waitUntil: 'networkidle' })
  await page.getByText('Vibe-shift results').first().waitFor({ timeout: 30000 })
  await sleep(1500)
  await shotEl('shot_results_overview.png', 'main', 1000)
  await shotEl('shot_vibe_heatmap.png', card('Historical vibe shift'), 1000)
  await shotEl(
    'shot_cluster_row.png',
    page.locator('div.grid', { hasText: 'Cluster profiles' }).first(),
    560,
  )
  await shotEl(
    'shot_projection_row.png',
    page.locator('div.grid', { hasText: 'PCA map' }).first(),
    620,
  )
  await shotEl('shot_benchmark.png', card('Execution benchmark'), 520)

  // BDA suite — core tabs
  const suite = page
    .locator('section.card', { hasText: 'Big Data Analytics suite' })
    .first()
  await shotEl('shot_bda_mapreduce.png', suite, 1150)
  await page.getByRole('button', { name: /MapReduce/ }).first().click()
  await sleep(500)
  await shotEl('shot_bda_mapreduce.png', suite, 1150)

  await page.getByRole('button', { name: /MongoDB/ }).first().click()
  await sleep(600)
  await shotEl('shot_bda_mongodb.png', suite, 1150)

  await page.getByRole('button', { name: /visualization|Statistics/i }).first().click()
  await sleep(600)
  await shotEl('shot_bda_eda.png', suite, 1150)

  await page.getByRole('button', { name: /additional analyses/i }).first().click()
  await sleep(500)
  await shotEl('shot_bda_advanced.png', suite, 700)

  // ----------------------------------------------------------------- concepts
  await page.goto(`${BASE}/concepts?run=${RUN}`, { waitUntil: 'networkidle' })
  await page.getByText('Core portion').first().waitFor({ timeout: 30000 })
  await sleep(1200)
  await shotEl('shot_concepts.png', 'main', 1250)
  await shotFromHere(
    'shot_concepts_core.png',
    page.getByRole('heading', { name: /Core portion/ }).first(),
    950,
  )

  // ------------------------------------------------------------ track explorer
  await page.goto(`${BASE}/runs/${RUN}/tracks`, { waitUntil: 'networkidle' })
  await page.getByPlaceholder(/search/i).first().waitFor({ timeout: 30000 })
  await page.getByPlaceholder(/search/i).first().fill('love')
  await sleep(1500)
  await shotEl('shot_track_explorer.png', 'main', 1150)

  await browser.close()
  if (errors.length) {
    console.log('\nconsole errors:')
    for (const e of errors.slice(0, 10)) console.log(' -', e)
  } else {
    console.log('\nno console errors')
  }
}

main().catch((e) => {
  console.error('FAILED:', e)
  process.exit(1)
})
