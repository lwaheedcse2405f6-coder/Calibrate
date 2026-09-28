// The only file that talks to the backend. VITE_USE_MOCK=false switches to the real API.
import { mockAsk, mockCorrect } from "./mock/engine";
import type {
  AskResponse,
  Belief,
  CalibrationCard,
  CorrectRequest,
  CorrectResponse,
  Deal,
  Evaluation,
  Mode,
  QuarterPoint,
  Rep,
  ScorePoint,
} from "./types";

export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";
export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const BUSY = "The AI is busy. Try again in 30 seconds.";
const MOCK_LATENCY_MS = 650;

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new Error("Can't reach the Calibrate server. Is the backend running?");
  }
  if (res.status === 429) throw new Error(BUSY);
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  // Vite answers unknown paths with index.html, so a missing mock file shows up as HTML.
  if (!(res.headers.get("content-type") ?? "").includes("json")) {
    throw new Error("No data available for this view yet.");
  }
  return res.json() as Promise<T>;
}

const mockUrl = (file: string) => `${import.meta.env.BASE_URL}mock/${file}.json`;

function get<T>(path: string, mockFile: string): Promise<T> {
  return request<T>(USE_MOCK ? mockUrl(mockFile) : `${API_URL}${path}`);
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------------------
// The real backend's field names differ from the mock files this UI was built on
// (e.g. corrected_prob vs calibrated_prob). These functions translate real responses
// into the UI's types, and pass mock data through unchanged.
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Raw = any;

const titleCase = (id: string) => (id ? id.charAt(0).toUpperCase() + id.slice(1) : id);

const TRAIT_LABELS: Record<string, string> = {
  single_contact_no_finance: "single-contact deals with no finance person",
  large_deal: "big-ticket products",
  end_of_quarter: "deals opened in the last 2 weeks of a quarter",
  overall: "all deals",
};

function describeBias(trait: string | null, direction: string | null): string | null {
  if (!trait || !direction) return null;
  const verb = direction === "under" ? "Under-calls" : "Over-calls";
  return `${verb} ${TRAIT_LABELS[trait] ?? trait.replace(/_/g, " ")}`;
}

const toQuarter = (q: Raw): QuarterPoint => ({
  ...q,
  belief_updates: (q.belief_updates ?? []).map((u: Raw) => ({
    rep_id: u.rep_id,
    rep_name: u.rep_name ?? titleCase(u.rep_id),
    quarter: u.quarter ?? q.quarter,
    kind: u.kind ?? "new",
    text: u.text ?? u.belief ?? "",
    n_deals: u.n_deals ?? u.evidence_count,
  })),
});

const toScore = (p: Raw): ScorePoint => ({ ...p, baseline: p.baseline ?? p.baseline_win_rate ?? 0 });

const toCard = (c: Raw, rep: string): CalibrationCard => ({
  ...c,
  rep_id: c.rep_id ?? rep,
  name: c.name ?? titleCase(rep),
  quarter: c.quarter ?? "",
  summary: c.summary ?? "",
  rules: (c.rules ?? []).map((r: Raw) => ({
    condition: r.condition ?? r.trait ?? "",
    stated_win_rate: r.stated_win_rate ?? r.stated_avg ?? 0,
    actual_win_rate: r.actual_win_rate ?? r.actual_rate ?? 0,
    adjustment: r.adjustment ?? 1,
    evidence_count: r.evidence_count ?? 0,
    confidence: r.confidence ?? "low",
  })),
});

function toBeliefs(rows: Raw[]): Belief[] {
  let prevStrength: number | null = null;
  let prevText = "";
  return rows.map((b: Raw, i: number) => {
    if (b.text !== undefined && b.status !== undefined) return b as Belief; // already UI-shaped
    const text = b.belief ?? "";
    const strength = Math.abs((b.adjustment ?? 1) - 1); // how hard the agent corrects
    let change: Belief["change"] = "new";
    if (prevStrength !== null) {
      if (text === prevText) change = "confirmed";
      else if (prevStrength > 0 && strength < prevStrength) change = "softened";
      else if (prevStrength > 0 && strength > prevStrength) change = "strengthened";
    }
    prevStrength = strength;
    prevText = text;
    return {
      quarter: b.quarter,
      text,
      status: i === rows.length - 1 ? "active" : "superseded",
      confidence: b.confidence ?? "low",
      evidence_count: b.evidence_count ?? 0,
      adjustment: b.adjustment,
      change,
    };
  });
}

const toDeal = (d: Raw): Deal => ({
  ...d,
  calibrated_prob: d.calibrated_prob ?? d.corrected_prob ?? d.stated_prob,
  quarter: d.forecast_quarter ?? d.quarter,
});

function toEvaluation(e: Raw): Evaluation {
  if (e.rows) return e as Evaluation;
  return {
    headline: e.headline ?? "",
    biases_found: e.biases_found ?? 0,
    biases_total: e.biases_total ?? 0,
    false_alarms: e.false_alarms ?? 0,
    rows: (e.per_rep ?? []).map((r: Raw) => ({
      rep_id: r.rep_id,
      rep_name: r.rep_name ?? titleCase(r.rep_id),
      hidden_bias: r.hidden_bias ?? describeBias(r.hidden_trait, r.hidden_direction),
      found: r.found === true,
      first_quarter_found: r.first_quarter_found ?? r.first_found_quarter ?? null,
      agent_rule: r.agent_rule ?? null,
    })),
  };
}

const toCorrection = (r: Raw, req: CorrectRequest): CorrectResponse => ({
  ...r,
  stated_prob: r.stated_prob ?? req.stated_prob,
  evidence_deals: (r.evidence_deals ?? r.evidence ?? []).map((e: Raw) => ({
    deal_id: e.deal_id ?? undefined,
    account: e.account ?? e.text ?? "Past deal",
    amount_inr: e.amount_inr,
    stated_prob: e.stated_prob ?? e.stated,
    outcome: e.outcome ?? "pending",
  })),
  questions: r.questions ?? r.questions_to_ask ?? [],
});

const toAsk = (r: Raw): AskResponse => ({ ...r, sources: r.sources ?? r.based_on ?? [] });

export interface ReplayHandlers {
  onQuarter: (q: QuarterPoint) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

export const api = {
  reps: () => get<Rep[]>("/api/reps", "reps"),
  quarters: (mode: Mode) =>
    get<Raw[]>(`/api/quarters?mode=${mode}`, `quarters_${mode}`).then((rows) => rows.map(toQuarter)),
  scores: () => get<Raw[]>("/api/scores", "scores").then((rows) => rows.map(toScore)),
  card: (rep: string, q: string) =>
    get<Raw>(`/api/reps/${rep}/card?quarter=${encodeURIComponent(q)}`, `card_${rep}`).then((c) =>
      toCard(c, rep),
    ),
  beliefs: (rep: string) => get<Raw[]>(`/api/reps/${rep}/beliefs`, `beliefs_${rep}`).then(toBeliefs),
  deals: (rep: string) => get<Raw[]>(`/api/reps/${rep}/deals`, `deals_${rep}`).then((rows) => rows.map(toDeal)),
  evaluation: () => get<Raw>("/api/eval", "eval").then(toEvaluation),

  correct: async (deal: CorrectRequest): Promise<CorrectResponse> => {
    if (!USE_MOCK) return post<Raw>("/api/forecast/correct", deal).then((r) => toCorrection(r, deal));
    await delay(MOCK_LATENCY_MS);
    return mockCorrect(deal, (rep) => api.deals(rep).catch(() => []));
  },

  ask: async (question: string): Promise<AskResponse> => {
    if (!USE_MOCK) return post<Raw>("/api/ask", { question }).then(toAsk);
    await delay(MOCK_LATENCY_MS);
    return mockAsk(question, () => request(mockUrl("ask")));
  },

  /** Streams one quarter at a time. Returns a function that stops the replay. */
  replay: (mode: Mode, h: ReplayHandlers): (() => void) => {
    if (USE_MOCK) {
      let cancelled = false;
      let timer: ReturnType<typeof setTimeout> | undefined;
      api
        .quarters(mode)
        .then((list) => {
          let i = 0;
          const tick = () => {
            if (cancelled) return;
            if (i >= list.length) return h.onDone();
            h.onQuarter(list[i++]);
            timer = setTimeout(tick, 1500);
          };
          timer = setTimeout(tick, 300);
        })
        .catch((e: Error) => !cancelled && h.onError(e.message));
      return () => {
        cancelled = true;
        clearTimeout(timer);
      };
    }

    let finished = false;
    const es = new EventSource(`${API_URL}/api/replay/stream?mode=${mode}`);
    es.onmessage = (e) => {
      try {
        h.onQuarter(toQuarter(JSON.parse(e.data)));
      } catch {
        /* ignore malformed frames */
      }
    };
    es.addEventListener("done", () => {
      finished = true;
      es.close();
      h.onDone();
    });
    es.onerror = () => {
      es.close();
      if (!finished) h.onError("The replay stream disconnected.");
      finished = true;
    };
    return () => {
      finished = true;
      es.close();
    };
  },
};
