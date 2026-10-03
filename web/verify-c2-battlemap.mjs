// C2 战斗可视化「只看地图」复测截图器
//
// 用途：驱动真实后端（同源托管 dist 产物）+ 真实 recent_battles，
// 在指定回合连拍地图帧，用于验收「单场战斗，观众只看地图、不看文字，3 秒内复述三件事」。
//
// 用法:
//   node verify-c2-battlemap.mjs <baseUrl> <outDir> [turns...]
// 例:
//   node verify-c2-battlemap.mjs http://127.0.0.1:8016 /tmp/c2shots 3 4
//
// 说明：
// - 走 WS 同源（window.location.host），所以前端必须由后端同源托管（dist 静态产物），
//   或由 vite dev server 代理到同一后端。不要用两个不同端口的组合。
// - 拍两类图：`*-full.png` = 整屏（1600x900）；`*.png` = 裁掉右侧 300px 面板的「只看地图」图。
// - 每到一个目标回合会**连拍多帧**（回放只有 ~1.5s/场），文件名带序号，事后挑帧。
import { chromium } from 'playwright'
import fs from 'node:fs'

const BASE = process.argv[2] || 'http://127.0.0.1:8016'
const OUT = process.argv[3] || '/tmp/c2shots'
const TURNS = process.argv.slice(4).map(Number).filter((n) => Number.isFinite(n))
fs.mkdirSync(OUT, { recursive: true })

const VW = 1600
const VH = 900
const PANEL_W = 300
const MAP_CLIP = { x: 0, y: 0, width: VW - PANEL_W, height: VH }

const log = (...a) => console.log('[c2]', ...a)

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: VW, height: VH }, deviceScaleFactor: 1 })
page.on('pageerror', (e) => log('PAGE EXCEPTION:', e.message))
page.on('console', (m) => { if (m.type() === 'error') log('PAGE ERROR:', m.text()) })

await page.goto(BASE, { waitUntil: 'networkidle' })
await page.waitForTimeout(3500)

/** 读界面上的回合号 */
const getTurn = () =>
  page.evaluate(() => {
    const m = document.body.innerText.match(/第\s*(\d+)\s*\/\s*\d+\s*回合/)
    return m ? parseInt(m[1]) : -1
  })

/** 读后端真实 recent_battles（不靠界面文字判断） */
const getBattles = () =>
  page.evaluate(async () => {
    const r = await fetch('/api/state')
    const d = await r.json()
    return d.recent_battles || []
  })

const shoot = async (name) => {
  await page.screenshot({ path: `${OUT}/${name}-full.png` })
  await page.screenshot({ path: `${OUT}/${name}.png`, clip: MAP_CLIP })
}

/** 推进到目标回合（点「下一回合」；CLI 规则 AI 单回合毫秒级） */
async function advanceTo(target) {
  for (let guard = 0; guard < 400; guard++) {
    const cur = await getTurn()
    if (cur >= target) return cur
    const btn = page.locator('button:has-text("下一回合")').first()
    if (await btn.count()) {
      await btn.click({ timeout: 5000 }).catch(() => {})
    } else {
      await page.keyboard.press('Space')
    }
    await page.waitForTimeout(400)
  }
  return await getTurn()
}

// 期望「连拍几帧」覆盖整个回放窗口 + 回放结束后的常驻态：
// REPLAY_MAX(3) × 1.5s + 0.7s 淡出 ≈ 5.2s → 取 20 帧 × 400ms = 8s，末几帧即「残留态」。
const FRAMES = 20
const FRAME_GAP = 400

console.log(`[c2] base=${BASE} out=${OUT} turns=${TURNS.join(',') || '(none)'}`)
log('初始回合 =', await getTurn())

for (const t of TURNS) {
  const reached = await advanceTo(t)
  const battles = await getBattles()
  log(`回合 ${reached}：recent_battles=${battles.length} 场`, battles.map((b) => `${b.attacker_faction}→${b.defender_city}(${b.result})`).join(' '))
  // 到站立刻连拍（不等回放播完）——抓「回放中」帧
  for (let f = 0; f < FRAMES; f++) {
    await shoot(`t${t}-f${String(f).padStart(2, '0')}`)
    await page.waitForTimeout(FRAME_GAP)
  }
}

await browser.close()
log('DONE')
