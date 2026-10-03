import { FACTION_COLORS, FACTION_GLYPH, contrastText } from '../theme'

/**
 * 势力单字徽标（可访问性：非颜色线索）
 *
 * 红绿色盲模拟下势力色最小 ΔE 仅 6.8（可靠区分需 >10），所以颜色之外必须再加一层线索。
 * 这里把「势力色底 + 姓氏单字」做成一个小徽标：色盲/灰度/小屏都能认出是谁。
 * 见 docs/art/2026-10-colorblind-non-color-cues.md。
 *
 * 前景色按背景亮度自动取深/浅（`contrastText`），保证在亮黄「张」、浅紫「焉」上也读得出。
 */
export function FactionBadge({ faction, size = 18 }: { faction: string; size?: number }) {
  const glyph = FACTION_GLYPH[faction]
  if (!glyph) return null
  const bg = FACTION_COLORS[faction] || '#888888'
  return (
    <span
      aria-hidden
      title={glyph}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        flexShrink: 0,
        borderRadius: `${Math.round(size * 0.22)}px`,
        backgroundColor: bg,
        color: contrastText(bg),
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: `${Math.round(size * 0.62)}px`,
        fontWeight: 700,
        lineHeight: 1,
        border: '1px solid rgba(0,0,0,0.35)',
        fontFamily: '"Songti SC", "STSong", "SimSun", serif',
        boxShadow: '0 0 0 1px rgba(255,255,255,0.06) inset',
      }}
    >
      {glyph}
    </span>
  )
}
