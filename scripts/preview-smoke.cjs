// Exercise the actual noindex root build, with analytics stubbed to avoid real visits.
const { createRequire } = require('node:module')
const path = require('node:path')
const fs = require('node:fs')
const requireSite = createRequire(path.resolve(process.argv[2], 'package.json'))
const { chromium } = requireSite('@playwright/test')
const site = path.resolve(process.argv[2])
const base = process.env.PREVIEW_URL || 'http://127.0.0.1:4175/'
const languages = ['ru', 'en', 'es', 'zh-Hans', 'ar']
const charts = { 'heteroplasmy-landscape': 1, 'embryo-concordance': 3, 'embryo-to-offspring': 2, 'pgt-mt-pgt-a-model': 3 }
function routes(dir, prefix) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? routes(path.join(dir, e.name), `${prefix}${e.name}/`) : e.name === 'index.html' ? [prefix] : [])
}
;(async () => {
  const browser = await chromium.launch({ headless: true })
  try {
    const context = await browser.newContext({ acceptDownloads: true })
    await context.route('https://gc.zgo.at/**', route => route.fulfill({ contentType: 'text/javascript', body: 'window.goatcounter={count:()=>{}}' }))
    await context.route('https://*.goatcounter.com/**', route => route.fulfill({ contentType: 'application/json', body: '{"count":"0"}' }))
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', e => errors.push(e.message))
    page.on('response', r => { if (r.url().startsWith(base) && r.status() >= 400) errors.push(`${r.status()} ${r.url()}`) })
    for (const lang of languages) {
      const pages = routes(path.join(site, 'dist', lang), `${lang}/`)
      if (pages.length !== 22) throw Error(`${lang}: expected 22 pages`)
      for (const route of pages) {
        const response = await page.goto(new URL(route, base).href)
        if (!response || response.status() !== 200) throw Error(`Missing ${route}`)
        if ((await page.locator('html').getAttribute('lang')) !== lang) throw Error(`Wrong language ${route}`)
        if (!(await page.locator('h1').first().isVisible())) throw Error(`Missing h1 ${route}`)
        const robots = await page.locator('meta[name="robots"]').allTextContents().catch(() => [])
        const content = await page.locator('meta[name="robots"]').first().getAttribute('content')
        if (!content || !content.includes('noindex')) throw Error(`Indexable preview ${route} ${robots}`)
      }
      await page.goto(new URL(`${lang}/ilya-mazunin/`, base).href)
      const image = page.locator('img[src*="ilya-mazunin.jpg"]').first()
      await image.scrollIntoViewIfNeeded()
      if (!await image.evaluate(e => e.complete && e.naturalWidth > 0)) throw Error(`Image failed ${lang}`)
      await page.goto(new URL(`${lang}/contribute/`, base).href)
      const [download] = await Promise.all([page.waitForEvent('download'), page.locator('a[download]').first().click()])
      if (await download.failure()) throw Error(`Download failed ${lang}`)
      for (const [route, count] of Object.entries(charts)) {
        await page.goto(new URL(`${lang}/science/${route}/`, base).href)
        await page.waitForFunction(({ count }) => document.querySelectorAll('.chart-frame .js-plotly-plot').length === count, { count }, { timeout: 30000 })
      }
      await page.goto(new URL(`${lang}/science/embryo-concordance?x=1#content`, base).href)
      if (page.url() !== new URL(`${lang}/science/embryo-concordance/?x=1#content`, base).href) throw Error(`Slash/query/hash ${lang}`)
    }
    if (errors.length) throw Error(errors.join('\n'))
    console.log('PASS: noindex preview, 110 direct routes, photos, downloads and all Plotly charts in 5 languages')
    await context.close()
  } finally { await browser.close() }
})().catch(err => { console.error(err); process.exitCode = 1 })
