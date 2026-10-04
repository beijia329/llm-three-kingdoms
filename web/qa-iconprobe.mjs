// M2 图标复验 + 放大帧（QA）—— 验证 mask 修复，并给美术出放大图
// 断言：① CSS.supports('mask-image', url(<实际URL>)) === true
//       ② 图标 span 的 computed mask-image 非 none（不再退化为实心方块）
// 产出：结算四态图标 / 战斗 crossed-swords / 地图城池·军队 剪影 放大帧
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'
const BASE = process.argv[2] || 'http://127.0.0.1:8011'
const OUT = process.argv[3] || '/tmp/sanguo-icons'
fs.mkdirSync(OUT, { recursive: true })
const log = (...a) => console.log('[icon]', ...a)
const browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true })
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 3 })
const page = await ctx.newPage()
let ws = null, lastState = null
await page.routeWebSocket('**/ws/**', (w) => {
  ws = w
  const s = w.connectToServer()
  w.onMessage((m) => s.send(m))
  s.onMessage((m) => { try { const o = JSON.parse(typeof m === 'string' ? m : m.toString()); if (o.type === 'state' && o.data) lastState = o.data } catch {} w.send(m) })
})
await page.goto(BASE, { waitUntil: 'networkidle' })
await page.waitForSelector('text=已连接', { timeout: 30000 }).catch(() => {})
await page.waitForTimeout(5000)
if (!lastState) lastState = await page.evaluate(async () => (await (await fetch('/api/state')).json()))
// 推进到 ~turn 12：让地图上有军队（军队剪影）
try {
  await page.keyboard.press('a')
  for (let i = 0; i < 60; i++) {
    await page.waitForTimeout(400)
    const t = await page.evaluate(() => { const m = document.body.innerText.match(/第\s*(\d+)/); return m ? parseInt(m[1]) : -1 })
    if (t >= 12) break
    if ((await page.locator('text=自动推进中').count()) === 0) break
  }
  if ((await page.locator('text=自动推进中').count()) > 0) await page.keyboard.press('a')
  await page.waitForTimeout(600)
} catch {}

