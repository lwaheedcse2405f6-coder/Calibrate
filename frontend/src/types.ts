// Shapes from the API contract. If Role 1's contract differs, change it here only.

export type Mode = "on" | "off";
export type Confidence = "low" | "medium" | "high";
export type Outcome = "won" | "lost" | "pending";
export type BeliefChange = "new" | "strengthened" | "softened" | "confirmed";

export interface Rep {
  rep_id: string;
  name: string;
  region?: string;
  tenure_quarters?: number;
  n_deals?: number;
}

export interface BeliefUpdate {
  rep_id: string;
  rep_name?: string;
  quarter?: string;
  kind?: BeliefChange;
  text: string;
  n_deals?: number;
}

export interface QuarterPoint {
  quarter: string;
  reps_forecast_inr: number;
  agent_forecast_inr: number;
  actual_inr: number;
  belief_updates?: BeliefUpdate[];
}

/** Brier score per quarter. Lower is better. */
export interface ScorePoint {
  quarter: string;
  reps: number;
  agent_off: number;
  agent_on: number;
  baseline: number;
}

export interface CalibrationRule {
  condition: string;
  stated_win_rate: number; // 0–1
  actual_win_rate: number; // 0–1
  adjustment: number; // multiplier, e.g. 0.5
  evidence_count: number;
  confidence: Confidence;
}

export interface CalibrationCard {
  rep_id: string;
  name: string;
  quarter: string;
  summary: string;
  rules: CalibrationRule[];
}

export interface Belief {
  quarter: string;
  text: string;
  status: "active" | "superseded";
  confidence: Confidence;
  evidence_count: number;
  adjustment?: number;
  change?: BeliefChange;
}

export interface Deal {
  deal_id: string;
  account: string;
  product: string;
  amount_inr: number;
  stated_prob: number; // 0–1
  calibrated_prob: number; // 0–1
  outcome: Outcome;
  quarter?: string;
  n_contacts?: number;
  has_finance_contact?: boolean;
  competitor?: boolean;
}

export interface EvalRow {
  rep_id: string;
  rep_name: string;
  hidden_bias: string | null;
  found: boolean;
  first_quarter_found: string | null;
  agent_rule: string | null;
}

export interface Evaluation {
  headline: string;
  biases_found: number;
  biases_total: number;
  false_alarms: number;
  rows: EvalRow[];
}

export const PRODUCTS = [
  "GTX Basic",
  "GTX Pro",
  "GTX Plus Basic",
  "GTX Plus Pro",
  "MG Special",
  "MG Advanced",
  "GTK 500",
] as const;

export interface CorrectRequest {
  rep_id: string;
  account: string;
  product: string;
  amount_inr: number;
  n_contacts: number;
  has_finance_contact: boolean;
  has_champion: boolean;
  competitor: boolean;
  stated_prob: number; // 0–1
}

export interface EvidenceDeal {
  deal_id?: string;
  account: string;
  amount_inr?: number;
  stated_prob?: number;
  outcome: Outcome;
}

export interface CorrectResponse {
  stated_prob: number;
  corrected_prob: number;
  explanation: string;
  evidence_deals: EvidenceDeal[];
  questions: string[];
  memory_used: boolean;
}

export interface AskResponse {
  answer: string;
  sources?: string[];
}
