"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, post } from "@/lib/api";
import { Meta, useApi } from "@/lib/hooks";
import { HEALTH_TEXT, pick, reasonText, renderFact, translator } from "@/lib/i18n";
import { AppState, currentOverlay, updateOverlay, useAppState } from "@/lib/store";
import { CareerGraph } from "@/components/CareerGraph";
import { CareerGraphData, GRAPH_COPY } from "@/lib/career-graph";

type Fact = { id: string; category: string; code: string; values: Record<string, any> };
type Cand = {
  event_id: string;
  title: string;
  type: string;
  format: string;
  duration_hours: number;
  action_kind: "start" | "continue";
  session: string | null;
  tier: number;
  score: number;
  breakdown: Record<string, number>;
  facts: Fact[];
  remaining_hours: number;
  history: { insufficient: boolean };
};
type Snapshot = any;
type Ai = { ai_status: string; model: string; choices: { event_id: string; evidence_ids: string[]; reason_codes: string[]; explanation: string }[]; elapsed_ms: number; fingerprint: string; validation?: string[] };

const pct = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(1));

export function EmployeeView({ employeeId, meta, section }: { employeeId: string; meta: Meta; section: string }) {
  const s = useAppState();
  const t = translator(s.locale);
  const { data: snap, error, loading } = useApi<Snapshot>(s, `/employees/${employeeId}`);
  const skill = (id: string) => meta.skills[id]?.name ?? id;
  const event = (id: string) => meta.events[id]?.title ?? id;
  const [toast, setToast] = useState<string | null>(null);
  const prevReadiness = useRef<number | null>(null);

  useEffect(() => {
    if (!snap) return;
    const now = snap.readiness.readiness_pct;
    if (prevReadiness.current != null && Math.abs(now - prevReadiness.current) > 0.001) {
      const d = now - prevReadiness.current;
      setToast(`${t("readinessDelta")}: ${pct(prevReadiness.current)}% → ${pct(now)}% (${d > 0 ? "+" : ""}${d.toFixed(1)} ${pick({ ru: "п.п.", en: "pp", kk: "п.т." }, s.locale)})`);
      setTimeout(() => setToast(null), 4000);
    }
    prevReadiness.current = now;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snap?.fingerprint]);

  if (error instanceof ApiError && error.status === 403) return <p>{t("forbidden")}</p>;
  if (!snap) return <p className="muted">{loading ? t("loading") : String(error)}</p>;

  const ctx = { s, t, snap, meta, skill, event, employeeId };
  return (
    <div className="stack">
      {section === "path" && <PathSection {...ctx} />}
      {section === "activities" && <Catalog {...ctx} />}
      {section === "history" && <History {...ctx} />}
      {section === "settings" && <Settings {...ctx} />}
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}

type Ctx = { s: AppState; t: ReturnType<typeof translator>; snap: Snapshot; meta: Meta; skill: (id: string) => string; event: (id: string) => string; employeeId: string };

function markDone(ctx: Ctx, c: { event_id: string; session: string | null }) {
  const gaming = !!currentOverlay(ctx.s).gaming[ctx.employeeId];
  updateOverlay((o) => ({
    ...o,
    completions: [...o.completions, { employee_id: ctx.employeeId, event_id: c.event_id, session_date: c.session, gaming }],
  }));
}

function toggleSnooze(ctx: Ctx, eventId: string) {
  updateOverlay((o) => {
    const cur = new Set(o.snoozes[ctx.employeeId] ?? []);
    cur.has(eventId) ? cur.delete(eventId) : cur.add(eventId);
    return { ...o, snoozes: { ...o.snoozes, [ctx.employeeId]: [...cur] } };
  });
}

function PathSection(ctx: Ctx) {
  const { snap, t } = ctx;
  return (
    <>
      <Hero {...ctx} />
      <NextStep {...ctx} />
      <Route {...ctx} />
      <Skills {...ctx} />
      {snap.gamification.opt_in && <Achievements {...ctx} />}
    </>
  );
}

function Hero(ctx: Ctx) {
  const { snap, t, meta } = ctx;
  const e = snap.employee;
  const r = snap.readiness;
  const [editing, setEditing] = useState(false);
  const [goal, setGoal] = useState(`${snap.target.role}|${snap.target.grade}`);
  return (
    <section className="hero">
      <div className="panel who">
        <h1>{e.full_name}</h1>
        <div className="facts">
          <span>{e.role}</span>
          <span>{e.grade}</span>
          <span>{e.department}</span>
          <span>
            {t("tenure")}: {e.tenure_months} {t("months")}
          </span>
          <span>{e.work_format}</span>
        </div>
        <div className="facts small">
          <span>
            {t("lastReview")}: {e.last_review_date}
          </span>
          <span>
            {t("asOf")}: {snap.as_of}
          </span>
        </div>
        <div className="goal-line">
          <span className="from">
            {e.role} {e.grade}
          </span>
          <span className="arrow" aria-hidden>
            ⟶
          </span>
          <span className="to">
            {snap.target.role} {snap.target.grade}
          </span>
        </div>
        <p className="small muted" style={{ marginTop: 6 }}>
          {t("src_" + snap.target.source)}
        </p>
        {!editing ? (
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn small" onClick={() => setEditing(true)}>
              {t("changeGoal")}
            </button>
            {snap.target.source === "user" && (
              <button
                className="btn ghost small"
                onClick={() =>
                  updateOverlay((o) => {
                    const g = { ...o.goals };
                    delete g[ctx.employeeId];
                    return { ...o, goals: g };
                  })
                }
              >
                {t("resetGoal")}
              </button>
            )}
          </div>
        ) : (
          <div className="row" style={{ marginTop: 12 }}>
            <select className="input" style={{ maxWidth: 320 }} value={goal} onChange={(ev) => setGoal(ev.target.value)}>
              {meta.targets.map((x) => (
                <option key={x} value={x}>
                  {x.replace("|", " — ")}
                </option>
              ))}
            </select>
            <button
              className="btn primary small"
              onClick={() => {
                const [role, grade] = goal.split("|");
                updateOverlay((o) => ({ ...o, goals: { ...o.goals, [ctx.employeeId]: { mode: "set", target_role: role, target_grade: grade } } }));
                setEditing(false);
              }}
            >
              {t("save")}
            </button>
          </div>
        )}
      </div>
      <div className="panel">
        <div className="section-head">
          <h2>{t("readiness")}</h2>
          <span className={`chip ${r.critical_gate_met ? "" : "amber"}`}>{r.critical_gate_met ? t("criticalMet") : t("criticalOpen")}</span>
        </div>
        <div className="readiness">
          <div className="num">
            {pct(r.readiness_pct)}
            <small>%</small>
          </div>
          <div className="small muted" style={{ paddingBottom: 6 }}>
            {t("critical")}: {pct(r.critical_readiness_pct)}%
          </div>
        </div>
        <div className="bar" aria-hidden>
          <span style={{ width: `${r.readiness_pct}%` }} />
        </div>
        <p className="small muted" style={{ marginTop: 12 }}>
          {t("readinessHint")}
        </p>
      </div>
    </section>
  );
}

function NextStep(ctx: Ctx) {
  const { snap, t, s, employeeId } = ctx;
  const [ai, setAi] = useState<Ai | null>(null);
  const [aiPending, setAiPending] = useState(false);
  const shortlist: Cand[] = snap.shortlist;
  useEffect(() => {
    if (!shortlist.length) return;
    let alive = true;
    setAiPending(true);
    setAi(null);
    const timer = setTimeout(() => alive && setAiPending(false), 10000);
    post<Ai>(s, `/employees/${employeeId}/ai`)
      .then((r) => alive && r.fingerprint === snap.fingerprint && setAi(r))
      .catch(() => alive && setAi({ ai_status: "fallback_unavailable", model: "", choices: [], elapsed_ms: 0, fingerprint: snap.fingerprint }))
      .finally(() => {
        clearTimeout(timer);
        if (alive) setAiPending(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snap.fingerprint, s.locale]);

  // an ai answer for an older state (before completion / goal change) must never be rendered
  const live = ai?.ai_status === "live_validated" && ai.fingerprint === snap.fingerprint;
  const byId = Object.fromEntries(shortlist.map((c) => [c.event_id, c]));
  const baseline = (snap.recommendations as Cand[]).map((c) => ({ cand: c }));
  // ai may return fewer than 3; fill the rest from the rule-based ranking without ai text
  const ordered: { cand: Cand; choice?: Ai["choices"][number] }[] = live
    ? [
        ...ai!.choices.filter((ch) => byId[ch.event_id]).map((ch) => ({ cand: byId[ch.event_id], choice: ch })),
        ...baseline.filter((b) => !ai!.choices.some((ch) => ch.event_id === b.cand.event_id)),
      ].slice(0, 3)
    : baseline;

  return (
    <section>
      <div className="section-head">
        <h2>{t("nextStep")}</h2>
        {shortlist.length > 0 &&
          (aiPending ? (
            <span className="ai-status pending">
              <span className="dot" />
              {t("aiChecking")}
            </span>
          ) : live ? (
            <span className="ai-status live" title={`${ai!.model}, ${ai!.elapsed_ms} ms`}>
              <span className="dot" />
              {t("aiLive")} · {ai!.model}
            </span>
          ) : (
            <span className="ai-status fallback">
              <span className="dot" />
              {t("aiFallback")}
              {ai ? ` (${t(ai.ai_status)})` : ""}
            </span>
          ))}
      </div>
      {ordered.length === 0 ? (
        <NoStep {...ctx} />
      ) : (
        <div className="recs">
          <RecCard ctx={ctx} cand={ordered[0].cand} choice={ordered[0].choice} main />
          <div className="alts">
            {ordered.slice(1).map((o) => (
              <RecCard key={o.cand.event_id} ctx={ctx} cand={o.cand} choice={o.choice} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

const CAT: Record<string, string> = {
  profile: "Профиль",
  target_requirement: "Требование цели",
  skill_gap: "Разрыв",
  event_effect: "Эффект",
  history: "История",
  eligibility: "Допуск",
  prerequisite_path: "Маршрут",
  limitation: "Ограничение",
};
const CAT_KK: Record<string, string> = {
  profile: "Профиль",
  target_requirement: "Мақсат талабы",
  skill_gap: "Алшақтық",
  event_effect: "Әсері",
  history: "Тарих",
  eligibility: "Қатысу шарты",
  prerequisite_path: "Жол",
  limitation: "Шектеу",
};
const CAT_EN: Record<string, string> = {
  profile: "Profile",
  target_requirement: "Goal requirement",
  skill_gap: "Gap",
  event_effect: "Effect",
  history: "History",
  eligibility: "Eligibility",
  prerequisite_path: "Route",
  limitation: "Limitation",
};

function RecCard({ ctx, cand, choice, main }: { ctx: Ctx; cand: Cand; choice?: Ai["choices"][number]; main?: boolean }) {
  const { t, s, skill, event } = ctx;
  const [open, setOpen] = useState<"why" | "whynot" | null>(null);
  const [sim, setSim] = useState(false);
  const chosen = new Set(choice?.evidence_ids ?? []);
  // short explanation: AI-chosen facts when validated, otherwise a fixed rule-based subset
  const summaryFacts = choice
    ? cand.facts.filter((f) => chosen.has(f.id))
    : cand.facts.filter((f) => ["SKILL_GAP", "EVENT_EFFECT", "HISTORY_INSUFFICIENT", "HISTORY_GROUP", "TARGET_CONTEXT"].includes(f.code)).slice(0, 5);
  const catName = s.locale === "en" ? CAT_EN : s.locale === "kk" ? CAT_KK : CAT;
  return (
    <article className={`rec ${main ? "main" : "alt"}`}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="kind">{main ? t("mainStep") : t("alternative")} · {t("tier" + cand.tier)}</span>
        <span className="chip grey">
          {cand.format} · {cand.type} · {cand.action_kind === "continue" ? `≈${cand.remaining_hours.toFixed(0)}` : cand.duration_hours} {t("hours")}
        </span>
      </div>
      <div className="title">{cand.title}</div>
      <div className="small muted">{cand.session ? `${t("session")}: ${cand.session}` : cand.action_kind === "continue" ? t("continue") : t("selfPaced")}</div>
      {choice?.explanation && <p className="ai-text">{choice.explanation}</p>}
      <ul className="facts">
        {summaryFacts.map((f) => (
          <li key={f.id}>{renderFact(f, s.locale, skill, event, t)}</li>
        ))}
      </ul>
      {open === "why" && (
        <div className="evidence">
          {cand.facts.map((f) => (
            <div key={f.id} className={`fact ${chosen.has(f.id) ? "chosen" : ""}`}>
              <span className="cat">
                {f.id} · {catName[f.category] ?? f.category}
              </span>
              <span>{renderFact(f, s.locale, skill, event, t)}</span>
            </div>
          ))}
          <div>
            <p className="small muted" style={{ margin: "6px 0" }}>
              {t("scoreBreakdown")}: {cand.score}
            </p>
            <div className="breakdown">
              {Object.entries(cand.breakdown).map(([k, v]) => (
                <FragmentRow key={k} k={k} v={v} />
              ))}
            </div>
          </div>
        </div>
      )}
      {open === "whynot" && <WhyNot ctx={ctx} cand={cand} />}
      <div className="actions">
        <button className="btn primary small" onClick={() => markDone(ctx, cand)}>
          {t("markDone")}
        </button>
        <button className="btn small" onClick={() => setSim(true)}>
          {t("whatIf")}
        </button>
        <button className="btn ghost small" aria-expanded={open === "why"} onClick={() => setOpen(open === "why" ? null : "why")}>
          {t("why")}
        </button>
        {main && (
          <button className="btn ghost small" aria-expanded={open === "whynot"} onClick={() => setOpen(open === "whynot" ? null : "whynot")}>
            {t("whyNot")}
          </button>
        )}
        <button className="btn ghost small" onClick={() => toggleSnooze(ctx, cand.event_id)}>
          {t("snooze")}
        </button>
      </div>
      {sim && <Simulation ctx={ctx} steps={[cand.event_id]} onClose={() => setSim(false)} />}
    </article>
  );
}

function FragmentRow({ k, v }: { k: string; v: number }) {
  return (
    <>
      <span>{k.replace(/_/g, " ")}</span>
      <b>{v > 0 ? `+${v}` : v}</b>
    </>
  );
}

function WhyNot({ ctx, cand }: { ctx: Ctx; cand: Cand }) {
  const { snap, s, t, skill } = ctx;
  const lowest = [...snap.skills].filter((x: any) => x.in_target && x.gap > 0).sort((a: any, b: any) => a.current - b.current)[0];
  const blocked = (snap.catalog as any[]).filter(
    (c) => !c.eligible && !c.reasons.some((r: any) => r.code === "MANDATORY" || r.code === "AUDIENCE_MISMATCH"),
  );
  return (
    <div className="evidence small">
      {lowest && lowest.skill_id && (
        <p>
          {pick({ ru: "Самый низкий навык цели", en: "Lowest goal skill", kk: "Мақсаттың ең төмен дағдысы" }, s.locale)}: <b>{skill(lowest.skill_id)}</b> ({lowest.current}/{lowest.required}
          {lowest.critical ? ", critical" : ""}). {pick(
            {
              ru: "Ранжирование учитывает критичность (×2), закрытие разрыва и историю — не только минимальный навык.",
              en: "Ranking weighs critical gaps ×2 and history, not just the minimum.",
              kk: "Рейтинг тек ең төмен дағдыны емес, сыни маңыздылықты (×2), алшақтықтың жабылуын және тарихты ескереді.",
            },
            s.locale,
          )}
        </p>
      )}
      {(snap.alternatives_considered as any[]).map((a) => (
        <p key={a.event_id}>
          <b>{a.title}</b> — {t("tier" + a.tier)}, {a.score} vs {cand.score}; {pick({ ru: "история", en: "history fit", kk: "тарих" }, s.locale)} {a.breakdown.history_fit}
        </p>
      ))}
      {blocked.slice(0, 4).map((c) => (
        <p key={c.event_id}>
          <b>{c.title}</b> — {c.reasons.map((r: any) => reasonText(r.code, s.locale)).join("; ")}
        </p>
      ))}
    </div>
  );
}

function NoStep(ctx: Ctx) {
  const { snap, t, s, skill, event } = ctx;
  return (
    <div className="panel">
      <h3>{t("noStep")}</h3>
      <ul style={{ margin: "10px 0 0", paddingLeft: 18 }}>
        {snap.no_step_reasons.map((r: any) => (
          <li key={r.code} style={{ marginBottom: 6 }}>
            {reasonText(r.code, s.locale)}
            {r.skills?.length ? `: ${r.skills.map(skill).join(", ")}` : ""}
            {r.event_ids?.length ? <span className="muted small"> ({r.event_ids.map(event).join(", ")})</span> : null}{" "}
            <span className="chip grey">{t("proof_" + r.proof_level)}</span>
          </li>
        ))}
      </ul>
      {snap.snoozed.length > 0 && (
        <div className="row" style={{ marginTop: 12 }}>
          {snap.snoozed.map((id: string) => (
            <button key={id} className="btn small" onClick={() => toggleSnooze(ctx, id)}>
              {t("unsnooze")}: {event(id)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Route(ctx: Ctx) {
  const { snap, t, skill, event } = ctx;
  const [sim, setSim] = useState(false);
  const best = snap.plan.best;
  const graph: CareerGraphData = snap.career_graph;
  const copy = GRAPH_COPY[ctx.s.locale];
  const remaining = graph.nodes.filter((n) => n.kind === "skill" && n.required != null && n.planned < n.required);
  return (
    <section className="panel">
      <div className="section-head">
        <h2>Career Graph · {t("route")}</h2>
        <span className="small muted">{t("plan_" + snap.plan.status)}</span>
      </div>
      <CareerGraph key={`${snap.dataset}:${ctx.employeeId}:${snap.fingerprint}`} graph={graph} locale={ctx.s.locale} skillName={skill} />
      {!best ? (
        <p className="muted">{snap.plan.status === "not_run" ? t("plan_not_run") : t("routeNone")}</p>
      ) : (
        <>
          <details className="graph-compact-route">
          <summary>{copy.route} · {copy.forecast}</summary>
          <ol className="route">
            {best.steps.map((st: any, i: number) => (
              <li key={st.event_id}>
                <span className="node">{i + 1}</span>
                <div className="step-title">
                  {event(st.event_id)} {st.action_kind === "continue" && <span className="chip">{t("continue")}</span>}
                </div>
                <div className="changes">
                  {st.estimated_start} → {st.estimated_finish} · {st.changes.map((c: any) => `${skill(c.skill_id)} ${c.before}→${c.after}`).join(", ")}
                </div>
              </li>
            ))}
            <li className="goal">
              <span className="node">✓</span>
              <div className="step-title">
                {snap.target.role} {snap.target.grade}
              </div>
              <div className="changes">
                {best.weighted_gap_after === 0
                  ? t("plan_target_reached_in_plan")
                  : `${t("gap")}: ${best.weighted_gap_after}, ${t("critical").toLowerCase()}: ${best.critical_gap_after}`}
              </div>
            </li>
          </ol>
          </details>
          {remaining.length > 0 && <p className="small graph-note">{copy.remaining}: {remaining.map((n) => n.kind === "skill" ? `${n.label} ${n.planned}/${n.required}${n.critical ? " ★" : ""}` : "").join(" · ")}</p>}
          <div className="row">
            <button className="btn small" onClick={() => setSim(true)}>
              {t("whatIf")}
            </button>
            <span className="small muted">{t("routeHint")}</span>
          </div>
          {sim && <Simulation ctx={ctx} steps={best.steps.map((x: any) => x.event_id)} onClose={() => setSim(false)} />}
        </>
      )}
    </section>
  );
}

function Simulation({ ctx, steps, onClose }: { ctx: Ctx; steps: string[]; onClose: () => void }) {
  const { s, t, skill, event, employeeId } = ctx;
  const { data } = useApi<any>(s, `/employees/${employeeId}/simulate`, { steps });
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal onClick={(e) => e.stopPropagation()}>
        <div className="section-head">
          <h2>{t("whatIf")}</h2>
          <button className="btn small" onClick={onClose}>
            {t("close")}
          </button>
        </div>
        <p className="small muted">{t("simTitle")}</p>
        {!data && <p>{t("loading")}</p>}
        {data?.error && <p>{data.error.code}: {(data.error.reasons ?? []).map((r: any) => reasonText(r.code, s.locale)).join("; ")}</p>}
        {data && !data.error && (
          <div className="stack" style={{ marginTop: 14, gap: 14 }}>
            <div className="readiness">
              <div className="num" style={{ fontSize: 40 }}>
                {pct(data.before.readiness_pct)}→{pct(data.after.readiness_pct)}
                <small>%</small>
              </div>
            </div>
            <div className="bar">
              <span className="ghost" style={{ width: `${data.after.readiness_pct}%` }} />
              <span style={{ width: `${data.before.readiness_pct}%`, position: "relative" }} />
            </div>
            <ol className="route">
              {data.steps.map((st: any, i: number) => (
                <li key={st.event_id}>
                  <span className="node">{i + 1}</span>
                  <div className="step-title">{st.title}</div>
                  <div className="changes">
                    {st.changes.filter((c: any) => c.actual > 0).map((c: any) => `${skill(c.skill_id)} ${c.before}→${c.after}`).join(", ") || "—"} · {t("readinessDelta")} +
                    {st.readiness_delta_pp.toFixed(1)} {pick({ ru: "п.п.", en: "pp", kk: "п.т." }, s.locale)}
                    {st.new_unlocks.length > 0 && ` · ${t("unlocks")}: ${st.new_unlocks.map(event).join(", ")}`}
                  </div>
                </li>
              ))}
            </ol>
            {data.after.remaining_gaps.length > 0 && (
              <p className="small">
                {t("gap")}: {data.after.remaining_gaps.map((g: any) => `${skill(g.skill_id)} ${g.current}/${g.required}${g.critical ? "*" : ""}`).join(", ")}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Skills(ctx: Ctx) {
  const { snap, t, skill } = ctx;
  const [all, setAll] = useState(false);
  const rows = (snap.skills as any[])
    .filter((r) => all || r.in_target)
    .sort((a, b) => Number(b.critical && b.gap > 0) - Number(a.critical && a.gap > 0) || b.gap - a.gap || (a.skill_id < b.skill_id ? -1 : 1));
  return (
    <section className="panel">
      <div className="section-head">
        <h2>{t("skills")}</h2>
        <div className="row">
          <div className="legend">
            <span><i style={{ background: "var(--green)" }} />{t("assessed")}</span>
            <span><i style={{ background: "repeating-linear-gradient(45deg, var(--green) 0 4px, #4fa887 4px 8px)" }} />{t("fromHistory")}</span>
            <span><i style={{ background: "var(--amber-soft)", boxShadow: "inset 0 0 0 2px var(--amber)" }} />{t("gap")}</span>
          </div>
          <button className="btn small" onClick={() => setAll(!all)}>
            {all ? t("targetSkills") : t("allSkills")}
          </button>
        </div>
      </div>
      <div className="skills">
        {rows.map((r) => (
          <SkillRow key={r.skill_id} r={r} name={skill(r.skill_id)} t={t} />
        ))}
      </div>
    </section>
  );
}

function SkillRow({ r, name, t }: { r: any; name: string; t: Ctx["t"] }) {
  const [open, setOpen] = useState(false);
  const cells = [1, 2, 3, 4, 5].map((lvl) => {
    if (lvl <= r.assessed) return "have";
    if (lvl <= r.current) return "gained";
    if (r.required != null && lvl <= r.required) return "need";
    return "";
  });
  return (
    <div className="skill">
      <div className="name">
        {name}
        {r.critical && <span className="crit">● {t("critical").toLowerCase()}</span>}
      </div>
      <div className="ruler" role="img" aria-label={`${name}: ${r.current} / ${r.required ?? "—"}`}>
        {cells.map((c, i) => (
          <span key={i} className={`cell ${c}`} />
        ))}
      </div>
      <div className="nums">
        {t("assessed")} {r.assessed} · {t("calculated")} <b>{r.current}</b> · {t("required")} {r.required ?? "—"}
        {r.applications.length > 0 && (
          <button className="btn ghost small" onClick={() => setOpen(!open)} aria-expanded={open}>
            ⓘ
          </button>
        )}
      </div>
      {open && (
        <div className="src">
          {r.applications.map((a: any) => (
            <div key={a.record_id}>
              {a.record_id} / {a.event_id}, {a.date} ({a.date_confidence === "proxy" ? t("proxyDate") : t("appRecord")}): max(0, min({a.gain}, {a.cap}−{a.before}, 5−{a.before})) = +{a.actual} → {a.after}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Achievements(ctx: Ctx) {
  const { snap, t } = ctx;
  const g = snap.gamification;
  const names: Record<string, string> =
    ctx.s.locale === "kk"
      ? { FIRST_STEP: "Алғашқы қадам", FIVE_STEPS: "Бес қадам", CRITICAL_GAP_CLOSED: "Сыни алшақтық жабылды" }
      : ctx.s.locale === "en"
        ? { FIRST_STEP: "First step", FIVE_STEPS: "Five steps", CRITICAL_GAP_CLOSED: "Critical gap closed" }
        : { FIRST_STEP: "Первый шаг", FIVE_STEPS: "Пять шагов", CRITICAL_GAP_CLOSED: "Критический разрыв закрыт" };
  return (
    <section className="panel">
      <div className="section-head">
        <h2>{t("achievements")}</h2>
        <span className="small muted">
          {t("gameLevel")} {g.level} · {g.xp} XP
        </span>
      </div>
      <div className="badge-row">
        {g.badges.map((b: any) => (
          <div key={b.code} className={`badge ${b.progress >= b.of ? "granted" : ""}`}>
            {names[b.code]} · {b.progress}/{b.of}
          </div>
        ))}
      </div>
    </section>
  );
}

function Catalog(ctx: Ctx) {
  const { snap, t, s, skill } = ctx;
  const rows = (snap.catalog as any[]).filter((c) => !c.reasons.some((r: any) => r.code === "AUDIENCE_MISMATCH"));
  return (
    <section className="panel">
      <div className="section-head">
        <h2>{t("catalog")}</h2>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>{t("catalog")}</th>
              <th>{t("session")}</th>
              <th>{t("eligible")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => {
              const ev = ctx.meta.events[c.event_id];
              return (
                <tr key={c.event_id}>
                  <td>
                    <b>{c.title}</b>
                    <div className="small muted">
                      {c.type} · {c.format} · {c.duration_hours} {t("hours")} ·{" "}
                      {ev.develops_skills.map((d: any) => `${skill(d.skill_id)} +${d.gain} (≤${d.max_level})`).join(", ")}
                    </div>
                  </td>
                  <td className="small">{c.session ?? (c.format === "self_paced" ? t("selfPaced") : "—")}</td>
                  <td className="small">
                    {c.eligible ? (
                      <span className="chip">{t("eligible")}</span>
                    ) : (
                      c.reasons.map((r: any) => (
                        <div key={r.code}>
                          {reasonText(r.code, s.locale)}
                          {r.unmet ? `: ${r.unmet.map((u: any) => `${skill(u.skill_id)} ${u.current}/${u.required}`).join(", ")}` : ""}
                        </div>
                      ))
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function History(ctx: Ctx) {
  const { snap, t, s } = ctx;
  const h = snap.health;
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <h2>{t("health")}</h2>
          <span className="small muted">
            {h.observations_count} {t("observations")}
            {h.history_observed_from ? ` · ${h.history_observed_from}…${snap.as_of}` : ""}
          </span>
        </div>
        <p>{(HEALTH_TEXT[h.code] ? pick(HEALTH_TEXT[h.code], s.locale) : h.code)}</p>
      </section>
      <section className="panel">
        <div className="section-head">
          <h2>{t("history")}</h2>
        </div>
        <div className="table-wrap">
          <table className="table">
            <tbody>
              {(snap.history as any[]).map((r) => (
                <tr key={r.record_id}>
                  <td className="small muted">{r.date}</td>
                  <td>
                    {r.title}
                    <div className="small muted">
                      {r.record_id} · {r.mandatory ? t("mandatory") : t("voluntary")} · {r.assigned_by}
                      {r.origin === "app" ? ` · ${t("appRecord")}` : ""}
                    </div>
                  </td>
                  <td>
                    <span className={`chip ${r.status === "completed" ? "" : r.status === "in_progress" ? "grey" : "amber"}`}>{t("status_" + r.status)}</span>
                  </td>
                  <td className="small num-cell">{r.status !== "completed" && r.completion_pct ? `${r.completion_pct}%` : r.score != null ? `score ${r.score}` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function Settings(ctx: Ctx) {
  const { t, s, employeeId, snap } = ctx;
  const o = currentOverlay(s);
  return (
    <section className="panel stack" style={{ gap: 16 }}>
      <h2>{t("navSettings")}</h2>
      <label className="row">
        <input
          type="checkbox"
          checked={!o.history_off[employeeId]}
          onChange={(e) => updateOverlay((x) => ({ ...x, history_off: { ...x.history_off, [employeeId]: !e.target.checked } }))}
        />
        {t("settingsHistory")}
      </label>
      <div>
        <label className="row">
          <input
            type="checkbox"
            checked={!!o.gaming[employeeId]}
            onChange={(e) => updateOverlay((x) => ({ ...x, gaming: { ...x.gaming, [employeeId]: e.target.checked } }))}
          />
          {t("settingsGaming")}
        </label>
        <p className="small muted" style={{ marginLeft: 26 }}>
          {t("settingsGamingHint")}
        </p>
      </div>
      {snap.snoozed.length > 0 && (
        <div className="row">
          {snap.snoozed.map((id: string) => (
            <button key={id} className="btn small" onClick={() => toggleSnooze(ctx, id)}>
              {t("unsnooze")}: {ctx.event(id)}
            </button>
          ))}
        </div>
      )}
      <div>
        <button
          className="btn small"
          onClick={() =>
            updateOverlay((x) => ({
              ...x,
              completions: x.completions.filter((c) => c.employee_id !== employeeId),
              snoozes: { ...x.snoozes, [employeeId]: [] },
            }))
          }
        >
          {t("settingsReset")}
        </button>
      </div>
    </section>
  );
}
