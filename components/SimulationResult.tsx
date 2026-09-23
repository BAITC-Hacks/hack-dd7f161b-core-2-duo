"use client";

import { pick, translator } from "@/lib/i18n";
import { Locale } from "@/lib/store";

export type SimulationData = {
  is_projection: boolean;
  before: { readiness_pct: number };
  after: { readiness_pct: number; remaining_gaps: { skill_id: string; current: number; required: number; critical: boolean }[] };
  steps: {
    event_id: string;
    title: string;
    changes: { skill_id: string; actual: number; before: number; after: number }[];
    readiness_delta_pp: number;
    new_unlocks: string[];
  }[];
};

// The card in chat and the existing What-if dialog share the same engine result view.
export function SimulationResult({ data, locale, skillName, eventName, compact = false }: {
  data: SimulationData;
  locale: Locale;
  skillName: (id: string) => string;
  eventName: (id: string) => string;
  compact?: boolean;
}) {
  const t = translator(locale);
  return (
    <div className={`simulation-result stack${compact ? " compact" : ""}`}>
      <div className="readiness">
        <div className="num" style={{ fontSize: compact ? 28 : 40 }}>
          {data.before.readiness_pct.toFixed(1)}→{data.after.readiness_pct.toFixed(1)}<small>%</small>
        </div>
      </div>
      <div className="bar" aria-hidden>
        <span className="ghost" style={{ width: `${data.after.readiness_pct}%` }} />
        <span style={{ width: `${data.before.readiness_pct}%`, position: "relative" }} />
      </div>
      <ol className="route">
        {data.steps.map((st, i) => (
          <li key={st.event_id}>
            <span className="node">{i + 1}</span>
            <div className="step-title">{st.title}</div>
            <div className="changes">
              {st.changes.filter((c) => c.actual > 0).map((c) => `${skillName(c.skill_id)} ${c.before}→${c.after}`).join(", ") || "-"} · {t("readinessDelta")} +
              {st.readiness_delta_pp.toFixed(1)} {pick({ ru: "п.п.", en: "pp", kk: "п.т." }, locale)}
              {st.new_unlocks.length > 0 && ` · ${t("unlocks")}: ${st.new_unlocks.map(eventName).join(", ")}`}
            </div>
          </li>
        ))}
      </ol>
      {data.after.remaining_gaps.length > 0 && (
        <p className="small">
          {t("gap")}: {data.after.remaining_gaps.map((g) => `${skillName(g.skill_id)} ${g.current}/${g.required}${g.critical ? "*" : ""}`).join(", ")}
        </p>
      )}
    </div>
  );
}
