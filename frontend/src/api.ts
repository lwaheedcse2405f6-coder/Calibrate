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

export interface ReplayHandlers {
  onQuarter: (q: QuarterPoint) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

export const api = {
  reps: () => get<Rep[]>("/api/reps", "reps"),
  quarters: (mode: Mode) => get<QuarterPoint[]>(`/api/quarters?mode=${mode}`, `quarters_${mode}`),
  scores: () => get<ScorePoint[]>("/api/scores", "scores"),
  card: (rep: string, q: string) =>
    get<CalibrationCard>(`/api/reps/${rep}/card?quarter=${encodeURIComponent(q)}`, `card_${rep}`),
  beliefs: (rep: string) => get<Belief[]>(`/api/reps/${rep}/beliefs`, `beliefs_${rep}`),
  deals: (rep: string) => get<Deal[]>(`/api/reps/${rep}/deals`, `deals_${rep}`),
  evaluation: () => get<Evaluation>("/api/eval", "eval"),

  correct: async (deal: CorrectRequest): Promise<CorrectResponse> => {
    if (!USE_MOCK) return post<CorrectResponse>("/api/forecast/correct", deal);
    await delay(MOCK_LATENCY_MS);
    return mockCorrect(deal, (rep) => api.deals(rep).catch(() => []));
  },

  ask: async (question: string): Promise<AskResponse> => {
    if (!USE_MOCK) return post<AskResponse>("/api/ask", { question });
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
        h.onQuarter(JSON.parse(e.data) as QuarterPoint);
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
