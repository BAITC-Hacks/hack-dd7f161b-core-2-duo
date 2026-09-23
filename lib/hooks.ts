"use client";

import { useEffect, useState } from "react";
import { post } from "./api";
import { AppState, currentOverlay } from "./store";

export type Meta = {
  dataset: string;
  as_of: string;
  employees: { employee_id: string; full_name: string; department: string; role: string; grade: string; preferred_language: string }[];
  skills: Record<string, { skill_id: string; name: string; type: string; category: string }>;
  events: Record<string, any>;
  targets: string[];
};

// refetches whenever the client-held overlay (or scenario / session) changes
export function useApi<T>(s: AppState, path: string | null, extra: Record<string, unknown> = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const depKey = JSON.stringify([path, currentOverlay(s), s.scenarioKey, s.scenario?.name, s.session, s.locale, extra]);
  useEffect(() => {
    if (!path) return;
    let alive = true;
    setLoading(true);
    post<T>(s, path, extra)
      .then((d) => alive && (setData(d), setError(null)))
      .catch((e) => alive && setError(e))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [depKey]);
  return { data, error, loading };
}
