// 终局文案「确定性注入」验证器（QA · 改后版）
//
// 目的：改后口径 = 文案真源在后端 `game.end_copy.format_end_copy`，/api/state 顶层
// 下发 `end_title`/`end_subtitle`，前端 **verbatim 渲染**。
// 本脚本用 Playwright 的 routeWebSocket 代理真实 WS，在拿到真实 state 后**注入构造 state**，
// 逐场景截图 + 抽取界面原文，做两类断言：
//   (1) 契约断言：界面标题/副行 == 注入的 end_title/end_subtitle（verbatim，逐字）；
//   (2) 红线断言：end_reason != unification 时，界面**不含**「统一/一统」。
// 另含**哨兵测试**：注入一段自定义文案，若前端仍残留本地映射则不会原文显示 → 直接抓出。
//
// 用法: node qa-endstate-matrix.mjs <baseUrl> <outDir>
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'

const BASE = process.argv[2] || 'http://127.0.0.1:8011'
const OUT = process.argv[3] || '/tmp/sanguo-endstate'
fs.mkdirSync(OUT, { recursive: true })
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const log = (...a) => console.log('[endstate]', ...a)

const browser = await chromium.launch({ executablePath: CHROME, headless: true })
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 })
const page = await ctx.newPage()
page.on('pageerror', (e) => log('PAGE EXCEPTION:', e.message))

let wsHandle = null
let lastState = null

await page.routeWebSocket('**/ws/**', (ws) => {
  wsHandle = ws
  const server = ws.connectToServer()
  ws.onMessage((m) => server.send(m))
  server.onMessage((m) => {
    try {
      const obj = JSON.parse(typeof m === 'string' ? m : m.toString())
      if (obj.type === 'state' && obj.data) lastState = obj.data
    } catch { /* ignore */ }
    ws.send(m)
  })
})

await page.goto(BASE, { waitUntil: 'networkidle' })
await page.waitForTimeout(5000)
if (!lastState) {
  log('WS 未截到 state，回退 REST /api/state')
  lastState = await page.evaluate(async () => (await (await fetch('/api/state')).json()))
}
log('基底 state: turn=%s max_turns=%s game_mode=%s', lastState?.turn, lastState?.max_turns, lastState?.game_mode)

const inject = (state) => wsHandle.send(JSON.stringify({ type: 'state', data: state }))

/** 抽取结束卡标题行 + 副行：先定位卡片，再按行序取「标题行的下一行」为副行 */
const readCard = () =>
  page.evaluate(() => {
    const cards = [...document.querySelectorAll('div')].filter((d) => {
      const t = d.textContent || ''
      return /查看棋盘/.test(t) && /(一统天下|领先胜出|天下未定|哨兵)/.test(t)
    })
    cards.sort((a, b) => (a.textContent || '').length - (b.textContent || '').length)
    const card = cards[0]
    if (!card) return { title: '', sub: '', full: '(未渲染结束卡)' }
    const lines = card.innerText.split('\n').map((s) => s.trim()).filter(Boolean)
    const idx = lines.findIndex((l) => /一统天下|领先胜出|天下未定|哨兵/.test(l))
    const title = idx >= 0 ? lines[idx] : ''
    const sub = idx >= 0 ? (lines[idx + 1] || '') : ''
    // 图标：卡内带 svg mask 的元素 → 取本地资产名（crown/scales/siege-tower/shaking-hands）
    const NAMES = ['crown', 'scales', 'siege-tower', 'shaking-hands']
    let iconAsset = null
    for (const n of [...card.querySelectorAll('*')]) {
      const cs = getComputedStyle(n)
      const m = cs.webkitMaskImage || cs.maskImage
      if (m && m !== 'none' && /\.svg/.test(m)) { iconAsset = NAMES.find((x) => m.includes(x)) || 'other-svg'; break }
      if (n.tagName === 'IMG') { const s = n.getAttribute('src') || ''; if (/\.svg/.test(s)) { iconAsset = NAMES.find((x) => s.includes(x)) || 'other-svg'; break } }
    }
    const emoji = /[🏆⚖⏳🤝]/.test(card.textContent || '')
    return { title, sub, full: card.innerText, iconAsset, emoji }
  })

