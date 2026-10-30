import { expect, test } from '../e2e/fixtures'
import { readdirSync } from 'node:fs'
import { join } from 'node:path'

const languages = ['ru', 'en', 'es', 'zh-Hans', 'ar']
const charts: Record<string, number> = { 'heteroplasmy-landscape': 1, 'embryo-concordance': 3, 'embryo-to-offspring': 2, 'pgt-mt-pgt-a-model': 3 }
function routes(dir: string, prefix = ''): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? routes(join(dir, e.name), `${prefix}${e.name}/`) : e.name === 'index.html' ? [prefix] : [])
}
for (const lang of languages) {
  test(`${lang}: direct entry, reload, assets and internal links`, async ({ page, request }) => {
    const paths = routes(`dist/${lang}`, `${lang}/`)
    expect(paths).toHaveLength(22)
    const failures: string[] = []
    page.on('pageerror', e => failures.push(e.message))
    page.on('response', r => { if (r.url().startsWith('http://localhost:4175/') && r.status() >= 400) failures.push(`${r.status()} ${r.url()}`) })
    for (const path of paths) {
      await page.goto(path)
      await expect(page.locator('html')).toHaveAttribute('lang', lang)
      await expect(page.locator('h1').first()).toBeVisible()
      await expect(page.locator('head link[rel=canonical]')).toHaveAttribute('href', `https://atlas.mazunin.science/${path}`)
      const links = await page.locator('a[href], img[src], script[src], link[rel=stylesheet][href]').evaluateAll(els => els.map(e => (e as HTMLAnchorElement | HTMLImageElement | HTMLScriptElement | HTMLLinkElement).getAttribute(e.tagName === 'IMG' || e.tagName === 'SCRIPT' ? 'src' : 'href')).filter(Boolean) as string[])
      for (const href of new Set(links)) {
        const url = new URL(href, `http://localhost:4175/${path}`)
        if (url.origin !== 'http://localhost:4175' || href.startsWith('#') || !/^https?:$/.test(url.protocol)) continue
        const response = await request.get(url.href)
        expect(response.status(), `${path} → ${href}`).toBe(200)
      }
    }
    await page.goto(`${lang}/science/embryo-concordance?x=1#content`)
    await expect(page).toHaveURL(`http://localhost:4175/${lang}/science/embryo-concordance/?x=1#content`)
    await page.reload()
    await expect(page.locator('h1').first()).toBeVisible()
    await page.goto(`${lang}/contribute/`)
    const downloadLink = page.locator('a[download]').first()
    await expect(downloadLink).toHaveCount(1)
    const [download] = await Promise.all([page.waitForEvent('download'), downloadLink.click()])
    expect(await download.failure()).toBeNull()
    expect((await download.path())).toBeTruthy()
    await page.goto(`${lang}/ilya-mazunin/`)
    await page.locator('img[src*="ilya-mazunin.jpg"]').first().scrollIntoViewIfNeeded()
    await expect.poll(() => page.locator('img[src*="ilya-mazunin.jpg"]').first().evaluate((e: HTMLImageElement) => e.naturalWidth)).toBeGreaterThan(0)
    for (const [path, count] of Object.entries(charts)) {
      await page.goto(`${lang}/science/${path}/`)
      await expect(page.locator('.chart-frame .js-plotly-plot')).toHaveCount(count, { timeout: 30000 })
      await expect(page.locator('.chart-placeholder')).toHaveCount(0)
    }
    expect(failures).toEqual([])
  })
}
test('root counter sends root paths and reads the total', async ({ page }) => {
  await page.route('https://gc.zgo.at/**', route => route.fulfill({ contentType: 'text/javascript', body: 'window.goatcounter={count:v=>(window.__gcPaths=window.__gcPaths||[]).push(v.path)}' }))
  await page.route('https://pgt-mt-atlas.goatcounter.com/counter/TOTAL.json', route => route.fulfill({ contentType: 'application/json', body: '{"count":"1,234"}' }))
  await page.goto('ru/')
  await expect(page.locator('.visitor-count-value')).toHaveText('1,234')
  await expect.poll(() => page.evaluate(() => (window as unknown as { __gcPaths?: string[] }).__gcPaths)).toEqual(['/ru/'])
  await page.locator('nav.primary').getByRole('link', { name: 'Основы ПГТ-мт' }).click()
  await expect.poll(() => page.evaluate(() => (window as unknown as { __gcPaths?: string[] }).__gcPaths)).toEqual(['/ru/', '/ru/fundamentals/'])
})
