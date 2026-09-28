# Calibrate frontend

React 18 + TypeScript + Vite + Tailwind v4 + Recharts + Lucide.

```bash
npm install
cp .env.example .env.local   # VITE_USE_MOCK=true by default
npm run dev                  # http://localhost:5173
```

Commit `package-lock.json` after the first `npm install` (CI runs `npm ci`).

## Pages

| Route | What it shows |
| --- | --- |
| `/` | KPIs, the three-line chart, animated replay with live belief updates, Ask box |
| `/reps/:repId` | Calibration card, belief timeline, deals table |
| `/forecast` | "Correct this forecast" live form (Priya demo pre-filled; `?rep=arjun` pre-selects) |
| `/evaluation` | Hidden-bias scorecard and error-score (Brier) chart |

The **Memory ON/OFF** switch in the header is global. OFF loads `quarters_off`, strikes out the
card multipliers, shows reps' own numbers in the deals table, and makes the live form pass the
stated probability through unchanged.

## Data

`src/api.ts` is the only file that fetches. With `VITE_USE_MOCK=true` it reads
`public/mock/*.json`, fakes the replay stream with a 1.5 s timer, and answers
`/api/forecast/correct` and `/api/ask` with `src/mock/engine.ts`. Set `VITE_USE_MOCK=false`
to hit `VITE_API_URL` (default `http://localhost:8000`), including the SSE stream at
`/api/replay/stream?mode=on|off`.

All response shapes are in `src/types.ts`. If Role 1's contract uses different field names,
change them there and in the mock files.

Colour key: violet = Calibrate, green = what actually closed, grey dashed = what reps said.
