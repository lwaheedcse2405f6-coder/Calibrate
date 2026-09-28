// Stand-in for the backend's correction + Q&A logic so the live demo works on mocks.
import type { AskResponse, CorrectRequest, CorrectResponse, Deal } from "../types";

interface MockRule {
  factor: number;
  explanation: string;
  matches: (d: Deal) => boolean;
  questions: string[];
}

const NAMES: Record<string, string> = {
  priya: "Priya",
  arjun: "Arjun",
  meera: "Meera",
  rahul: "Rahul",
  sana: "Sana",
  karan: "Karan",
};

const RULES: Record<string, (d: CorrectRequest) => MockRule | null> = {
  priya: (d) => {
    if (d.n_contacts <= 1)
      return {
        factor: 0.55,
        explanation:
          "Priya's single-contact deals close far less often than she calls them. Her 85–90% calls with one contact have closed about 45% of the time.",
        matches: (x) => (x.n_contacts ?? 0) <= 1,
        questions: [
          "Who else at the account has seen the proposal?",
          "Can you get a second stakeholder on the next call?",
          "Has anyone in finance approved the budget?",
        ],
      };
    if (!d.has_finance_contact)
      return {
        factor: 0.7,
        explanation:
          "Without a finance contact, Priya's deals have slipped more often than her forecast suggests.",
        matches: (x) => !x.has_finance_contact,
        questions: ["Who signs off on the budget?", "When can we meet their finance team?"],
      };
    return null;
  },
  arjun: (d) =>
    d.stated_prob < 0.5
      ? {
          factor: 1.8,
          explanation:
            "Arjun sandbags. Deals he calls under 50% have actually closed about 64% of the time, so Calibrate raises his number.",
          matches: (x) => x.stated_prob < 0.5,
          questions: [
            "What would have to go wrong for this deal to be lost?",
            "Is the customer already in procurement?",
          ],
        }
      : null,
  meera: (d) =>
    d.competitor
      ? {
          factor: 0.5,
          explanation:
            "Meera discounts competitor risk. When a competitor is involved her deals close about half as often as she forecasts.",
          matches: (x) => !!x.competitor,
          questions: [
            "Which competitor, and how far along are they?",
            "What's our answer if they undercut on price?",
          ],
        }
      : null,
  rahul: (d) =>
    d.amount_inr >= 5_000_000
      ? {
          factor: 0.5,
          explanation:
            "Rahul is over-optimistic on big-ticket deals. Above ₹50 L his calls have closed about 40% of the time against an 80% forecast.",
          matches: (x) => x.amount_inr >= 5_000_000,
          questions: [
            "Is there a signed-off budget for the full amount?",
            "Could this close as a smaller first phase?",
          ],
        }
      : null,
  sana: () => ({
    factor: 0.9,
    explanation:
      "Sana used to be over-optimistic across the board, but since Q3 her calls have been close to reality. Calibrate now applies only a small trim.",
    matches: () => true,
    questions: ["What changed in this deal since last week?"],
  }),
};

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export async function mockCorrect(
  d: CorrectRequest,
  loadDeals: (rep: string) => Promise<Deal[]>,
): Promise<CorrectResponse> {
  const name = NAMES[d.rep_id] ?? d.rep_id;
  const ruleFor = RULES[d.rep_id];

  if (!ruleFor) {
    return {
      stated_prob: d.stated_prob,
      corrected_prob: d.stated_prob,
      explanation: `${name} is new and has no closed deals in memory yet, so Calibrate keeps the rep's number unchanged instead of guessing.`,
      evidence_deals: [],
      questions: ["What's your evidence for this probability?", "Who is the decision maker?"],
      memory_used: false,
    };
  }

  const rule = ruleFor(d);
  const deals = (await loadDeals(d.rep_id)).filter((x) => x.outcome !== "pending");

  if (!rule) {
    return {
      stated_prob: d.stated_prob,
      corrected_prob: d.stated_prob,
      explanation: `This deal doesn't match any of ${name}'s known bias patterns. On deals like this, ${name}'s forecasts have been accurate.`,
      evidence_deals: deals.slice(0, 2),
      questions: ["What's the expected close date?"],
      memory_used: true,
    };
  }

  return {
    stated_prob: d.stated_prob,
    corrected_prob: Math.round(clamp(d.stated_prob * rule.factor, 0.02, 0.97) * 100) / 100,
    explanation: rule.explanation,
    evidence_deals: deals.filter(rule.matches).slice(0, 4),
    questions: rule.questions,
    memory_used: true,
  };
}

export interface MockAskFile {
  answers: { match: string[]; answer: string; sources: string[] }[];
  fallback: AskResponse;
}

export async function mockAsk(question: string, load: () => Promise<MockAskFile>): Promise<AskResponse> {
  const file = await load();
  const q = question.toLowerCase();
  const hit = file.answers.find((a) => a.match.some((m) => q.includes(m)));
  return hit ? { answer: hit.answer, sources: hit.sources } : file.fallback;
}
