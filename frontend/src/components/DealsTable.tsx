import { ArrowDownRight, ArrowRight, ArrowUpRight, Table2 } from "lucide-react";
import { inr, pct } from "../lib/format";
import type { Deal } from "../types";
import { EmptyBlock, OutcomeBadge, Panel, PanelHeader } from "./ui";

function Shift({ from, to }: { from: number; to: number }) {
  const d = Math.round((to - from) * 100);
  if (Math.abs(d) < 2) return <ArrowRight className="size-4 text-slate-500" aria-label="unchanged" />;
  return d < 0 ? (
    <ArrowDownRight className="size-4 text-rose-400" aria-label={`down ${-d} points`} />
  ) : (
    <ArrowUpRight className="size-4 text-emerald-400" aria-label={`up ${d} points`} />
  );
}

export function DealsTable({ deals, memoryOn }: { deals: Deal[]; memoryOn: boolean }) {
  return (
    <Panel>
      <PanelHeader
        icon={<Table2 className="size-5" aria-hidden />}
        title="Deals"
        subtitle="What the rep said, what Calibrate said, and what happened."
      />
      {deals.length === 0 ? (
        <EmptyBlock title="No deals yet" />
      ) : (
        <div className="-mx-6 overflow-x-auto px-6">
          <table className="w-full min-w-[720px] text-left">
            <thead>
              <tr className="border-b border-slate-800 text-sm font-medium tracking-wide text-slate-400 uppercase">
                <th scope="col" className="py-3 pr-4 font-medium">Account</th>
                <th scope="col" className="py-3 pr-4 font-medium">Product</th>
                <th scope="col" className="py-3 pr-4 text-right font-medium">Amount</th>
                <th scope="col" className="py-3 pr-4 text-right font-medium">Rep said</th>
                <th scope="col" className="py-3 pr-4 text-right font-medium text-violet-300">Calibrate</th>
                <th scope="col" className="py-3 font-medium">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {deals.map((d) => {
                const cal = memoryOn ? d.calibrated_prob : d.stated_prob;
                return (
                  <tr key={d.deal_id} className="border-b border-slate-800/60 transition-colors last:border-0 hover:bg-slate-800/30">
                    <td className="py-3.5 pr-4">
                      <p className="text-[16px] font-medium text-white">{d.account}</p>
                      {d.quarter && <p className="text-sm text-slate-400">{d.quarter}</p>}
                    </td>
                    <td className="py-3.5 pr-4 text-[15px] text-slate-300">{d.product}</td>
                    <td className="py-3.5 pr-4 text-right font-mono text-[15px] text-slate-200">{inr(d.amount_inr)}</td>
                    <td className="py-3.5 pr-4 text-right font-mono text-[16px] text-slate-300">{pct(d.stated_prob)}</td>
                    <td className="py-3.5 pr-4 text-right">
                      <span
                        className={`inline-flex items-center gap-1.5 font-mono text-[16px] font-semibold ${
                          memoryOn ? "text-violet-300" : "text-slate-500"
                        }`}
                        title={memoryOn ? undefined : "Memory OFF: Calibrate repeats the rep's number"}
                      >
                        {memoryOn && <Shift from={d.stated_prob} to={cal} />}
                        {pct(cal)}
                      </span>
                    </td>
                    <td className="py-3.5">
                      <OutcomeBadge outcome={d.outcome} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
