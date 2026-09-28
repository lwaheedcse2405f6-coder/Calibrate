export const inCrore = (v: number) => `₹${(v / 1e7).toFixed(1)} Cr`;

/** ₹ in lakhs below 1 crore, crores above. */
export function inr(v: number): string {
  if (v >= 1e7) return `₹${trim((v / 1e7).toFixed(2))} Cr`;
  return `₹${trim((v / 1e5).toFixed(1))} L`;
}

export const pct = (p: number) => `${Math.round(p * 100)}%`;

export const times = (m: number) => `×${trim(m.toFixed(2))}`;

function trim(s: string) {
  return s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s;
}

/** Percentage drop in error from `before` to `after`. */
export const reduction = (before: number, after: number) =>
  before > 0 ? Math.round(((before - after) / before) * 100) : 0;
