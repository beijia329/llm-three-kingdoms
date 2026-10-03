import ReactDOM from 'react-dom/client'
import App from './App'

// [离线可用 2026-10-04] Font Awesome 由 CDN 改为本地依赖。
// 此前 index.html 从 cdnjs 引 all.min.css，断网/内网/代理掉线时图标全部渲染为 0 尺寸
// （实测 62/62 个 i.fa-solid 不可见）。本地化后所有 `fa-solid fa-xxx` 类名不变，
// 视觉零变化，且不再依赖外网。
import '@fortawesome/fontawesome-free/css/all.min.css'

ReactDOM.createRoot(document.getElementById('root')!).render(<App />)

