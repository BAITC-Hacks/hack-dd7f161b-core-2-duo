"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { HrView } from "@/components/HrView";
import { SideNav, Topbar } from "@/components/Shell";
import { Meta, useApi } from "@/lib/hooks";
import { translator } from "@/lib/i18n";
import { getState, useAppState, useHydrated } from "@/lib/store";

export default function HrPage() {
  const s = useAppState();
  const t = translator(s.locale);
  const router = useRouter();
  const [section, setSection] = useState("skills");
  const { data: meta } = useApi<Meta>(s, "/meta");
  const hydrated = useHydrated();
  // read storage directly: the first client render still carries the server snapshot
  useEffect(() => {
    if (hydrated && getState().session === null) router.replace("/");
  }, [hydrated, s.session, router]);
  return (
    <>
      <Topbar asOf={meta?.as_of} who="HR" />
      <div className="layout">
        <SideNav
          current={section}
          onSelect={setSection}
          items={[
            ["skills", t("navSkills")],
            ["team", t("navTeam")],
            ["participation", t("navParticipation")],
            ["data", t("navData")],
          ]}
        />
        <main className="main">{meta ? <HrView section={section} meta={meta} /> : <p className="muted">{t("loading")}</p>}</main>
      </div>
    </>
  );
}
