import { ArrowRight, BrainCircuit, CircleHelp, FileSearch, Lightbulb, WandSparkles, Zap } from "lucide-react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { PageTitle } from "../components/Layout";
import { EmptyBlock, ErrorBlock, OutcomeBadge, Panel, PanelHeader, Spinner } from "../components/ui";
import { useMemory } from "../context/MemoryContext";
import { useAsync } from "../hooks/useAsync";
import { inr, pct } from "../lib/format";
import { PRODUCTS, type CorrectRequest, type CorrectResponse } from "../types";

interface FormState {
  rep_id: string;
  account: string;
  product: string;
  amount_inr: string;
  n_contacts: string;
  has_finance_contact: boolean;
  has_champion: boolean;
  competitor: boolean;
  stated_pct: number;
}

const PRESETS: { label: string; form: FormState }[] = [
  {
    label: "Priya · 1 contact · 90%",
    form: {
      rep_id: "priya",
      account: "Zenith Logistics",
      product: "GTX Pro",
      amount_inr: "4200000",
      n_contacts: "1",
      has_finance_contact: false,
      has_champion: true,
      competitor: false,
      stated_pct: 90,
    },
  },
  {
    label: "Arjun · sandbagging at 30%",
    form: {
      rep_id: "arjun",
      account: "Vega Telecom",
      product: "MG Advanced",
      amount_inr: "3800000",
      n_contacts: "3",
      has_finance_contact: true,
      has_champion: true,
      competitor: false,
      stated_pct: 30,
    },
  },
  {
    label: "Meera · competitor · 80%",
    form: {
      rep_id: "meera",
      account: "Harbor Shipping",
      product: "GTK 500",
      amount_inr: "6500000",
      n_contacts: "3",
      has_finance_contact: true,
      has_champion: false,
      competitor: true,
      stated_pct: 80,
    },
  },
  {
    label: "Karan · new rep · 75%",
    form: {
      rep_id: "karan",
      account: "Kite Payments",
      product: "GTX Plus Pro",
      amount_inr: "2500000",
      n_contacts: "2",
      has_finance_contact: false,
      has_champion: true,
      competitor: false,
      stated_pct: 75,
    },
  },
];

type Errors = Partial<Record<keyof FormState, string>>;

function validate(f: FormState): Errors {
  const e: Errors = {};
  if (!f.rep_id) e.rep_id = "Choose a rep.";
  if (!f.account.trim()) e.account = "Enter the account name.";
  if (!f.product) e.product = "Choose a product.";
  const amt = Number(f.amount_inr);
  if (!f.amount_inr.trim() || !Number.isFinite(amt) || amt <= 0) e.amount_inr = "Enter an amount above ₹0.";
  else if (amt > 1e10) e.amount_inr = "That's over ₹1,000 Cr. Check the amount.";
  const n = Number(f.n_contacts);
  if (!Number.isInteger(n) || n < 1 || n > 5) e.n_contacts = "Contacts must be a whole number from 1 to 5.";
  return e;
}

const inputCls = (err?: string) =>
  `h-12 w-full rounded-xl border bg-slate-950/60 px-4 text-[16px] text-white placeholder:text-slate-500 transition-colors focus:outline-none ${
    err ? "border-rose-500/70 focus:border-rose-400" : "border-slate-700 focus:border-violet-500"
  }`;

function Field({ id, label, error, hint, children }: { id: string; label: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[15px] font-medium text-slate-200">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${id}-err`} className="mt-1.5 text-sm font-medium text-rose-300" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1.5 text-sm text-slate-400">{hint}</p>
      ) : null}
    </div>
  );
}

