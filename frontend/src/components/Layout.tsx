import { Brain, Database } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { USE_MOCK } from "../api";
import { useMemory } from "../context/MemoryContext";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/reps", label: "Rep Profiles" },
  { to: "/forecast", label: "Live Calibration" },
  { to: "/evaluation", label: "Evaluation & Proof" },
];

function Logo() {
  return (
    <NavLink to="/" className="flex items-center gap-2.5" aria-label="Calibrate home">
      <span className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-500 shadow-lg shadow-violet-900/40">
        <svg viewBox="0 0 24 24" className="size-6" fill="none" aria-hidden>
          <circle cx="12" cy="12" r="7" stroke="white" strokeWidth="2" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" stroke="white" strokeWidth="2" strokeLinecap="round" />
          <circle cx="12" cy="12" r="2.4" fill="#10B981" />
        </svg>
      </span>
      <span className="text-xl font-semibold tracking-tight text-white">Calibrate</span>
    </NavLink>
  );
}

export function MemoryToggle() {
  const { memoryOn, toggle } = useMemory();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={memoryOn}
      onClick={toggle}
      title={memoryOn ? "Calibrate is using what it learned" : "Calibrate has no memory: it repeats what reps said"}
      className={`group flex cursor-pointer items-center gap-3 rounded-full border py-1.5 pr-1.5 pl-4 transition-all duration-300 ${
        memoryOn
          ? "border-violet-500/60 bg-violet-500/15 shadow-[0_0_24px_-4px_rgb(139_92_246/0.6)]"
          : "border-slate-700 bg-slate-800/70"
      }`}
    >
      <Brain className={`size-5 transition-colors ${memoryOn ? "text-violet-300" : "text-slate-400"}`} aria-hidden />
      <span className="text-[15px] font-medium text-slate-100">Memory</span>
      <span
        className={`relative flex h-8 w-[4.5rem] items-center rounded-full text-xs font-bold tracking-wide transition-colors duration-300 ${
          memoryOn ? "bg-violet-500 text-white" : "bg-slate-600 text-slate-200"
        }`}
      >
        <span className={`absolute ${memoryOn ? "left-2.5" : "right-2.5"}`}>{memoryOn ? "ON" : "OFF"}</span>
        <span
          className={`absolute top-1 size-6 rounded-full bg-white shadow transition-transform duration-300 ${
            memoryOn ? "translate-x-[2.75rem]" : "translate-x-1"
          }`}
        />
      </span>
    </button>
  );
}

function TopNav() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-800/60 bg-ink/75 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 py-4 sm:px-6 lg:px-8">
        <Logo />

        <nav
          aria-label="Main"
          className="order-3 -mx-1 flex w-full gap-1 overflow-x-auto rounded-full border border-slate-800 bg-slate-900/70 p-1.5 lg:order-none lg:mx-0 lg:w-auto"
        >
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `shrink-0 rounded-full px-4 py-2 text-[15px] font-medium whitespace-nowrap transition-colors duration-200 ${
                  isActive ? "bg-slate-100 text-slate-950 shadow" : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          {USE_MOCK && (
            <span
              className="hidden items-center gap-1.5 rounded-full bg-amber-500/10 px-3 py-1.5 text-sm font-medium text-amber-300 ring-1 ring-amber-400/30 xl:inline-flex"
              title="Reading example data from public/mock. Set VITE_USE_MOCK=false for the live backend."
            >
              <Database className="size-4" aria-hidden /> Mock data
            </span>
          )}
          <MemoryToggle />
          <span
            className="hidden size-11 place-items-center rounded-full bg-gradient-to-br from-sky-400 to-indigo-500 text-sm font-semibold text-white ring-2 ring-slate-800 sm:grid"
            title="Sales Ops"
            aria-label="Signed in as Sales Ops"
          >
            SO
          </span>
        </div>
      </div>
    </header>
  );
}

function MemoryBanner() {
  const { memoryOn, setMemoryOn } = useMemory();
  if (memoryOn) return null;
  return (
    <div className="border-b border-slate-800 bg-slate-800/50">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-[15px] sm:px-6 lg:px-8">
        <span className="text-slate-200">
          <strong className="font-semibold text-white">Memory is OFF.</strong> Calibrate has no history, so it just
          repeats what reps said.
        </span>
        <button
          type="button"
          onClick={() => setMemoryOn(true)}
          className="cursor-pointer rounded-full bg-violet-500 px-3.5 py-1 text-sm font-semibold text-white transition-colors hover:bg-violet-400"
        >
          Turn memory on
        </button>
      </div>
    </div>
  );
}

export function Layout() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [pathname]);

  return (
    <div className="min-h-screen">
      <TopNav />
      <MemoryBanner />
      <main className="mx-auto max-w-[1440px] px-4 pt-8 pb-16 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}

export function PageTitle({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-4xl font-semibold tracking-tight text-white md:text-5xl">{title}</h1>
        {subtitle && <p className="mt-2 max-w-2xl text-lg text-slate-400">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}