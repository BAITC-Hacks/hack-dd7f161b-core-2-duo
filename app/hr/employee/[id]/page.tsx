"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { EmployeeView } from "@/components/EmployeeView";
import { SideNav, Topbar } from "@/components/Shell";
import { Meta, useApi } from "@/lib/hooks";
import { translator } from "@/lib/i18n";
import { useAppState } from "@/lib/store";

export default function HrEmployeePage() {
  const { id } = useParams<{ id: string }>();
  const s = useAppState();
  const t = translator(s.locale);
  const [section, setSection] = useState("path");
  const { data: meta } = useApi<Meta>(s, "/meta");
  return (
    <>
      <Topbar asOf={meta?.as_of} who="HR" />
      <div className="layout">
        <SideNav
          current={section}
          onSelect={setSection}
          items={[
            ["path", t("navPath")],
            ["activities", t("navActivities")],
            ["history", t("navHistory")],
          ]}
        />
        <main className="main">
          <Link href="/hr" className="btn ghost small">
            ← {t("back")}
          </Link>
          <div style={{ marginTop: 12 }}>{meta ? <EmployeeView employeeId={id} meta={meta} section={section} /> : <p className="muted">{t("loading")}</p>}</div>
        </main>
      </div>
    </>
  );
}
