# Career Quest: explainable development navigator

HackAlem AI, Halyk Bank track, case "Career Quest".

The app gives an employee **1–3 next development steps**. Each step comes with an explanation built from checkable facts. The app also shows a **route of up to 4 activities** to the goal and a what-if preview. HR gets a view of **skills that fall short, why the catalog can't close them, and who has no step**.

The core of the case is the quality and explainability of the recommendation. That's why the numbers are computed by a deterministic core. The LLM chooses among valid options and wording, and the server checks its answer.

## Quick start

```bash
# requirements: Python 3.12 + uv, Node.js >= 20
uv sync
npm install
cp .env.example .env        # put OPENAI_API_KEY here (optional; without it the rules-based fallback is shown honestly)
npm run dev                 # FastAPI :8000 + Next.js :3000 with one command
```

Open http://localhost:3000 and sign in as an employee (search by name/ID) or as HR.

Tests:

```bash
uv run pytest -q            # calculation core, AI response validation, full dataset
npm run build               # typecheck + frontend build
```

### Vercel deployment

One project: Next.js (frontend) + `api/index.py` (FastAPI as a Python Serverless Function, see `vercel.json`).
Environment variables in the Vercel project: `OPENAI_API_KEY` (required for the AI layer) and `OPENAI_MODEL` (default `gpt-4.1-mini`).

```bash
npx vercel login && npx vercel --prod
```

## Architecture

```text
data/dataset/*.json|csv  ─┐
uploaded check scenario  ─┤→ career_quest (pure Python functions, no HTTP/DB)
localStorage overlay     ─┘     dataset.py      loading, validation of jury profiles
(completions, goals,             progression.py  gain/max_level rule, replay of history after the review
 snoozes, settings)              goals.py        effective target, gaps, readiness
                                 history.py      affinity by format/type/skills, development health
                                 engine.py       eligibility, beam search route, ranking, evidence facts, what-if
                                 hr.py           skill deficits, bottleneck detector, participation
                                 ai.py           OpenAI: choosing from the shortlist + server-side validation
                         api/index.py (FastAPI) → Next.js 15 (app/, components/, lib/)
```

**Storage.** Source data ships with the deployment, so a first-time visitor sees all 200 employees at once. User actions are the "overlay": completion marks, chosen goal, snoozes, gamification and personalization settings, the uploaded check scenario. They live in the browser's `localStorage` and survive a page reload. The server is stateless: every request carries the overlay, and the server recomputes the whole state through the same core. That makes it impossible to double-count a completion. Tradeoff: state isn't shared across devices (see Limitations).

**Single calculation core.** Recommendations, simulation, completion and the HR screen call the same functions. The frontend doesn't compute formulas.

## Algorithm (project decisions, not official Halyk methodology)

1. **Current skills** = the last assessment + `completed` records after `last_review_date` (up to the snapshot date `2026-10-01`), applied through
   `actual_gain = max(0, min(gain, max_level − current, 5 − current))`. A skill never goes down. The CSV date is marked as a proxy completion date. The UI shows the formula for each record.
2. **Goal:** user's choice → `career_goal` from the profile → the next grade of the same role (a provisional scenario, labeled as such) → for a Lead, fit with the current role.
3. **Gaps and readiness:** `gap = max(0, required − current)`. Critical skills have weight 2.
   `readiness = Σ w·min(x,r) / Σ w·r`. This is requirement coverage, not a promotion probability.
4. **Eligibility of a step:** not mandatory, audience (current role/grade), prerequisites, not completed yet (except the `EV_036` club), a future session or self-paced, not snoozed. For `in_progress`, the step is "continue".
5. **Route:** bounded beam search (depth 4, beam 40, horizon 120 days). The search state holds the whole skill vector, so AND-prerequisites and caps are handled correctly.
6. **Ranking** (spec §10.4): tiers (0 — reduces a critical gap or opens a route to it; 1 — another goal gap; 2 — preparatory step), then
   `60·G + 25·C + 20·U + 10·(2·affinity−1) + 3·feedback + format bonus + continue bonus − effort − wait`.
   `affinity` uses history by format (0.5), type (0.2) and similar skills (0.3), with recency decay and smoothing. With fewer than 3 observations it is neutral at 0.5, and the explanation says so explicitly.
