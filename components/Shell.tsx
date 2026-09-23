"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { post } from "@/lib/api";
import { translator } from "@/lib/i18n";
import { getState, Locale, setState, useAppState } from "@/lib/store";

export function Topbar({ asOf, who }: { asOf?: string; who?: string }) {
  const s = useAppState();
  const t = translator(s.locale);
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);
  const signOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    try {
      await post(s, "/auth/logout");
    } catch {
      // Always clear this browser's session, even if the server is unreachable.
    } finally {
      if (getState().session?.token === s.session?.token) {
        setState((x) => ({ ...x, session: null }));
        router.replace("/");
      }
      setSigningOut(false);
    }
  };
  return (
    <header className="topbar">
      <span className="brand">
        <span className="brand-mark" aria-hidden />
        Career Quest
      </span>
      <span className={`chip scenario-chip ${s.scenarioKey === "check" ? "amber" : "grey"}`}>
        {s.scenarioKey === "check" ? `${t("scenarioCheck")}: ${s.scenario?.name ?? ""}` : t("scenarioBase")}
      </span>
      {asOf && (
        <span className="meta">
          {t("asOf")}: {asOf}
        </span>
      )}
      <span className="chip grey">{t("synthetic")}</span>
      <span className="spacer" />
      {who && <span className="meta">{who}</span>}
      <LangSwitch />
      {s.session && (
        <button
          className="btn small"
          disabled={signingOut}
          onClick={signOut}
        >
          {t(signingOut ? "signingOut" : "logout")}
        </button>
      )}
    </header>
  );
}

export function LangSwitch() {
  const s = useAppState();
  const langs: Locale[] = ["ru", "kk", "en"];
  return (
    <div className="langs" role="group" aria-label="language">
      {langs.map((l) => (
        <button key={l} aria-pressed={s.locale === l} onClick={() => setState((x) => ({ ...x, locale: l }))}>
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

export function SideNav({ items, current, onSelect }: { items: [string, string][]; current: string; onSelect: (k: string) => void }) {
  return (
    <nav className="sidenav">
      {items.map(([k, label]) => (
        <button key={k} aria-current={current === k ? "page" : undefined} onClick={() => onSelect(k)}>
          {label}
        </button>
      ))}
    </nav>
  );
}
