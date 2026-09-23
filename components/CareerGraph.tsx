"use client";

import { useId, useMemo, useState } from "react";
import { CareerGraphData, GRAPH_COPY, GraphNode } from "@/lib/career-graph";
import { reasonText, translator } from "@/lib/i18n";
import { Locale } from "@/lib/store";

const WIDTH = 224;
const HEIGHT = 126;
const X = { activity: 18, skill: 456, goal: 800 };

function wrapLabel(label: string): string[] {
  const lines: string[] = [];
  let line = "";
  for (const word of label.split(/\s+/)) {
    if (line && (line + " " + word).length > 27) {
      lines.push(line);
      line = word;
    } else line = line ? `${line} ${word}` : word;
  }
  if (line) lines.push(line);
  return lines.length > 2 ? [lines[0], lines[1].slice(0, 25) + "…"] : lines;
}

export function CareerGraph({ graph, locale, skillName }: {
  graph: CareerGraphData; locale: Locale; skillName: (id: string) => string;
}) {
  const c = GRAPH_COPY[locale];
  const t = translator(locale);
  const uid = useId().replace(/:/g, "");
  const [view, setView] = useState<"graph" | "list" | "auto">("auto");
  const [scope, setScope] = useState<"route" | "catalog">("route");
  const [selectedId, setSelectedId] = useState(graph.nodes.find((n) => n.kind === "activity" && n.step === 1)?.id ?? "goal");
  const hasRoute = graph.nodes.some((n) => n.kind === "activity" && n.step != null);
  const nodes = useMemo(() => {
    if (scope === "catalog" || !hasRoute) return graph.nodes;
    const keep = new Set(graph.nodes.filter((n) => n.kind === "goal" || (n.kind === "skill" && n.required != null) || (n.kind === "activity" && n.step != null)).map((n) => n.id));
    for (const e of graph.edges) {
      if (e.kind === "develops" && keep.has(e.source)) keep.add(e.target);
      if (e.kind === "prerequisite" && keep.has(e.target)) keep.add(e.source);
    }
    return graph.nodes.filter((n) => keep.has(n.id));
  }, [graph, scope, hasRoute]);
  const nodeIds = new Set(nodes.map((n) => n.id));
  const edges = graph.edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
  const selected = nodes.find((n) => n.id === selectedId) ?? nodes[0];
  const adjacent = new Set([selected.id]);
  edges.filter((e) => e.source === selected.id || e.target === selected.id).forEach((e) => {
    adjacent.add(e.source); adjacent.add(e.target);
  });
  const rows = { activity: 0, skill: 0, goal: 0 };
  const routeSkills = [...new Set(nodes.flatMap((n) => n.kind === "activity" && n.step ? n.effects.map((e) => `skill:${e.skill_id}`) : []))];
  const layoutNodes = [...nodes].sort((a, b) => (routeSkills.includes(a.id) ? routeSkills.indexOf(a.id) : 999) - (routeSkills.includes(b.id) ? routeSkills.indexOf(b.id) : 999));
  const positions = new Map(layoutNodes.map((n) => [n.id, { x: X[n.kind], y: 52 + rows[n.kind]++ * 154 }]));
  const height = Math.max(260, 68 + Math.max(...Object.values(rows)) * 154);
  const describe = (n: GraphNode) => n.kind === "skill"
    ? `${c.now}: ${n.current}${n.required == null ? "" : ` / ${n.required}`}${n.critical ? " · ★" : ""}`
    : n.kind === "activity" ? `${n.step ? `${c.step} ${n.step} · ` : ""}${n.duration_hours} ${t("hours")} · ${n.format}` : t("src_" + n.source);
  const nodeButton = (n: GraphNode) => <button className="btn small" aria-pressed={selected.id === n.id} onClick={() => setSelectedId(n.id)}>{n.label}</button>;

  return <div className="career-graph" data-view={view}>
    <div className="graph-toolbar">
      <div className="graph-view-toggle" role="group" aria-label={c.title}>
        <button className="btn small graph-toggle" aria-pressed={view === "auto" ? undefined : view === "graph"} onClick={() => setView("graph")}>{c.graph}</button>
        <button className="btn small list-toggle" aria-pressed={view === "auto" ? undefined : view === "list"} onClick={() => setView("list")}>{c.list}</button>
      </div>
      <label className="small">{c.scope} <select className="input" value={hasRoute ? scope : "catalog"} onChange={(e) => setScope(e.target.value as "route" | "catalog")}>
        <option value="route" disabled={!hasRoute}>{c.route}</option>
        <option value="catalog">{c.catalog}</option>
      </select></label>
      <span className="chip grey">{c.current}</span>
    </div>
    {!hasRoute && <p className="small muted graph-note">{graph.nodes.find((n) => n.id === "goal")?.status === "met" ? t("plan_not_run") : c.noRoute}</p>}
    <div className="graph-visual">
      <p className="small muted graph-note" id={`${uid}-hint`}>{c.hint}</p>
      <div className="graph-viewport" role="region" aria-label={c.graph} tabIndex={0}>
        <svg width="1044" height={height} viewBox={`0 0 1044 ${height}`} role="group" aria-label={c.title} aria-describedby={`${uid}-hint`}>
          <defs>
            <marker id={`${uid}-arrow`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke" /></marker>
          </defs>
          {(["activity", "skill", "goal"] as const).map((kind) => <text key={kind} x={X[kind]} y={27} className="graph-column">{c[kind]}</text>)}
          {[...edges].sort((a, b) => Number(a.source === selected.id || a.target === selected.id) - Number(b.source === selected.id || b.target === selected.id)).map((e) => {
            const from = positions.get(e.source)!;
            const to = positions.get(e.target)!;
            const outgoing = edges.filter((other) => other.source === e.source && other.kind === e.kind);
            const incoming = edges.filter((other) => other.target === e.target && other.kind === e.kind);
            const sourcePort = (outgoing.findIndex((other) => other.id === e.id) + 1) / (outgoing.length + 1);
            const targetPort = (incoming.findIndex((other) => other.id === e.id) + 1) / (incoming.length + 1);
            const right = from.x < to.x;
            const x1 = from.x + (right ? WIDTH : 0);
            const x2 = to.x + (right ? 0 : WIDTH);
            const y1 = from.y + 24 + sourcePort * 65;
            const y2 = to.y + (e.kind === "prerequisite" ? 86 + targetPort * 28 : 24 + targetPort * 65);
            const direction = right ? 1 : -1;
            const active = e.source === selected.id || e.target === selected.id;
            const label = `${e.kind}${e.level != null ? ` ≥${e.level}` : ` +${e.gain} ≤${e.cap}`}`;
            return <g key={e.id} className={`graph-edge ${e.kind} ${active ? "is-active" : ""}`}>
              <title>{`${e.kind}: ${nodes.find((n) => n.id === e.source)?.label} → ${nodes.find((n) => n.id === e.target)?.label}`}</title>
              <path d={`M${x1},${y1} C${x1 + direction * 115},${y1} ${x2 - direction * 100},${y2} ${x2},${y2}`} markerEnd={`url(#${uid}-arrow)`} />
              <text x={right ? x1 + 9 : x2 + 9} y={(right ? y1 : y2) - 5}>{label}</text>
            </g>;
          })}
          {nodes.map((n) => {
            const p = positions.get(n.id)!;
            return <g key={n.id} transform={`translate(${p.x},${p.y})`} role="button" tabIndex={0}
              aria-label={`${n.label}. ${describe(n)}. ${c[n.status]}`} aria-pressed={selected.id === n.id} aria-controls={`${uid}-details`}
              className={`graph-node ${n.status} ${selected.id === n.id ? "is-selected" : ""} ${adjacent.has(n.id) ? "is-related" : ""}`}
              onClick={() => setSelectedId(n.id)} onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedId(n.id); }
              }}>
              <title>{n.label}</title>
              <rect width={WIDTH} height={HEIGHT} rx={12} />
              <text x={13} y={20} className="graph-kind">{n.kind === "activity" ? n.event_id : n.kind === "skill" && n.critical ? `★ ${t("critical")}` : c[n.kind]}</text>
              <text x={13} y={43} className="graph-label">{wrapLabel(n.label).map((line, i) => <tspan key={i} x={13} dy={i ? 17 : 0}>{line}</tspan>)}</text>
              <text x={13} y={84} className="graph-meta">{describe(n).length > 34 ? describe(n).slice(0, 32) + "…" : describe(n)}</text>
              <text x={13} y={109} className="graph-status">{c[n.status]}</text>
            </g>;
          })}
        </svg>
      </div>
      <div className="graph-legend small">
        {(["requires", "develops", "prerequisite"] as const).map((kind) => <span key={kind}><b>{kind}</b> - {c[kind]}</span>)}
      </div>
    </div>
    <div className="graph-list">
      <ol className="graph-step-list">
        {nodes.filter((n) => n.kind === "activity").map((n) => n.kind === "activity" && <li key={n.id}>
          <div className="row">{n.step && <b>{c.step} {n.step}</b>}{nodeButton(n)}<span className={`chip ${n.status === "blocked" || n.status === "after_previous" ? "amber" : "grey"}`}>{c[n.status]}</span></div>
          <p className="small muted">{n.prerequisites.length ? n.prerequisites.map((p) => `${skillName(p.skill_id)}: ${p.current} / ${p.required} ${p.met ? "✓" : `(${c.level} ${p.required})`}`).join(" · ") : c.noConditions}</p>
          {n.reasons.length > 0 && <p className="small">{n.reasons.map((r) => reasonText(r.code, locale)).join("; ")}</p>}
        </li>)}
      </ol>
      {nodes.every((n) => n.kind !== "activity") && <p className="small muted">{c.noActivity}</p>}
      <div className="graph-table-wrap"><table>
        <caption>{c.conditions}</caption><thead><tr><th>{c.skill}</th><th>{c.now}</th><th>{t("required")}</th></tr></thead>
        <tbody>{nodes.filter((n) => n.kind === "skill").map((n) => n.kind === "skill" && <tr key={n.id}><td>{nodeButton(n)}{n.critical && " ★"}</td><td>{n.current}</td><td>{n.required ?? "-"}</td></tr>)}</tbody>
      </table></div>
      {nodeButton(graph.nodes.find((n) => n.id === "goal")!)}
    </div>
    <div className="graph-details" id={`${uid}-details`} role="region" aria-label={c.selected} aria-live="polite">
      <div className="section-head"><div><p className="small muted">{c.selected}</p><h3>{selected.label}</h3></div><span className="chip grey">{c[selected.status]}</span></div>
      {selected.kind === "activity" && <>
        <p className="small">{selected.duration_hours} {t("hours")} · {selected.format} · {selected.session ?? t("selfPaced")}</p>
        {selected.reasons.length > 0 && <p className="graph-blockers small">{selected.reasons.map((r) => reasonText(r.code, locale)).join("; ")}</p>}
        <div className="graph-detail-columns">
          <div><h4>{c.conditions}</h4>{selected.prerequisites.length ? <ul>{selected.prerequisites.map((p) => <li key={p.skill_id}>{skillName(p.skill_id)}: {p.current} / {p.required} - {p.met ? "✓" : `${c.level} ${p.required}`}</li>)}</ul> : <p className="small muted">{c.noConditions}</p>}</div>
          <div><h4>{c.effects}</h4><ul>{selected.effects.map((e) => <li key={e.skill_id}>{skillName(e.skill_id)}: {e.before} → {e.after} (+{e.actual}; {c.cap} {e.cap})</li>)}</ul></div>
        </div>
        {selected.plan_step && <p className="small graph-forecast"><b>{c.forecast} · {c.step} {selected.step}</b>: {selected.plan_step.estimated_start} → {selected.plan_step.estimated_finish}<br />{selected.plan_step.changes.map((e) => `${skillName(e.skill_id)}: ${e.before} → ${e.after}`).join(" · ")}</p>}
      </>}
      {selected.kind === "skill" && <>
        <p>{c.now}: <b>{selected.current}</b>{selected.required != null && ` · ${t("required")}: ${selected.required}`}{selected.critical && ` · ${t("critical")}`}</p>
        {hasRoute && <p className="small graph-forecast">{c.forecast}: {selected.current} → {selected.planned}</p>}
        {!graph.edges.some((e) => e.kind === "develops" && e.target === selected.id) && <p className="small graph-blockers">{c.noProvider}</p>}
      </>}
      {selected.kind === "goal" && <p className="small">{t("src_" + selected.source)}. {t("readinessHint")}</p>}
      <ul className="graph-related-list">{edges.filter((e) => e.source === selected.id || e.target === selected.id).map((e) => {
        const other = nodes.find((n) => n.id === (e.source === selected.id ? e.target : e.source))!;
        return <li key={e.id}><span className="small">{e.kind}{e.level != null ? ` ≥ ${e.level}` : ` +${e.gain} (${c.cap} ${e.cap})`} → </span>{nodeButton(other)}</li>;
      })}</ul>
    </div>
    <p className="small muted graph-note">{c.forecastHint}</p>
  </div>;
}
