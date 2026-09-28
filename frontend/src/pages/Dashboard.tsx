import {
  Activity,
  ArrowRight,
  BrainCircuit,
  ChevronRight,
  CircleCheck,
  IndianRupee,
  Play,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Users,
  WandSparkles,
} from "lucide-react";
import { useMemo, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { AskBox } from "../components/AskBox";
import { BeliefUpdateCard } from "../components/BeliefFeed";
import { PageTitle } from "../components/Layout";
import { ChartLegend, ThreeLineChart, type ChartRow } from "../components/ThreeLineChart";
import { EmptyBlock, ErrorBlock, LoadingBlock, Panel, PanelHeader, RepAvatar, Skeleton } from "../components/ui";
import { useMemory } from "../context/MemoryContext";
import { useAsync } from "../hooks/useAsync";
import { useReplay } from "../hooks/useReplay";
import { inCrore, reduction } from "../lib/format";
import type { BeliefUpdate } from "../types";

function KpiCard({
  icon,
  label,
  value,
  chip,
  chipTone = "good",
  caption,
  delay,
}: {
  icon: ReactNode;
  label: string;
  value?: ReactNode;
  chip?: string;
  chipTone?: "good" | "neutral";
  caption: string;
  delay: number;
}) {
  return (
    <Panel delay={delay} className="flex flex-col justify-between gap-3 !p-5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[15px] font-medium text-slate-300">{label}</span>
        <span className="grid size-9 place-items-center rounded-xl bg-slate-800/80 text-slate-300">{icon}</span>
      </div>
      {value == null ? (
        <Skeleton className="h-10 w-28" />
      ) : (
        <p className="font-mono text-[2rem] leading-none font-semibold tracking-tight text-white">{value}</p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-slate-400">{caption}</span>
        {chip && (
          <span
            className={`rounded-lg px-2 py-0.5 text-sm font-semibold whitespace-nowrap ${
              chipTone === "good" ? "bg-emerald-400 text-emerald-950" : "bg-slate-200 text-slate-900"
            }`}
          >
            {chip}
          </span>
        )}
      </div>
    </Panel>
  );
}

export default function Dashboard() {
  const { memoryOn, mode } = useMemory();
  const onData = useAsync(() => api.quarters("on"), []);
  const offData = useAsync(() => api.quarters("off"), []);
  const scores = useAsync(api.scores, []);
  const reps = useAsync(api.reps, []);
  const evaluation = useAsync(api.evaluation, []);
  const replay = useReplay(mode);

  const current = memoryOn ? onData : offData;
  const full = current.data ?? [];
  const replaying = replay.status !== "idle";

  // Keep the x-axis fixed during the replay: quarters not yet streamed have no values.
  const rows: ChartRow[] = useMemo(() => {
    if (!replaying) return full;
    return full.map((q, i) => replay.points[i] ?? { quarter: q.quarter });
  }, [replaying, full, replay.points]);

  const scaleRows = useMemo(() => [...(onData.data ?? []), ...(offData.data ?? [])], [onData.data, offData.data]);

  const lastScore = scores.data?.[scores.data.length - 1];
  const errorDrop = lastScore ? reduction(lastScore.reps, memoryOn ? lastScore.agent_on : lastScore.agent_off) : undefined;

  const q4 = full[full.length - 1];
  const totalClosed = full.reduce((s, q) => s + q.actual_inr, 0);

  const learned: BeliefUpdate[] = useMemo(() => {
    if (replaying) return replay.updates;
    if (!memoryOn) return [];
    return (onData.data ?? [])
      .flatMap((q) => (q.belief_updates ?? []).map((b) => ({ ...b, quarter: b.quarter ?? q.quarter })))
      .reverse();
  }, [replaying, replay.updates, memoryOn, onData.data]);

  const replayQuarter = replay.points[replay.points.length - 1]?.quarter;
  const latestUpdate = replay.status === "running" ? replay.updates[0] : undefined;

  return (
    <>
      <PageTitle
        title="My Dashboard"
        subtitle="Calibrate remembers every rep's forecasts and what actually closed, learns each rep's bias, and corrects new forecasts."
      />

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left column */}
        <div className="space-y-6 lg:col-span-8 xl:col-span-9">
          <div className="grid gap-6 xl:grid-cols-[1.15fr_1fr]">
            {/* Hero */}
            <section
              className={`relative animate-fade-up overflow-hidden rounded-2xl p-7 shadow-2xl transition-[background] duration-500 ${
                memoryOn
                  ? "bg-gradient-to-br from-violet-600 via-indigo-600 to-sky-500 shadow-violet-900/40"
                  : "bg-gradient-to-br from-slate-700 via-slate-700 to-slate-600 shadow-black/40"
              }`}
            >
              <div className="pointer-events-none absolute -top-24 -right-20 size-72 rounded-full bg-white/10 blur-2xl" aria-hidden />
              <div className="pointer-events-none absolute -bottom-28 left-10 size-72 rounded-full bg-emerald-300/10 blur-3xl" aria-hidden />
              <div className="relative flex h-full flex-col gap-6">
                <div>
                  <p className="text-lg font-medium text-white/85">Forecast error, 2017</p>
                  {errorDrop == null ? (
                    <Skeleton className="mt-3 h-16 w-72 !bg-white/15" />
                  ) : (
                    <p className="mt-2 text-5xl leading-tight font-semibold tracking-tight text-white md:text-6xl">
                      {errorDrop > 0 ? `Down ${errorDrop}%` : "No change"}
                      <span className="block text-2xl font-medium text-white/85 md:text-3xl">by Q4</span>
                    </p>
                  )}
                  <p className="mt-3 max-w-md text-[16px] text-white/85">
                    {memoryOn
                      ? q4 &&
                        `In Q4 reps said ${inCrore(q4.reps_forecast_inr)}, Calibrate said ${inCrore(
                          q4.agent_forecast_inr,
                        )}, and ${inCrore(q4.actual_inr)} actually closed.`
                      : "With memory OFF, Calibrate can only repeat what reps said, so the error stays the same."}
                  </p>
                </div>
                <div className="mt-auto flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={replay.start}
                    disabled={replay.status === "running" || !full.length}
                    className="inline-flex h-12 cursor-pointer items-center gap-2 rounded-xl bg-slate-950 px-5 text-[16px] font-semibold text-white shadow-lg transition-colors hover:bg-black disabled:cursor-wait disabled:opacity-80"
                  >
                    {replay.status === "running" ? (
                      <>
                        <Activity className="size-5 animate-pulse" aria-hidden /> Replaying {replayQuarter ?? "…"}
                      </>
                    ) : replay.status === "done" ? (
                      <>
                        <RotateCcw className="size-5" aria-hidden /> Replay again
                      </>
                    ) : (
                      <>
                        <Play className="size-5" aria-hidden /> Replay the year
                      </>
                    )}
                  </button>
                  <Link
                    to="/forecast"
                    className="inline-flex h-12 items-center gap-2 rounded-xl bg-white px-5 text-[16px] font-semibold text-slate-900 shadow-lg transition-colors hover:bg-slate-100"
                  >
                    <WandSparkles className="size-5" aria-hidden /> Correct a forecast
                  </Link>
                </div>
              </div>
            </section>

            {/* KPIs */}
            <div className="grid grid-cols-2 gap-4">
              <KpiCard
                delay={60}
                icon={<IndianRupee className="size-5" aria-hidden />}
                label="Revenue closed"
                value={full.length ? inCrore(totalClosed) : undefined}
                caption="2017, all reps"
              />
              <KpiCard
                delay={120}
                icon={<ShieldCheck className="size-5" aria-hidden />}
                label="Error reduction"
                value={errorDrop != null ? `${errorDrop}%` : undefined}
                chip={memoryOn ? "Memory ON" : "Memory OFF"}
                chipTone={memoryOn ? "good" : "neutral"}
                caption="Q4 vs. reps"
              />
              <KpiCard
                delay={180}
                icon={<Users className="size-5" aria-hidden />}
                label="Active reps"
                value={reps.data?.length}
                caption="Tracked in memory"
              />
              <KpiCard
                delay={240}
                icon={<BrainCircuit className="size-5" aria-hidden />}
                label="Biases found"
                value={evaluation.data ? `${evaluation.data.biases_found}/${evaluation.data.biases_total}` : undefined}
                chip={evaluation.data ? `${evaluation.data.false_alarms} false alarms` : undefined}
                caption="Hidden biases"
              />
            </div>
          </div>

          {/* Three-line chart */}
          <Panel delay={120} className="relative">
            <PanelHeader
              title="What reps said vs. what Calibrate said vs. what closed"
              subtitle={
                memoryOn
                  ? "The violet line learns each rep's bias and moves towards the green line."
                  : "Memory OFF: the violet line sits on top of the grey one."
              }
              action={
                <div className="flex items-center gap-1 rounded-full border border-slate-800 bg-slate-950/50 p-1" aria-label="Replay progress">
                  {full.map((q, i) => {
                    const reached = !replaying || i < replay.points.length;
                    return (
                      <span
                        key={q.quarter}
                        className={`rounded-full px-3 py-1 font-mono text-sm font-semibold transition-colors duration-300 ${
                          replaying && i === replay.points.length - 1
                            ? "bg-violet-500 text-white"
                            : reached
                              ? "text-slate-200"
                              : "text-slate-600"
                        }`}
                      >
                        {q.quarter.replace(/^\d{4}-/, "")}
                      </span>
                    );
                  })}
                </div>
              }
            />
            <div className="mb-4">
              <ChartLegend />
            </div>
            {current.error ? (
              <ErrorBlock message={current.error} onRetry={current.retry} />
            ) : !current.data ? (
              <LoadingBlock height="h-[340px]" label="Loading chart" />
            ) : (
              <ThreeLineChart data={rows} scaleFrom={scaleRows} />
            )}
            {replay.error && <ErrorBlock message={replay.error} onRetry={replay.start} />}

            {latestUpdate && (
              <div
                key={`${latestUpdate.rep_id}-${latestUpdate.text}`}
                className="pointer-events-none absolute top-28 right-8 z-10 hidden w-80 animate-pop-in rounded-xl border border-violet-400/50 bg-slate-950/90 p-4 shadow-2xl shadow-violet-900/40 backdrop-blur md:block"
                role="status"
              >
                <p className="flex items-center gap-1.5 text-sm font-semibold text-violet-300">
                  <Sparkles className="size-4" aria-hidden /> Calibrate just learned
                </p>
                <p className="mt-1 text-[15px] leading-snug text-white">{latestUpdate.text}</p>
              </div>
            )}
          </Panel>

          <AskBox delay={200} />
        </div>

        {/* Right column */}
        <aside className="space-y-6 lg:col-span-4 xl:col-span-3">
          <Panel delay={80}>
            <PanelHeader
              title="What Calibrate learned"
              subtitle={replaying ? "Live, as each quarter closes" : "Belief updates across 2017"}
            />
            {replay.status === "running" && learned.length === 0 ? (
              <p className="flex items-center gap-2 rounded-xl border border-dashed border-slate-700 p-4 text-[15px] text-slate-300">
                <Activity className="size-5 animate-pulse text-violet-400" aria-hidden /> Watching {replayQuarter ?? "Q1"} close…
              </p>
            ) : learned.length === 0 ? (
              <EmptyBlock title={memoryOn ? "Nothing yet" : "Memory is OFF"}>
                {memoryOn ? "Press “Replay the year” to watch Calibrate learn." : "With no memory, Calibrate learns nothing."}
              </EmptyBlock>
            ) : (
              <ul className="max-h-[560px] space-y-3 overflow-y-auto pr-1" aria-live="polite">
                {learned.map((u, i) => (
                  <li key={`${u.rep_id}-${u.quarter}-${u.text}`}>
                    <BeliefUpdateCard u={u} fresh={replay.status === "running" && i === 0} />
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel delay={160}>
            <PanelHeader
              title="Reps"
              action={
                <Link to="/reps" className="text-sm font-medium text-slate-300 transition-colors hover:text-white">
                  View all
                </Link>
              }
            />
            {evaluation.error ? (
              <ErrorBlock message={evaluation.error} onRetry={evaluation.retry} />
            ) : !evaluation.data ? (
              <LoadingBlock height="h-60" />
            ) : (
              <ul className="space-y-2.5">
                {evaluation.data.rows.map((r) => (
                  <li key={r.rep_id}>
                    <Link
                      to={`/reps/${r.rep_id}`}
                      className="group flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-3 transition-colors hover:border-slate-600"
                    >
                      <RepAvatar id={r.rep_id} name={r.rep_name} />
                      <div className="min-w-0 flex-1">
                        <p className="text-[16px] font-medium text-white">{r.rep_name}</p>
                        <p className="truncate text-sm text-slate-400">
                          {memoryOn ? (r.agent_rule ?? "No bias found") : "Not learned (memory OFF)"}
                        </p>
                      </div>
                      {memoryOn && r.found && r.hidden_bias && <CircleCheck className="size-5 text-emerald-400" aria-label="Bias found" />}
                      <ChevronRight className="size-5 text-slate-500 transition-transform group-hover:translate-x-0.5" aria-hidden />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Link
            to="/evaluation"
            className="group flex animate-fade-up items-center justify-between gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-5 transition-colors hover:bg-emerald-500/15"
          >
            <span>
              <span className="block text-[16px] font-semibold text-emerald-200">See the proof</span>
              <span className="block text-sm text-emerald-100/80">Hidden biases planted vs. found</span>
            </span>
            <ArrowRight className="size-5 text-emerald-300 transition-transform group-hover:translate-x-1" aria-hidden />
          </Link>
        </aside>
      </div>
    </>
  );
}