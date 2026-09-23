"use client";

import { AppState, getState, requestOverlay, setState } from "./store";

function headers(s: AppState): Record<string, string> {
  const h: Record<string, string> = { "content-type": "application/json" };
  if (s.session?.token) h.Authorization = `Bearer ${s.session.token}`;
  return h;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(`api ${status}`);
  }
}

export type LoginResponse = {
  token: string;
  role: "employee" | "hr";
  employee_id: string | null;
  expires_at: number;
};

async function response<T>(res: Response, s: AppState, requireSession: boolean): Promise<T> {
  if (!res.ok) {
    // A failed password attempt stays on the login form. An older in-flight
    // request must not clear a session created by a more recent login.
    if (res.status === 401 && requireSession && getState().session?.token === s.session?.token) {
      setState((current) => ({ ...current, session: null }));
      if (typeof window !== "undefined") window.location.replace("/");
    }
    throw new ApiError(res.status, await res.json().catch(() => null));
  }
  return res.json();
}

export async function post<T>(s: AppState, path: string, extra: Record<string, unknown> = {}): Promise<T> {
  const res = await fetch(`/api/py${path}`, {
    method: "POST",
    headers: headers(s),
    body: JSON.stringify({ overlay: requestOverlay(s), locale: s.locale, ...extra }),
  });
  return response<T>(res, s, !["/auth/login", "/meta", "/health"].includes(path));
}

export async function uploadFiles(s: AppState, files: File[]) {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  const h = headers(s);
  delete h["content-type"];
  const res = await fetch("/api/py/hr/import/validate", { method: "POST", headers: h, body: fd });
  return response<any>(res, s, true);
}
