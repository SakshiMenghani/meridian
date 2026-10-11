"use client";

import { ArrowUp, Eye, KeyRound, Link2, Loader2, Lock, MessageSquarePlus, RefreshCw, Sparkles } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { AnswerCard } from "@/components/answer-card";
import { SourcePicker, scopeLabel } from "@/components/source-picker";
import { api } from "@/lib/api";
import type { AskResult, Meta, Source, Suggestions } from "@/lib/types";

type Turn = {
  question: string;
  result?: AskResult;
  error?: string;
};

const THINKING = ["Reading your data", "Planning the query", "Checking the SQL", "Running it", "Writing the answer"];

function ChatWorkspace() {
  const search = useSearchParams();
  const preset = search.get("source");
  const [sources, setSources] = useState<Source[] | null>(null);
  const [selected, setSelected] = useState<string[]>(preset ? [preset] : []);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestions | null>(null);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState(0);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api<Source[]>("/api/sources").then(setSources).catch(() => setSources([]));
    api<Meta>("/api/meta").then(setMeta).catch(() => setMeta(null));
  }, []);

  const loadSuggestions = useCallback(() => {
    setLoadingSuggestions(true);
    api<Suggestions>("/api/suggestions", {
      method: "POST",
      body: JSON.stringify({ source_ids: selected.length ? selected : null }),
    })
      .then(setSuggestions)
      .catch(() => setSuggestions(null))
      .finally(() => setLoadingSuggestions(false));
  }, [selected]);

  useEffect(() => {
    loadSuggestions();
  }, [loadSuggestions]);

  useEffect(() => {
    if (turns.length) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, busy]);

  useEffect(() => {
    if (!busy) return;
    setPhase(0);
    const timer = setInterval(() => setPhase((value) => Math.min(value + 1, THINKING.length - 1)), 2200);
    return () => clearInterval(timer);
  }, [busy]);

  useEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
  }, [question]);

  async function ask(text: string) {
    const trimmed = text.trim();
    if (trimmed.length < 3 || busy) return;
    setQuestion("");
    setTurns((current) => [...current, { question: trimmed }]);
    setBusy(true);
    try {
      const result = await api<AskResult>("/api/ask", {
        method: "POST",
        body: JSON.stringify({ question: trimmed, source_ids: selected.length ? selected : null }),
      });
      setTurns((current) => current.map((turn, index) => (index === current.length - 1 ? { ...turn, result } : turn)));
    } catch (err) {
      const message = err instanceof Error ? err.message : "The question could not be answered.";
      setTurns((current) => current.map((turn, index) => (index === current.length - 1 ? { ...turn, error: message } : turn)));
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  const enabled = (sources ?? []).filter((source) => source.enabled);
  const scope = sources ? scopeLabel(sources, selected) : "your sources";
  const noSources = sources !== null && enabled.length === 0;

  return (
    <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-4xl flex-col">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Ask</p>
          <h1 className="font-display mt-2 text-4xl">Ask your data anything</h1>
          {turns.length === 0 ? (
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              Type a question the way you would ask a colleague. You get the answer, a chart, the table behind it, and the
              exact query that ran.
            </p>
          ) : null}
        </div>
        {turns.length > 0 ? (
          <button type="button" onClick={() => setTurns([])} disabled={busy} className="btn btn-secondary">
            <MessageSquarePlus size={15} /> New conversation
          </button>
        ) : null}
      </header>

      {meta && !meta.openai_configured ? (
        <div className="mb-5 flex items-start gap-3 rounded-2xl border border-warn/30 bg-warn/5 px-4 py-3 text-sm">
          <KeyRound size={16} className="mt-0.5 shrink-0 text-warn" />
          <p>
            Offline mode: totals, rankings and simple reports work. For open-ended questions and questions across sources,{" "}
            <Link href="/settings" className="font-semibold text-tide underline">
              add an OpenAI key
            </Link>
            .
          </p>
        </div>
      ) : null}

      <div className="flex-1 space-y-8">
        {noSources ? (
          <div className="card px-6 py-10 text-center">
            <p className="font-display text-2xl">Connect a source to start</p>
            <p className="mx-auto mt-2 max-w-md text-sm text-muted">
              Add a database, upload a spreadsheet, or attach marketing data. Then come back and ask anything about it.
            </p>
            <Link href="/sources/new" className="btn btn-primary mt-5">
              Connect a source
            </Link>
          </div>
        ) : null}

        {turns.length === 0 && !noSources ? (
          <section>
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Sparkles size={15} className="text-tide" />
                <h2 className="text-sm font-semibold">Try one of these</h2>
                <span className="text-xs text-muted">
                  {loadingSuggestions ? `Reading ${scope}…` : suggestions ? `Written from your ${suggestions.tables.length} tables` : ""}
                </span>
              </div>
              <button type="button" onClick={loadSuggestions} disabled={loadingSuggestions} className="btn btn-ghost btn-sm">
                <RefreshCw size={12} className={loadingSuggestions ? "animate-spin" : ""} /> More ideas
              </button>
            </div>
            <div className="grid gap-2.5 sm:grid-cols-2">
              {loadingSuggestions && !suggestions
                ? Array.from({ length: 6 }).map((_, index) => <div key={index} className="h-[60px] animate-pulse rounded-2xl bg-panel" />)
                : (suggestions?.questions ?? []).map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => ask(item)}
                      className="group card flex items-start gap-3 px-4 py-3.5 text-left text-sm leading-5 transition hover:-translate-y-px hover:border-tide/40"
                    >
                      <span className="mt-0.5 text-tide/60 group-hover:text-tide">
                        <ArrowUp size={14} className="rotate-45" />
                      </span>
                      {item}
                    </button>
                  ))}
            </div>
            <ul className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted">
              <li className="flex items-center gap-1.5">
                <Lock size={13} className="text-tide" /> Read-only. Nothing in your data is changed.
              </li>
              <li className="flex items-center gap-1.5">
                <Link2 size={13} className="text-tide" /> Sources are combined only on{" "}
                <Link href="/links" className="font-semibold text-tide">
                  links you confirmed
                </Link>
              </li>
              <li className="flex items-center gap-1.5">
                <Eye size={13} className="text-tide" /> Every answer shows the query behind it.
              </li>
            </ul>
          </section>
        ) : null}

        {turns.map((turn, index) => (
          <article key={`${turn.question}-${index}`} className="space-y-3">
            <p className="ml-auto w-fit max-w-xl rounded-3xl rounded-br-md bg-tide px-4 py-2.5 text-sm text-white">{turn.question}</p>
            {turn.error ? <p className="max-w-2xl rounded-2xl bg-bad/10 px-4 py-3 text-sm text-bad">{turn.error}</p> : null}
            {turn.result ? <AnswerCard result={turn.result} onAsk={ask} /> : null}
          </article>
        ))}
        {busy ? <Thinking phase={phase} /> : null}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          ask(question);
        }}
        className="sticky bottom-0 mt-8 bg-gradient-to-t from-paper via-paper to-paper/0 pt-6 pb-3"
      >
        <div className="card p-2 transition focus-within:border-tide focus-within:ring-4 focus-within:ring-tide/10">
          <textarea
            ref={inputRef}
            rows={1}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                ask(question);
              }
            }}
            placeholder={turns.length ? "Ask a follow-up question…" : 'Ask a question, or say "make a report on…"'}
            aria-label="Your question"
            className="block max-h-40 w-full resize-none bg-transparent px-3 pt-2 pb-1 text-[15px] leading-6 outline-none placeholder:text-muted/70"
          />
          <div className="flex items-center justify-between gap-2 pt-1">
            {sources && enabled.length ? (
              <SourcePicker sources={sources} selected={selected} onChange={setSelected} placement="top" />
            ) : (
              <span />
            )}
            <div className="flex items-center gap-3">
              <span className="hidden text-xs text-muted sm:inline">Enter to send · Shift+Enter for a new line</span>
              <button
                type="submit"
                disabled={busy || question.trim().length < 3 || enabled.length === 0}
                className="flex h-9 w-9 items-center justify-center rounded-full bg-tide text-white hover:bg-tide-deep"
                aria-label="Send question"
              >
                {busy ? <Loader2 size={16} className="animate-spin" /> : <ArrowUp size={16} />}
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}

function Thinking({ phase }: { phase: number }) {
  return (
    <div className="card max-w-md px-4 py-3">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Loader2 size={14} className="animate-spin text-tide" />
        {THINKING[phase]}…
      </div>
      <div className="mt-3 flex gap-1">
        {THINKING.map((step, index) => (
          <span key={step} className={`h-1 flex-1 rounded-full transition-colors ${index <= phase ? "bg-tide" : "bg-line"}`} />
        ))}
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}>
      <ChatWorkspace />
    </Suspense>
  );
}
