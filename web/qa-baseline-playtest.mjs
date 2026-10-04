// 乱斗三国 · 试玩基线截图器（2026-10-04 · 现状基线，改动前）
//
// 用途：驱动真实后端（同源托管 web/dist）+ 真实规则 AI 对局，按玩家视角拍一组
// 覆盖「首屏 / 势力 / 城池卡 / 军队行军 / 战报 / 外交 / 决策 / 结束界面」的截图，
// 并抽取结束界面文案原文（玩家反馈第 3 条「判定/文案不统一」的关键证据）。
//
// 用法:
//   node qa-baseline-playtest.mjs <baseUrl> <outDir>
// 例:
//   node qa-baseline-playtest.mjs http://127.0.0.1:8011 docs/qa/screenshots-2026-10-04-baseline
//
// 只读：不修改任何游戏代码/状态（除推进回合与"重开一局"外无副作用；本脚本不重开）。
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'

const BASE = process.argv[2] || 'http://127.0.0.1:8011'
const OUT = process.argv[3] || '/tmp/sanguo-baseline'
fs.mkdirSync(OUT, { recursive: true })

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const VW = 1920
const VH = 1080
const PANEL_W = 320

const log = (...a) => console.log('[qa]', ...a)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await chromium.launch({ executablePath: CHROME, headless: true })
const ctx = await browser.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: 1 })
const page = await ctx.newPage()
page.on('pageerror', (e) => log('PAGE EXCEPTION:', e.message))
page.on('console', (m) => { if (m.type() === 'error') log('PAGE ERROR:', m.text()) })

const shot = async (name) => {
  const p = path.join(OUT, name)
  await page.screenshot({ path: p })
  log('shot →', name)
}

/** 从顶栏读「第 N / M 回合」或「第 N∞ 回合」 */
const getTurn = () =>
  page.evaluate(() => {
    const m = document.body.innerText.match(/第\s*(\d+)\s*(?:\/\s*(\d+)|∞)\s*回合/)
    return m ? { turn: parseInt(m[1]), max: m[2] ? parseInt(m[2]) : null } : { turn: -1, max: null }
  })

const bodyHas = async (t) => (await page.locator(`text=${t}`).count()) > 0

/** 自动推进是否开启（界面会显示「自动推进中」） */
const isAutoOn = async () => (await page.locator('text=自动推进中').count()) > 0

async function setAuto(on) {
  if (on === (await isAutoOn())) return
  await page.keyboard.press('a')
  await page.waitForTimeout(350)
}

const isGameOver = async () =>
  page.evaluate(() => /一统天下|天下未定|领先胜出|并列/.test(document.body.innerText))

/** 点击右侧面板 tab（用 tab 内 span 精确文本，避免 Font Awesome 图标污染可访问名） */
async function clickTab(label) {
  try {
    await page.getByText(label, { exact: true }).first().click({ timeout: 5000 })
    await page.waitForTimeout(500)
    log('clickTab ok →', label)
    return true
  } catch (e) {
    log('clickTab 失败 →', label, e.message)
    return false
  }
}

/** 点击一个「视野内」的地图标记，并返回是否成功（避免点到屏幕外） */
async function clickMarkerInViewport(attr) {
  const list = await page.evaluate((a) => {
    return [...document.querySelectorAll(`[${a}]`)].map((el) => {
      const r = el.getBoundingClientRect()
      return {
        id: el.getAttribute(a),
        cx: r.left + r.width / 2,
        cy: r.top + r.height / 2,
        w: r.width,
        h: r.height,
      }
    })
  }, attr)
  const vw = VW
  const vh = VH
  const usable = list.filter(
    (m) => m.w > 0 && m.h > 0 && m.cx > 640 && m.cx < vw - PANEL_W - 40 && m.cy > 150 && m.cy < vh - 40,
  )
  if (usable.length === 0) return null
  // 取最靠近地图中心的
  usable.sort(
    (a, b) =>
      Math.hypot(a.cx - (vw - PANEL_W) / 2, a.cy - vh / 2) -
      Math.hypot(b.cx - (vw - PANEL_W) / 2, b.cy - vh / 2),
  )
  const pick = usable[0]
  await page.mouse.click(pick.cx, pick.cy)
  await page.waitForTimeout(700)
  return pick.id
}

