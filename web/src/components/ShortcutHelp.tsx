import type { CSSProperties } from 'react'
import panelFrame from '../assets/ui/panel-frame.svg'

/**
 * 快捷键说明面板（审计 §4-7）
 *
 * 此前快捷键只以「按钮上一行小字」零散提示，用户看不到全貌。这里集中成一张
 * 「?」可随时调出的说明卡，并列出全部已实现的快捷键（与 App.tsx 的 keydown 一一对应）。
 * 说明面板本身可点背景关闭，也可按 Esc / ? 关闭。
 */
const GROUPS: { title: string; items: { keys: string[]; desc: string }[] }[] = [
  {
    title: '回合',
    items: [
      { keys: ['空格'], desc: '推进下一回合（自动推进中不可用）' },
      { keys: ['A'], desc: '开 / 关自动推进（800ms 一回合）' },
    ],
  },
  {
    title: '面板',
    items: [
      { keys: ['1'], desc: '势力' },
      { keys: ['2'], desc: '城市' },
      { keys: ['3'], desc: '武将' },
      { keys: ['4'], desc: '外交' },
      { keys: ['5'], desc: '数据' },
      { keys: ['6'], desc: '事件' },
      { keys: ['7'], desc: '战报' },
      { keys: ['8'], desc: '决策' },
    ],
  },
  {
    title: '视图',
    items: [
      { keys: ['?', 'H'], desc: '打开 / 关闭本说明' },
      { keys: ['Esc'], desc: '关闭弹层 / 取消选中城池、军队' },
      { keys: ['滚轮'], desc: '以鼠标为中心缩放地图' },
      { keys: ['拖拽'], desc: '平移地图' },
      { keys: ['单击城池'], desc: '打开城池详情卡并居中' },
      { keys: ['单击军队'], desc: '打开军队详情卡' },
    ],
  },
]

export function ShortcutHelp({ onClose }: { onClose: () => void }) {
  return (
    <div style={styles.backdrop} onClick={onClose} role="dialog" aria-modal="true" aria-label="快捷键说明">
      <div style={styles.panel} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <span className="font-serif" style={styles.title}>
            <i className="fa-solid fa-keyboard" style={{ marginRight: '8px' }}></i>
            快捷键
          </span>
          <button style={styles.close} onClick={onClose} aria-label="关闭" title="关闭（Esc）">
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>

        <div style={styles.body}>
          {GROUPS.map((g) => (
            <div key={g.title} style={styles.group}>
              <div style={styles.groupTitle}>{g.title}</div>
              {g.items.map((it, i) => (
                <div key={i} style={styles.row}>
                  <span style={styles.keys}>
                    {it.keys.map((k) => (
                      <kbd key={k} style={styles.kbd}>{k}</kbd>
                    ))}
                  </span>
                  <span style={styles.desc}>{it.desc}</span>
                </div>
              ))}
            </div>
          ))}
        </div>

        <div style={styles.footer}>
          提示：在输入框 / 下拉框中打字时，快捷键会自动让位，不会误触。
        </div>
      </div>
    </div>
  )
}

const styles: Record<string, CSSProperties> = {
  backdrop: {
    position: 'fixed', inset: 0, zIndex: 200,
    background: 'rgba(6, 6, 14, 0.6)', backdropFilter: 'blur(3px)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  panel: {
    width: '460px', maxWidth: '92vw', maxHeight: '86vh', overflowY: 'auto',
    background: 'rgba(16, 16, 30, 0.98)',
    border: '8px solid transparent',
    borderImage: `url("${panelFrame}") 8 / 8px / 0 stretch`,
    boxShadow: '0 16px 48px rgba(0, 0, 0, 0.6)',
    padding: '14px 16px', boxSizing: 'border-box',
  },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' },
  title: { color: 'var(--gold)', fontSize: '17px', fontWeight: 700, display: 'flex', alignItems: 'center' },
  close: { background: 'transparent', border: 'none', color: 'var(--text-2)', cursor: 'pointer', fontSize: '14px', padding: '2px 6px' },
  body: { display: 'flex', flexDirection: 'column', gap: '12px' },
  group: { display: 'flex', flexDirection: 'column', gap: '5px' },
  groupTitle: {
    color: 'var(--text-muted)', fontSize: '11px', letterSpacing: '1px',
    borderBottom: '1px solid rgba(255,255,255,0.07)', paddingBottom: '4px', marginBottom: '2px',
  },
  row: { display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12px' },
  keys: { display: 'inline-flex', gap: '4px', flexShrink: 0, minWidth: '132px' },
  kbd: {
    display: 'inline-block', minWidth: '20px', textAlign: 'center',
    padding: '2px 7px', borderRadius: '5px',
    background: 'rgba(200, 168, 90, 0.14)', border: '1px solid rgba(200, 168, 90, 0.4)',
    color: '#e8c877', fontSize: '11px', fontWeight: 600, fontFamily: 'inherit',
  },
  desc: { color: '#b8b3aa' },
  footer: {
    marginTop: '14px', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.07)',
    color: 'var(--text-muted)', fontSize: '11px', lineHeight: 1.6,
  },
}
