import { chromium } from 'playwright'
const CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const b=await chromium.launch({executablePath:CHROME,headless:true})
const p=await b.newPage({viewport:{width:1920,height:1080}})
await p.goto('http://127.0.0.1:8011',{waitUntil:'networkidle'}); await p.waitForTimeout(4500)
const out=await p.evaluate(()=>{
  const city=[...document.querySelectorAll('[data-city-id]')][0]
  const spans=city?[...city.querySelectorAll('span')]:[]
  const info=spans.slice(0,4).map(s=>({aria:s.getAttribute('aria-hidden'),hasMaskAttr:/mask-image/.test(s.getAttribute('style')||''),style:(s.getAttribute('style')||'').slice(0,170)}))
  return {cityId:city?.getAttribute('data-city-id'), info}
})
console.log(JSON.stringify(out,null,2))
await b.close()
