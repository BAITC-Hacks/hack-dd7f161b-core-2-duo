"use client";

import { useEffect, useRef } from "react";
import type { CompletionImpact } from "@/lib/completion-impact";
import { pick, translator } from "@/lib/i18n";
import type { Locale } from "@/lib/store";

const COPY = {
  ru: {
    done: "Шаг завершён", result: "Ваш результат", skills: "Навыки выросли", critical: "Критические разрывы закрыты",
    unlocked: "Теперь доступны", noGain: "Уровни навыков не изменились: достигнут потолок этой активности.",
    note: "Результат по обновлённым данным. Рекомендации и маршрут уже пересчитаны.",
  },
  en: {
    done: "Step completed", result: "Your result", skills: "Skills improved", critical: "Critical gaps closed",
    unlocked: "Now available", noGain: "Skill levels have not changed: this activity's skill caps are already reached.",
    note: "Based on updated data. Recommendations and your route have been recalculated.",
  },
  kk: {
    done: "Қадам аяқталды", result: "Сіздің нәтижеңіз", skills: "Дағдылар өсті", critical: "Сыни алшақтықтар жабылды",
    unlocked: "Енді қолжетімді", noGain: "Дағды деңгейлері өзгермеді: осы белсенділіктің шегіне жеткенсіз.",
    note: "Жаңартылған деректер нәтижесі. Ұсыныстар мен маршрут қайта есептелді.",
  },
};

export function CompletionResult({ impact, title, locale, skillName, onClose }: {
  impact: CompletionImpact;
  title: string;
  locale: Locale;
  skillName: (id: string) => string;
  onClose: () => void;
}) {
  const copy = COPY[locale];
  const t = translator(locale);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    panel.current?.focus({ preventScroll: true });
    panel.current?.scrollIntoView({ block: "nearest", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  }, [impact]);
  const delta = impact.after - impact.before;
  return (
    <section ref={panel} className="panel completion-result" tabIndex={-1} aria-label={copy.result}>
      <div className="section-head">
        <div className="row">
          <span className="completion-check" aria-hidden>✓</span>
          <div><span className="completion-eyebrow">{copy.done}</span><h2>{title}</h2></div>
        </div>
        <button className="btn small" onClick={onClose}>{t("close")}</button>
      </div>
      <div className="completion-metrics">
        <div>
          <p className="small">{t("readiness")}</p>
          <div className="completion-readiness"><span>{impact.before.toFixed(1)}%</span><span aria-hidden>→</span><strong>{impact.after.toFixed(1)}%</strong></div>
        </div>
        <span className="chip">{delta >= 0 ? "+" : ""}{delta.toFixed(1)} {pick({ ru: "п.п.", en: "pp", kk: "п.т." }, locale)}</span>
        {impact.xp > 0 && <span className="chip">+{impact.xp} XP</span>}
      </div>
      <div className="completion-outcomes">
        <div>
          <h3>{copy.skills}</h3>
          {impact.skills.length ? <ul className="completion-skills">{impact.skills.map((s) => (
            <li key={s.skillId}><span>{skillName(s.skillId)}</span><strong>{s.before} → {s.after}</strong></li>
          ))}</ul> : <p className="small">{copy.noGain}</p>}
        </div>
        {(impact.closedCritical.length > 0 || impact.unlocked.length > 0) && <div className="completion-milestones">
          {impact.closedCritical.length > 0 && <div><h3>{copy.critical}</h3><div className="tag-list">
            {impact.closedCritical.map((id) => <span className="chip" key={id}>✓ {skillName(id)}</span>)}
          </div></div>}
          {impact.unlocked.length > 0 && <div><h3>{copy.unlocked}</h3><ul>
            {impact.unlocked.map((e) => <li key={e.eventId}>{e.title}</li>)}
          </ul></div>}
        </div>}
      </div>
      <p className="small completion-note">{copy.note}</p>
    </section>
  );
}
