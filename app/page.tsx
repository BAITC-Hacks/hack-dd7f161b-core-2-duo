"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Topbar } from "@/components/Shell";
import { Meta, useApi } from "@/lib/hooks";
import { translator } from "@/lib/i18n";
import { Locale, setState, useAppState } from "@/lib/store";

export default function Login() {
  const s = useAppState();
  const t = translator(s.locale);
  const router = useRouter();
  const [q, setQ] = useState("");
  const { data: meta } = useApi<Meta>(s, "/meta");
  const people = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (meta?.employees ?? []).filter(
      (e) => !needle || `${e.employee_id} ${e.full_name} ${e.role} ${e.grade}`.toLowerCase().includes(needle),
    );
  }, [meta, q]);

  const enterEmployee = (id: string, lang: string) => {
    setState((x) => ({ ...x, session: { role: "employee", actor: id }, locale: (["ru", "kk", "en"].includes(lang) ? lang : "ru") as Locale }));
    router.push("/me");
  };

  return (
    <>
      <Topbar asOf={meta?.as_of} />
      <main className="login">
        <section>
          <h1>{t("loginTitle")}</h1>
          <p className="lead">{t("loginLead")}</p>
          <div className="row" style={{ marginTop: 28 }}>
            <button
              className="btn primary"
              onClick={() => {
                setState((x) => ({ ...x, session: { role: "hr" } }));
                router.push("/hr");
              }}
            >
              {t("asHr")}
            </button>
          </div>
        </section>
        <section className="picker" aria-label={t("asEmployee")}>
          <h2>{t("asEmployee")}</h2>
          <input className="input" placeholder={t("searchEmployee")} value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="people">
            {!meta && <p className="muted" style={{ padding: 14 }}>{t("loading")}</p>}
            {people.map((e) => (
              <button key={e.employee_id} className="person" onClick={() => enterEmployee(e.employee_id, e.preferred_language)}>
                <span>
                  {e.full_name} <span className="muted small">{e.employee_id}</span>
                </span>
                <span className="r">
                  {e.role} · {e.grade}
                </span>
              </button>
            ))}
          </div>
        </section>
      </main>
    </>
  );
}
