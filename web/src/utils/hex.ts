import type { HexCoord } from '../types'

export const HEX_SIZE = 32

export function axialToPixel(coord: HexCoord, size: number = HEX_SIZE): { x: number; y: number } {
  const q = coord.q
  const r = coord.r
  const x = size * (Math.sqrt(3) * q + (Math.sqrt(3) / 2) * r)
  const y = size * (1.5 * r)
  return { x, y }
}

export function pixelToAxial(x: number, y: number, size: number = HEX_SIZE): HexCoord {
  const q = ((Math.sqrt(3) / 3) * x - (1.0 / 3) * y) / size
  const r = ((2.0 / 3) * y) / size
  return hexRound(q, r)
}

function hexRound(q: number, r: number): HexCoord {
  const s = -q - r
  let rq = Math.round(q)
  let rr = Math.round(r)
  const rs = Math.round(s)
  const dq = Math.abs(rq - q)
  const dr = Math.abs(rr - r)
  const ds = Math.abs(rs - s)
  if (dq > dr && dq > ds) {
    rq = -rr - rs
  } else if (dr > ds) {
    rr = -rq - rs
  }
  return { q: rq, r: rr }
}

export function hexPoints(x: number, y: number, size: number): number[] {
  const points: number[] = []
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 3) * i - Math.PI / 6
    points.push(x + size * Math.cos(angle))
    points.push(y + size * Math.sin(angle))
  }
  return points
}

export function hexNeighbors(center: HexCoord): HexCoord[] {
  const dirs = [
    { q: 1, r: 0 },
    { q: 1, r: -1 },
    { q: 0, r: -1 },
    { q: -1, r: 0 },
    { q: -1, r: 1 },
    { q: 0, r: 1 },
  ]
  return dirs.map((d) => ({ q: center.q + d.q, r: center.r + d.r }))
}
