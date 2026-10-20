import { useEffect, useMemo, useRef, useState } from 'react'

/**
 * Single-series column chart of questions per day.
 * One hue (brand), no legend (the card title names the series), thin columns
 * with 4px rounded tops anchored to the baseline, recessive grid, and a hover
 * tooltip with a hit area wider than the mark.
 */
const H = 200
const PAD = { top: 12, right: 8, bottom: 24, left: 32 }

function niceMax(v) {
  if (v <= 4) return 4
  const pow = 10 ** Math.floor(Math.log10(v))
  const step = [1, 2, 2.5, 5, 10].find((s) => (s * pow * 4) >= v) * pow
  return step * 4
}

export default function DailyChart({ data }) {
  const [hover, setHover] = useState(null)
  const [width, setWidth] = useState(640)
  const boxRef = useRef(null)
  useEffect(() => {
    const el = boxRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(240, Math.floor(entry.contentRect.width))))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const max = useMemo(() => niceMax(Math.max(...data.map((d) => d.count), 0)), [data])
  const plotW = width - PAD.left - PAD.right
  const plotH = H - PAD.top - PAD.bottom
  const slot = plotW / data.length
  const barW = Math.max(2, Math.min(24, slot - 2)) // 2px gap between neighbours, capped at 24px
  const ticks = [0, max / 4, max / 2, (3 * max) / 4, max]
  const y = (v) => PAD.top + plotH - (v / max) * plotH

  const labelEvery = data.length > 14 ? 7 : data.length > 7 ? 2 : 1

  return (
    <div
      className="relative w-full"
      ref={boxRef}
    >
      <svg width={width} height={H} role="img" aria-label="Questions per day" className="block">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="#E2E8F0" strokeWidth={t === 0 ? 1 : 0.5} strokeDasharray={t === 0 ? '' : '2 3'} />
            <text x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-slate-400 text-[10px] tabular-nums">
              {Number.isInteger(t) ? t.toLocaleString() : ''}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const cx = PAD.left + slot * i + slot / 2
          const h = (d.count / max) * plotH
          const r = Math.min(4, barW / 2, h)
          const x0 = cx - barW / 2
          const base = PAD.top + plotH
          const path =
            h <= 0
              ? null
              : `M${x0},${base} V${base - h + r} Q${x0},${base - h} ${x0 + r},${base - h} H${x0 + barW - r} Q${x0 + barW},${base - h} ${x0 + barW},${base - h + r} V${base} Z`
          return (
            <g key={d.date}>
              {path && <path d={path} fill="#6366F1" opacity={hover === null || hover === i ? 1 : 0.45} />}
              {i % labelEvery === (data.length - 1) % labelEvery && (
                <text x={cx} y={H - 6} textAnchor="middle" className="fill-slate-400 text-[10px]">
                  {new Date(d.date + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}
                </text>
              )}
              {/* Full-height hit target, wider than the mark */}
              <rect
                x={PAD.left + slot * i}
                y={PAD.top}
                width={slot}
                height={plotH}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                onTouchStart={() => setHover(i)}
              />
            </g>
          )
        })}
      </svg>
      {hover !== null && (
        <div
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow-pop"
          style={{
            left: Math.min(Math.max(PAD.left + slot * hover + slot / 2, 60), width - 60),
            top: y(data[hover].count) - 6,
          }}
        >
          <div className="text-slate-500">
            {new Date(data[hover].date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })}
          </div>
          <div className="font-semibold tabular-nums text-slate-900">
            {data[hover].count} question{data[hover].count === 1 ? '' : 's'}
          </div>
        </div>
      )}
    </div>
  )
}
