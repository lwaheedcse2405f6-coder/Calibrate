# Calibrate — 2-Minute Demo Script

> **Owner:** Role 5 — Evaluation & Quality Engineer
> **Format:** Screen-share + narration | Hard stop: 2:10
> **Core Arc:** Problem → Dashboard OFF → Memory ON → Drill-down → Live → Ask

---

## Pre-Demo Checklist

- [ ] App running: `uvicorn backend.main:app --reload`
- [ ] Dashboard open — Memory toggle **OFF**
- [ ] Priya's and Sana's deal cards pre-loaded
- [ ] `eval.json` visible in VS Code side panel
- [ ] Timer set to 2:10

---

## [0:00 – 0:15] Title / Problem

**Action:** Show title screen or opening slide.

> *"Sales reps don't lie. They just believe their own gut. And finance builds the quarter on that gut. Three lines explain why that's a problem:"*

> *"Reps call 85%. They close 52%.*
> Finance forecasts on 85%.*
> Every quarter, the number is wrong."*

> *"This is Calibrate. It fixes the number before it leaves the rep's screen."*

---

## [0:15 – 0:45] Dashboard OFF — The Baseline

**Action:** Point to the Brier score bar chart. Memory toggle is **OFF**.

> *"Here's our dashboard. Memory is OFF. The AI is running, but it has no history. Watch what happens when I load Priya's pipeline."*

**Action:** Click Priya's name. Show her calibration card.

> *"She says 80% on a ₹25-lakh deal. The AI, with no memory, says... 79%. A 1-point nudge. Statistically useless."*

**Action:** Point to the Brier score.

> *"Brier score: 0.33. That's barely better than flipping a coin. This is what 'trust the rep' looks like in a number."*

---

## [0:45 – 1:15] Memory ON — The Reveal

**Action:** Toggle Memory **ON**. Wait for dashboard to update.

> *"Now we switch Memory ON. Hindsight connects. The model sees three years of Priya's history."*

**Action:** Show the memory surface panel — facts, observations, directives loading.

> *"It sees that Priya inflates probability by 22 percentage points at Proposal Sent. It sees her true win rate is 52%, not 80%."*

**Action:** Point to Priya's updated card.

> *"Her card now reads: corrected probability — 58%. That's a 22-point correction. And it's based on 14 real closed deals, not a feeling."*

**Action:** Point to the updated Brier score.

> *"Brier score drops to 0.22. That drop is Memory doing its job. Not the model. The memory."*

---

## [1:15 – 1:35] Priya / Sana Drill-down

**Action:** Switch to Sana's card.

> *"Now look at Sana. She had an overall over-confidence bias. Last quarter, every card flagged it."*

**Action:** Show Sana's latest card — no strong overall/over rule.

> *"This quarter? The flag is gone. Our bias checker — the one that runs automatically — noticed. It injected this:"*

**Action:** Show `eval.json` — highlight `"sana_improvement_noticed": true`.

> *"'Sana improvement noticed.' She recalibrated. The system caught it before her manager did."*

> *"This is what Memory ON looks like for a rep who's genuinely getting better."*

---

## [1:35 – 1:55] Live Form

**Action:** Open the forecast form. Fill in a new deal live.

> *"Let me show you it working in real time."*

**Action:** Type in: Amount = ₹18,00,000 | Stage = Proposal Sent | Win prob = 0.82 | Finance contact = No.

> *"No finance contact on an ₹18-lakh deal at Proposal Sent. That's a single-contact-no-finance pattern."*

**Action:** Click "Get Calibrated Probability". Wait for response.

> *"Corrected probability: 61%. Correction: minus 21 points. Based on 9 past deals of the same type."*

> *"The rep can see exactly why. No black box."*

---

## [1:55 – 2:10] Ask Box

**Action:** Return to the dashboard overview.

> *"67 tests. 0 failures. The no-peeking rule is enforced — the AI literally cannot see the future."*

> *"Memory OFF: Brier 0.137. Memory ON: Brier 0.126. Over 1,162 deals across 4 quarters, memory consistently delivers superior calibration."*

> *"Calibrate doesn't replace your reps. It calibrates them.*
> *One number. Three years of history. No gut feelings."*


> *"Thank you."*

---

## Timing Reference

| Segment | Duration | End Cue |
|---|---|---|
| Title / Problem | 0:15 | "fixes the number" |
| Dashboard OFF | 0:30 | "trust the rep in a number" |
| Memory ON | 0:30 | "Memory doing its job" |
| Priya / Sana Drill-down | 0:20 | "getting better" |
| Live Form | 0:20 | "No black box" |
| Ask Box | 0:15 | "Thank you" |
| **Total** | **2:10** | |

---

## Fallback Lines

| What breaks | What to say |
|---|---|
| App crashes | *"This is why we have 55 tests — we catch this in CI. Here's the eval.json output directly."* |
| Groq API down | *"Memory OFF mode is still live — the point holds. The correction we showed is pre-computed."* |
| Hindsight times out | *"Hindsight is our memory layer. Without it, you get the 0.33 score. That's the argument."* |
| Wrong Brier score shows | *"The exact number depends on the live dataset — what matters is the direction. It drops."* |

---

## Recording Notes

- 1920×1080, 30fps
- OBS or Loom — no background music
- Hard stop at 2:30 (judges mute at 3:00)
- Rehearse twice before recording
