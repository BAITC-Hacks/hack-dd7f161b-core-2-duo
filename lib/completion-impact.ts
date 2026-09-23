export type ImpactSnapshot = {
  employee: { employee_id: string };
  dataset: string;
  fingerprint: string;
  target: { role: string; grade: string };
  readiness: { readiness_pct: number };
  skills: { skill_id: string; current: number }[];
  gaps: { skill_id: string; gap: number; critical: boolean }[];
  catalog: { event_id: string; title: string; eligible: boolean }[];
  history: { event_id: string; status: string; origin: string }[];
  gamification: { opt_in: boolean; xp: number };
};

export type CompletionImpact = {
  eventId: string;
  before: number;
  after: number;
  skills: { skillId: string; before: number; after: number }[];
  closedCritical: string[];
  unlocked: { eventId: string; title: string }[];
  xp: number;
};

// Only compare confirmed server snapshots. No simulation or skill formula in the UI.
export function completionImpact(before: ImpactSnapshot, after: ImpactSnapshot, eventId: string): CompletionImpact | null {
  if (before.employee.employee_id !== after.employee.employee_id || before.dataset !== after.dataset ||
      before.target.role !== after.target.role || before.target.grade !== after.target.grade) return null;
  const completions = (snapshot: ImpactSnapshot) => snapshot.history.filter((h) => h.event_id === eventId && h.origin === "app" && h.status === "completed").length;
  if (completions(after) <= completions(before)) return null;

  const oldSkills = new Map(before.skills.map((s) => [s.skill_id, s.current]));
  const newGaps = new Map(after.gaps.map((g) => [g.skill_id, g.gap]));
  const availableBefore = new Set(before.catalog.filter((c) => c.eligible).map((c) => c.event_id));
  return {
    eventId,
    before: before.readiness.readiness_pct,
    after: after.readiness.readiness_pct,
    skills: after.skills.flatMap((s) => {
      const previous = oldSkills.get(s.skill_id);
      return previous != null && s.current > previous ? [{ skillId: s.skill_id, before: previous, after: s.current }] : [];
    }),
    closedCritical: before.gaps.filter((g) => g.critical && g.gap > 0 && newGaps.get(g.skill_id) === 0).map((g) => g.skill_id),
    unlocked: after.catalog.filter((c) => c.eligible && c.event_id !== eventId && !availableBefore.has(c.event_id))
      .map((c) => ({ eventId: c.event_id, title: c.title })),
    xp: after.gamification.opt_in ? Math.max(0, after.gamification.xp - before.gamification.xp) : 0,
  };
}
