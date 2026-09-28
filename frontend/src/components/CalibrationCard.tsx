import { BrainCircuit, ScrollText } from "lucide-react";
import { pct, times } from "../lib/format";
import type { CalibrationCard as Card } from "../types";
import { ConfidenceBadge, EmptyBlock, Panel, PanelHeader } from "./ui";

function RateBars({ stated, actual }: { stated: number; actual: number }) {
  return (
    <div className="space-y-1.5">
      {[
        { label: "Said", v: stated, cls: "bg-slate-400" },
        { label: "Closed", v: actual, cls: "bg-emerald-400" },
      ].map((r) => (
        <div key={r.label} className="flex items-center gap-2.5">
          <span className="w-14 text-sm text-slate-400">{r.label}</span>
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-800">
            <div className={`h-full rounded-full ${r.cls} transition-[width] duration-700`} style={{ width: pct(r.v) }} />
          </div>
          <span className="w-11 text-right font-mono text-[15px] font-semibold text-white">{pct(r.v)}</span>
        </div>
      ))}
    </div>
  );
}

export function CalibrationCard({ card, memoryOn }: { card: Card; memoryOn: boolean }) {
  return (
    <Panel>
      <PanelHeader
        icon={<ScrollText className="size-5" aria-hidden />}
        title="Calibration card"
        subtitle={`Rules Calibrate learned about ${card.name.split(" ")[0]} · as of ${card.quarter}`}
      />

      {card.rules.length === 0 ? (
        <EmptyBlock title="No rules yet" icon={<BrainCircuit className="size-5" aria-hidden />}>
          Not enough closed deals to learn from. Calibrate passes this rep's numbers through unchanged instead of
          guessing.
        </EmptyBlock>
      ) : (
        <ul className="space-y-3">
          {card.rules.map((r, i) => {
            const neutral = Math.abs(r.adjustment - 1) < 0.05;
            return (
              <li
                key={i}
                className="grid animate-fade-up gap-4 rounded-xl border border-slate-800 bg-slate-950/40 p-4 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1.4fr)_auto]"
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <div>
                  <p className="text-sm font-medium tracking-wide text-slate-400 uppercase">When</p>
                  <p className="mt-1 text-[17px] font-medium text-white">{r.condition}</p>
                  <p className="mt-2 text-sm text-slate-400">
                    Based on <span className="font-semibold text-slate-200">{r.evidence_count} deals</span>
                  </p>
                </div>
                <RateBars stated={r.stated_win_rate} actual={r.actual_win_rate} />
                <div className="flex items-center justify-between gap-4 md:flex-col md:items-end md:justify-center">
                  <span
                    className={`font-mono text-3xl font-semibold ${
                      !memoryOn ? "text-slate-500 line-through" : neutral ? "text-slate-300" : "text-violet-300"
                    }`}
                    title={memoryOn ? "Multiplier applied to this rep's stated probability" : "Not applied: memory is OFF"}
                  >
                    {times(r.adjustment)}
                  </span>
                  <ConfidenceBadge level={r.confidence} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}
