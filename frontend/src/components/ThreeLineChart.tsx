import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { inCrore } from "../lib/format";
import { SERIES } from "../theme";

/** One row per quarter. Values are undefined for quarters the replay hasn't reached yet. */
export interface ChartRow {
  quarter: string;
  reps_forecast_inr?: number;
  agent_forecast_inr?: number;
  actual_inr?: number;
}

export const LINES = [
  { key: "reps_forecast_inr", name: "What reps said", color: SERIES.reps, dashed: true },
  { key: "agent_forecast_inr", name: "What Calibrate said", color: SERIES.calibrate, dashed: false },
  { key: "actual_inr", name: "What actually closed", color: SERIES.actual, dashed: false },
] as const;

export function ChartLegend() {
  return (
    <ul className="flex flex-wrap items-center gap-x-6 gap-y-2" aria-label="Chart legend">
      {LINES.map((l) => (
        <li key={l.key} className="flex items-center gap-2.5 text-[15px] font-medium text-slate-200">
          <svg width="28" height="10" aria-hidden>
            <line
              x1="1"
              y1="5"
              x2="27"
              y2="5"
              stroke={l.color}
              strokeWidth={l.key === "actual_inr" ? 5 : 3.5}
              strokeDasharray={l.dashed ? "5 4" : undefined}
              strokeLinecap="round"
            />
          </svg>
          {l.name}
        </li>
      ))}
    </ul>
  );
}

interface TooltipLikeProps {
  active?: boolean;
  label?: string;
  payload?: { dataKey?: string | number; value?: number }[];
}

function ChartTooltip({ active, label, payload }: TooltipLikeProps) {
  if (!active || !payload?.length) return null;
  const val = (k: string) => payload.find((p) => p.dataKey === k)?.value;
  const actual = val("actual_inr");
  return (
    <div className="min-w-60 rounded-xl border border-slate-700 bg-slate-950/95 p-4 shadow-2xl backdrop-blur">
      <p className="mb-2 text-sm font-semibold tracking-wide text-slate-400 uppercase">{label}</p>
      <ul className="space-y-1.5">
        {LINES.map((l) => {
          const v = val(l.key);
          if (v == null) return null;
          const off = actual != null && l.key !== "actual_inr" ? v - actual : null;
          const close = off != null && actual != null && Math.abs(off) < 0.1 * actual;
          return (
            <li key={l.key} className="flex items-center justify-between gap-4 text-[15px]">
              <span className="flex items-center gap-2 text-slate-300">
                <span className="size-2.5 rounded-full" style={{ background: l.color }} />
                {l.name}
              </span>
              <span className="font-mono font-semibold text-white">
                {inCrore(v)}
                {off != null && (
                  <span className={`ml-2 text-xs ${close ? "text-emerald-400" : "text-rose-400"}`}>
                    {off >= 0 ? "+" : "−"}
                    {inCrore(Math.abs(off))}
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Y range from the full year, so the axis doesn't jump while the replay fills in. */
function yDomain(rows: ChartRow[]): [number, number] | undefined {
  const vals = rows.flatMap((r) => [r.reps_forecast_inr, r.agent_forecast_inr, r.actual_inr]).filter(
    (v): v is number => typeof v === "number",
  );
  if (!vals.length) return undefined;
  const step = 5e6; // ₹0.5 Cr
  return [Math.floor((Math.min(...vals) * 0.9) / step) * step, Math.ceil((Math.max(...vals) * 1.04) / step) * step];
}

export function ThreeLineChart({
  data,
  scaleFrom = data,
  height = 340,
}: {
  data: ChartRow[];
  scaleFrom?: ChartRow[];
  height?: number;
}) {
  const domain = yDomain(scaleFrom) ?? [0, 1e8];
  return (
    <div role="img" aria-label="Line chart comparing what reps said, what Calibrate said, and what actually closed, per quarter">
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={SERIES.grid} strokeDasharray="3 6" vertical={false} />
          <XAxis
            dataKey="quarter"
            tick={{ fill: SERIES.axis, fontSize: 14 }}
            tickLine={false}
            axisLine={{ stroke: SERIES.grid }}
            padding={{ left: 24, right: 24 }}
          />
          <YAxis
            tickFormatter={inCrore}
            tick={{ fill: SERIES.axis, fontSize: 14 }}
            tickLine={false}
            axisLine={false}
            width={78}
            domain={domain}
            allowDataOverflow
          />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: "#475569", strokeDasharray: "4 4" }} />
          {/* Draw order: reps, actual, then Calibrate on top so it visibly sits on the reps line with memory OFF. */}
          <Line
            dataKey="reps_forecast_inr"
            name="What reps said"
            stroke={SERIES.reps}
            strokeWidth={2.5}
            strokeDasharray="7 6"
            dot={{ r: 4, fill: "#0A0E17", strokeWidth: 2 }}
            activeDot={{ r: 6 }}
            animationDuration={700}
          />
          <Line
            dataKey="actual_inr"
            name="What actually closed"
            stroke={SERIES.actual}
            strokeWidth={4.5}
            dot={{ r: 5, fill: SERIES.actual, strokeWidth: 0 }}
            activeDot={{ r: 7 }}
            animationDuration={700}
          />
          <Line
            dataKey="agent_forecast_inr"
            name="What Calibrate said"
            stroke={SERIES.calibrate}
            strokeWidth={3.5}
            dot={{ r: 5, fill: "#0A0E17", stroke: SERIES.calibrate, strokeWidth: 3 }}
            activeDot={{ r: 7, fill: SERIES.calibrate }}
            className="calibrate-line"
            animationDuration={700}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