const results = []
async function scenario(tag, patch, expTitle, expSub, expIcon) {
  inject({ ...lastState, ...patch })
  await page.waitForTimeout(900)
  await page.screenshot({ path: path.join(OUT, `${tag}.png`) })
  const { title, sub, full, iconAsset, emoji } = await readCard()
  fs.writeFileSync(path.join(OUT, `${tag}.txt`), full)
  const noUnify = !/统一|一统/.test(title + sub)
  const check = expTitle === null ? null : (title.trim() === expTitle && sub.startsWith(expSub))
  const iconOk = expIcon === null ? true : iconAsset === expIcon
  results.push({ tag, title, sub, iconAsset, emoji, expTitle, expSub, expIcon, noUnify, check, iconOk })
  log(`===== ${tag} =====`)
  log(`  title=[${title}]  sub=[${sub}]`)
  log(`  icon=[${iconAsset}] 期望=[${expIcon}]  ✅=${iconOk}  | 界面含emoji=${emoji}  verbatim=${check === null ? 'n/a' : check}  非统一红线=${noUnify}`)
}

// A1 真统一：文案保留「一统天下」+ 图标 crown
await scenario('A1-unification', {
  game_over: true, turn: 30, max_turns: 192, winner: 'caocao', end_reason: 'unification',
  end_title: '曹操 一统天下', end_subtitle: '第 30 回合 · 廓清寰宇', end_icon: 'crown',
}, '曹操 一统天下', '第 30 回合 · 廓清寰宇', 'crown')

// A2 时限：领先胜出 + 图标 siege-tower
await scenario('A2-timeout', {
  game_over: true, turn: 48, max_turns: 48, winner: 'sunjian', end_reason: 'timeout',
  end_title: '孙坚 领先胜出', end_subtitle: '第 48 / 48 回合 · 时限已到，天下未定', end_icon: 'siege-tower',
}, '孙坚 领先胜出', '第 48 / 48', 'siege-tower')

// A3 僵局：领先胜出 + 图标 scales
await scenario('A3-stalemate', {
  game_over: true, turn: 55, max_turns: 192, winner: 'sunjian', end_reason: 'stalemate', stalemate_turns: 6,
  end_title: '孙坚 领先胜出', end_subtitle: '连续 6 回合无战事 · 僵局收束，天下未定', end_icon: 'scales',
}, '孙坚 领先胜出', '连续 6 回合无战事', 'scales')

// A4 平局（winner 空；基线 S3 漏洞点）：天下未定 · 并列 + 图标 shaking-hands
await scenario('A4-draw', {
  game_over: true, turn: 48, max_turns: 48, winner: null, end_reason: 'timeout',
  end_title: '天下未定 · 并列', end_subtitle: '第 48 / 48 回合 · 时限已到，天下未定', end_icon: 'shaking-hands',
}, '天下未定 · 并列', '第 48 / 48', 'shaking-hands')

// A5 哨兵（文案 verbatim）：注入自定义文案 + end_icon=scales → 界面须逐字显示 + 渲染 scales
await scenario('A5-sentinel-verbatim', {
  game_over: true, turn: 40, max_turns: 48, winner: 'sunjian', end_reason: 'timeout',
  end_title: '【哨兵】标题应逐字渲染', end_subtitle: '【哨兵】副行应逐字渲染', end_icon: 'scales',
}, '【哨兵】标题应逐字渲染', '【哨兵】副行应逐字渲染', 'scales')

// A6 图标哨兵（未知资产名）→ 前端只查表，未知名应**不渲染任何图标**（证明无本地映射）
await scenario('A6-sentinel-unknown-icon', {
  game_over: true, turn: 40, max_turns: 48, winner: 'sunjian', end_reason: 'timeout',
  end_title: '孙坚 领先胜出', end_subtitle: '第 40 / 48 回合 · 时限已到，天下未定', end_icon: '__NOPE__',
}, '孙坚 领先胜出', '第 40 / 48', null)

// ===== 汇总判定 =====
let fail = 0
for (const r of results) {
  const bad = (r.check === false) || (r.tag.startsWith('A5') && !/哨兵/.test(r.title)) || (r.iconOk === false) || (r.emoji === true)
  const red = !(r.tag.startsWith('A1')) && !r.noUnify
  if (bad || red) { fail += 1; log(`❌ ${r.tag} FAIL (verbatim=${r.check} icon=${r.iconOk} emoji=${r.emoji} 红线=${r.noUnify})`) }
}
log(`===== 终局矩阵判定：${fail === 0 ? 'PASS' : 'FAIL(' + fail + ')'} =====`)
fs.writeFileSync(path.join(OUT, 'endstate-verdict.txt'), (fail === 0 ? 'PASS' : `FAIL(${fail})`) + '\n' + JSON.stringify(results, null, 2))

await browser.close()
log('DONE')
process.exit(fail === 0 ? 0 : 2)