// 0) 先从任一 mask 元素取实际 URL，做 CSS.supports 断言
const sup = await page.evaluate(() => {
  const el = [...document.querySelectorAll('[data-city-id] span')].find((n) => {
    const cs = getComputedStyle(n); const m = cs.maskImage || cs.webkitMaskImage
    return m && m !== 'none'
  }) || [...document.querySelectorAll('[data-city-id] span')][0]
  const cs = el ? getComputedStyle(el) : null
  const raw = cs ? (cs.maskImage || cs.webkitMaskImage || '') : ''
  const url = (raw.match(/url\((["']?)(.*?)\1\)/) || [])[2] || raw
  let supports = null, supportsUnq = null
  try { supports = CSS.supports('mask-image', `url("${url}")`) } catch {}
  try { supportsUnq = CSS.supports('mask-image', `url(${url})`) } catch {}
  return { cityMaskComputed: raw.slice(0, 50), url: url.slice(0, 60), supportsQuoted: supports, supportsUnquoted: supportsUnq }
})
log('CSS.supports 断言 =', JSON.stringify(sup))
log(`  >>> 回归断言(CSS.supports quoted=true, 图标 mask非none)：${sup.supportsQuoted === true && !/none/.test(sup.cityMaskComputed) ? 'PASS' : 'FAIL'}`)

const shot = async (tag, box, pad = 34) => {
  if (!box) { log(tag, '未找到元素'); return }
  await page.screenshot({ path: path.join(OUT, `${tag}.png`), clip: { x: Math.max(0, box.cx - pad), y: Math.max(0, box.cy - pad), width: pad * 2, height: pad * 2 } })
  log(tag, '已存')
}

// 1) 地图城池 / 军队剪影
const mapInfo = await page.evaluate(() => {
  const pick = (sel) => {
    const els = [...document.querySelectorAll(sel)].map((e) => { const r = e.getBoundingClientRect(); return { e, cx: r.left + r.width / 2, cy: r.top + r.height / 2, w: r.width } })
      .filter((m) => m.w > 0 && m.cx > 700 && m.cx < 1550 && m.cy > 220 && m.cy < 1000)
    if (!els.length) return null
    const m = els[0]
    const span = [...m.e.querySelectorAll('span')].find((n) => { const cs = getComputedStyle(n); const mm = cs.maskImage || cs.webkitMaskImage; return mm && mm !== 'none' })
    const cs = span ? getComputedStyle(span) : null
    return { cx: m.cx, cy: m.cy, mask: cs ? (cs.maskImage || cs.webkitMaskImage || '').slice(0, 40) : '(无 mask span)' }
  }
  return { city: pick('[data-city-id]'), army: pick('[data-army-id]') }
})
log('城池剪影 mask =', JSON.stringify(mapInfo.city))
log('军队剪影 mask =', JSON.stringify(mapInfo.army))
await shot('map-city-silhouette', mapInfo.city, 40)
await shot('map-army-silhouette', mapInfo.army, 40)

// 2) 战斗 crossed-swords：推进到有战斗，截标签
try { await page.locator('button:has-text("下一回合")').first().click({ timeout: 4000 }) } catch {}
let gotB = false
for (let a = 0; a < 3 && !gotB; a++) {
  for (let i = 0; i < 30 && !gotB; i++) {
    const box = await page.evaluate(() => {
      const el = [...document.querySelectorAll('div')].find((d) => { const t = d.textContent || ''; if (!/(占领|守住|溃退|相持)/.test(t) || t.length > 200) return false; const r = d.getBoundingClientRect(); return r.width > 200 && r.left >= 0 && r.right <= 1610 && r.top > 150 && r.bottom < 1060 })
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { cx: r.left + r.width / 2, cy: r.top + r.height / 2, w: r.width }
    })
    if (box) { await page.screenshot({ path: path.join(OUT, 'battle-crossed-swords.png'), clip: { x: Math.max(0, box.cx - 160), y: Math.max(0, box.cy - 60), width: 320, height: 120 } }); log('battle-crossed-swords 已存'); gotB = true; break }
    await page.waitForTimeout(150)
  }
  if (!gotB) { try { await page.locator('button:has-text("下一回合")').first().click({ timeout: 3000 }) } catch {} }
}

// 3) 结算四态图标
async function endIcon(tag, icon) {
  ws.send(JSON.stringify({ type: 'state', data: { ...lastState, game_over: true, turn: 30, max_turns: 192, winner: 'sunjian', end_reason: 'timeout', end_title: '测试 领先胜出', end_subtitle: '副行', end_icon: icon } }))
  let info = null
  for (let a = 0; a < 6 && !info; a++) {
    await page.waitForTimeout(400)
    info = await page.evaluate(() => {
      const el = [...document.querySelectorAll('span')].find((n) => { const r = n.getBoundingClientRect(); return r.width >= 40 && r.width <= 48 && r.height >= 40 && r.height <= 48 })
      if (!el) return null
      const cs = getComputedStyle(el)
      const m = cs.maskImage || cs.webkitMaskImage || ''
      const r = el.getBoundingClientRect()
      return { cx: r.left + r.width / 2, cy: r.top + r.height / 2, mask: m.slice(0, 45) }
    })
  }
  log(tag, JSON.stringify(info))
  if (info) await page.screenshot({ path: path.join(OUT, `${tag}.png`), clip: { x: Math.max(0, info.cx - 30), y: Math.max(0, info.cy - 30), width: 60, height: 60 } })
}
await endIcon('end-icon-crown', 'crown')
await endIcon('end-icon-siege-tower', 'siege-tower')
await endIcon('end-icon-scales', 'scales')
await endIcon('end-icon-shaking-hands', 'shaking-hands')

await browser.close()
log('DONE')
