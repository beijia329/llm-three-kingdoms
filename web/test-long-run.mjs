import { chromium } from 'playwright'
import { spawn } from 'child_process'
import { setTimeout } from 'timers/promises'

const ROOT = '/Users/dongsheng/Documents/llm-sanguo-project'
const PYTHON = '/Library/Frameworks/Python.framework/Versions/3.12/bin/python3'
const TARGET_TURNS = 50

console.log('启动后端...')
const backend = spawn(PYTHON, ['-m', 'uvicorn', 'api.server:app', '--host', '127.0.0.1', '--port', '8000'], {
  cwd: ROOT,
  stdio: 'pipe',
})

console.log('启动前端 dev server...')
const frontend = spawn('npm', ['run', 'dev'], {
  cwd: `${ROOT}/web`,
  stdio: 'pipe',
})

await setTimeout(4000)

const errors = []
let browser

try {
  console.log('打开浏览器...')
  browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  page.on('pageerror', (err) => {
    console.error('页面 JS 错误:', err.message)
    errors.push(err.message)
  })
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      console.error('Console error:', msg.text())
      errors.push(msg.text())
    }
  })

  // 拦截外部瓦片请求，避免网络等待
  await page.route('https://*.basemaps.cartocdn.com/**', (route) => route.abort('blockedbyclient'))

  console.log('访问 http://localhost:5173 ...')
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
  await setTimeout(2000)

  // 获取初始回合
  const getTurn = async () => {
    const text = await page.evaluate(() => document.body.innerText)
    const match = text.match(/第 (\d+)\/\d+ 回合/)
    return match ? parseInt(match[1]) : 0
  }

  let startTurn = await getTurn()
  console.log(`初始回合: ${startTurn}`)

  // 切换到自动模式（快速推进）
  console.log('切换到自动模式...')
  await page.keyboard.press('a')
  await setTimeout(500)

  // 等待到达目标回合
  let currentTurn = startTurn
  const startTime = Date.now()
  while (currentTurn < startTurn + TARGET_TURNS) {
    await setTimeout(2000)
    currentTurn = await getTurn()
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
    process.stdout.write(`\r回合 ${currentTurn} / ${startTurn + TARGET_TURNS} | 已运行 ${elapsed}s | 错误 ${errors.length} 个`)
  }

  console.log('\n')

  // 截图最终状态
  await page.screenshot({ path: `${ROOT}/web/long-run-final.png`, fullPage: false })

  // 检查内存（通过 Performance API）
  const memory = await page.evaluate(() => {
    // @ts-ignore
    const perf = performance?.memory
    return perf ? {
      usedJSHeapSize: Math.round(perf.usedJSHeapSize / 1024 / 1024),
      totalJSHeapSize: Math.round(perf.totalJSHeapSize / 1024 / 1024),
    } : null
  })

  if (memory) {
    console.log(`内存使用: ${memory.usedJSHeapSize}MB / ${memory.totalJSHeapSize}MB`)
  }

  if (errors.length === 0) {
    console.log(`✓ 长流程测试通过：${TARGET_TURNS} 回合无错误`)
  } else {
    console.log(`✗ 发现 ${errors.length} 个页面错误：`)
    errors.forEach((e, i) => console.log(`  ${i + 1}. ${e}`))
    process.exitCode = 1
  }
} catch (e) {
  console.error('测试异常:', e)
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  frontend.kill('SIGTERM')
  backend.kill('SIGTERM')
  await setTimeout(1000)
}