function Toggle({ id, label, checked, onChange }: { id: string; label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label
      htmlFor={id}
      className={`flex min-h-12 cursor-pointer items-center justify-between gap-3 rounded-xl border px-4 py-2.5 transition-colors ${
        checked ? "border-violet-500/60 bg-violet-500/10" : "border-slate-700 bg-slate-950/60 hover:border-slate-600"
      }`}
    >
      <span className="text-[15px] font-medium text-slate-100">{label}</span>
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="peer sr-only" />
      <span
        aria-hidden
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-violet-400 ${
          checked ? "bg-violet-500" : "bg-slate-600"
        }`}
      >
        <span className={`absolute top-0.5 size-5 rounded-full bg-white transition-transform ${checked ? "translate-x-5.5" : "translate-x-0.5"}`} />
      </span>
    </label>
  );
}

function Result({ r, repName }: { r: CorrectResponse; repName: string }) {
  const delta = Math.round((r.corrected_prob - r.stated_prob) * 100);
  return (
    <div className="animate-fade-up space-y-5">
      <Panel className="!border-violet-500/40 bg-gradient-to-br from-violet-600/25 via-slate-900/70 to-slate-900/60">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-lg font-medium text-slate-200">{repName} said → Calibrate says</p>
          {r.memory_used ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-violet-500/20 px-3 py-1 text-sm font-semibold text-violet-200 ring-1 ring-violet-400/40">
              <BrainCircuit className="size-4" aria-hidden /> Memory used
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-700/70 px-3 py-1 text-sm font-semibold text-slate-200 ring-1 ring-slate-500/50">
              No memory used
            </span>
          )}
        </div>
        <p className="mt-4 flex flex-wrap items-center gap-4 font-mono font-semibold" aria-label={`${pct(r.stated_prob)} corrected to ${pct(r.corrected_prob)}`}>
          <span className="text-5xl text-slate-400 md:text-6xl">{pct(r.stated_prob)}</span>
          <ArrowRight className="size-10 text-violet-300" aria-hidden />
          <span className="text-6xl text-white drop-shadow-[0_0_24px_rgb(139_92_246/0.6)] md:text-7xl">{pct(r.corrected_prob)}</span>
          {delta !== 0 && (
            <span
              className={`rounded-lg px-2.5 py-1 font-sans text-base font-semibold ${
                delta < 0 ? "bg-rose-500/20 text-rose-200" : "bg-emerald-500/20 text-emerald-200"
              }`}
            >
              {delta > 0 ? "+" : "−"}
              {Math.abs(delta)} pts
            </span>
          )}
        </p>
        <p className="mt-5 text-[17px] leading-relaxed text-slate-100">{r.explanation}</p>
      </Panel>

      <div className="grid gap-5 md:grid-cols-2">
        <Panel>
          <PanelHeader icon={<FileSearch className="size-5" aria-hidden />} title="Evidence deals" />
          {r.evidence_deals.length === 0 ? (
            <p className="text-[15px] text-slate-400">No past deals to point to.</p>
          ) : (
            <ul className="space-y-2.5">
              {r.evidence_deals.map((d) => (
                <li key={d.deal_id ?? d.account} className="flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                  <div className="min-w-0">
                    <p className="truncate text-[15px] font-medium text-white">{d.account}</p>
                    <p className="text-sm text-slate-400">
                      {d.amount_inr != null && inr(d.amount_inr)}
                      {d.stated_prob != null && ` · said ${pct(d.stated_prob)}`}
                    </p>
                  </div>
                  <OutcomeBadge outcome={d.outcome} />
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel>
          <PanelHeader icon={<CircleHelp className="size-5" aria-hidden />} title="Questions to ask the rep" />
          <ul className="space-y-2.5">
            {r.questions.map((q) => (
              <li key={q} className="flex gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-3 text-[15px] text-slate-100">
                <Lightbulb className="mt-0.5 size-4.5 shrink-0 text-amber-300" aria-hidden />
                {q}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}

export default function NewForecast() {
  const [params] = useSearchParams();
  const { memoryOn } = useMemory();
  const reps = useAsync(api.reps, []);
  const initial = PRESETS.find((p) => p.form.rep_id === params.get("rep"))?.form ?? PRESETS[0].form;
  const [form, setForm] = useState<FormState>(initial);
  const [errors, setErrors] = useState<Errors>({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string>();
  const [result, setResult] = useState<{ r: CorrectResponse; repName: string }>();

  // Coming from a rep page with a rep that has no preset: keep the demo deal, switch the rep.
  useEffect(() => {
    const rep = params.get("rep");
    if (rep && !PRESETS.some((p) => p.form.rep_id === rep)) setForm((f) => ({ ...f, rep_id: rep }));
  }, [params]);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    if (errors[k]) setErrors((e) => ({ ...e, [k]: undefined }));
  };

  const repName = (id: string) => reps.data?.find((r) => r.rep_id === id)?.name.split(" ")[0] ?? id;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const errs = validate(form);
    setErrors(errs);
    if (Object.keys(errs).length) return;

    const body: CorrectRequest = {
      rep_id: form.rep_id,
      account: form.account.trim(),
      product: form.product,
      amount_inr: Number(form.amount_inr),
      n_contacts: Number(form.n_contacts),
      has_finance_contact: form.has_finance_contact,
      has_champion: form.has_champion,
      competitor: form.competitor,
      stated_prob: form.stated_pct / 100,
    };

    setApiError(undefined);
    if (!memoryOn) {
      setResult({
        repName: repName(body.rep_id),
        r: {
          stated_prob: body.stated_prob,
          corrected_prob: body.stated_prob,
          explanation: "Memory is OFF. With no history, Calibrate can only repeat the rep's own number. Turn memory on to correct it.",
          evidence_deals: [],
          questions: ["Turn memory on and run this again."],
          memory_used: false,
        },
      });
      return;
    }

    setLoading(true);
    try {
      setResult({ r: await api.correct(body), repName: repName(body.rep_id) });
    } catch (err) {
      setApiError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const amountPreview = Number(form.amount_inr) > 0 ? inr(Number(form.amount_inr)) : undefined;

  return (
    <>
      <PageTitle
        title="Correct this forecast"
        subtitle="Enter a deal the way a rep would. Calibrate checks what it remembers about that rep and corrects the probability."
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <Panel>
          <PanelHeader icon={<Zap className="size-5" aria-hidden />} title="New forecast" />

          <div className="mb-6">
            <p className="mb-2 text-sm font-medium text-slate-400">Demo examples</p>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => {
                    setForm(p.form);
                    setErrors({});
                  }}
                  className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors ${
                    form.rep_id === p.form.rep_id && form.account === p.form.account
                      ? "border-violet-500/60 bg-violet-500/15 text-violet-100"
                      : "border-slate-700 bg-slate-800/60 text-slate-300 hover:border-slate-500 hover:text-white"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={onSubmit} noValidate className="space-y-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <Field id="rep_id" label="Rep" error={errors.rep_id}>
                <select
                  id="rep_id"
                  value={form.rep_id}
                  onChange={(e) => set("rep_id", e.target.value)}
                  className={`${inputCls(errors.rep_id)} cursor-pointer`}
                  aria-invalid={!!errors.rep_id}
                >
                  {!reps.data && <option value={form.rep_id}>{form.rep_id}</option>}
                  {reps.data?.map((r) => (
                    <option key={r.rep_id} value={r.rep_id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field id="product" label="Product" error={errors.product}>
                <select
                  id="product"
                  value={form.product}
                  onChange={(e) => set("product", e.target.value)}
                  className={`${inputCls(errors.product)} cursor-pointer`}
                >
                  {PRODUCTS.map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </Field>
            </div>

            <Field id="account" label="Account name" error={errors.account}>
              <input
                id="account"
                value={form.account}
                onChange={(e) => set("account", e.target.value)}
                placeholder="e.g. Zenith Logistics"
                className={inputCls(errors.account)}
                aria-invalid={!!errors.account}
                aria-describedby={errors.account ? "account-err" : undefined}
              />
            </Field>

            <div className="grid gap-5 sm:grid-cols-2">
              <Field id="amount_inr" label="Deal amount (₹)" error={errors.amount_inr} hint={amountPreview}>
                <input
                  id="amount_inr"
                  inputMode="numeric"
                  value={form.amount_inr}
                  onChange={(e) => set("amount_inr", e.target.value.replace(/[^\d]/g, ""))}
                  placeholder="4200000"
                  className={`${inputCls(errors.amount_inr)} font-mono`}
                  aria-invalid={!!errors.amount_inr}
                  aria-describedby={errors.amount_inr ? "amount_inr-err" : undefined}
                />
              </Field>
              <Field id="n_contacts" label="Contacts on the deal" error={errors.n_contacts} hint="1 to 5">
                <input
                  id="n_contacts"
                  type="number"
                  min={1}
                  max={5}
                  step={1}
                  value={form.n_contacts}
                  onChange={(e) => set("n_contacts", e.target.value)}
                  className={`${inputCls(errors.n_contacts)} font-mono`}
                  aria-invalid={!!errors.n_contacts}
                  aria-describedby={errors.n_contacts ? "n_contacts-err" : undefined}
                />
              </Field>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <Toggle id="has_finance_contact" label="Finance contact" checked={form.has_finance_contact} onChange={(v) => set("has_finance_contact", v)} />
              <Toggle id="has_champion" label="Champion" checked={form.has_champion} onChange={(v) => set("has_champion", v)} />
              <Toggle id="competitor" label="Competitor" checked={form.competitor} onChange={(v) => set("competitor", v)} />
            </div>

            <div>
              <div className="mb-2 flex items-end justify-between">
                <label htmlFor="stated_prob" className="text-[15px] font-medium text-slate-200">
                  Rep's stated probability
                </label>
                <span className="font-mono text-4xl font-semibold text-white">{form.stated_pct}%</span>
              </div>
              <input
                id="stated_prob"
                type="range"
                min={0}
                max={100}
                step={5}
                value={form.stated_pct}
                onChange={(e) => set("stated_pct", Number(e.target.value))}
                className="h-2 w-full cursor-pointer accent-violet-500"
                aria-valuetext={`${form.stated_pct} percent`}
              />
              <div className="mt-1 flex justify-between text-sm text-slate-400">
                <span>0%</span>
                <span>50%</span>
                <span>100%</span>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="inline-flex h-14 w-full cursor-pointer items-center justify-center gap-2.5 rounded-xl bg-violet-500 text-lg font-semibold text-white shadow-lg shadow-violet-900/40 transition-colors hover:bg-violet-400 disabled:cursor-wait disabled:opacity-70"
            >
              {loading ? <Spinner className="size-5" /> : <WandSparkles className="size-5" aria-hidden />}
              {loading ? "Checking memory…" : "Correct this forecast"}
            </button>
          </form>
        </Panel>

        <div aria-live="polite">
          {apiError && !loading ? (
            <ErrorBlock message={apiError} />
          ) : loading ? (
            <Panel className="flex min-h-[420px] flex-col items-center justify-center gap-4 text-center">
              <Spinner className="size-10 text-violet-400" />
              <p className="text-lg text-slate-200">Looking up {repName(form.rep_id)}'s history…</p>
            </Panel>
          ) : result ? (
            <Result r={result.r} repName={result.repName} />
          ) : (
            <Panel className="flex min-h-[420px] items-center justify-center">
              <EmptyBlock title="The corrected forecast shows up here" icon={<WandSparkles className="size-5" aria-hidden />}>
                The Priya example is already filled in. Press “Correct this forecast”.
              </EmptyBlock>
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}
