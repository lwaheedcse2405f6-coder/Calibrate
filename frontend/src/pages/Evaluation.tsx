import { BarChart3, CircleCheck, CircleX, Microscope, ShieldCheck, TrendingDown, Trophy } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorScoreChart } from "../components/ErrorScoreChart";
import { PageTitle } from "../components/Layout";
import { ErrorBlock, LoadingBlock, Panel, PanelHeader, RepAvatar } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { reduction } from "../lib/format";

export default function Evaluation() {
  const evaluation = useAsync(api.evaluation, []);
  const scores = useAsync(api.scores, []);

  const e = evaluation.data;
  const avg = (k: "reps" | "agent_on" | "agent_off" | "baseline") =>
    scores.data?.length ? scores.data.reduce((s, p) => s + p[k], 0) / scores.data.length : undefined;
  const last = scores.data?.[scores.data.length - 1];

  return (
    <>
      <PageTitle
        title="Evaluation & proof"
        subtitle="We planted a hidden bias in each rep's synthetic history, then checked whether Calibrate found it without being told."
      />

      {/* Headline banner */}
      {evaluation.error ? (
        <div className="mb-6">
          <ErrorBlock message={evaluation.error} onRetry={evaluation.retry} />
        </div>
      ) : !e ? (
        <div className="mb-6">
          <LoadingBlock height="h-40" />
        </div>
      ) : (
        <section className="relative mb-6 animate-fade-up overflow-hidden rounded-2xl border border-emerald-400/30 bg-gradient-to-r from-emerald-600/30 via-slate-900/70 to-violet-600/30 p-7 shadow-2xl">
          <div className="pointer-events-none absolute -top-20 -left-10 size-64 rounded-full bg-emerald-400/20 blur-3xl" aria-hidden />
          <div className="relative flex flex-wrap items-center gap-6">
            <span className="grid size-16 place-items-center rounded-2xl bg-emerald-400 text-emerald-950 shadow-lg shadow-emerald-900/50">
              <Trophy className="size-8" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold tracking-wider text-emerald-300 uppercase">Result</p>
              <h2 className="mt-1 text-3xl leading-tight font-semibold tracking-tight text-white md:text-4xl">{e.headline}</h2>
            </div>
          </div>
          <dl className="relative mt-6 grid gap-4 sm:grid-cols-3">
            {[
              { k: "Hidden biases found", v: `${e.biases_found} of ${e.biases_total}`, icon: <Microscope className="size-5" aria-hidden /> },
              { k: "False alarms", v: String(e.false_alarms), icon: <ShieldCheck className="size-5" aria-hidden /> },
              {
                k: "Error drop by Q4",
                v: last ? `${reduction(last.reps, last.agent_on)}%` : "—",
                icon: <TrendingDown className="size-5" aria-hidden />,
              },
            ].map((s) => (
              <div key={s.k} className="rounded-xl border border-white/10 bg-slate-950/40 p-4 backdrop-blur">
                <dt className="flex items-center gap-2 text-[15px] text-slate-300">
                  {s.icon}
                  {s.k}
                </dt>
                <dd className="mt-1 font-mono text-4xl font-semibold text-white">{s.v}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.25fr_1fr]">
        {/* Bias recovery table */}
        <Panel delay={80}>
          <PanelHeader
            icon={<Microscope className="size-5" aria-hidden />}
            title="Hidden bias scorecard"
            subtitle="What we planted vs. what Calibrate learned on its own."
          />
          {e ? (
            <div className="-mx-6 overflow-x-auto px-6">
              <table className="w-full min-w-[680px] text-left">
                <thead>
                  <tr className="border-b border-slate-800 text-sm font-medium tracking-wide text-slate-400 uppercase">
                    <th scope="col" className="py-3 pr-4 font-medium">Rep</th>
                    <th scope="col" className="py-3 pr-4 font-medium">Hidden bias (planted)</th>
                    <th scope="col" className="py-3 pr-4 text-center font-medium">Found?</th>
                    <th scope="col" className="py-3 pr-4 font-medium">First found</th>
                    <th scope="col" className="py-3 font-medium text-violet-300">Calibrate's rule</th>
                  </tr>
                </thead>
                <tbody>
                  {e.rows.map((r) => {
                    const control = r.hidden_bias == null;
                    const correct = control ? !r.found : r.found;
                    return (
                      <tr key={r.rep_id} className="border-b border-slate-800/60 align-top last:border-0">
                        <td className="py-4 pr-4">
                          <Link to={`/reps/${r.rep_id}`} className="flex items-center gap-2.5 hover:underline">
                            <RepAvatar id={r.rep_id} name={r.rep_name} size="sm" />
                            <span className="text-[16px] font-medium text-white">{r.rep_name}</span>
                          </Link>
                        </td>
                        <td className="py-4 pr-4 text-[15px] text-slate-200">
                          {control ? <span className="text-slate-400 italic">None (control)</span> : r.hidden_bias}
                        </td>
                        <td className="py-4 pr-4 text-center">
                          {correct ? (
                            <CircleCheck className="mx-auto size-7 text-emerald-400" aria-label={control ? "Correctly found nothing" : "Found"} />
                          ) : (
                            <CircleX className="mx-auto size-7 text-rose-400" aria-label="Missed" />
                          )}
                        </td>
                        <td className="py-4 pr-4 font-mono text-[15px] text-slate-300">{r.first_quarter_found ?? "—"}</td>
                        <td className="py-4 text-[15px] text-violet-200">{r.agent_rule ?? <span className="text-slate-400">No rule (correct)</span>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            !evaluation.error && <LoadingBlock height="h-72" />
          )}
        </Panel>

        {/* Error score chart */}
        <Panel delay={140}>
          <PanelHeader
            icon={<BarChart3 className="size-5" aria-hidden />}
            title="Forecast error per quarter"
            subtitle="Brier score: how far each forecast was from what happened."
          />
          {scores.error ? (
            <ErrorBlock message={scores.error} onRetry={scores.retry} />
          ) : scores.data ? (
            <>
              <ErrorScoreChart data={scores.data} />
              <dl className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
                {[
                  { k: "Reps", v: avg("reps") },
                  { k: "Baseline", v: avg("baseline") },
                  { k: "Memory OFF", v: avg("agent_off") },
                  { k: "Memory ON", v: avg("agent_on"), hi: true },
                ].map((s) => (
                  <div
                    key={s.k}
                    className={`rounded-xl border p-3 ${s.hi ? "border-violet-500/50 bg-violet-500/10" : "border-slate-800 bg-slate-950/40"}`}
                  >
                    <dt className="text-sm text-slate-400">{s.k} (avg)</dt>
                    <dd className={`font-mono text-2xl font-semibold ${s.hi ? "text-violet-200" : "text-white"}`}>{s.v?.toFixed(3) ?? "—"}</dd>
                  </div>
                ))}
              </dl>
            </>
          ) : (
            <LoadingBlock height="h-80" />
          )}
        </Panel>
      </div>
    </>
  );
}
