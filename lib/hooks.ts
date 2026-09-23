"use client";

import { useCallback, useEffect, useState } from "react";
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
  const [result, setResult] = useState<{ data: T | null; error: unknown; key: string | null; dataKey: string | null }>({ data: null, error: null, key: null, dataKey: null });
  const [pending, setPending] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  const depKey = JSON.stringify([path, currentOverlay(s), s.scenarioKey, s.scenario?.name, s.session, s.locale, extra, attempt]);
  useEffect(() => {
    if (!path) return;
    let alive = true;
    setPending(true);
    post<T>(s, path, extra)
      .then((data) => alive && setResult({ data, error: null, key: depKey, dataKey: depKey }))
      .catch((error) => alive && setResult((previous) => ({ ...previous, error, key: depKey })))
      .finally(() => alive && setPending(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [depKey]);
  return {
    data: result.data,
    error: result.key === depKey ? result.error : null,
    loading: !!path && (pending || result.key !== depKey),
    stale: result.data !== null && result.dataKey !== depKey,
    retry,
  };
}
