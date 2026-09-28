import { ArrowDown } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { SERIES } from "../theme";
import type { ScorePoint } from "../types";

const BARS = [
  { key: "reps", name: "What reps said", color: SERIES.reps, opacity: 1 },
  { key: "baseline", name: "Simple baseline", color: SERIES.baseline, opacity: 0.85 },
  { key: "agent_off", name: "Calibrate, memory OFF", color: SERIES.calibrate, opacity: 0.35 },
  { key: "agent_on", name: "Calibrate, memory ON", color: SERIES.calibrate, opacity: 1 },
] as const;

interface TooltipLikeProps {
  active?: boolean;
  label?: string;
  payload?: { dataKey?: string | number; value?: number }[];
}

function ScoreTooltip({ active, label, payload }: TooltipLikeProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="min-w-56 rounded-xl border border-slate-700 bg-slate-950/95 p-4 shadow-2xl">
      <p className="mb-2 text-sm font-semibold tracking-wide text-slate-400 uppercase">{label}</p>
      <ul className="space-y-1.5">
        {BARS.map((b) => {
          const v = payload.find((p) => p.dataKey === b.key)?.value;
          return v == null ? null : (
            <li key={b.key} className="flex items-center justify-between gap-4 text-[15px]">
              <span className="flex items-center gap-2 text-slate-300">
                <span className="size-2.5 rounded-sm" style={{ background: b.color, opacity: b.opacity }} />
                {b.name}
              </span>
              <span className="font-mono font-semibold text-white">{v.toFixed(3)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function ErrorScoreChart({ data, height = 320 }: { data: ScorePoint[]; height?: number }) {
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <ul className="flex flex-wrap gap-x-5 gap-y-2" aria-label="Chart legend">
          {BARS.map((b) => (
            <li key={b.key} className="flex items-center gap-2 text-[15px] font-medium text-slate-200">
              <span className="size-3.5 rounded" style={{ background: b.color, opacity: b.opacity }} aria-hidden />
              {b.name}
            </li>
          ))}
        </ul>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-sm font-semibold text-emerald-300 ring-1 ring-emerald-400/30">
          <ArrowDown className="size-4" aria-hidden /> Lower is better
        </span>
      </div>
      <div role="img" aria-label="Bar chart of forecast error (Brier score) per quarter. Lower is better.">
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} barGap={4} barCategoryGap="22%" margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid stroke={SERIES.grid} strokeDasharray="3 6" vertical={false} />
            <XAxis dataKey="quarter" tick={{ fill: SERIES.axis, fontSize: 14 }} tickLine={false} axisLine={{ stroke: SERIES.grid }} />
            <YAxis
              tick={{ fill: SERIES.axis, fontSize: 14 }}
              tickLine={false}
              axisLine={false}
              width={52}
              tickFormatter={(v: number) => v.toFixed(2)}
              label={{ value: "Error (Brier)", angle: -90, position: "insideLeft", fill: SERIES.axis, fontSize: 13, dy: 40 }}
            />
            <Tooltip content={<ScoreTooltip />} cursor={{ fill: "rgb(148 163 184 / 0.08)" }} />
            {BARS.map((b) => (
              <Bar
                key={b.key}
                dataKey={b.key}
                name={b.name}
                fill={b.color}
                fillOpacity={b.opacity}
                radius={[6, 6, 0, 0]}
                animationDuration={800}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
