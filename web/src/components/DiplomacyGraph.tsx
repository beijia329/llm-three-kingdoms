import { useMemo, useState } from 'react'
import type { FactionRelation, GameState } from '../types'
import { FACTION_COLORS, FACTION_GLYPH, FACTIONS, contrastText, UI_COLORS } from '../theme'

/**
 * 外交关系可视化（v4.1 · 阶段D）
 *
 * 背景：README 把「外交博弈：信使系统、正式盟约、流言策反、背盟欺诈」列为头部特性，
 * 但界面上原来只有一个**列表** + 一个**没有行列标题**的 24 格色块网格——头号卖点在界面上看不见。
 * 本文件补两样东西：
 *   1. `RelationGraph`  —— 环形节点图（势力间连线，颜色=战/盟/和），可点选聚焦单个势力；
 *   2. `RelationMatrix` —— 12×12 带行列标的完整矩阵，**全部 66 对**关系（含中立）都能定位。
 *
 * 🔴 三个实测坑（都已处理，勿踩回去）：
 *   a. `neutral` 会作为**关系的一方**出现（打中立城时生成，实测 6 回合后节点数 13 = 12+neutral）。
 *      它不是势力（没有君主/LLM/领地），画成第 13 个节点是错的 → 这里按 id 排除。
 *   b. `neutral` **既是势力 id 又是状态值**（status ∈ {war,neutral,alliance,truce}）。两个命名空间
 *      撞名，本文件用 `NON_FACTION_ID`（id）与 `status`（状态）分开命名，禁止混用。
 *   c. **开局是 66 对全 neutral、trust 全 50**（实测 turn 1）。若无条件画 66 条灰线，
 *      用户第一眼看到一坨一模一样的线，比列表还难读 → 中立关系默认不画（只画 战/盟/和）。
 */

/** 关系状态配色（与列表标签共用同一事实源，避免两处各写一份） */
export const REL_STATUS_COLOR: Record<string, string> = {
  war: '#c85046',
  neutral: UI_COLORS.textSecondary,
  alliance: '#5ab464',
  truce: '#d4a84b',
}

/** 单字标签（矩阵/列表里用） */
export const REL_STATUS_LABEL: Record<string, string> = {
  war: '战',
  neutral: '中',
  alliance: '盟',
  truce: '和',
}

/** 全称（图例/提示里用） */
export const REL_STATUS_NAME: Record<string, string> = {
  war: '交战',
  neutral: '中立',
  alliance: '同盟',
  truce: '停战',
}

/** `neutral` 是"中立城"的伪势力 id，不是势力（见文件头 a/b 条） */
const NON_FACTION_ID = 'neutral'

export interface RelEdge {
  a: string
  b: string
  status: string
  trust: number
}

/** 关系强度 0..1：**战争越不信任越强**；**同盟/停战越信任越强**。
 *  只驱动线宽与不透明度，不改语义——所以图例必须写清楚（见 RelationGraph 下方）。 */
export function relIntensity(status: string, trust: number): number {
  const t = Math.max(0, Math.min(100, trust || 0)) / 100
  return status === 'war' ? 1 - t : t
}

function factionName(id: string): string {
  return FACTIONS[id] || (id === NON_FACTION_ID ? '中立' : id)
}

/** 从 state 抽出「真实势力节点 + 非中立关系边」 */
function useRelationModel(state: GameState) {
  return useMemo(() => {
    const nodes = new Set<string>()
    // 节点来源一：本局真实存在的势力（faction_stats 的键）
    for (const f of Object.keys(state.faction_stats || {})) {
      if (f !== NON_FACTION_ID) nodes.add(f)
    }
    const edges: RelEdge[] = []
    for (const r of state.faction_relations || []) {
      const a = r.faction_a
      const b = r.faction_b
      if (!a || !b) continue
      // 含中立城的"关系"不是势力间关系 → 整条丢掉，别让 neutral 变成第 13 个节点
      if (a === NON_FACTION_ID || b === NON_FACTION_ID) continue
      nodes.add(a)
      nodes.add(b)
      // 开局 66 对全 neutral：不画（见文件头 c 条）
      if (r.status === 'neutral') continue
      edges.push({ a, b, status: r.status, trust: r.trust })
    }
    // 稳定顺序：先按 theme 里的势力顺序（汉室在前），其余按字典序 —— 保证重渲染时节点不跳位
    const canonical = Object.keys(FACTION_GLYPH)
    const list = [...nodes].sort((x, y) => {
      const ix = canonical.indexOf(x)
      const iy = canonical.indexOf(y)
      if (ix >= 0 && iy >= 0) return ix - iy
      if (ix >= 0) return -1
      if (iy >= 0) return 1
      return x.localeCompare(y)
    })
    return { nodes: list, edges }
  }, [state.faction_relations, state.faction_stats])
}

