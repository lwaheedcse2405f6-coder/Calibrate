import { WandSparkles } from "lucide-react";
import { Link, NavLink, useParams } from "react-router-dom";
import { api } from "../api";
import { BeliefTimeline } from "../components/BeliefTimeline";
import { CalibrationCard } from "../components/CalibrationCard";
import { DealsTable } from "../components/DealsTable";
import { ErrorBlock, LoadingBlock, Panel, RepAvatar, Skeleton } from "../components/ui";
import { useMemory } from "../context/MemoryContext";
import { useAsync } from "../hooks/useAsync";
import { pct } from "../lib/format";
import type { Deal } from "../types";

const CARD_QUARTER = "2017-Q4";

function winStats(deals: Deal[]) {
  const closed = deals.filter((d) => d.outcome !== "pending");
  const won = closed.filter((d) => d.outcome === "won").length;
  const avgStated = closed.length ? closed.reduce((s, d) => s + d.stated_prob, 0) / closed.length : 0;
  return { closed: closed.length, won, avgStated, actual: closed.length ? won / closed.length : 0 };
}

export default function RepPage() {
  const { repId = "priya" } = useParams();
  const { memoryOn } = useMemory();
  const reps = useAsync(api.reps, []);
  const card = useAsync(() => api.card(repId, CARD_QUARTER), [repId]);
  const beliefs = useAsync(() => api.beliefs(repId), [repId]);
  const deals = useAsync(() => api.deals(repId), [repId]);

  const rep = reps.data?.find((r) => r.rep_id === repId);
  const name = rep?.name ?? card.data?.name ?? repId;
  const first = name.split(" ")[0];
  const stats = deals.data ? winStats(deals.data) : undefined;

  return (
    <>
      {/* Rep selector */}
      <nav aria-label="Choose a rep" className="mb-8 -mx-1 flex gap-3 overflow-x-auto px-1 pb-2">
        {(reps.data ?? []).map((r) => (
          <NavLink
            key={r.rep_id}
            to={`/reps/${r.rep_id}`}
            className={({ isActive }) =>
              `flex shrink-0 items-center gap-3 rounded-2xl border py-2.5 pr-5 pl-2.5 transition-all duration-200 ${
                isActive
                  ? "border-violet-500/60 bg-violet-500/15 shadow-[0_0_24px_-8px_rgb(139_92_246/0.8)]"
                  : "border-slate-800 bg-slate-900/60 hover:border-slate-600"
              }`
            }
          >
            <RepAvatar id={r.rep_id} name={r.name} />
            <span className="text-left">
              <span className="block text-[16px] font-medium text-white">{r.name.split(" ")[0]}</span>
              {r.region && <span className="block text-sm text-slate-400">{r.region}</span>}
            </span>
          </NavLink>
        ))}
        {reps.loading && !reps.data && [0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-16 w-40 shrink-0" />)}
      </nav>
      {reps.error && (
        <div className="mb-6">
          <ErrorBlock message={reps.error} onRetry={reps.retry} />
        </div>
      )}

      {/* Header */}
      <Panel className="mb-6">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div className="flex items-center gap-5">
            <RepAvatar id={repId} name={name} size="lg" />
            <div>
              <h1 className="text-4xl font-semibold tracking-tight text-white">{name}</h1>
              {card.data ? (
                <p className="mt-1.5 max-w-2xl text-lg text-slate-300">{card.data.summary}</p>
              ) : card.loading ? (
                <Skeleton className="mt-2 h-6 w-96 max-w-full" />
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-6">
            {stats && stats.closed > 0 && (
              <dl className="flex gap-6">
                <div>
                  <dt className="text-sm text-slate-400">Usually says</dt>
                  <dd className="font-mono text-3xl font-semibold text-slate-200">{pct(stats.avgStated)}</dd>
                </div>
                <div>
                  <dt className="text-sm text-slate-400">Actually wins</dt>
                  <dd className="font-mono text-3xl font-semibold text-emerald-400">{pct(stats.actual)}</dd>
                </div>
              </dl>
            )}
            <Link
              to={`/forecast?rep=${repId}`}
              className="inline-flex h-12 items-center gap-2 rounded-xl bg-violet-500 px-5 text-[16px] font-semibold text-white transition-colors hover:bg-violet-400"
            >
              <WandSparkles className="size-5" aria-hidden /> Correct a {first} forecast
            </Link>
          </div>
        </div>
      </Panel>

      <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <div className="space-y-6">
          {card.error ? (
            <ErrorBlock message={card.error} onRetry={card.retry} />
          ) : card.data ? (
            <CalibrationCard card={card.data} memoryOn={memoryOn} />
          ) : (
            <LoadingBlock height="h-80" label="Loading calibration card" />
          )}

          {deals.error ? (
            <ErrorBlock message={deals.error} onRetry={deals.retry} />
          ) : deals.data ? (
            <DealsTable deals={deals.data} memoryOn={memoryOn} />
          ) : (
            <LoadingBlock height="h-72" label="Loading deals" />
          )}
        </div>

        <div>
          {beliefs.error ? (
            <ErrorBlock message={beliefs.error} onRetry={beliefs.retry} />
          ) : beliefs.data ? (
            <BeliefTimeline beliefs={beliefs.data} repName={first} />
          ) : (
            <LoadingBlock height="h-[480px]" label="Loading belief timeline" />
          )}
        </div>
      </div>
    </>
  );
}
