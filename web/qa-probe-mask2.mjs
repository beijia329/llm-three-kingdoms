import { chromium } from 'playwright'
import fs from 'node:fs'
const f = fs.readdirSync('web/dist/assets').find(n=>/^index-.*\.js$/.test(n))
const js = fs.readFileSync('web/dist/assets/'+f,'utf8')
const m = js.match(/"data:image\/svg\+xml,([^"]{0,900})"/) || js.match(/'data:image\/svg\+xml,([^']{0,900})'/)
const uri = m ? 'data:image/svg+xml,'+m[1] : null
console.log('URI 长度 =', uri ? uri.length : 0, '| 含单引号 =', uri ? uri.includes("'") : 'n/a')
console.log('URI 片段 =', uri ? uri.slice(0,120) : '(未找到)')
const b=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true})
const p=await b.newPage({viewport:{width:400,height:120}})
await p.setContent('<div id="d" style="width:60px;height:60px;background:#c02a18"></div>')
const res=await p.evaluate((uri)=>{
  const d=document.getElementById('d')
  const test=(v)=>{ d.style.maskImage=''; d.style.maskImage=v; return d.style.maskImage ? 'SET' : 'DROPPED' }
  return { unquoted: test('url('+uri+')'), quoted: test('url("'+uri+'")'), supportsUnq: CSS.supports('mask-image','url('+uri+')') }
}, uri)
console.log('测试结果 =', JSON.stringify(res))
await b.close()
