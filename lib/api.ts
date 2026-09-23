"use client";

import { AppState, requestOverlay } from "./store";

function headers(s: AppState): Record<string, string> {
  const h: Record<string, string> = { "content-type": "application/json" };
  if (s.session) {
    h["x-role"] = s.session.role;
    if (s.session.actor) h["x-actor"] = s.session.actor;
  }
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

export async function post<T>(s: AppState, path: string, extra: Record<string, unknown> = {}): Promise<T> {
  const res = await fetch(`/api/py${path}`, {
    method: "POST",
    headers: headers(s),
    body: JSON.stringify({ overlay: requestOverlay(s), locale: s.locale, ...extra }),
  });
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null));
  return res.json();
}

export async function uploadFiles(s: AppState, files: File[]) {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  const h = headers(s);
  delete h["content-type"];
  const res = await fetch("/api/py/hr/import/validate", { method: "POST", headers: h, body: fd });
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null));
  return res.json();
}
