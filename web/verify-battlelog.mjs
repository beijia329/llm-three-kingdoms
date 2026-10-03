// 专项验证：战报 tab 分类（建国刷屏 vs 真实战斗）
import { chromium } from 'playwright'
const BASE = process.argv[2] || 'http://127.0.0.1:8010'
const OUT = process.argv[3] || '/tmp/sanguo-v31'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 950 }, deviceScaleFactor: 2 })
await page.goto(BASE, { waitUntil: 'networkidle' })
await page.waitForTimeout(3500)
await page.locator('text=战报').first().click()
await page.waitForTimeout(1200)

// 折叠态：战斗应置顶可见，建国折叠在下方
const battleFirst = await page.evaluate(() => {
  const heads = [...document.querySelectorAll('div')].filter(d => d.textContent?.trim() === '战事')
  if (!heads.length) return 'no-battle-head'
  const battleBox = heads[0].getBoundingClientRect()
  const kingdomFold = [...document.querySelectorAll('button')].find(b => b.textContent?.includes('建国'))
  if (!kingdomFold) return 'no-kingdom-fold'
  return battleBox.top < kingdomFold.getBoundingClientRect().top ? 'battle-on-top' : 'kingdom-on-top'
})
console.log('[verify] 战事置顶 =', battleFirst)
const foldTxt = await page.locator('button:has-text("建国")').first().innerText()
console.log('[verify] 建国折叠条 =', JSON.stringify(foldTxt.replace(/\s+/g, ' ')))
await page.screenshot({ path: `${OUT}/08-battle-log-categorized.png` })
console.log('[verify] shot 08: 战报分类（折叠态）')

// 展开建国分类
await page.locator('button:has-text("建国")').first().click()
await page.waitForTimeout(900)
const kingdomCount = await page.locator('text=/称kingdom/').count()
console.log('[verify] 展开后建国事件数 =', kingdomCount)
await page.screenshot({ path: `${OUT}/08b-battle-log-kingdom-expanded.png` })
console.log('[verify] shot 08b: 建国分类展开')
await browser.close()
console.log('[verify] DONE')
