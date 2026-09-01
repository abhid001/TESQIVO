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

export interface TrendPoint {
  date: string;
  passed: number;
  failed: number;
  blocked: number;
  other: number;
  total: number;
}

/** Stacked-area chart of executions per day, split by result. */
export function TrendChart({ series }: { series: TrendPoint[] }) {
  const [tip, setTip] = useState<Tip | null>(null);
  const w = 440;
  const h = 190;
  const padL = 24;
  const padR = 8;
  const padT = 10;
  const padB = 24;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;
  const n = series.length;
  const maxY = Math.max(1, ...series.map((d) => d.passed + d.failed + d.blocked));
  const x = (i: number) => padL + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const y = (v: number) => padT + plotH - (v / maxY) * plotH;

  const band = (lo: (d: TrendPoint) => number, hi: (d: TrendPoint) => number, fill: string) => {
    const fwd = series.map((d, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(hi(d)).toFixed(1)}`).join(" ");
    const back = series
      .map((_d, i) => n - 1 - i)
      .map((i) => `L${x(i).toFixed(1)},${y(lo(series[i])).toFixed(1)}`)
      .join(" ");
    return <path d={`${fwd} ${back} Z`} fill={fill} opacity={0.92} />;
  };

  const p = (d: TrendPoint) => d.passed;
  const pf = (d: TrendPoint) => d.passed + d.failed;
  const pfb = (d: TrendPoint) => d.passed + d.failed + d.blocked;
  const ticks = [0, Math.ceil(maxY / 2), maxY];
  const labelEvery = Math.max(1, Math.floor(n / 6));

  return (
    <div className="viz" style={{ position: "relative" }}>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Executions per day">
        {ticks.map((t) => (
          <g key={t}>
            <line className="viz-grid" x1={padL} x2={w - padR} y1={y(t)} y2={y(t)} />
            <text className="viz-axis" x={padL - 4} y={y(t) + 3} textAnchor="end">{t}</text>
          </g>
        ))}
        {band(() => 0, p, "var(--viz-pass)")}
        {band(p, pf, "var(--viz-fail)")}
        {band(pf, pfb, "var(--viz-block)")}
        {series.map((d, i) =>
          i % labelEvery === 0 ? (
            <text key={d.date} className="viz-axis" x={x(i)} y={h - 8} textAnchor="middle">
              {d.date.slice(5).replace("-", "/")}
            </text>
          ) : null,
        )}
        {series.map((d, i) => (
          <rect
            key={d.date}
            x={x(i) - plotW / n / 2}
            y={padT}
            width={Math.max(plotW / n, 4)}
            height={plotH}
            fill="transparent"
            onMouseMove={(e) =>
              setTip({
                x: e.clientX,
                y: e.clientY,
                content: (
                  <>
                    <strong>{d.date}</strong>
                    <br />
                    {d.total} run · {d.passed}P / {d.failed}F / {d.blocked}B
                  </>
                ),
              })
            }
            onMouseLeave={() => setTip(null)}
          />
        ))}
      </svg>
      <div className="viz-legend">
        <span><i style={{ background: "var(--viz-pass)" }} />Passed</span>
        <span><i style={{ background: "var(--viz-fail)" }} />Failed</span>
        <span><i style={{ background: "var(--viz-block)" }} />Blocked</span>
      </div>
      <Tooltip tip={tip} />
    </div>
  );
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

export interface HBarDatum {
  label: string;
  value: number;
  /** bar length is value / max */
  max: number;
  display: string;
  color: string; // css color or var()
  onClick?: () => void;
}

/** Compact labelled horizontal bars (coverage %, defect counts). Pure HTML. */
export function HBars({ rows }: { rows: HBarDatum[] }) {
  return (
    <div className="hbars viz">
      {rows.map((r) => {
        const pct = r.max > 0 ? Math.max((r.value / r.max) * 100, r.value > 0 ? 4 : 0) : 0;
        const inner = (
          <>
            <span className="muted" style={{ fontSize: 12.5 }}>{r.label}</span>
            <span className="hbar-track">
              <span className="hbar-fill" style={{ width: `${pct}%`, background: r.color }} />
            </span>
            <span className="hbar-val">{r.display}</span>
          </>
        );
        return r.onClick ? (
          <button key={r.label} className="hbar-row" onClick={r.onClick}>{inner}</button>
        ) : (
          <div key={r.label} className="hbar-row">{inner}</div>
        );
      })}
    </div>
  );
}

/** Semicircular score gauge (0–100) with a status label. */
export function Gauge({
  value,
  label,
  tone,
}: {
  value: number;
  label: string;
  tone: "good" | "warn" | "bad";
}) {
  const size = 148;
  const stroke = 12;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;
  const frac = Math.max(0, Math.min(1, value / 100));
  const color = tone === "good" ? "var(--viz-pass)" : tone === "warn" ? "var(--viz-block)" : "var(--viz-fail)";
  return (
    <div className="viz" style={{ textAlign: "center" }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label={`${label}: ${value}`}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${frac * circ} ${circ}`}
          transform={`rotate(-90 ${cx} ${cy})`}
        />
        <text x={cx} y={cy - 2} textAnchor="middle" fontSize={30} fontWeight={750} fill="var(--viz-ink)">
          {value}
        </text>
        <text x={cx} y={cy + 20} textAnchor="middle" fontSize={11} fill="var(--viz-ink-dim)">
          out of 100
        </text>
      </svg>
      <div style={{ marginTop: 4 }}>
        <span className={`badge ${tone === "good" ? "PASSED" : tone === "warn" ? "at_risk" : "FAILED"}`}>{label}</span>
      </div>
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
  size = 168,
}: {
  segments: DonutSegment[];
  centerLabel: string;
  centerValue: string;
  size?: number;
}) {
  const [tip, setTip] = useState<Tip | null>(null);
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 22;
  const sw = size < 150 ? 22 : 26;
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