function GlyphBadge({ faction, size = 18, dim = false }: { faction: string; size?: number; dim?: boolean }) {
  const color = FACTION_COLORS[faction] || '#888'
  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: 4,
        background: color,
        color: contrastText(color),
        fontSize: size * 0.6,
        fontWeight: 700,
        lineHeight: 1,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: '1px solid rgba(0,0,0,0.45)',
        opacity: dim ? 0.35 : 1,
        flex: '0 0 auto',
      }}
    >
      {FACTION_GLYPH[faction] || '?'}
    </span>
  )
}

/** 图例（图与矩阵共用） */
export function RelationLegend() {
  return (
    <div style={{ display: 'flex', gap: 10, fontSize: 11, color: UI_COLORS.textSecondary, flexWrap: 'wrap' }}>
      {(['war', 'alliance', 'truce'] as const).map((s) => (
        <span key={s} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 9, height: 9, borderRadius: 2, background: REL_STATUS_COLOR[s], display: 'inline-block' }} />
          {REL_STATUS_LABEL[s]}
          {REL_STATUS_NAME[s]}
        </span>
      ))}
      <span style={{ color: '#6f6b80' }}>（粗细/深浅 = 关系强度）</span>
    </div>
  )
}

const SIZE = 276
const R_RING = 103
const R_NODE = 13