// ============================================================
// 0. 打开并等待首屏
// ============================================================
log('打开', BASE)
await page.goto(BASE, { waitUntil: 'networkidle' })
// 等地图与顶栏出现（首帧含 2.4 万格地图解析）
await page.waitForSelector('text=已连接', { timeout: 30000 }).catch(() => {})
await page.waitForTimeout(4500)
let tm = await getTurn()
log('首屏回合 =', JSON.stringify(tm))

// ============================================================
// 1. 首屏地图全景
// ============================================================
await shot('01-初始地图全景.png')

// ============================================================
// 2. 选中某势力（势力 tab → 曹操卡）
// ============================================================
await clickTab('势力')
// FactionBadge 的单字徽标嵌在名称 span 内，pure text 匹配不可靠 → 用「含名+含城且 cursor:pointer 的最内层 div」
const facBox = await page.evaluate(() => {
  const divs = [...document.querySelectorAll('div')]
  const cands = divs.filter((d) => {
    const t = d.textContent || ''
    return /曹操/.test(t) && /城/.test(t) && d.style && d.style.cursor === 'pointer'
  })
  cands.sort((a, b) => (a.textContent || '').length - (b.textContent || '').length)
  const c = cands[0]
  if (!c) return null
  const r = c.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2, text: (c.textContent || '').slice(0, 40) }
})
if (facBox) {
  await page.mouse.click(facBox.x, facBox.y)
  await page.waitForTimeout(500)
  log('点击势力卡 =', JSON.stringify(facBox.text))
} else {
  log('★ 未找到曹操势力卡')
}
await shot('02-选中势力-曹操.png')

// ============================================================
// 3. 推进到中盘：开自动推进，跑到 turn>=20 或出现战斗
// ============================================================
log('开始自动推进…')
await setAuto(true)
let guard = 0
let reached = tm.turn
while (guard++ < 120) {
  await page.waitForTimeout(500)
  const t = await getTurn()
  reached = t.turn
  if (t.turn >= 20) break
  if (await isGameOver()) break
}
await setAuto(false)
await page.waitForTimeout(600)
tm = await getTurn()
log('中盘停在第', tm.turn, '回合')

// 若 armies 少，多推几回合（用下一回合按钮）
const armyCount = async () =>
  page.evaluate(() => document.querySelectorAll('[data-army-id]').length)
log('当前可见军队标记数 =', await armyCount())

// ============================================================
// 4. 城池卡（点地图上的城）
// ============================================================
let cityId = await clickMarkerInViewport('data-city-id')
if (!cityId) {
  log('★ 视野内无城池标记，改用「城市」tab 定位')
  await clickTab('城市')
  await page.waitForTimeout(400)
  const row = page.locator('[data-panel-city-id]').first()
  if (await row.count()) {
    cityId = await row.getAttribute('data-panel-city-id')
    await row.click()
    await page.waitForTimeout(800)
  }
}
const hasCityCard = (await page.locator('[data-city-card]').count()) > 0
log('城池卡出现 =', hasCityCard, '| cityId =', cityId)
await shot('03-城池卡.png')
await page.keyboard.press('Escape')
await page.waitForTimeout(400)

// ============================================================
// 5. 军队与行军状态（点地图上的军队）
// ============================================================
let armyId = await clickMarkerInViewport('data-army-id')
let hasArmyCard = (await page.locator('text=的部队').count()) > 0
log('军队卡出现 =', hasArmyCard, '| armyId =', armyId)
await shot('04-军队与行军状态.png')
if (hasArmyCard) {
  // 读取军队卡里的状态原文（取"包含『的部队』且文本最短"的 div = 最内层卡片）
  const armyTxt = await page.evaluate(() => {
    const cands = [...document.querySelectorAll('div')].filter((d) =>
      /的部队/.test(d.textContent || '') && /状态：/.test(d.textContent || '') && d.children.length <= 4,
    )
    cands.sort((a, b) => (a.textContent || '').length - (b.textContent || '').length)
    return cands[0] ? cands[0].innerText.replace(/\s*\n\s*/g, ' | ') : ''
  })
  log('军队卡原文 =', armyTxt)
  fs.writeFileSync(path.join(OUT, 'army-card.txt'), armyTxt)
}
await page.keyboard.press('Escape')
await page.waitForTimeout(400)

