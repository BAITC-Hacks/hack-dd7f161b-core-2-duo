"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";
import { Topbar } from "@/components/Shell";
import { ApiError, LoginResponse, post } from "@/lib/api";
import { Meta, useApi } from "@/lib/hooks";
import { translator } from "@/lib/i18n";
import { Locale, setState, useAppState } from "@/lib/store";

export default function Login() {
  const s = useAppState();
  const t = translator(s.locale);
  const router = useRouter();
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<{ login: string; language?: string } | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { data: meta } = useApi<Meta>(s, "/meta");
  const people = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (meta?.employees ?? []).filter(
      (e) => !needle || `${e.employee_id} ${e.full_name} ${e.role} ${e.grade}`.toLowerCase().includes(needle),
    );
  }, [meta, q]);

  const selectAccount = (login: string, language?: string) => {
    setSelected({ login, language });
    setPassword(login === "hr" ? "hr-demo" : "demo");
    setError(null);
  };

  const signIn = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await post<LoginResponse>(s, "/auth/login", { login: selected.login, password });
      const language = selected.language;
      setState((x) => ({
        ...x,
        session: { role: result.role, actor: result.employee_id ?? undefined, token: result.token },
        locale: language ? (["ru", "kk", "en"].includes(language) ? language : "ru") as Locale : x.locale,
      }));
      router.push(result.role === "hr" ? "/hr" : "/me");
    } catch (reason) {
      setError(reason instanceof ApiError && reason.status === 401 ? "invalidCredentials" : "loginUnavailable");
    } finally {
      setSubmitting(false);
    }
  };

  const passwordForm = selected && (
    <form key={selected.login} id="login-password-form" className="login-password" onSubmit={signIn} aria-busy={submitting}>
      <input type="hidden" name="username" autoComplete="username" value={selected.login} />
      <label htmlFor="login-password">{t("password")}</label>
      <div className="row">
        <input
          id="login-password"
          className="input"
          type="password"
          name="password"
          autoComplete="current-password"
          autoFocus
          required
          disabled={submitting}
          value={password}
          aria-invalid={error === "invalidCredentials" || undefined}
          aria-describedby={`login-password-hint${error ? " login-error" : ""}`}
          onChange={(event) => {
            setPassword(event.target.value);
            setError(null);
          }}
        />
        <button className="btn primary" type="submit" disabled={submitting || !password}>
          {t(submitting ? "signingIn" : "signIn")}
        </button>
      </div>
      <p id="login-password-hint" className="muted small">
        {t("demoPassword")}: {selected.login === "hr" ? "hr-demo" : "demo"}
      </p>
      {error && <p id="login-error" className="login-error small" role="alert">{t(error)}</p>}
    </form>
  );

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
              disabled={submitting}
              aria-expanded={selected?.login === "hr"}
              aria-controls={selected?.login === "hr" ? "login-password-form" : undefined}
              onClick={() => selectAccount("hr")}
            >
              {t("asHr")}
            </button>
          </div>
          {selected?.login === "hr" && passwordForm}
        </section>
        <section className="picker" aria-label={t("asEmployee")}>
          <h2>{t("asEmployee")}</h2>
          <input className="input" placeholder={t("searchEmployee")} value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="people">
            {!meta && <p className="muted" style={{ padding: 14 }}>{t("loading")}</p>}
            {people.map((e) => (
              <div key={e.employee_id}>
                <button
                  className="person"
                  disabled={submitting}
                  aria-expanded={selected?.login === e.employee_id}
                  aria-controls={selected?.login === e.employee_id ? "login-password-form" : undefined}
                  onClick={() => selectAccount(e.employee_id, e.preferred_language)}
                >
                  <span>
                    {e.full_name} <span className="muted small">{e.employee_id}</span>
                  </span>
                  <span className="r">
                    {e.role} · {e.grade}
                  </span>
                </button>
                {selected?.login === e.employee_id && passwordForm}
              </div>
            ))}
          </div>
        </section>
      </main>
    </>
  );
}