/** 环形关系图。点势力节点 = 只看它的关系（再点取消）。 */
export function RelationGraph({ state }: { state: GameState }) {
  const { nodes, edges } = useRelationModel(state)
  const [focus, setFocus] = useState<string | null>(null)
  const C = SIZE / 2

  const pos = useMemo(() => {
    const p: Record<string, { x: number; y: number }> = {}
    nodes.forEach((f, i) => {
      const ang = (Math.PI * 2 * i) / Math.max(1, nodes.length) - Math.PI / 2
      p[f] = { x: C + R_RING * Math.cos(ang), y: C + R_RING * Math.sin(ang) }
    })
    return p
  }, [nodes, C])

  const neighbours = useMemo(() => {
    const m = new Map<string, Set<string>>()
    for (const e of edges) {
      if (!m.has(e.a)) m.set(e.a, new Set())
      if (!m.has(e.b)) m.set(e.b, new Set())
      m.get(e.a)!.add(e.b)
      m.get(e.b)!.add(e.a)
    }
    return m
  }, [edges])

  if (nodes.length === 0) {
    return <div style={{ fontSize: 12, color: '#8a86a0', padding: '12px 0' }}>暂无外交关系数据</div>
  }

  return (
    <div>
      <svg width={SIZE} height={SIZE} style={{ display: 'block', margin: '0 auto' }} role="img" aria-label="势力外交关系图">
        {/* 边：只在「无聚焦」或「与聚焦势力相关」时绘制 */}
        {edges
          .filter((e) => !focus || e.a === focus || e.b === focus)
          .map((e, i) => {
            const p = pos[e.a]
            const q = pos[e.b]
            if (!p || !q) return null
            const inten = relIntensity(e.status, e.trust)
            return (
              <line
                key={`${e.a}-${e.b}-${i}`}
                x1={p.x}
                y1={p.y}
                x2={q.x}
                y2={q.y}
                stroke={REL_STATUS_COLOR[e.status] || UI_COLORS.textSecondary}
                strokeWidth={1.1 + 2.6 * inten}
                strokeOpacity={focus ? 0.95 : 0.35 + 0.5 * inten}
                strokeLinecap="round"
              />
            )
          })}

        {/* 节点 */}
        {nodes.map((f) => {
          const p = pos[f]
          const color = FACTION_COLORS[f] || '#888'
          const active = focus === f
          const related = focus ? neighbours.get(focus)?.has(f) : false
          const dim = !!focus && !active && !related
          return (
            <g
              key={f}
              onClick={() => setFocus(active ? null : f)}
              style={{ cursor: 'pointer' }}
              role="button"
              aria-label={`${factionName(f)}（点击只看它的关系）`}
            >
              <title>{factionName(f)}</title>
              {active && <circle cx={p.x} cy={p.y} r={R_NODE + 4} fill="none" stroke="#d4a84b" strokeWidth={2} />}
              <circle
                cx={p.x}
                cy={p.y}
                r={R_NODE}
                fill={color}
                stroke="#12101c"
                strokeWidth={1.5}
                opacity={dim ? 0.22 : 1}
              />
              <text
                x={p.x}
                y={p.y + 4}
                textAnchor="middle"
                fontSize={11}
                fontWeight={700}
                fill={contrastText(color)}
                opacity={dim ? 0.25 : 1}
                style={{ pointerEvents: 'none' }}
              >
                {FACTION_GLYPH[f] || '?'}
              </text>
            </g>
          )
        })}
      </svg>

      {focus ? (
        <div style={{ fontSize: 11, color: '#d4a84b', textAlign: 'center', marginTop: 2 }}>
          只看 <b>{factionName(focus)}</b>：{edges.filter((e) => e.a === focus || e.b === focus).length} 条关系
          <button
            type="button"
            onClick={() => setFocus(null)}
            style={{ marginLeft: 8, background: 'none', border: 'none', color: '#8a86a0', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            取消
          </button>
        </div>
      ) : (
        <div style={{ fontSize: 11, color: '#8a86a0', textAlign: 'center', marginTop: 2 }}>
          {edges.length === 0
            ? '开局：12 方互不相犯（66 对关系全部中立）'
            : `共 ${edges.length} 条非中立关系 · 点势力可只看它`}
        </div>
      )}

      <div style={{ marginTop: 8 }}>
        <RelationLegend />
      </div>
    </div>
  )
}

const CELL = 20

/** 12×12 完整关系矩阵（含中立）。原来的"关系矩阵"只有 24 个**无行列标**的色块，
 *  根本定位不到是哪一对——这里给每一行/列都挂上势力单字徽标。 */
export function RelationMatrix({ state }: { state: GameState }) {
  const { nodes } = useRelationModel(state)

  const lookup = useMemo(() => {
    const m = new Map<string, FactionRelation>()
    for (const r of state.faction_relations || []) {
      if (r.faction_a === NON_FACTION_ID || r.faction_b === NON_FACTION_ID) continue
      m.set(`${r.faction_a}|${r.faction_b}`, r)
      m.set(`${r.faction_b}|${r.faction_a}`, r)
    }
    return m
  }, [state.faction_relations])

  if (nodes.length === 0) {
    return <div style={{ fontSize: 12, color: '#8a86a0' }}>暂无关系数据</div>
  }

  return (
    <div style={{ display: 'inline-block' }}>
      {/* 表头行 */}
      <div style={{ display: 'flex' }}>
        <div style={{ width: CELL, height: CELL }} />
        {nodes.map((f) => (
          <div key={`h-${f}`} style={{ width: CELL, height: CELL, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <GlyphBadge faction={f} size={CELL - 4} />
          </div>
        ))}
      </div>
      {/* 数据行 */}
      {nodes.map((row) => (
        <div key={`r-${row}`} style={{ display: 'flex' }}>
          <div style={{ width: CELL, height: CELL, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <GlyphBadge faction={row} size={CELL - 4} />
          </div>
          {nodes.map((col) => {
            if (row === col) {
              return <div key={`c-${row}-${col}`} style={{ width: CELL, height: CELL, background: 'rgba(255,255,255,0.04)' }} />
            }
            const rel = lookup.get(`${row}|${col}`)
            const status = rel?.status || 'neutral'
            const trust = rel?.trust ?? 0
            const inten = rel ? relIntensity(status, trust) : 0
            const color = REL_STATUS_COLOR[status] || UI_COLORS.textSecondary
            // 中立格压到很浅：66 对里大部分是中立，若同色会淹没真正的战/盟
            const alpha = status === 'neutral' ? 0.13 : 0.3 + 0.6 * inten
            return (
              <div
                key={`c-${row}-${col}`}
                title={`${factionName(row)} ↔ ${factionName(col)}：${REL_STATUS_NAME[status] || status}${rel ? `（信任 ${trust}）` : ''}`}
                style={{
                  width: CELL,
                  height: CELL,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 10,
                  fontWeight: status === 'neutral' ? 400 : 700,
                  color: status === 'neutral' ? '#6f6b80' : '#12101c',
                  background: status === 'neutral' ? 'transparent' : color,
                  opacity: status === 'neutral' ? 1 : alpha,
                  outline: status === 'neutral' ? '1px solid rgba(255,255,255,0.05)' : 'none',
                  outlineOffset: -1,
                }}
              >
                {status === 'neutral' ? '' : REL_STATUS_LABEL[status]}
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}

/** 当前最强的 N 条**非中立**关系（给列表用：一句话说出"谁和谁在打 / 谁和谁结盟"）。
 *  观战模式下原来列表取 `relations.slice(0,12)` → 全是「汉室↔X」那 12 条，看不出战局，
 *  这里改成按强度排序、且排除中立与中立城。返回原对象，方便复用现有渲染。 */
export function topRelations(state: GameState, n = 8): FactionRelation[] {
  const out: FactionRelation[] = []
  for (const r of state.faction_relations || []) {
    if (r.faction_a === NON_FACTION_ID || r.faction_b === NON_FACTION_ID) continue
    if (r.status === 'neutral') continue
    out.push(r)
  }
  return out
    .sort((x, y) => relIntensity(y.status, y.trust) - relIntensity(x.status, x.trust))
    .slice(0, n)
}

export { NON_FACTION_ID, factionName as relFactionName }
