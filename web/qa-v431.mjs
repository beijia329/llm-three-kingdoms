// v4.3.1 视觉复验（QA）：M4 响应式窄屏 + H3 战斗聚焦 + emoji 扫描
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'
const BASE = process.argv[2] || 'http://127.0.0.1:8011'
const OUT = process.argv[3] || '/tmp/sanguo-v431'
fs.mkdirSync(OUT, { recursive: true })
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const EMO = /[🏆⚖⏳🤝🏰🏯⚔]/
const log = (...a) => console.log('[v431]', ...a)
const browser = await chromium.launch({ executablePath: CHROME, headless: true })

async function mk(w, h = 900) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 })
  const page = await ctx.newPage()
  page.on('pageerror', (e) => log('PAGE EXCEPTION:', e.message))
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForSelector('text=已连接', { timeout: 30000 }).catch(() => {})
  await page.waitForTimeout(4000)
  return { ctx, page }
}
const isAutoOn = async (page) => (await page.locator('text=自动推进中').count()) > 0
async function setAuto(page, on) { if (on !== (await isAutoOn(page))) { await page.keyboard.press('a'); await page.waitForTimeout(300) } }
const getTurn = (page) => page.evaluate(() => { const m = document.body.innerText.match(/第\s*(\d+)\s*(?:\/\s*(\d+)|∞)\s*回合/); return m ? parseInt(m[1]) : -1 })
async function clickTab(page, label) { await page.getByText(label, { exact: true }).first().click({ timeout: 5000 }).catch(() => {}); await page.waitForTimeout(400) }

// 0) 先把地图/外交数据推进到中盘（服务端全局状态，后续各视口共用）
{
  const { ctx, page } = await mk(1920, 1080)
  await setAuto(page, true)
  for (let i = 0; i < 120; i++) { await page.waitForTimeout(500); if ((await getTurn(page)) >= 14) break }
  await setAuto(page, false)
  log('推进到 turn =', await getTurn(page))
  await ctx.close()
}

// 1) M4 响应式：三种宽度
const results = []
for (const w of [1920, 1366, 1280]) {
  const { ctx, page } = await mk(w, 900)
  await clickTab(page, '外交')
  await page.waitForTimeout(500)
  const m = await page.evaluate(() => {
    const canvas = document.querySelector('canvas')
    const mapC = canvas ? canvas.parentElement : null           // GameMap 容器（= mapArea 宽）
    const mapW = mapC ? Math.round(mapC.getBoundingClientRect().width) : null
    const panelW = mapW != null ? window.innerWidth - mapW : null
    // 环 view 先量
    const ring = !!document.body.innerText.match(/共 \d+ 条非中立关系|开局：12 方/)
    return { vw: window.innerWidth, mapW, panelW, ringVisible: ring }
  })
  await page.screenshot({ path: path.join(OUT, `M4-${w}-环形图.png`) })
  // 切矩阵
  await page.getByText('关系矩阵', { exact: true }).first().click({ timeout: 4000 }).catch(() => {})
  await page.waitForTimeout(600)
  const m2 = await page.evaluate(() => {
    const cells = [...document.querySelectorAll('div[title*="↔"]')]
    const c0 = cells[0]
    const cell = c0 ? Math.round(c0.getBoundingClientRect().width) : null
    // 图例是否另起一行（在矩阵下方）
    const legend = [...document.querySelectorAll('*')].find((e) => /交战/.test(e.textContent || '') && /同盟/.test(e.textContent || '') && (e.children.length || 0) <= 8 && (e.textContent || '').length < 80)
    let legendBelowMatrix = null
    if (legend && c0) legendBelowMatrix = legend.getBoundingClientRect().top >= c0.getBoundingClientRect().bottom - 4
    const fold = [...document.querySelectorAll('button')].some((b) => /当前战况摘要/.test(b.textContent || ''))
    return { cell, cellCount: cells.length, legendBelowMatrix, foldBtn: fold }
  })
  await page.screenshot({ path: path.join(OUT, `M4-${w}-关系矩阵.png`) })
  // 摘要展开
  await page.getByText('当前战况摘要', { exact: false }).first().click({ timeout: 3000 }).catch(() => {})
  await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(OUT, `M4-${w}-摘要展开.png`) })
  const emo = await page.evaluate(() => (document.body.innerText.match(/[🏆⚖⏳🤝🏰🏯⚔]/g) || []))
  const rec = { width: w, ...m, ...m2, emoji: emo }
  results.push(rec)
  log(`宽度 ${w}: panel=${m.panelW} map=${m.mapW} cell=${m2.cell} legendBelowMatrix=${m2.legendBelowMatrix} foldBtn=${m2.foldBtn} emoji=${JSON.stringify(emo)}`)
  await ctx.close()
}
fs.writeFileSync(path.join(OUT, 'M4-responsive.json'), JSON.stringify(results, null, 2))

// 2) H3 战斗聚焦：推进到有战斗的回合，连拍
{
  const { ctx, page } = await mk(1920, 1080)
  await clickTab(page, '战报')
  let battleTurnInfo = null
  for (let a = 0; a < 6 && !battleTurnInfo; a++) {
    try { await page.locator('button:has-text("下一回合")').first().click({ timeout: 4000 }) } catch {}
    for (let i = 0; i < 30; i++) {
      const st = await page.evaluate(async () => { try { const d = await (await fetch('/api/state')).json(); const b = d.recent_battles || []; const last = b[b.length - 1] || {}; const sameTurn = b.filter((x) => x.turn === last.turn).length; return { lastTurn: last.turn, sameTurn, total: b.length } } catch { return {} } })
      if (st.sameTurn >= 2) { battleTurnInfo = st; break }
      await page.waitForTimeout(200)
    }
  }
  log('H3 多战斗回合 =', JSON.stringify(battleTurnInfo))
  // 连拍抓回放
  for (let f = 0; f < 10; f++) {
    await page.screenshot({ path: path.join(OUT, `H3-focus-f${String(f).padStart(2, '0')}.png`) })
    await page.waitForTimeout(280)
  }
  const emo = await page.evaluate(() => (document.body.innerText.match(/[🏆⚖⏳🤝🏰🏯⚔]/g) || []))
  log('H3 后整页 emoji =', JSON.stringify(emo))
  await ctx.close()
}

await browser.close()
log('DONE')
