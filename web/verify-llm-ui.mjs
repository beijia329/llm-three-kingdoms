// Playwright 真实浏览器验证：LLM 模式入口 / 决策 tab 中文命令 / 降级提示条
// 用法: node verify-llm-ui.mjs <baseUrl> <outDir>
import { chromium } from 'playwright'
import fs from 'node:fs'

const BASE = process.argv[2] || 'http://127.0.0.1:8010'
const OUT = process.argv[3] || '/tmp/sanguo-v31'
fs.mkdirSync(OUT, { recursive: true })

const log = (...a) => console.log('[verify]', ...a)

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const ctx = await browser.newContext({ viewport: { width: 1600, height: 950 }, deviceScaleFactor: 2 })
const page = await ctx.newPage()
page.on('console', (m) => { if (m.type() === 'error') log('PAGE ERROR:', m.text()) })
page.on('pageerror', (e) => log('PAGE EXCEPTION:', e.message))

await page.goto(BASE, { waitUntil: 'networkidle' })
await page.waitForTimeout(3500)

// ---------- 截图 1：LLM 模式入口 ----------
await page.screenshot({ path: `${OUT}/01-llm-mode-entry.png` })
log('shot 01: LLM 模式入口')

// 校验模式按钮真的存在
const modeButtons = await page.locator('text=LLM 围观').count()
log('LLM 围观 按钮数 =', modeButtons)
if (modeButtons === 0) throw new Error('未找到「LLM 围观」模式按钮')

// 切到 LLM 模式并展开势力多选
await page.locator('button:has-text("LLM 围观")').first().click()
await page.waitForTimeout(400)
await page.locator('button:has-text("参战势力")').first().click()
await page.waitForTimeout(600)
await page.screenshot({ path: `${OUT}/02-llm-faction-picker.png` })
log('shot 02: 势力多选面板')

// 先清空再选 3 方（曹操/刘备/孙坚），避免与初始化回填的勾选态互相抵消
await page.locator('button:has-text("清空（= 全部）")').first().click()
await page.waitForTimeout(400)
for (const name of ['曹操', '刘备', '孙坚']) {
  const chip = page.locator(`button:has-text("${name}")`).first()
  if (await chip.count()) await chip.click()
  await page.waitForTimeout(250)
}
const selLabel = await page.locator('text=/参战势力\\s*\\d+ 方/').first().innerText()
log('已选势力 =', JSON.stringify(selLabel.replace(/\s+/g, ' ')))
if (!/3 方/.test(selLabel)) throw new Error(`期望选中 3 方，实际="${selLabel}"`)
await page.screenshot({ path: `${OUT}/03-llm-3-factions-selected.png` })
log('shot 03: 已选 3 方')

// 关掉下拉，点「重开一局」
await page.keyboard.press('Escape')
await page.mouse.click(900, 500)
await page.waitForTimeout(500)
await page.locator('button:has-text("重开一局")').first().click()
log('已点击「重开一局」，等待后端建局...')
await page.waitForTimeout(9000)
await page.screenshot({ path: `${OUT}/04-after-restart-llm.png` })
log('shot 04: 重开后的 LLM 局')

// 读取后端回报的真实 LLM 状态
const badge = await page.locator('text=模型在跑').count()
const badgeCli = await page.locator('text=规则 AI').count()
log('状态徽标: 模型在跑 =', badge, '/ 规则 AI =', badgeCli)

// 直接查后端接口确认真的建了 LLMPlayer（不只信前端徽标）
const apiState = await page.evaluate(async () => {
  const r = await fetch('/api/state')
  return r.json()
})
log('后端 llm_active =', apiState.llm_active, '| llm_model =', apiState.llm_model,
    '| llm_factions =', JSON.stringify(apiState.llm_factions))
if (apiState.llm_active !== true) throw new Error('后端未真正启用 LLM（llm_active != true）')
if (!Array.isArray(apiState.llm_factions) || apiState.llm_factions.length !== 3) {
  throw new Error(`期望 3 方参战，实际 ${JSON.stringify(apiState.llm_factions)}`)
}

// ---------- 推进一回合（验证中文命令 + 思考中反馈） ----------
await page.locator('text=决策').first().click()
await page.waitForTimeout(500)
await page.screenshot({ path: `${OUT}/05-reasoning-empty-guide.png` })
log('shot 05: 决策 tab（开局引导）')

log('点击「下一回合」——LLM 需约 30 秒')
await page.locator('button:has-text("下一回合")').first().click()
await page.waitForTimeout(2500)
// 思考中反馈
const thinkingTxt = await page.locator('text=AI 正在思考中').count()
log('思考中提示可见 =', thinkingTxt)
await page.screenshot({ path: `${OUT}/06-thinking-feedback.png` })
log('shot 06: 长耗时反馈')

// 等这一回合算完（最多 180s）
for (let i = 0; i < 90; i++) {
  await page.waitForTimeout(2000)
  const stillThinking = await page.locator('text=AI 正在思考中').count()
  if (stillThinking === 0) { log('回合完成，用时约', (i + 1) * 2, '秒'); break }
}
await page.waitForTimeout(1500)

// ---------- 截图 2：决策 tab 中文命令 ----------
await page.locator('text=决策').first().click()
await page.waitForTimeout(1200)
await page.screenshot({ path: `${OUT}/07-reasoning-chinese-commands.png` })
log('shot 07: 决策 tab 中文命令')

// 校验：页面上不应再出现裸类名
const bodyText = await page.locator('body').innerText()
const leaked = ['DevelopCommand', 'AttackCommand', 'MessageCommand', 'RecruitCommand',
  'ExploreCommand', 'RewardCommand', 'ProposeAllianceCommand', 'DeclareWarCommand']
const found = leaked.filter((c) => bodyText.includes(c))
log('泄漏的裸类名 =', found.length ? found.join(',') : '无')
const cn = ['发展', '进攻', '通使', '征兵', '探索', '赏赐', '结盟', '宣战'].filter((c) => bodyText.includes(c))
log('可见中文命令 =', cn.join('/') || '无')

// ---------- 截图 3：战报 tab 分类 ----------
await page.locator('text=战报').first().click()
await page.waitForTimeout(1000)
await page.screenshot({ path: `${OUT}/08-battle-log-categorized.png` })
log('shot 08: 战报分类')

// ---------- 降级提示条：用无 key 的后端实例验证 ----------
const DEGRADED = process.argv[4]
if (DEGRADED) {
  log('切换到无 key 后端验证降级提示:', DEGRADED)
  const p2 = await ctx.newPage()
  await p2.goto(DEGRADED, { waitUntil: 'networkidle' })
  await p2.waitForTimeout(3000)
  await p2.locator('button:has-text("LLM 围观")').first().click()
  await p2.waitForTimeout(300)
  await p2.locator('button:has-text("重开一局")').first().click()
  await p2.waitForTimeout(9000)
  const hasBanner = await p2.locator('text=LLM 未生效').count()
  log('降级提示条可见 =', hasBanner)
  await p2.screenshot({ path: `${OUT}/09-degrade-banner.png` })
  log('shot 09: 降级提示条')
  if (hasBanner === 0) throw new Error('静默回退时未显示降级提示条')
  await p2.close()
}

await browser.close()
log('DONE')