7. **Evidence facts:** each card gets facts from ≥ 4 categories: profile/grade, target requirement, gap, history, activity effect, eligibility, remaining critical gaps.
8. **Empty result is also an answer:** 0 recommendations with a precise reason (`TARGET_REQUIREMENTS_MET`, `NO_RELEVANT_CATALOG_EVENT`, `SKILL_CAP_CEILING`, `AUDIENCE_MISMATCH`, `PREREQUISITES_UNMET`, …) and a proof level.

**Why "take the lowest skill" doesn't work:** in `tests/test_core.py::test_multi_factor_recommendation_beats_lowest_skill_rule` the lowest skill is Public Speaking with three past no-shows, while System Design is critical for Senior. The engine picks System Design (tier 0), and the explanation includes the history fact.

## The AI layer's role (fair description)

- The model gets a **minimized context**: no name, no ID, no manager. It sees role/grade, the goal, relevant gaps, and up to 8 valid candidates with their facts.
- The model **picks 1–3 steps from the shortlist only** (a JSON Schema with an enum of event_id and fact IDs), orders them, picks the supporting facts, and writes 2–3 sentences of explanation in the user's language.
- The server **validates** the answer (`career_quest/ai.py::validate_selection`):
  - IDs come from the shortlist only;
  - the main step belongs to the minimum tier and is within 15 points of the best one;
  - facts belong to their own candidate and cover ≥ 3 categories, including history;
  - `HISTORY_FAVORABLE` is rejected when history is insufficient;
  - **every number in the text must be present in the chosen facts**, otherwise the text is dropped.
- On a missing key, timeout (9 s), network error or invalid answer, the UI shows "Recommendation calculated by rules; AI is unavailable" with the reason. A template is never passed off as AI.
- Protection from prompt injection: no tools, a strict schema and server-side validation (test `test_rejects_injected_unknown_event`).
- The model is set by `OPENAI_MODEL`. There is no trained ML model for forecasting in the project.

## Main scenario (demo)

1. Sign in as an employee → "My path": profile, goal and readiness, the main step and alternatives with an AI status, route, skill ruler (assessed / from history / required).
2. "Why this step?" shows all facts and the score breakdown. "Why not another?" shows the lowest skill, other candidates and blocked activities with reasons.
3. "What changes?" is a what-if with no data changes. "Mark as done" moves skills, readiness and route (a toast shows the delta in percentage points).
4. Sign in as HR → "Skills and constraints": critical gaps, catalog coverage (has a step / via preparation / no step), bottleneck reasons and a draft of what to change in the catalog. "No next step": the list with reasons. "Participation": voluntary and mandatory activities shown separately.
5. "Data" → upload `employees.json` + `activity_history.csv` of the check profiles → validation report → an isolated check scenario (catalog from the original set, employees and history from the files only).

## Constraints of the case being respected

- No public ratings of people. HR lists are sorted by ID, not by "quality".
- Mandatory activities are not recommended and give no XP.
- Gamification (XP, badges) is off by default, voluntary, and doesn't affect skills or recommendations.
- The employee sees only their own profile. The server checks the `x-role`/`x-actor` headers and returns 403 for someone else's ID. The HR API is for HR only.
- "Not now" doesn't create a `declined` entry and doesn't penalize.

## Limitations (honestly)

- **Demo auth:** the role is picked on the sign-in screen, and permissions are checked on the server based on it. There are no real accounts or passwords.
- **State is in the browser:** marks and the check scenario are local to the browser. On another device the user sees the clean original dataset.
- The route dates are a sequence estimate (self-paced 4 h/day, scheduled ceil(h/8) days), not a booking.
- Readiness and route are not promotion forecasts. The dataset has no capacity or budget data, so HR doesn't get conclusions about a shortage of seats.
- Localization: RU and EN are full; KK covers the main interface, and the rest falls back to Russian. Catalog titles stay in English, as in the dataset.
- The data is synthetic and belongs to the hackathon organizer's dataset.
