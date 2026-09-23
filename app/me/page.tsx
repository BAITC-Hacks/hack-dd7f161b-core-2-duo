"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { EmployeeView } from "@/components/EmployeeView";
import { SideNav, Topbar } from "@/components/Shell";
import { Meta, useApi } from "@/lib/hooks";
import { translator } from "@/lib/i18n";
import { useAppState } from "@/lib/store";

export default function MePage() {
  const s = useAppState();
  const t = translator(s.locale);
  const router = useRouter();
  const [section, setSection] = useState("path");
  const { data: meta } = useApi<Meta>(s, "/meta");
  const actor = s.session?.role === "employee" ? s.session.actor : undefined;
  useEffect(() => {
    if (s.session === null) router.replace("/");
  }, [s.session, router]);
  const me = meta?.employees.find((e) => e.employee_id === actor);
  return (
    <>
      <Topbar asOf={meta?.as_of} who={me ? `${me.full_name} · ${me.employee_id}` : undefined} />
      <div className="layout">
        <SideNav
          current={section}
          onSelect={setSection}
          items={[
            ["path", t("navPath")],
            ["activities", t("navActivities")],
            ["history", t("navHistory")],
            ["settings", t("navSettings")],
          ]}
        />
        <main className="main">{meta && actor ? <EmployeeView employeeId={actor} meta={meta} section={section} /> : <p className="muted">{t("loading")}</p>}</main>
      </div>
    </>
  );
}
