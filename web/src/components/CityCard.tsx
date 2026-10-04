import { useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import type { City, GameState } from '../types'
import { FACTION_COLORS, FACTIONS, STAT_COLORS, UI_COLORS } from '../theme'
import { Hint } from './Tooltip'
import { FactionBadge } from './FactionBadge'
import panelFrame from '../assets/ui/panel-frame.svg'
import type { UseGameReturn } from '../hooks/useGame'

/**
 * 城池详情卡（战旗游戏基本元素 · 审计 §4-10）
 *
 * 点击地图/列表中的城市 → 弹出本卡，显示等级/守军/城墙/民心/金钱/粮草/驻守将领，
 * 并给出**可执行操作**。
 *
 * 🔴 关于操作的真实性（本轮头号纪律：「绝对不要做点了没反应的控件」）：
 *    后端 `POST /api/command`（WebSocket `{type:"command"}`）**真的**能执行
 *    `develop` / `recruit` / `attack` 三类命令，`game/engine.py` 会校验城池归属与兵力、
 *    真实改动状态，并把人类可读的 `description` 回执回来（实测：
 *    `成功征兵100人，消耗100金钱、200粮草`）。因此这里接的是**真命令**，不是占位。
 *
 *    ⚠️ 本作 Web 端是**纯观战**：`human_faction` 恒为 null，没有人类势力。
 *    所有操作以「该城所属势力」的名义下发，属于观战者的人为干预 —— 卡片顶部已明确标注，
 *    不让用户误以为这是"自己的回合"。做不到的操作（无相邻敌城 / 无可用将领）会**明确置灰并注明原因**。
 */

const DEVELOP_TYPES: { value: string; label: string; hint: string }[] = [
  { value: 'economy', label: '经济', hint: '提升金钱产出（消耗金钱）' },
  { value: 'military', label: '军事', hint: '提升城防/征兵效率（消耗金钱）' },
  { value: 'culture', label: '文化', hint: '提升民心与文化（消耗金钱）' },
]

function moraleColor(v: number): string {
  return v > 70 ? 'var(--green)' : v > 40 ? 'var(--gold)' : 'var(--red)'
}

export function CityCard({
  state,
  city,
  onClose,
  onSelectCity,
  runCommand,
  commandPending,
  commandResult,
}: {
  state: GameState
  city: City
  onClose: () => void
  onSelectCity: (id: string) => void
  runCommand: UseGameReturn['runCommand']
  commandPending: UseGameReturn['commandPending']
  commandResult: UseGameReturn['commandResult']
}) {
  const color = FACTION_COLORS[city.faction] || '#888888'
  const factionName = FACTIONS[city.faction] || city.faction
  const busy = commandPending !== null

  const [recruitTroops, setRecruitTroops] = useState(100)
  const [developType, setDevelopType] = useState('economy')
  const [atkTarget, setAtkTarget] = useState('')
  const [atkGeneral, setAtkGeneral] = useState('')
  const [atkTroops, setAtkTroops] = useState(() => Math.max(1, Math.floor(city.garrison / 2)))

  // 驻守将领（本城）优先，其次本势力任一城市中的可用将领（引擎支持"调将前来领兵"）。
  // 🔴 必须滤掉 `location` 不是己方城池的将领：他可能**正在带兵**（location = army id），
  //    引擎 `_execute_attack` 只接受 "位于己方城市" 的将领，否则回执
  //    「将领 X 不在 Y」—— 若不过滤，下拉里就会出现一个**选了必失败**的选项。
  const generals = useMemo(() => {
    const usable = (g: (typeof state.generals)[string]) =>
      !!g && !g.is_captured && state.cities[g.location]?.faction === city.faction
    const atCity = (city.generals || []).map((id) => state.generals[id]).filter(usable)
    const ownElsewhere = Object.values(state.generals).filter(
      (g) => g.faction === city.faction && usable(g),
    )
    const seen = new Set<string>()
    return [...atCity, ...ownElsewhere].filter((g) => {
      if (seen.has(g.id)) return false
      seen.add(g.id)
      return true
    })
  }, [city.generals, city.faction, state.generals, state.cities])

  // 出征目标：相邻且非本势力的城市
  const targets = useMemo(
    () => (city.neighbors || []).map((id) => state.cities[id]).filter((c) => c && c.faction !== city.faction),
    [city.neighbors, city.faction, state.cities],
  )

  const wallRatio = city.wall_max_hp > 0 ? city.wall_hp / city.wall_max_hp : 0
  const provinceName = city.province_id ? (state.provinces?.[city.province_id]?.name || city.province_id) : '—'
  // v4.2.0：州郡生产 modifier（如「京畿重地：金钱产出 +15%」）
  const provinceModifier = city.province_id ? state.provinces?.[city.province_id]?.modifier_desc : ''

  const attackDisabledReason =
    targets.length === 0 ? '无相邻敌城，无法出征'
      : generals.length === 0 ? '本势力暂无可用将领'
        : atkTroops <= 0 ? '兵力需大于 0'
          : atkTroops > city.garrison ? `兵力超过守军（${city.garrison}）`
            : !atkTarget ? '请选择目标城池'
              : !atkGeneral ? '请选择主将'
                : ''

  const doRecruit = () => {
    runCommand(
      { type: 'recruit', faction: city.faction, turn: state.turn, params: { city: city.id, troops: Number(recruitTroops) || 0 } },
      `征兵 ${city.name}`,
    )
  }
  const doDevelop = () => {
    runCommand(
      { type: 'develop', faction: city.faction, turn: state.turn, params: { city: city.id, develop_type: developType } },
      `发展 ${city.name}（${DEVELOP_TYPES.find((d) => d.value === developType)?.label}）`,
    )
  }
  const doAttack = () => {
    if (attackDisabledReason) return
    runCommand(
      {
        type: 'attack',
        faction: city.faction,
        turn: state.turn,
        params: { from_city: city.id, to_city: atkTarget, troops: Number(atkTroops) || 0, general: atkGeneral },
      },
      `出征 ${city.name} → ${state.cities[atkTarget]?.name || atkTarget}`,
    )
  }

  return (
    <div style={styles.card} data-city-card={city.id}>
      {/* 势力色内衬条：不覆盖九宫格边框（border-image 下改 borderLeft 会撕坏左边缘） */}
      <span aria-hidden style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '3px', background: color, opacity: 0.9, borderRadius: '2px' }} />
      {/* 头部 */}
      <div style={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px', minWidth: 0 }}>
          <FactionBadge faction={city.faction} size={18} />
          <span className="font-serif" style={{ color, fontSize: '16px', fontWeight: 700, whiteSpace: 'nowrap' }}>{city.name}</span>
          <span style={styles.factionName}>{factionName}</span>
          <span style={{ display: 'inline-flex', gap: '1px' }} title={`等级 ${city.level}`}>
            {Array.from({ length: city.level }).map((_, i) => (
              <i key={i} className="fa-solid fa-star" style={{ color: 'var(--gold)', fontSize: '9px' }}></i>
            ))}
          </span>
        </div>
        <button style={styles.close} onClick={onClose} aria-label="关闭城池详情" title="关闭（Esc）">
          <i className="fa-solid fa-xmark"></i>
        </button>
      </div>

      {city.is_besieged && (
        <div style={styles.besieged}>
          <i className="fa-solid fa-triangle-exclamation"></i>
          被围困中 · {city.besieging_armies?.length || 0} 支敌军在城外
        </div>
      )}

      {/* 资源与防务（数字均可悬停查看说明） */}
      <div style={styles.grid}>
        <Hint content={info('守军', '城内可守之兵。出征会从此处扣除。')}><Label icon="fa-users" text="守军" /></Hint>
        <span style={{ color: 'var(--text)', fontWeight: 600 }}>{city.garrison.toLocaleString()}</span>

        <Hint content={info('城墙', '城墙耐久。攻城先破墙，墙破则守军承压。')}><Label icon="fa-shield-halved" text="城墙" /></Hint>
        <span style={{ color: 'var(--text)' }}>
          {city.wall_hp.toLocaleString()} / {city.wall_max_hp.toLocaleString()}
          <span style={{ ...styles.bar, marginTop: '3px' }}>
            <span style={{ ...styles.barFill, width: `${Math.round(wallRatio * 100)}%`, background: wallRatio > 0.5 ? 'var(--green)' : 'var(--red)' }} />
          </span>
        </span>

        <Hint content={info('金钱', '城内金库。征兵、发展、赏赐都要花钱。')}><Label icon="fa-coins" text="金钱" /></Hint>
        <span style={{ color: 'var(--gold)', fontWeight: 600 }}>{city.gold.toLocaleString()}</span>

        <Hint content={info('粮草', '军粮储备。征兵消耗粮草，缺粮会打击士气。')}><Label icon="fa-bread-slice" text="粮草" /></Hint>
        <span style={{ color: 'var(--green)' }}>{city.food.toLocaleString()}</span>

        <Hint content={info('民心', '民心越高，产出与守城越稳；过低易生内乱。')}><Label icon="fa-heart" text="民心" /></Hint>
        <span style={{ color: moraleColor(city.morale), fontWeight: 600 }}>{city.morale}</span>

        <Hint content={info('人口', '城市人口规模，是兵源与经济的基础。')}><Label icon="fa-people-group" text="人口" /></Hint>
        <span style={{ color: 'var(--text)' }}>{city.population.toLocaleString()}</span>

        <Hint content={info('州郡', provinceModifier ? `所属州：${provinceModifier}` : '所属州。相邻同州城常有地缘牵动。')}><Label icon="fa-map" text="州郡" /></Hint>
        <span style={{ color: 'var(--text)' }}>
          {provinceName}
          {provinceModifier && (
            <span style={{ display: 'block', color: '#c9a96e', fontSize: '10px', lineHeight: 1.4 }}>{provinceModifier}</span>
          )}
        </span>

        {typeof city.economic_bonus === 'number' && city.economic_bonus > 0 && (
          <>
            <Hint content={info('经济加成', '历次「经济发展」累积的产出加成。')}><Label icon="fa-arrow-trend-up" text="经济加成" /></Hint>
            <span style={{ color: 'var(--green)' }}>+{city.economic_bonus}%</span>
          </>
        )}
      </div>

      {/* 驻守将领 */}
      <div style={styles.sectionTitle}>
        <i className="fa-solid fa-user-shield"></i> 驻守武将
        <span style={styles.count}>{generals.filter((g) => g.location === city.id).length}</span>
      </div>
      {generals.filter((g) => g.location === city.id).length === 0 ? (
        <div style={styles.dim}>本城无驻将</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
          {generals.filter((g) => g.location === city.id).map((g) => (
            <div key={g.id} style={styles.genRow}>
              <i className="fa-solid fa-user" style={{ color: UI_COLORS.textSecondary, fontSize: '9px' }}></i>
              <span style={{ color: 'var(--text)', minWidth: '46px' }}>{g.name}</span>
              {g.element_name && (
                <span style={{ color: ELEMENT_COLORS[g.element || ''] || UI_COLORS.textSecondary, border: `1px solid ${ELEMENT_COLORS[g.element || ''] || UI_COLORS.textSecondary}`, borderRadius: '3px', padding: '0 3px', fontSize: '9px' }}>{g.element_name}</span>
              )}
              <span style={{ color: STAT_COLORS.command, marginLeft: 'auto' }}>统{g.command}</span>
              <span style={{ color: STAT_COLORS.bravery }}>武{g.bravery}</span>
              <span style={{ color: STAT_COLORS.intelligence }}>智{g.intelligence}</span>
            </div>
          ))}
        </div>
      )}

      {/* 可执行操作 */}
      <div style={styles.sectionTitle}>
        <i className="fa-solid fa-gavel"></i> 可执行操作
      </div>
      <div style={styles.warnNote}>
        <i className="fa-solid fa-circle-info" style={{ marginRight: '5px' }}></i>
        观战模式下无人类势力：以下操作以 <b style={{ color }}>{factionName}</b> 的名义下发，属人为干预，会真实改变对局。
      </div>

      {/* 征兵 */}
      <div style={styles.actionRow}>
        <span style={styles.actionLabel}><i className="fa-solid fa-users" style={{ marginRight: '5px' }}></i>征兵</span>
        <input
          type="number"
          min={1}
          value={recruitTroops}
          onChange={(e) => setRecruitTroops(Number(e.target.value))}
          disabled={busy}
          style={styles.input}
          aria-label="征兵数量"
        />
        <ActionButton
          label="征兵"
          busyLabel="征募中"
          busy={busy && commandPending?.type === 'recruit'}
          disabled={busy || recruitTroops <= 0}
          onClick={doRecruit}
          title={recruitTroops <= 0 ? '兵力需大于 0' : '消耗金钱与粮草，增加守军'}
        />
      </div>

      {/* 发展 */}
      <div style={styles.actionRow}>
        <span style={styles.actionLabel}><i className="fa-solid fa-city" style={{ marginRight: '5px' }}></i>发展</span>
        <select
          value={developType}
          onChange={(e) => setDevelopType(e.target.value)}
          disabled={busy}
          style={styles.select}
          aria-label="发展类型"
        >
          {DEVELOP_TYPES.map((d) => (
            <option key={d.value} value={d.value} title={d.hint}>{d.label}</option>
          ))}
        </select>
        <ActionButton
          label="发展"
          busyLabel="发展中"
          busy={busy && commandPending?.type === 'develop'}
          disabled={busy}
          onClick={doDevelop}
          title="消耗金钱提升城市发展度"
        />
      </div>

      {/* 出征 */}
      <div style={styles.actionRow}>
        <span style={styles.actionLabel}><i className="fa-solid fa-crosshairs" style={{ marginRight: '5px' }}></i>出征</span>
        <select
          value={atkTarget}
          onChange={(e) => setAtkTarget(e.target.value)}
          disabled={busy || targets.length === 0}
          style={styles.select}
          aria-label="出征目标"
        >
          <option value="">目标城…</option>
          {targets.map((t) => (
            <option key={t.id} value={t.id}>{t.name}（{FACTIONS[t.faction] || t.faction}）</option>
          ))}
        </select>
        <select
          value={atkGeneral}
          onChange={(e) => setAtkGeneral(e.target.value)}
          disabled={busy || generals.length === 0}
          style={styles.select}
          aria-label="出征主将"
        >
          <option value="">主将…</option>
          {generals.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}{g.location === city.id ? '' : '（他城）'}
            </option>
          ))}
        </select>
        <input
          type="number"
          min={1}
          max={city.garrison}
          value={atkTroops}
          onChange={(e) => setAtkTroops(Number(e.target.value))}
          disabled={busy}
          style={{ ...styles.input, width: '64px' }}
          aria-label="出征兵力"
        />
        <ActionButton
          label="出征"
          busyLabel="出征中"
          busy={busy && commandPending?.type === 'attack'}
          disabled={busy || !!attackDisabledReason}
          onClick={doAttack}
          title={attackDisabledReason || '派兵攻打目标城'}
        />
      </div>
      {attackDisabledReason && (
        <div style={styles.reasonNote}>
          <i className="fa-solid fa-ban" style={{ marginRight: '5px' }}></i>出征不可用：{attackDisabledReason}
        </div>
      )}

      {/* 命令回执（真实后端 description） */}
      {commandResult && (
        <div style={{ ...styles.result, color: commandResult.success ? 'var(--green)' : '#e0776d', borderColor: commandResult.success ? 'rgba(90,180,100,0.45)' : 'rgba(157,41,51,0.5)' }}>
          <i className={`fa-solid ${commandResult.success ? 'fa-circle-check' : 'fa-circle-exclamation'}`} style={{ marginRight: '6px' }}></i>
          {commandResult.description}
        </div>
      )}
      {commandPending && (
        <div style={styles.pending}>
          <i className="fa-solid fa-spinner fa-spin" style={{ marginRight: '6px' }}></i>
          {commandPending.label} 执行中…
        </div>
      )}

      {/* 相邻城池快捷跳转 */}
      {targets.length > 0 && (
        <>
          <div style={{ ...styles.sectionTitle, marginTop: '10px' }}>
            <i className="fa-solid fa-location-dot"></i> 相邻敌城
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
            {targets.map((t) => (
              <button
                key={t.id}
                style={{ ...styles.neighborChip, borderColor: FACTION_COLORS[t.faction] || '#888' }}
                onClick={() => onSelectCity(t.id)}
                title={`查看 ${t.name}`}
              >
                {t.name}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

const ELEMENT_COLORS: Record<string, string> = {
  fire: '#d9604a', earth: '#c9a24b', metal: '#c8c2b4', water: '#5b93c4', wood: '#5aa86a',
}

function info(title: string, line: string) {
  return { title, lines: [line] }
}

function Label({ icon, text }: { icon: string; text: string }) {
  return (
    <span style={styles.dim}>
      <i className={`fa-solid ${icon}`} style={{ marginRight: '5px', width: '14px', textAlign: 'center' }}></i>
      {text}
    </span>
  )
}

function ActionButton({
  label, busyLabel, busy, disabled, onClick, title,
}: {
  label: string; busyLabel: string; busy: boolean; disabled: boolean; onClick: () => void; title?: string
}) {
  return (
    <button
      style={{
        ...styles.button,
        opacity: disabled && !busy ? 0.45 : 1,
        cursor: disabled || busy ? 'not-allowed' : 'pointer',
      }}
      disabled={disabled || busy}
      onClick={onClick}
      title={title}
    >
      {busy && <i className="fa-solid fa-spinner fa-spin" style={{ marginRight: '4px' }}></i>}
      {busy ? busyLabel : label}
    </button>
  )
}

const styles: Record<string, CSSProperties> = {
  card: {
    position: 'absolute',
    top: '74px',
    left: '12px',
    width: '302px',
    maxHeight: 'calc(100% - 150px)',
    overflowY: 'auto',
    padding: '12px',
    background: 'rgba(16, 16, 30, 0.94)',
    // Kenney UI Pack 面板九宫格边框（CC0，见 assets/art/ATTRIBUTION.md）
    border: '8px solid transparent',
    borderImage: `url("${panelFrame}") 8 / 8px / 0 stretch`,
    boxShadow: '0 10px 36px rgba(0, 0, 0, 0.5)',
    zIndex: 31,
    boxSizing: 'border-box',
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: '8px', gap: '6px',
  },
  factionName: { color: UI_COLORS.textSecondary, fontSize: '11px', whiteSpace: 'nowrap' },
  close: { background: 'transparent', border: 'none', color: 'var(--text-2)', cursor: 'pointer', fontSize: '13px', padding: '2px 4px', flexShrink: 0 },
  besieged: {
    margin: '0 0 8px', padding: '6px 9px', background: 'rgba(157, 41, 51, 0.15)',
    borderRadius: '6px', color: 'var(--red)', fontSize: '11px',
  },
  grid: {
    display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '7px 12px',
    fontSize: '12px', alignItems: 'center', marginBottom: '10px',
  },
  dim: { color: 'var(--text-2)', fontSize: '12px', display: 'inline-flex', alignItems: 'center' },
  bar: { display: 'block', width: '100%', height: '3px', background: '#282836', borderRadius: '2px', overflow: 'hidden' },
  barFill: { display: 'block', height: '100%', borderRadius: '2px', transition: 'width 0.3s ease' },
  sectionTitle: {
    color: 'var(--gold)', fontSize: '12px', fontWeight: 600, margin: '8px 0 6px',
    display: 'flex', alignItems: 'center', gap: '5px',
  },
  count: { color: 'var(--text-muted)', fontSize: '10px', fontWeight: 400 },
  genRow: { display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', padding: '2px 0' },
  warnNote: {
    color: '#b8b3aa', fontSize: '10px', lineHeight: 1.6, background: 'rgba(200, 168, 90, 0.08)',
    border: '1px solid rgba(200, 168, 90, 0.22)', borderRadius: '6px', padding: '6px 8px', marginBottom: '8px',
  },
  actionRow: { display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px', flexWrap: 'wrap' },
  actionLabel: { color: 'var(--text)', fontSize: '12px', width: '52px', flexShrink: 0 },
  input: {
    width: '72px', padding: '4px 6px', background: 'rgba(255,255,255,0.06)',
    border: '1px solid rgba(255,255,255,0.14)', borderRadius: '5px', color: 'var(--text)',
    fontSize: '12px', fontFamily: 'inherit',
  },
  select: {
    flex: 1, minWidth: '86px', padding: '4px 6px', background: 'rgba(255,255,255,0.06)',
    border: '1px solid rgba(255,255,255,0.14)', borderRadius: '5px', color: 'var(--text)',
    fontSize: '12px', fontFamily: 'inherit',
  },
  button: {
    padding: '4px 12px', borderRadius: '6px', border: '1px solid rgba(200, 168, 90, 0.55)',
    background: 'rgba(200, 168, 90, 0.16)', color: '#e8c877', fontSize: '12px',
    fontWeight: 600, fontFamily: 'inherit', display: 'inline-flex', alignItems: 'center',
  },
  reasonNote: { color: '#c99a5a', fontSize: '10px', marginBottom: '6px' },
  result: {
    marginTop: '6px', padding: '6px 9px', fontSize: '11px', lineHeight: 1.5,
    border: '1px solid', borderRadius: '6px', background: 'rgba(255,255,255,0.03)',
  },
  pending: {
    marginTop: '6px', padding: '6px 9px', fontSize: '11px', color: 'var(--gold)',
    border: '1px solid rgba(200,168,90,0.35)', borderRadius: '6px', background: 'rgba(200,168,90,0.08)',
  },
  neighborChip: {
    padding: '3px 9px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)',
    border: '1px solid', color: '#c9c3b8', fontSize: '11px', fontFamily: 'inherit', cursor: 'pointer',
  },
}