// ============================================================
// 6. 战报 / 战斗
// ============================================================
// 6a. 地图层战斗回放（best-effort）：推进一回合后立刻连拍，抓「战斗回放」帧
try {
  const before = await page.evaluate(async () => (await (await fetch('/api/state')).json()).recent_battles?.length || 0)
  await page.locator('button:has-text("下一回合")').first().click({ timeout: 4000 })
  for (let f = 0; f < 8; f++) {
    await page.waitForTimeout(250)
    await page.screenshot({ path: path.join(OUT, `05-战斗回放-f${String(f).padStart(2, '0')}.png`) })
  }
  const after = await page.evaluate(async () => (await (await fetch('/api/state')).json()).recent_battles?.length || 0)
  log('战斗回放连拍: recent_battles', before, '→', after)
} catch (e) {
  log('战斗回放连拍跳过:', e.message)
}

await clickTab('战报')
await shot('05-战报.png')

// 若地图上有战斗回放（recent_battles），补拍一张
const battleN = await page.evaluate(async () => {
  try {
    const r = await fetch('/api/state')
    const d = await r.json()
    return (d.recent_battles || []).length
  } catch { return -1 }
})
log('recent_battles =', battleN)

// ============================================================
// 7. 外交图（关系环形图 + 矩阵）
// ============================================================
await clickTab('外交')
await page.waitForTimeout(500)
await shot('06-外交关系图.png')

// ============================================================
// 8. 决策面板
// ============================================================
await clickTab('决策')
await shot('07-决策面板.png')

// ============================================================
// 9. 跑到结束（关键）
// ============================================================
log('继续自动推进直到对局结束…')
await setAuto(true)
guard = 0
while (guard++ < 200) {
  await page.waitForTimeout(500)
  if (await isGameOver()) break
}
await setAuto(false)
await page.waitForTimeout(1000)
tm = await getTurn()
log('结束回合 =', JSON.stringify(tm), '| 结束界面出现 =', await isGameOver())

await shot('08-结束界面.png')

// 抽取结束界面文案原文
const overText = await page.evaluate(() => {
  const cards = [...document.querySelectorAll('div')].filter((d) => {
    const t = d.textContent || ''
    return /一统天下|天下未定/.test(t) && t.length < 260
  })
  cards.sort((a, b) => (a.textContent || '').length - (b.textContent || '').length)
  const card = cards.find((d) => /回合|坐拥|平局/.test(d.textContent || '')) || cards[0]
  return card ? card.innerText : '(未找到结束卡片)'
})
log('===== 结束界面原文 =====')
log(overText)
fs.writeFileSync(path.join(OUT, 'gameover-text.txt'), overText)

// 顶栏 + 事件流（含结束事件）原文
const bodyText = await page.evaluate(() => document.body.innerText)
fs.writeFileSync(path.join(OUT, 'end-body-text.txt'), bodyText)

// 后端权威字段
const api = await page.evaluate(async () => {
  const r = await fetch('/api/state')
  const d = await r.json()
  return {
    turn: d.turn, max_turns: d.max_turns, game_over: d.game_over, winner: d.winner,
    game_mode: d.game_mode, stalemate_turns: d.stalemate_turns,
    end_reason: d.end_reason, end_title: d.end_title, end_subtitle: d.end_subtitle, end_icon: d.end_icon,
  }
})
log('后端权威 =', JSON.stringify(api))
fs.writeFileSync(path.join(OUT, 'end-api-state.json'), JSON.stringify(api, null, 2))

await browser.close()
log('DONE')
