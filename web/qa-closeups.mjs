// M2/M4 证据补拍器（QA · 改后 @6f01d53）
//   M2：① 地图城名特写（无 🏯）② 事件流称王特写（无 🏰 → 本地 svg）③ 战斗标签特写（⚔ → crossed-swords svg）
//   M4：外交面板「环形图 / 关系矩阵」二选一 + 战况摘要折叠 是否生效；矩阵是否还被截
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'

const BASE = process.argv[2] || 'http://127.0.0.1:8011'
const OUT = process.argv[3] || '/tmp/sanguo-closeups'
fs.mkdirSync(OUT, { recursive: true })
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const VW = 1920, VH = 1080, PANEL_W = 300
const PANEL_X = VW - PANEL_W
const CLIP = { x: PANEL_X, y: 0, width: PANEL_W, height: VH }
const log = (...a) => console.log('[closeup]', ...a)
const EMO = /[🏆⚖⏳🤝🏰🏯⚔]/

const browser = await chromium.launch({ executablePath: CHROME, headless: true })
const ctx = await browser.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: 1 })
const page = await ctx.newPage()
page.on('pageerror', (e) => log('PAGE EXCEPTION:', e.message))

const isAutoOn = async () => (await page.locator('text=自动推进中').count()) > 0
async function setAuto(on) { if (on !== (await isAutoOn())) { await page.keyboard.press('a'); await page.waitForTimeout(350) } }
const getTurn = () => page.evaluate(() => { const m = document.body.innerText.match(/第\s*(\d+)\s*(?:\/\s*(\d+)|∞)\s*回合/); return m ? parseInt(m[1]) : -1 })
async function clickTab(label) { await page.getByText(label, { exact: true }).first().click({ timeout: 5000 }).catch((e) => log('clickTab fail', label)); await page.waitForTimeout(500) }

await page.goto(BASE, { waitUntil: 'networkidle' })
await page.waitForSelector('text=已连接', { timeout: 30000 }).catch(() => {})
await page.waitForTimeout(4500)
await setAuto(true)
for (let i = 0; i < 120; i++) { await page.waitForTimeout(500); if ((await getTurn()) >= 20) break }
await setAuto(false)
await page.waitForTimeout(600)
log('中盘回合 =', await getTurn())

// ---------- M2a 地图城名特写 ----------
const cityBox = await page.evaluate(() => {
  const vw = innerWidth, vh = innerHeight
  const ok = [...document.querySelectorAll('[data-city-id]')].map((e) => { const r = e.getBoundingClientRect(); return { id: e.getAttribute('data-city-id'), cx: r.left + r.width / 2, cy: r.top + r.height / 2, w: r.width, h: r.height } })
    .filter((m) => m.w > 0 && m.cx > 640 && m.cx < vw - 340 && m.cy > 200 && m.cy < vh - 120)
  ok.sort((a, b) => Math.hypot(a.cx - (vw - 340) / 2, a.cy - vh / 2) - Math.hypot(b.cx - (vw - 340) / 2, b.cy - vh / 2))
  return ok[0] || null
})
if (cityBox) {
  await page.screenshot({ path: path.join(OUT, 'M2a-地图城名-特写.png'), clip: { x: Math.max(0, cityBox.cx - 130), y: Math.max(0, cityBox.cy - 90), width: 260, height: 180 } })
  log('M2a 城名特写已存 cityId=', cityBox.id)
}
const mapEmoji = await page.evaluate(() => [...document.querySelectorAll('[data-city-id]')].some((e) => /🏯/.test(e.textContent || '')))
log('地图城名含 🏯 =', mapEmoji)

// ---------- M2b 事件流称王特写 ----------
await clickTab('战报')
await page.getByText('建国 · 称王', { exact: false }).first().click({ timeout: 4000 }).catch(() => {})
await page.waitForTimeout(600)
await page.screenshot({ path: path.join(OUT, 'M2b-事件流称王-特写.png'), clip: CLIP })
const kingdomInfo = await page.evaluate(() => {
  const el = [...document.querySelectorAll('div')].find((d) => /称王|称帝|国号/.test(d.textContent || '') && (d.textContent || '').length < 160)
  const txt = el ? el.innerText.trim() : '(无)'
  return { txt, hasEmoji: /[🏆⚖⏳🤝🏰🏯⚔]/.test(txt) }
})
log('称王事件样本 =', JSON.stringify(kingdomInfo))

// ---------- M4 外交：环形图 / 关系矩阵 二选一 + 摘要折叠 ----------
await clickTab('外交')
await page.waitForTimeout(700)
// 默认 ring
await page.screenshot({ path: path.join(OUT, 'M4b-外交-环形图.png'), clip: CLIP })
const ringState = await page.evaluate(() => ({ hasRing: /共 \d+ 条非中立关系|开局：12 方/.test(document.body.innerText), hasMatrix: /关系矩阵（全 12 方/.test(document.body.innerText) }))
log('默认视图(ring)：hasRing=%s hasMatrix=%s', ringState.hasRing, ringState.hasMatrix)

