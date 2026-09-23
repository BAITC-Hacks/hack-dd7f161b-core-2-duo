"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

export type Locale = "ru" | "kk" | "en";
export type Session = { role: "employee" | "hr"; actor?: string } | null;

export type Overlay = {
  completions: { employee_id: string; event_id: string; session_date: string | null; gaming: boolean }[];
  goals: Record<string, { mode: "set" | "cleared"; target_role?: string; target_grade?: string }>;
  snoozes: Record<string, string[]>;
  gaming: Record<string, boolean>;
  history_off: Record<string, boolean>;
};

export type Scenario = { name: string; employees: unknown[]; history: unknown[] };

export type AppState = {
  session: Session;
  locale: Locale;
  scenarioKey: "base" | "check";
  scenario: Scenario | null;
  overlays: Record<string, Overlay>;
};

const KEY = "career-quest:v1";
const emptyOverlay = (): Overlay => ({ completions: [], goals: {}, snoozes: {}, gaming: {}, history_off: {} });
const initial: AppState = { session: null, locale: "ru", scenarioKey: "base", scenario: null, overlays: {} };

let state: AppState = initial;
let loaded = false;
const listeners = new Set<() => void>();

function load() {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) state = { ...initial, ...JSON.parse(raw) };
  } catch {
    // private mode or corrupted storage: start clean
  }
}

export function setState(update: (s: AppState) => AppState) {
  load();
  state = update(state);
  try {
    window.localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // storage full or blocked: keep in-memory state
  }
  listeners.forEach((l) => l());
}

export function getState(): AppState {
  load();
  return state;
}

export function useAppState(): AppState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    getState,
    () => initial,
  );
}

export function currentOverlay(s: AppState): Overlay {
  return s.overlays[s.scenarioKey] ?? emptyOverlay();
}

export function updateOverlay(fn: (o: Overlay) => Overlay) {
  setState((s) => ({ ...s, overlays: { ...s.overlays, [s.scenarioKey]: fn(currentOverlay(s)) } }));
}

export function requestOverlay(s: AppState) {
  return { ...currentOverlay(s), scenario: s.scenarioKey === "check" ? s.scenario : null };
}

// false during ssr/hydration, when useAppState still returns the empty server snapshot
export function useHydrated(): boolean {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);
  return hydrated;
}
