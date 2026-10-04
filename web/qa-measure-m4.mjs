// M4 精确几何测量（QA）：外交 tab 里「关系矩阵」被截断的真实滚动容器与几何
import { chromium } from 'playwright'
const BASE = process.argv[2] || 'http://127.0.0.1:8011'
const OUT = process.argv[3] || '/tmp/sanguo-m4measure'
import fs from 'node:fs'
fs.mkdirSync(OUT, { recursive: true })
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const log = (...a) => console.log('[m4]', ...a)
const browser = await chromium.launch({ executablePath: CHROME, headless: true })
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 })
await page.goto(BASE, { waitUntil: 'networkidle' })
await page.waitForTimeout(4500)
await page.getByText('外交', { exact: true }).first().click().catch(() => {})
await page.waitForTimeout(900)

const data = await page.evaluate(() => {
  const all = [...document.querySelectorAll('div')]
  const cap = all.find((d) => /关系矩阵（全 12 方/.test(d.textContent || '') && d.children.length === 0)
  // 矩阵实际渲染块：矩阵 = inline-block，含 13×(13) 个 20px 格；用其 title 属性最密者近似
  const cells = [...document.querySelectorAll('div[title*="↔"]')]
  const cell0 = cells[0]
  const cellRect = cell0 ? cell0.getBoundingClientRect() : null
  // 走 caption 的祖先链，找出真正会滚动的容器
  const anc = []
  let p = cap ? cap.parentElement : null
  while (p) {
    const cs = getComputedStyle(p)
    anc.push({
      tag: p.tagName,
      overflowY: cs.overflowY,
      clientH: p.clientHeight,
      scrollH: p.scrollHeight,
      hiddenBelow: Math.max(0, p.scrollHeight - p.clientHeight),
      scrollTop: p.scrollTop,
      cls: (p.className || '').toString().slice(0, 30),
    })
    p = p.parentElement
  }
  const scroller = anc.find((a) => a.hiddenBelow > 0) || null
  return {
    viewport: { vw: innerWidth, vh: innerHeight },
    panelW: 300,
    matrixCellDiv: {
      count: cells.length,
      w: cellRect ? Math.round(cellRect.width) : null,
      h: cellRect ? Math.round(cellRect.height) : null,
      fontPx: cell0 ? getComputedStyle(cell0).fontSize : null,
    },
    captionY: cap ? Math.round(cap.getBoundingClientRect().top) : null,
    matrixBlock: (() => {
      const m = cap ? cap.parentElement : null
      if (!m) return null
      const r = m.getBoundingClientRect()
      return { top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height), w: Math.round(r.width) }
    })(),
    realScroller: scroller,
    ancestors: anc,
  }
})
fs.writeFileSync(`${OUT}/M4-measure.json`, JSON.stringify(data, null, 2))
log(JSON.stringify(data, null, 2))
// 滚到真滚动容器底部再拍一张，确认矩阵能完整露出
await page.evaluate(() => {
  const all = [...document.querySelectorAll('div')]
  const cap = all.find((d) => /关系矩阵（全 12 方/.test(d.textContent || '') && d.children.length === 0)
  let p = cap ? cap.parentElement : null
  while (p) { if (p.scrollHeight > p.clientHeight) { p.scrollTop = p.scrollHeight; break } p = p.parentElement }
})
await page.waitForTimeout(400)
await page.screenshot({ path: `${OUT}/M4-矩阵滚到底.png`, clip: { x: 1620, y: 0, width: 300, height: 1080 } })
await browser.close()
log('DONE')
