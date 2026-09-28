import { BookOpen, MessageSquareText, SendHorizontal, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { AskResponse } from "../types";
import { ErrorBlock, Panel, PanelHeader, Spinner } from "./ui";

const SUGGESTIONS = [
  "What's our realistic Q3 number?",
  "Which rep should I trust least right now?",
  "Why did you lower Priya's Zenith deal?",
];

export function AskBox({ delay = 0 }: { delay?: number }) {
  const [question, setQuestion] = useState(SUGGESTIONS[0]);
  const [asked, setAsked] = useState<string>();
  const [answer, setAnswer] = useState<AskResponse>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);

  async function ask(q: string) {
    const text = q.trim();
    if (!text || loading) return;
    setQuestion(text);
    setAsked(text);
    setLoading(true);
    setError(undefined);
    try {
      setAnswer(await api.ask(text));
    } catch (e) {
      setAnswer(undefined);
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void ask(question);
  };

  return (
    <Panel delay={delay}>
      <PanelHeader
        icon={<MessageSquareText className="size-5" aria-hidden />}
        title="Ask Calibrate"
        subtitle="Answers come from what Calibrate remembers, with sources."
      />

      <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
        <label htmlFor="ask-input" className="sr-only">
          Your question
        </label>
        <div className="relative flex-1">
          <Sparkles className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-violet-400" aria-hidden />
          <input
            id="ask-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about the forecast…"
            className="h-13 w-full rounded-xl border border-slate-700 bg-slate-950/60 pr-4 pl-12 text-[16px] text-white placeholder:text-slate-500 transition-colors focus:border-violet-500 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="inline-flex h-13 cursor-pointer items-center justify-center gap-2 rounded-xl bg-violet-500 px-6 text-[16px] font-semibold text-white transition-colors hover:bg-violet-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? <Spinner /> : <SendHorizontal className="size-5" aria-hidden />}
          Ask
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => void ask(s)}
            className="cursor-pointer rounded-full border border-slate-700 bg-slate-800/60 px-3.5 py-1.5 text-sm text-slate-300 transition-colors hover:border-violet-500/60 hover:text-white"
          >
            {s}
          </button>
        ))}
      </div>

      <div aria-live="polite" className="mt-5 empty:hidden">
        {loading && (
          <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-slate-300">
            <Spinner className="size-5 text-violet-400" /> Checking memory…
          </div>
        )}
        {error && !loading && <ErrorBlock message={error} onRetry={() => asked && void ask(asked)} />}
        {answer && !loading && (
          <div className="animate-fade-up rounded-xl border border-violet-500/30 bg-violet-500/[0.07] p-5">
            {asked && <p className="mb-2 text-sm font-medium text-slate-400">“{asked}”</p>}
            <p className="text-[17px] leading-relaxed text-slate-100">{answer.answer}</p>
            {answer.sources && answer.sources.length > 0 && (
              <div className="mt-4 border-t border-slate-800 pt-3">
                <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-400">
                  <BookOpen className="size-4" aria-hidden /> Based on
                </p>
                <ul className="flex flex-wrap gap-2">
                  {answer.sources.map((s) => (
                    <li key={s} className="rounded-lg bg-slate-800/80 px-3 py-1.5 text-sm text-slate-200 ring-1 ring-slate-700">
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
