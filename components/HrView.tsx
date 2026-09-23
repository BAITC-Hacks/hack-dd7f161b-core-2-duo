"use client";

import Link from "next/link";
import { Fragment, useState } from "react";
import { uploadFiles } from "@/lib/api";
import { Meta, useApi } from "@/lib/hooks";
import { INTERVENTION_TEXT, pick, reasonText, translator } from "@/lib/i18n";
import { setState, useAppState } from "@/lib/store";

const fmtPct = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(0)}%`);

export function HrView({ section, meta }: { section: string; meta: Meta }) {
  const s = useAppState();
  const t = translator(s.locale);
  const { data, loading, error } = useApi<any>(s, section === "data" ? null : "/hr/dashboard");
  if (section === "data") return <DataSection />;
  if (!data) return <p className="muted">{loading ? t("loading") : String(error)}</p>;
  const c = data.cards;
  return (
    <div className="stack">
      <div className="cards">
        {(["employees", "open_critical", "no_step", "target_met"] as const).map((k) => (
          <div key={k} className="card-stat">
            <div className="v">{c[k] ?? 0}</div>
            <div className="l">{t("hr_" + k)}</div>
          </div>
        ))}
      </div>
      <p className="small muted">
        {t("population")}: {data.population} · {t("asOf")}: {data.as_of}
      </p>
      {section === "skills" && <SkillsSection data={data} meta={meta} />}
      {section === "team" && <NoStepSection data={data} meta={meta} />}
      {section === "participation" && <Participation data={data} />}
    </div>
  );
}

function SkillsSection({ data, meta }: { data: any; meta: Meta }) {
  const s = useAppState();
  const t = translator(s.locale);
  const [open, setOpen] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const rows = all ? data.skills : data.skills.slice(0, 15);
  return (
    <section className="panel">
      <div className="section-head">
        <h2>{t("hrSkillsTitle")}</h2>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>{t("skills")}</th>
              <th className="num-cell">{t("criticalGapCount")}</th>
              <th className="num-cell">{t("belowTarget")}</th>
              <th className="num-cell">{t("providers")}</th>
              <th>
                {t("actionable")} / {t("bridgeCnt")} / {t("uncovered")}
              </th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((k: any) => {
              const tot = k.actionable_employee_count + k.bridge_employee_count + k.uncovered_employee_count || 1;
              return (
                <Fragment key={k.skill_id}>
                  <tr>
                    <td>
                      <b>{k.name}</b>
                      <div className="small muted">{k.type}</div>
                    </td>
                    <td className="num-cell">{k.critical_gap_count}</td>
                    <td className="num-cell">
                      {k.below_target_count} / {k.required_count}
                      <div className="small muted">{fmtPct(k.gap_rate)}</div>
                    </td>
                    <td className="num-cell">{k.catalog_event_count}</td>
                    <td>
                      <div className="split" title={`${k.actionable_employee_count} / ${k.bridge_employee_count} / ${k.uncovered_employee_count}`}>
                        <span style={{ width: `${(100 * k.actionable_employee_count) / tot}%`, background: "var(--green)" }} />
                        <span style={{ width: `${(100 * k.bridge_employee_count) / tot}%`, background: "#79bea3" }} />
                        <span style={{ width: `${(100 * k.uncovered_employee_count) / tot}%`, background: "var(--amber)" }} />
                      </div>
                      <div className="small muted">
                        {k.actionable_employee_count} / {k.bridge_employee_count} / {k.uncovered_employee_count}
                      </div>
                    </td>
                    <td>
                      {k.blockers.length > 0 && (
                        <button className="btn ghost small" onClick={() => setOpen(open === k.skill_id ? null : k.skill_id)}>
                          {t("intervention")}
                        </button>
                      )}
                    </td>
                  </tr>
                  {open === k.skill_id && (
                    <tr>
                      <td colSpan={6} style={{ background: "var(--paper)" }}>
                        {k.intervention && (
                          <p>
                            <b>{INTERVENTION_TEXT[k.intervention] ? pick(INTERVENTION_TEXT[k.intervention], s.locale) : k.intervention}</b>
                          </p>
                        )}
                        {k.blockers.map((b: any) => (
                          <p key={b.code} className="small">
                            {reasonText(b.code, s.locale)} — {b.count} · <span className="chip grey">{t("proof_" + b.proof_level)}</span>{" "}
                            {b.event_ids.map((id: string) => meta.events[id]?.title ?? id).join(", ")}
                          </p>
                        ))}
                        <p className="small muted">{k.top_groups.map((g: any) => `${g[0]}: ${g[1]}`).join(" · ")}</p>
                        <p className="small muted">
                          {pick(
                            {
                              ru: "Черновик для проверки HR. В датасете нет вместимости и бюджета — выводов о нехватке мест не делаем.",
                              en: "Draft for HR review. No capacity or budget data in the dataset, so no seat-shortage conclusions.",
                              kk: "HR тексеруіне арналған жоба. Деректерде сыйымдылық пен бюджет жоқ — орын тапшылығы туралы қорытынды жасамаймыз.",
                            },
                            s.locale,
                          )}
                        </p>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {data.skills.length > 15 && (
        <button className="btn small" style={{ marginTop: 12 }} onClick={() => setAll(!all)}>
          {all
            ? pick({ ru: "Показать первые 15", en: "Show top 15", kk: "Алғашқы 15-ін көрсету" }, s.locale)
            : `${pick({ ru: "Показать все", en: "Show all", kk: "Барлығын көрсету" }, s.locale)} ${data.skills.length}`}
        </button>
      )}
    </section>
  );
}

function NoStepSection({ data, meta }: { data: any; meta: Meta }) {
  const s = useAppState();
  const t = translator(s.locale);
  const skill = (id: string) => meta.skills[id]?.name ?? id;
  return (
    <section className="panel">
      <div className="section-head">
        <h2>{t("hrNoStepTitle")}</h2>
        <span className="small muted">{data.no_step.length}</span>
      </div>
      <div className="table-wrap">
        <table className="table">
          <tbody>
            {data.no_step.map((r: any) => (
              <tr key={r.employee_id}>
                <td>
                  <b>{r.full_name}</b>
                  <div className="small muted">
                    {r.employee_id} · {r.role} {r.grade} → {r.target.role} {r.target.grade} ({t("src_" + r.target.source).toLowerCase()})
                  </div>
                </td>
                <td className="small">
                  {r.critical_gaps.map((g: any) => `${skill(g.skill_id)} ${g.current}/${g.required}`).join(", ")}
                </td>
                <td className="small">
                  {r.reasons.map((x: any) => (
                    <div key={x.code}>
                      {reasonText(x.code, s.locale)} <span className="muted">({t("proof_" + x.proof_level)})</span>
                    </div>
                  ))}
                </td>
                <td>
                  <Link className="btn small" href={`/hr/employee/${r.employee_id}`}>
                    {t("openEmployee")}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Participation({ data }: { data: any }) {
  const s = useAppState();
  const t = translator(s.locale);
  const [mand, setMand] = useState(false);
  const rows = data.participation.filter((r: any) => r.mandatory === mand);
  return (
    <section className="panel">
      <div className="section-head">
        <h2>{t("hrPartTitle")}</h2>
        <div className="langs">
          <button aria-pressed={!mand} onClick={() => setMand(false)}>
            {t("voluntary")}
          </button>
          <button aria-pressed={mand} onClick={() => setMand(true)}>
            {t("mandatory")}
          </button>
        </div>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>{t("catalog")}</th>
              <th className="num-cell">{t("status_completed")}</th>
              <th className="num-cell">{t("status_no_show")}</th>
              <th className="num-cell">{t("status_dropped")}</th>
              <th className="num-cell">{t("status_declined")}</th>
              {mand && <th className="num-cell">{t("status_overdue")}</th>}
              {!mand && <th className="num-cell">{t("completionShare")}</th>}
              {!mand && <th className="num-cell">{t("attendance")}</th>}
              <th className="num-cell">{t("feedback")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r: any) => (
              <tr key={r.event_id}>
                <td>
                  {r.title}
                  <div className="small muted">
                    {r.type} · {r.format} · {r.observations} {t("observations")} · {r.unique_employees} {t("uniqueEmployees")}
                    {r.counts.app_completed ? ` · +${r.counts.app_completed} ${t("appRecord")}` : ""}
                  </div>
                </td>
                <td className="num-cell">{r.counts.completed ?? 0}</td>
                <td className="num-cell">{r.counts.no_show ?? 0}</td>
                <td className="num-cell">{r.counts.dropped ?? 0}</td>
                <td className="num-cell">{r.counts.declined ?? 0}</td>
                {mand && <td className="num-cell">{r.counts.overdue ?? 0}</td>}
                {!mand && <td className="num-cell">{fmtPct(r.completion_share)}</td>}
                {!mand && <td className="num-cell">{fmtPct(r.attendance_proxy)}</td>}
                <td className="num-cell">
                  {r.avg_feedback == null ? "—" : r.avg_feedback.toFixed(1)} <span className="muted small">n={r.feedback_n}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DataSection() {
  const s = useAppState();
  const t = translator(s.locale);
  const [files, setFiles] = useState<File[]>([]);
  const [report, setReport] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  return (
    <section className="panel stack" style={{ gap: 14 }}>
      <h2>{t("uploadTitle")}</h2>
      <p className="muted" style={{ maxWidth: "70ch" }}>
        {t("uploadLead")}
      </p>
      <div className="row">
        <input type="file" multiple accept=".json,.csv" onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
        <button
          className="btn"
          disabled={!files.length || busy}
          onClick={async () => {
            setBusy(true);
            try {
              setReport(await uploadFiles(s, files));
            } catch (e: any) {
              setReport({ ok: false, errors: [{ code: "UPLOAD_FAILED", path: "", detail: String(e?.detail ?? e) }], warnings: [] });
            } finally {
              setBusy(false);
            }
          }}
        >
          {t("validate")}
        </button>
      </div>
      {report && (
        <div className="stack" style={{ gap: 10 }}>
          {report.counts && (
            <p>
              employees: <b>{report.counts.employees}</b>, history: <b>{report.counts.history}</b>
            </p>
          )}
          {report.errors.length > 0 && (
            <div>
              <h3>{t("errors")}</h3>
              {report.errors.map((e: any, i: number) => (
                <p key={i} className="small">
                  {e.path} — {e.code} {e.detail}
                </p>
              ))}
            </div>
          )}
          {report.warnings.length > 0 && (
            <div>
              <h3>{t("warnings")}</h3>
              {report.warnings.map((e: any, i: number) => (
                <p key={i} className="small muted">
                  {e.path} — {e.code} {e.detail}
                </p>
              ))}
            </div>
          )}
          {report.ok && (
            <button
              className="btn primary"
              onClick={() => {
                const name = `${files.map((f) => f.name).join(" + ")}`;
                setState((x) => ({
                  ...x,
                  scenario: { name, ...report.scenario },
                  scenarioKey: "check",
                  overlays: { ...x.overlays, check: { completions: [], goals: {}, snoozes: {}, gaming: {}, history_off: {} } },
                }));
                setReport(null);
              }}
            >
              {t("commit")} ({report.employee_ids.join(", ")})
            </button>
          )}
        </div>
      )}
      <div className="row">
        {s.scenarioKey === "check" ? (
          <button className="btn" onClick={() => setState((x) => ({ ...x, scenarioKey: "base" }))}>
            {t("switchBase")}
          </button>
        ) : (
          s.scenario && (
            <button className="btn" onClick={() => setState((x) => ({ ...x, scenarioKey: "check" }))}>
              {t("switchCheck")}
            </button>
          )
        )}
      </div>
    </section>
  );
}
