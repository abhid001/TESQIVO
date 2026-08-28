import { useState, type ReactNode } from "react";

/* Charts are hand-rolled inline SVG, theme-aware via the `.viz` CSS-var scope
   (palette validated with the dataviz skill). Marks: <=24px bars, 4px rounded
   data-end, 2px surface gaps, recessive hairline grid, direct labels, hover. */

interface Tip {
  x: number;
  y: number;
  content: ReactNode;
}

function Tooltip({ tip }: { tip: Tip | null }) {
  if (!tip) return null;
  return (
    <div className="viz-tip" style={{ left: tip.x + 12, top: tip.y + 12 }}>
      {tip.content}
    </div>
  );
}

export interface BarDatum {
  label: string;
  /** 0..1, or null when there is no denominator */
  value: number | null;
  sub?: string;
  onClick?: () => void;
}

/** Horizontal bar chart for a single measure (e.g. coverage %) across ordered stages. */
export function CoverageBars({ data }: { data: BarDatum[] }) {
  const [tip, setTip] = useState<Tip | null>(null);
  const rowH = 34;
  const barH = 16;
  const padL = 132;
  const padR = 52;
  const width = 460;
  const plotW = width - padL - padR;
  const height = data.length * rowH + 20;
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="viz" style={{ position: "relative" }}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label="Coverage by stage">
        {ticks.map((t) => (
          <g key={t}>
            <line
              className="viz-grid"
              x1={padL + t * plotW}
              x2={padL + t * plotW}
              y1={6}
              y2={height - 14}
            />
            <text className="viz-axis" x={padL + t * plotW} y={height - 2} textAnchor="middle">
              {t * 100}%
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const y = 10 + i * rowH;
          const w = d.value === null ? 0 : Math.max(d.value * plotW, d.value > 0 ? 3 : 0);
          return (
            <g
              key={d.label}
              className="viz-bar-row"
              onMouseMove={(e) =>
                setTip({
                  x: e.clientX,
                  y: e.clientY,
                  content: (
                    <>
                      <strong>{d.label}</strong>
                      <br />
                      {d.value === null ? "no data in scope" : `${(d.value * 100).toFixed(1)}%`}
                      {d.sub ? ` · ${d.sub}` : ""}
                    </>
                  ),
                })
              }
              onMouseLeave={() => setTip(null)}
              onClick={d.onClick}
            >
              <rect className="viz-bar-hit" x={0} y={y - 4} width={width} height={barH + 8} fill="var(--viz-ink)" opacity={0} />
              <text x={padL - 10} y={y + barH / 2 + 4} textAnchor="end" fontSize={12.5}>
                {d.label}
              </text>
              <rect x={padL} y={y} width={plotW} height={barH} rx={4} fill="var(--viz-track)" />
              {w > 0 && (
                <rect x={padL} y={y} width={w} height={barH} rx={4} fill="var(--viz-bar)" />
              )}
              <text
                x={padL + (d.value === null ? 0 : w) + 8}
                y={y + barH / 2 + 4}
                fontSize={12}
                fill="var(--viz-ink-dim)"
              >
                {d.value === null ? "–" : `${(d.value * 100).toFixed(0)}%`}
              </text>
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} />
    </div>
  );
}

export interface DonutSegment {
  label: string;
  value: number;
  varName: string; // css var, e.g. "--viz-cat-1"
}

/** Donut for a part-to-whole split (<=4 categories, legend + direct values). */
export function Donut({
  segments,
  centerLabel,
  centerValue,
}: {
  segments: DonutSegment[];
  centerLabel: string;
  centerValue: string;
}) {
  const [tip, setTip] = useState<Tip | null>(null);
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const size = 168;
  const cx = size / 2;
  const cy = size / 2;
  const r = 62;
  const sw = 26;
  const circ = 2 * Math.PI * r;
  const gap = 2; // 2px surface gap between segments
  let offset = 0;

  return (
    <div className="viz">
      <div style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap", position: "relative" }}>
        <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label={centerLabel}>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={sw} />
          {segments.map((seg) => {
            const frac = seg.value / total;
            const len = Math.max(frac * circ - gap, 0);
            const dash = `${len} ${circ - len}`;
            const el = (
              <circle
                key={seg.label}
                cx={cx}
                cy={cy}
                r={r}
                fill="none"
                stroke={`var(${seg.varName})`}
                strokeWidth={sw}
                strokeDasharray={dash}
                strokeDashoffset={-offset}
                transform={`rotate(-90 ${cx} ${cy})`}
                onMouseMove={(e) =>
                  setTip({
                    x: e.clientX,
                    y: e.clientY,
                    content: (
                      <>
                        <strong>{seg.label}</strong>
                        <br />
                        {seg.value} · {(frac * 100).toFixed(0)}%
                      </>
                    ),
                  })
                }
                onMouseLeave={() => setTip(null)}
              />
            );
            offset += frac * circ;
            return el;
          })}
          <text x={cx} y={cy - 2} textAnchor="middle" fontSize={22} fontWeight={700} fill="var(--viz-ink)">
            {centerValue}
          </text>
          <text x={cx} y={cy + 16} textAnchor="middle" fontSize={10.5} fill="var(--viz-ink-dim)">
            {centerLabel}
          </text>
        </svg>
        <div className="viz-legend" style={{ flexDirection: "column", marginTop: 0 }}>
          {segments.map((seg) => (
            <span key={seg.label}>
              <i style={{ background: `var(${seg.varName})` }} />
              {seg.label} <strong style={{ color: "var(--text)" }}>{seg.value}</strong>
            </span>
          ))}
        </div>
        <Tooltip tip={tip} />
      </div>
    </div>
  );
}
