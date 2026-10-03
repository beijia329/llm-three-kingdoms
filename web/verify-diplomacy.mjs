// 外交关系图复测截图器（阶段D）
//
// 用真实对局数据，在指定回合截「外交」tab 的关系图 + 完整矩阵。
// 用法: node verify-diplomacy.mjs <baseUrl> <outDir> [turn] [focusFactionLabel]
// 例:   node verify-diplomacy.mjs http://127.0.0.1:8016 /tmp/dip 20 曹操
//
// 说明：
// - 前端需由后端**同源**托管（dist 静态产物）或 vite 代理到同一后端，WS 才连得对。
// - 「外交」tab 的快捷键是 4（见 App.tsx）。
import { chromium } from 'playwright'
import fs from 'node:fs'

const BASE = process.argv[2] || 'http://127.0.0.1:8016'
const OUT = process.argv[3] || '/tmp/dip'
const TARGET_TURN = Number(process.argv[4] || 20)
const FOCUS = process.argv[5] || ''
fs.mkdirSync(OUT, { recursive: true })

const VW = 1600
const VH = 900
const PANEL_CLIP = { x: VW - 300, y: 0, width: 300, height: VH - 22 }

const log = (...a) => console.log('[dip]', ...a)

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: VW, height: VH }, deviceScaleFactor: 1 })
page.on('pageerror', (e) => log('PAGE EXCEPTION:', e.message))
page.on('console', (m) => { if (m.type() === 'error') log('PAGE ERROR:', m.text()) })

await page.goto(BASE, { waitUntil: 'networkidle' })
await page.waitForTimeout(3500)

const getTurn = () =>
  page.evaluate(() => {
    const m = document.body.innerText.match(/第\s*(\d+)\s*\/\s*\d+\s*回合/)
    return m ? parseInt(m[1]) : -1
  })

// 打开「外交」tab（快捷键 4）
await page.keyboard.press('4')
await page.waitForTimeout(600)

// 推进到目标回合
for (let g = 0; g < 200; g++) {
  const cur = await getTurn()
  if (cur >= TARGET_TURN) break
  const btn = page.locator('button:has-text("下一回合")').first()
  if (await btn.count()) await btn.click({ timeout: 5000 }).catch(() => {})
  else await page.keyboard.press('Space')
  await page.waitForTimeout(350)
}
const turn = await getTurn()
log('到达回合 =', turn)

// 记录后端真实关系统计（不靠界面文字）
const stats = await page.evaluate(async () => {
  const r = await fetch('/api/state')
  const d = await r.json()
  const rels = d.faction_relations || []
  const hist = {}
  let nonFaction = 0
  for (const x of rels) {
    hist[x.status] = (hist[x.status] || 0) + 1
    if (x.faction_a === 'neutral' || x.faction_b === 'neutral') nonFaction++
  }
  const real = rels.filter((x) => x.status !== 'neutral' && x.faction_a !== 'neutral' && x.faction_b !== 'neutral')
  return { hist, nonFaction, real: real.map((x) => `${x.faction_a}↔${x.faction_b}(${x.status},${x.trust})`) }
})
log('关系状态直方图 =', JSON.stringify(stats.hist), '| 含中立城的对 =', stats.nonFaction)
log('非中立(真实势力间)关系 =', stats.real.length, stats.real.slice(0, 12).join(' '))

await page.waitForTimeout(1200)
await page.screenshot({ path: `${OUT}/t${turn}-full.png` })
await page.screenshot({ path: `${OUT}/t${turn}-panel.png`, clip: PANEL_CLIP })
log(`shot t${turn}（全屏 + 面板）`)

// 面板可滚动：再截一张滚到底的（关系矩阵在下方）
await page.evaluate(() => {
  const els = Array.from(document.querySelectorAll('div'))
  const sc = els.find((e) => e.scrollHeight > e.clientHeight + 40 && e.clientWidth > 200 && e.clientWidth < 420)
  if (sc) sc.scrollTop = sc.scrollHeight
})
await page.waitForTimeout(500)
await page.screenshot({ path: `${OUT}/t${turn}-matrix.png`, clip: PANEL_CLIP })
log(`shot t${turn} 关系矩阵（滚动到底）`)
await page.evaluate(() => {
  const els = Array.from(document.querySelectorAll('div'))
  const sc = els.find((e) => e.scrollHeight > e.clientHeight + 40 && e.clientWidth > 200 && e.clientWidth < 420)
  if (sc) sc.scrollTop = 0
})
await page.waitForTimeout(400)

// 聚焦某个势力（点图上的节点；节点带 aria-label）
if (FOCUS) {
  const node = page.locator(`svg g[aria-label^="${FOCUS}"]`).first()
  if (await node.count()) {
    await node.click()
    await page.waitForTimeout(700)
    await page.screenshot({ path: `${OUT}/t${turn}-focus-${FOCUS}.png`, clip: PANEL_CLIP })
    log(`shot t${turn} 聚焦 ${FOCUS}`)
    const focused = await page.locator('text=/^只看/').count()
    log('聚焦提示可见 =', focused)
  } else {
    log(`⚠️ 未找到节点 ${FOCUS}`)
  }
}

await browser.close()
log('DONE')
