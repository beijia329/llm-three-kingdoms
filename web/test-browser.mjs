import { chromium } from 'playwright'
import { spawn } from 'child_process'
import { setTimeout } from 'timers/promises'

const ROOT = '/Users/dongsheng/Documents/llm-sanguo-project'
const PYTHON = '/Library/Frameworks/Python.framework/Versions/3.12/bin/python3'

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

  // 拦截外部瓦片请求，避免 networkidle 被卡
  await page.route('https://*.basemaps.cartocdn.com/**', (route) => route.abort('blockedbyclient'))
  await page.route('https://cdnjs.cloudflare.com/**', (route) => route.continue())

  console.log('访问 http://localhost:5173 ...')
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
  await setTimeout(2000)

  const turn1 = await page.evaluate(() => document.body.innerText)
  console.log('页面文本片段:', turn1.slice(0, 200).replace(/\n/g, ' '))

  console.log('截图: initial.png')
  await page.screenshot({ path: `${ROOT}/web/initial.png`, fullPage: false })

  console.log('按空格键下一回合...')
  await page.keyboard.press('Space')
  await setTimeout(1500)

  console.log('截图: after-turn.png')
  await page.screenshot({ path: `${ROOT}/web/after-turn.png`, fullPage: false })

  const turn2 = await page.evaluate(() => document.body.innerText)
  console.log('回合后文本片段:', turn2.slice(0, 200).replace(/\n/g, ' '))

  if (errors.length === 0) {
    console.log('✓ 浏览器测试通过，无页面错误')
  } else {
    console.log(`✗ 发现 ${errors.length} 个页面错误`)
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
