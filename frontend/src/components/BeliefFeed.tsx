import { CircleCheck, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { BeliefChange, BeliefUpdate } from "../types";
import { RepAvatar } from "./ui";

const ICON: Record<BeliefChange, ReactNode> = {
  new: <Sparkles className="size-4" aria-hidden />,
  strengthened: <TrendingUp className="size-4" aria-hidden />,
  softened: <TrendingDown className="size-4" aria-hidden />,
  confirmed: <CircleCheck className="size-4" aria-hidden />,
};

const LABEL: Record<BeliefChange, string> = {
  new: "New belief",
  strengthened: "Strengthened",
  softened: "Softened",
  confirmed: "Confirmed",
};

export function BeliefUpdateCard({ u, fresh = false }: { u: BeliefUpdate; fresh?: boolean }) {
  const kind = u.kind ?? "new";
  const name = u.rep_name ?? u.rep_id;
  return (
    <Link
      to={`/reps/${u.rep_id}`}
      className={`group block rounded-xl border p-3.5 transition-colors ${
        fresh
          ? "animate-pop-in border-violet-500/50 bg-violet-500/10 shadow-[0_0_28px_-8px_rgb(139_92_246/0.7)]"
          : "border-slate-800 bg-slate-950/40 hover:border-slate-700"
      }`}
    >
      <div className="flex items-start gap-3">
        <RepAvatar id={u.rep_id} name={name} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="inline-flex items-center gap-1 text-sm font-semibold text-violet-300">
              {ICON[kind]} {LABEL[kind]}
            </span>
            {u.quarter && <span className="font-mono text-xs text-slate-400">{u.quarter}</span>}
          </div>
          <p className="mt-1 text-[15px] leading-snug text-slate-100">{u.text}</p>
          {u.n_deals != null && <p className="mt-1 text-sm text-slate-400">{u.n_deals} deals of evidence</p>}
        </div>
      </div>
    </Link>
  );
}