// 切到矩阵
await page.getByText('关系矩阵', { exact: true }).first().click({ timeout: 4000 }).catch((e) => log('切矩阵失败', e.message))
await page.waitForTimeout(700)
await page.screenshot({ path: path.join(OUT, 'M4a-外交-关系矩阵.png'), clip: CLIP })
const matrixState = await page.evaluate(() => ({ hasRing: /共 \d+ 条非中立关系/.test(document.body.innerText), hasMatrix: /关系矩阵（全 12 方/.test(document.body.innerText) }))
log('切换后(matrix)：hasRing=%s hasMatrix=%s', matrixState.hasRing, matrixState.hasMatrix)

// 矩阵视图下测量（是否还被截）
const meas = await page.evaluate(() => {
  const all = [...document.querySelectorAll('div')]
  const cap = all.find((d) => /关系矩阵（全 12 方/.test(d.textContent || '') && d.children.length === 0)
  const anc = []
  let p = cap ? cap.parentElement : null
  while (p) { const cs = getComputedStyle(p); anc.push({ overflowY: cs.overflowY, clientH: p.clientHeight, scrollH: p.scrollHeight, hiddenBelow: Math.max(0, p.scrollHeight - p.clientHeight) }); p = p.parentElement }
  const scroller = anc.find((a) => a.hiddenBelow > 0) || null
  const cells = [...document.querySelectorAll('div[title*="↔"]')]
  const c0 = cells[0]
  const r = cap ? cap.getBoundingClientRect() : null
  return {
    panelW: 300, cell: c0 ? { w: Math.round(c0.getBoundingClientRect().width), h: Math.round(c0.getBoundingClientRect().height), fontPx: getComputedStyle(c0).fontSize } : null,
    captionTopY: r ? Math.round(r.top) : null, matrixHiddenBelowPx: scroller ? scroller.hiddenBelow : 0, realScroller: scroller,
  }
})
fs.writeFileSync(path.join(OUT, 'M4-measurements.json'), JSON.stringify(meas, null, 2))
log('M4(矩阵视图) 测量 =', JSON.stringify(meas))

// 摘要展开（默认折叠；展开看是否可用 / 是否又溢出）
await page.getByText('当前战况摘要', { exact: false }).first().click({ timeout: 4000 }).catch((e) => log('展开摘要失败', e.message))
await page.waitForTimeout(600)
await page.screenshot({ path: path.join(OUT, 'M4c-战况摘要-展开.png'), clip: CLIP })
const sumState = await page.evaluate(() => {
  const btn = [...document.querySelectorAll('button')].find((b) => /当前战况摘要/.test(b.textContent || ''))
  const all = [...document.querySelectorAll('div')]
  const sc = all.filter((d) => /当前战况摘要/.test(d.textContent || '') && getComputedStyle(d).overflowY === 'auto').sort((a, b) => a.clientHeight - b.clientHeight)[0]
  let hidden = 0
  if (sc) hidden = Math.max(0, sc.scrollHeight - sc.clientHeight)
  return { buttonText: btn ? btn.innerText.replace(/\s+/g, ' ').trim() : '', hiddenBelow: hidden }
})
log('摘要展开后：', JSON.stringify(sumState))

// ---------- M2c 战斗标签特写 ----------
await clickTab('战报')
let got = false
for (let attempt = 0; attempt < 4 && !got; attempt++) {
  try { await page.locator('button:has-text("下一回合")').first().click({ timeout: 4000 }) } catch { /* ignore */ }
  for (let i = 0; i < 40 && !got; i++) {
    const box = await page.evaluate(() => {
      const el = [...document.querySelectorAll('div')].find((d) => {
        const t = d.textContent || ''
        if (!/(占领|守住|溃退|相持)/.test(t)) return false
        if (t.length > 200) return false
        const r = d.getBoundingClientRect()
        if (r.width < 200 || r.height < 10) return false
        if (r.left < 0 || r.right > 1610 || r.top < 150 || r.bottom > 1060) return false
        return true
      })
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { cx: r.left + r.width / 2, cy: r.top + r.height / 2, txt: (el.textContent || '').slice(0, 80), hasEmoji: /[🏆⚖⏳🤝🏰🏯⚔]/.test(el.textContent || '') }
    })
    if (box) {
      await page.screenshot({ path: path.join(OUT, 'M2c-战斗回放标签-特写.png'), clip: { x: Math.max(0, box.cx - 320), y: Math.max(0, box.cy - 120), width: 640, height: 240 } })
      log('M2c 战斗标签已存；含 emoji =', box.hasEmoji, '| 文本=', box.txt.replace(/\s+/g, ' '))
      got = true; break
    }
    await page.waitForTimeout(150)
  }
}
if (!got) log('M2c 未抓到战斗标签')

// ---------- 全局 emoji 兜底扫描（可见文本）----------
const bodyEmoji = await page.evaluate(() => (document.body.innerText.match(/[🏆⚖⏳🤝🏰🏯⚔]/g) || []))
log('整页可见文本剩余 emoji =', JSON.stringify(bodyEmoji))

await browser.close()
log('DONE')
