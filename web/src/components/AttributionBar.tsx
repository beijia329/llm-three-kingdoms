import { useState } from 'react'

/**
 * 素材署名条（阶段A 2026-10-03）
 *
 * 🔴 这是**许可义务**，不是装饰：game-icons.net 是 CC BY 3.0、Font Awesome Free 是
 *    CC BY 4.0 —— 两者都要求「在产物中可见地署名」。所以这里是一条**始终可见**的页脚，
 *    点击可展开完整署名（作者名 + 许可 + 链接）。
 *
 * 维护约定：**新增任何第三方素材时，必须同步往下面 CREDITS 里加一条**，
 * 否则又会变成「写了没接线」的假署名。
 */
interface Credit {
  name: string
  detail: string
  license: string
  url: string
}

const CREDITS: Credit[] = [
  {
    name: 'game-icons.net',
    detail: '图标：Lorc、Delapouite、Skoll 等',
    license: 'CC BY 3.0',
    url: 'https://game-icons.net',
  },
  {
    name: 'Font Awesome Free 6.5.1',
    detail: '界面图标',
    license: 'Icons CC BY 4.0 · Fonts OFL 1.1 · Code MIT',
    url: 'https://fontawesome.com/license/free',
  },
  {
    name: 'Noto Sans SC',
    detail: '正文字体',
    license: 'SIL OFL 1.1',
    url: 'https://fonts.google.com/noto',
  },
  {
    // 2026-10-03 接入：城池详情卡 / 快捷键面板的九宫格边框（web/src/assets/ui/panel-frame.svg）。
    // CC0 **不要求**署名，此处列出属礼节性致谢 —— 但它是**真的用在了产物里**的素材，
    // 与下面那条"未接入故不列"的说明并不矛盾。
    name: 'Kenney UI Pack',
    detail: '面板九宫格边框（改色）',
    license: 'CC0 1.0',
    url: 'https://kenney.nl/assets/ui-pack',
  },
  // ⚠️ 这里**只列真正在产物里被使用的素材**——本组件是对外的**许可声明**面。
  //    Kenney 六角地块（CC0）仍**未接入**（见 docs/design/art-asset-plan.md §7），
  //    素材仅作素材库保留、且 CC0 不要求署名，故**刻意不列**：在"声明谁被使用了"的地方
  //    写一个未使用的素材，等于一句不实陈述，还会让读者分不清哪些署名是真有义务的。
  //    台账（含未接入素材）见 assets/art/ATTRIBUTION.md。
]

export function AttributionBar() {
  const [open, setOpen] = useState(false)

  return (
    <div style={styles.wrap}>
      {open && (
        <div style={styles.panel} role="region" aria-label="素材署名详情">
          {CREDITS.map((c) => (
            <div key={c.name} style={styles.row}>
              <a href={c.url} target="_blank" rel="noopener noreferrer" style={styles.link}>
                {c.name}
              </a>
              <span style={styles.detail}>{c.detail}</span>
              <span style={styles.license}>{c.license}</span>
            </div>
          ))}
          <div style={styles.note}>
            完整清单见仓库 <code>assets/art/ATTRIBUTION.md</code>
          </div>
        </div>
      )}
      <div style={styles.bar}>
        <i className="fa-solid fa-scroll" style={{ color: '#8a86a0', fontSize: '9px', marginRight: '6px' }}></i>
        <span style={styles.summary}>
          素材署名：game-icons.net（CC BY 3.0）· Font Awesome（CC BY 4.0）· Noto Sans SC（OFL）· Kenney（CC0）
        </span>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          style={styles.toggle}
        >
          {open ? '收起' : '详情'}
          <i className={`fa-solid fa-chevron-${open ? 'down' : 'up'}`} style={{ marginLeft: '4px', fontSize: '8px' }}></i>
        </button>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  wrap: {
    flexShrink: 0,
    width: '100%',
    position: 'relative',
    zIndex: 30,
  },
  bar: {
    height: '22px',
    display: 'flex',
    alignItems: 'center',
    padding: '0 12px',
    backgroundColor: 'rgba(14, 14, 26, 0.96)',
    borderTop: '1px solid rgba(255, 255, 255, 0.06)',
  },
  summary: {
    flex: 1,
    color: '#8a86a0',
    fontSize: '10px',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  toggle: {
    flexShrink: 0,
    background: 'none',
    border: 'none',
    color: '#d4a84b',
    fontSize: '10px',
    fontFamily: 'inherit',
    cursor: 'pointer',
    padding: '2px 4px',
  },
  panel: {
    position: 'absolute',
    bottom: '22px',
    left: 0,
    right: 0,
    padding: '10px 14px',
    backgroundColor: 'rgba(14, 14, 26, 0.98)',
    borderTop: '1px solid rgba(212, 168, 75, 0.35)',
    boxShadow: '0 -8px 24px rgba(0,0,0,0.45)',
  },
  row: {
    display: 'flex',
    alignItems: 'baseline',
    gap: '10px',
    padding: '3px 0',
    fontSize: '11px',
  },
  link: {
    color: '#d4a84b',
    textDecoration: 'none',
    minWidth: '140px',
  },
  detail: {
    color: '#a8a29a',
    flex: 1,
  },
  license: {
    color: '#8a86a0',
    whiteSpace: 'nowrap',
  },
  note: {
    marginTop: '6px',
    paddingTop: '6px',
    borderTop: '1px solid rgba(255,255,255,0.06)',
    color: '#8a86a0',
    fontSize: '10px',
  },
}
