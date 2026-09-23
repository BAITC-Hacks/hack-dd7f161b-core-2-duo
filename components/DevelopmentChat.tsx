"use client";

import { FormEvent, useEffect, useId, useRef, useState } from "react";
import { post } from "@/lib/api";
import { CHAT_COPY, ChatResponse } from "@/lib/chat";
import { Meta } from "@/lib/hooks";
import { AppState } from "@/lib/store";
import { SimulationData, SimulationResult } from "@/components/SimulationResult";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  fingerprint: string;
  simulation?: SimulationData | null;
  unavailable?: boolean;
};

export function DevelopmentChat({ s, employeeId, meta, fingerprint, suggestedTitle }: {
  s: AppState;
  employeeId: string;
  meta: Meta;
  fingerprint: string;
  suggestedTitle?: string;
}) {
  const copy = CHAT_COPY[s.locale];
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const launcher = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const request = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const panelId = useId();
  const inputId = useId();

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);
  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [messages, pending, open]);
  useEffect(() => {
    setPending(false);
    return () => {
      request.current?.abort();
      request.current = null;
    };
  }, [fingerprint]);

  function close() {
    setOpen(false);
    launcher.current?.focus();
  }

  function clear() {
    request.current?.abort();
    request.current = null;
    setPending(false);
    setMessages([]);
    input.current?.focus();
  }

  function suggest(text: string) {
    setDraft(text.slice(0, 2000));
    input.current?.focus();
  }

  async function send(e: FormEvent) {
    e.preventDefault();
    const message = draft.trim();
    if (!message || request.current) return;
    const controller = new AbortController();
    request.current = controller;
    const history = messages.filter((m) => m.fingerprint === fingerprint && !m.unavailable).slice(-8)
      .map(({ role, content }) => ({ role, content: content.slice(0, 2000) }));
    const userMessage: Message = { id: ++sequence.current, role: "user", content: message, fingerprint };
    setMessages((previous) => [...previous.slice(-39), userMessage]);
    setDraft("");
    setPending(true);
    // A client deadline also covers a stalled proxy or disconnected server.
    const timer = setTimeout(() => controller.abort(), 10_000);
    const append = (content: string, simulation?: SimulationData | null, unavailable = false) => {
      if (request.current !== controller) return;
      const reply: Message = { id: ++sequence.current, role: "assistant", content, simulation, fingerprint, unavailable };
      setMessages((previous) => [...previous.slice(-39), reply]);
    };
    try {
      const result = await post<ChatResponse>(s, `/employees/${employeeId}/chat`, { message, history }, controller.signal);
      if (!result.reply_text?.trim()) throw new Error("empty_chat_response");
      append(result.reply_text, result.simulation, result.ai_status.startsWith("fallback_"));
    } catch {
      append(copy.unavailable, null, true);
    } finally {
      clearTimeout(timer);
      if (request.current === controller) {
        request.current = null;
        setPending(false);
      }
    }
  }

  return (
    <div className="development-chat">
      {open && (
        <section id={panelId} className="chat-panel" role="dialog" aria-label={copy.title}
          onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } }}>
          <div className="chat-header">
            <div><h2>{copy.title}</h2><p className="small">{copy.subtitle}</p></div>
            <button type="button" className="btn ghost small" onClick={close} aria-label={copy.close}>✕</button>
          </div>
          <div className="chat-log" ref={log} role="log" aria-label={copy.log} aria-live="polite" aria-relevant="additions">
            <p className="chat-intro">{copy.intro}</p>
            {messages.length === 0 && (
              <div className="chat-suggestions">
                <button type="button" className="btn small" onClick={() => suggest(copy.glossary)}>{copy.glossary}</button>
                {suggestedTitle && <button type="button" className="btn small" onClick={() => suggest(copy.scenario.replace("{title}", suggestedTitle))}>{copy.scenarioButton.replace("{title}", suggestedTitle)}</button>}
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`chat-message ${m.role}${m.unavailable ? " unavailable" : ""}`}>
                <span className="chat-author">{m.role === "user" ? copy.you : copy.bot}</span>
                {m.simulation && m.fingerprint !== fingerprint ? <p>{copy.stale}</p> : (
                  <>
                    <p>{m.content}</p>
                    {m.simulation && <SimulationResult compact data={m.simulation} locale={s.locale}
                      skillName={(id) => meta.skills[id]?.name ?? id} eventName={(id) => meta.events[id]?.title ?? id} />}
                  </>
                )}
              </div>
            ))}
            {pending && <p className="chat-thinking">{copy.thinking}</p>}
          </div>
          <form className="chat-form" onSubmit={send}>
            <label htmlFor={inputId} className="small">{copy.label}</label>
            <textarea ref={input} id={inputId} className="input" rows={2} maxLength={2000} value={draft}
              placeholder={copy.placeholder} onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }} />
            <div className="row">
              <button type="button" className="btn ghost small" onClick={clear} disabled={!messages.length}>{copy.clear}</button>
              <span className="spacer" />
              <button type="submit" className="btn primary" disabled={pending || !draft.trim()}>{copy.send}</button>
            </div>
            <p className="chat-privacy">{copy.privacy}</p>
          </form>
        </section>
      )}
      <button ref={launcher} type="button" className="btn primary chat-launcher" aria-expanded={open} aria-controls={open ? panelId : undefined}
        onClick={() => open ? close() : setOpen(true)}>
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
          <path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-8l-6 3v-3a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" /><path d="M7 9h10M7 13h6" />
        </svg>
        {copy.title}
      </button>
    </div>
  );
}
