import { CircleCheck, CircleX, Clock, Inbox, RotateCcw, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import type { Confidence, Outcome } from "../types";

export function Panel({
  children,
  className = "",
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <section
      style={{ animationDelay: `${delay}ms` }}
      className={`animate-fade-up rounded-2xl border border-slate-800/80 bg-slate-900/60 p-6 shadow-xl shadow-black/30 backdrop-blur-md ${className}`}
    >
      {children}
    </section>
  );
}

export function PanelHeader({
  title,
  subtitle,
  action,
  icon,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <header className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        {icon && (
          <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl bg-slate-800/80 text-slate-200">
            {icon}
          </span>
        )}
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-white">{title}</h2>
          {subtitle && <p className="mt-1 text-[15px] text-slate-400">{subtitle}</p>}
        </div>
      </div>
      {action}
    </header>
  );
}

const CONFIDENCE_STYLE: Record<Confidence, string> = {
  low: "bg-slate-700/60 text-slate-200 ring-slate-500/40",
  medium: "bg-amber-500/15 text-amber-300 ring-amber-400/30",
  high: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30",
};

export function ConfidenceBadge({ level }: { level: Confidence }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-medium capitalize ring-1 ${CONFIDENCE_STYLE[level]}`}
    >
      <span className="flex gap-0.5" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={`h-2.5 w-1 rounded-full ${
              i <= ["low", "medium", "high"].indexOf(level) ? "bg-current" : "bg-current/25"
            }`}
          />
        ))}
      </span>
      {level}
    </span>
  );
}

const OUTCOME_STYLE: Record<Outcome, { cls: string; icon: ReactNode; label: string }> = {
  won: {
    cls: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30",
    icon: <CircleCheck className="size-4" aria-hidden />,
    label: "Won",
  },
  lost: {
    cls: "bg-rose-500/15 text-rose-300 ring-rose-400/30",
    icon: <CircleX className="size-4" aria-hidden />,
    label: "Lost",
  },
  pending: {
    cls: "bg-slate-700/50 text-slate-300 ring-slate-500/40",
    icon: <Clock className="size-4" aria-hidden />,
    label: "Pending",
  },
};

export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  const s = OUTCOME_STYLE[outcome];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-medium ring-1 ${s.cls}`}>
      {s.icon}
      {s.label}
    </span>
  );
}

const AVATAR_TONES = [
  "from-fuchsia-400 to-rose-400",
  "from-sky-400 to-cyan-300",
  "from-amber-300 to-orange-400",
  "from-emerald-300 to-teal-400",
  "from-indigo-400 to-violet-400",
  "from-slate-300 to-slate-500",
];
const REP_ORDER = ["priya", "arjun", "meera", "rahul", "sana", "karan"];

export function RepAvatar({ id, name, size = "md" }: { id: string; name: string; size?: "sm" | "md" | "lg" }) {
  const idx = REP_ORDER.indexOf(id);
  const tone = AVATAR_TONES[(idx < 0 ? name.length : idx) % AVATAR_TONES.length];
  const dim = { sm: "size-8 text-xs", md: "size-10 text-sm", lg: "size-16 text-xl" }[size];
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <span
      aria-hidden
      className={`grid shrink-0 place-items-center rounded-full bg-gradient-to-br font-semibold text-slate-950 ${tone} ${dim}`}
    >
      {initials}
    </span>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

export function LoadingBlock({ label = "Loading…", height = "h-48" }: { label?: string; height?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <Skeleton className={`w-full ${height}`} />
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function ErrorBlock({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-rose-200"
    >
      <span className="flex items-center gap-2 text-base">
        <TriangleAlert className="size-5 shrink-0" aria-hidden />
        {message}
      </span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-full bg-rose-500/20 px-3 py-1.5 text-sm font-medium transition-colors hover:bg-rose-500/30"
        >
          <RotateCcw className="size-4" aria-hidden /> Try again
        </button>
      )}
    </div>
  );
}

export function EmptyBlock({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-700 px-6 py-10 text-center">
      <span className="grid size-11 place-items-center rounded-full bg-slate-800 text-slate-300">
        {icon ?? <Inbox className="size-5" aria-hidden />}
      </span>
      <p className="text-base font-medium text-slate-200">{title}</p>
      {children && <p className="max-w-sm text-[15px] text-slate-400">{children}</p>}
    </div>
  );
}

export function Pill({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full bg-slate-800/80 px-3 py-1 text-sm font-medium text-slate-200 ring-1 ring-slate-700 ${className}`}
    >
      {children}
    </span>
  );
}

export function Spinner({ className = "size-5" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
