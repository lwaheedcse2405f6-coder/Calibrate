import { History, Sparkles, TrendingDown, TrendingUp, CircleCheck } from "lucide-react";
import type { ReactNode } from "react";
import { times } from "../lib/format";
import type { Belief, BeliefChange } from "../types";
import { ConfidenceBadge, EmptyBlock, Panel, PanelHeader } from "./ui";

const CHANGE: Record<BeliefChange, { label: string; icon: ReactNode; cls: string }> = {
  new: { label: "New belief", icon: <Sparkles className="size-3.5" aria-hidden />, cls: "text-violet-300 bg-violet-500/15" },
  strengthened: {
    label: "Strengthened",
    icon: <TrendingUp className="size-3.5" aria-hidden />,
    cls: "text-amber-300 bg-amber-500/15",
  },
  softened: {
    label: "Softened",
    icon: <TrendingDown className="size-3.5" aria-hidden />,
    cls: "text-emerald-300 bg-emerald-500/15",
  },
  confirmed: {
    label: "Confirmed",
    icon: <CircleCheck className="size-3.5" aria-hidden />,
    cls: "text-sky-300 bg-sky-500/15",
  },
};

export function BeliefTimeline({ beliefs, repName }: { beliefs: Belief[]; repName: string }) {
  const quarters = [...new Set(beliefs.map((b) => b.quarter))];

  return (
    <Panel className="h-full">
      <PanelHeader
        icon={<History className="size-5" aria-hidden />}
        title="Belief timeline"
        subtitle={`How Calibrate's view of ${repName} changed. Old beliefs stay, in grey.`}
      />

      {beliefs.length === 0 ? (
        <EmptyBlock title="Nothing learned yet">
          {repName} has no closed deals in memory, so Calibrate hasn't formed any beliefs.
        </EmptyBlock>
      ) : (
        <ol className="relative space-y-6 border-l-2 border-slate-800 pl-6">
          {quarters.map((q, qi) => (
            <li key={q} className="animate-fade-up" style={{ animationDelay: `${qi * 90}ms` }}>
              <span
                className={`absolute -left-[9px] mt-1 size-4 rounded-full ring-4 ring-slate-900 ${
                  beliefs.some((b) => b.quarter === q && b.status === "active") ? "bg-violet-500" : "bg-slate-600"
                }`}
                aria-hidden
              />
              <p className="mb-2 font-mono text-sm font-semibold tracking-wider text-slate-400">{q}</p>
              <ul className="space-y-2.5">
                {beliefs
                  .filter((b) => b.quarter === q)
                  .map((b, i) => {
                    const old = b.status === "superseded";
                    const change = b.change ? CHANGE[b.change] : null;
                    return (
                      <li
                        key={i}
                        className={`rounded-xl border p-3.5 transition-colors ${
                          old ? "border-slate-800 bg-slate-900/40" : "border-violet-500/30 bg-violet-500/[0.07]"
                        }`}
                      >
                        <div className="mb-1.5 flex flex-wrap items-center gap-2">
                          {change && (
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${
                                old ? "bg-slate-800 text-slate-400" : change.cls
                              }`}
                            >
                              {change.icon}
                              {change.label}
                            </span>
                          )}
                          {old && <span className="text-xs font-medium text-slate-500 uppercase">Replaced</span>}
                        </div>
                        <p className={`text-[16px] leading-snug ${old ? "text-slate-500" : "text-slate-100"}`}>{b.text}</p>
                        <div className="mt-2.5 flex flex-wrap items-center gap-3 text-sm">
                          {b.adjustment != null && (
                            <span className={`font-mono font-semibold ${old ? "text-slate-500" : "text-violet-300"}`}>
                              {times(b.adjustment)}
                            </span>
                          )}
                          <span className={old ? "text-slate-500" : "text-slate-400"}>{b.evidence_count} deals</span>
                          {!old && <ConfidenceBadge level={b.confidence} />}
                        </div>
                      </li>
                    );
                  })}
              </ul>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}
