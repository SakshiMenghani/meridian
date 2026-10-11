"use client";

import { ArrowUp, Database, KeyRound, Link2, Loader2, MessageSquareText, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { AnswerCard } from "@/components/answer-card";
import { SourcePicker } from "@/components/source-picker";
import { api } from "@/lib/api";
import type { AskResult, Meta, Source, Suggestions } from "@/lib/types";

type Turn = {
  question: string;
  result?: AskResult;
  error?: string;
};

const THINKING = ["Reading your data…", "Planning the query…", "Checking the SQL…", "Running it…", "Writing the answer…"];

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
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, busy]);

  useEffect(() => {
    if (!busy) return;
    setPhase(0);
    const timer = setInterval(() => setPhase((value) => Math.min(value + 1, THINKING.length - 1)), 2200);
    return () => clearInterval(timer);
  }, [busy]);

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
    }
  }

  const enabled = (sources ?? []).filter((source) => source.enabled);
  const scope = selected.length ? `${selected.length} selected source${selected.length === 1 ? "" : "s"}` : "all your sources";

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-5xl flex-col">
      <header className="mb-5">
        <p className="text-xs font-semibold tracking-[0.16em] text-tide uppercase">Ask</p>
        <h1 className="font-display mt-2 text-4xl">Ask your data anything</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          Write a question in plain words. Meridian reads the sources you pick, writes a safe read-only query, and shows
          the answer with a chart, the table, and the exact SQL it ran.
        </p>
      </header>

      {meta && !meta.openai_configured ? (
        <div className="mb-4 flex items-start gap-3 rounded-2xl border border-warn/30 bg-warn/5 px-4 py-3 text-sm">
          <KeyRound size={16} className="mt-0.5 shrink-0 text-warn" />
          <p className="text-ink">
            Running in offline mode. Simple questions and reports work; for open-ended questions and joins across sources,{" "}
            <Link href="/settings" className="font-semibold text-tide underline">
              add an OpenAI key
            </Link>
            .
          </p>
        </div>
      ) : null}

      <div className="mb-5 rounded-2xl border border-line bg-panel p-3">
        <p className="mb-2 px-1 text-xs font-semibold text-muted">Answer from</p>
        {sources === null ? (
          <div className="h-8 w-2/3 animate-pulse rounded-full bg-paper" />
        ) : enabled.length ? (
          <SourcePicker sources={sources} selected={selected} onChange={setSelected} />
        ) : (
          <p className="px-1 text-sm text-muted">
            No sources yet.{" "}
            <Link href="/sources/new" className="font-semibold text-tide">
              Connect one
            </Link>{" "}
            to start asking.
          </p>
        )}
      </div>

      <div className="flex-1 space-y-6">
        {turns.length === 0 ? (
          <section className="space-y-5">
            <div className="grid gap-3 sm:grid-cols-3">
              <HowItWorks icon={<Database size={16} />} title="1. Pick sources" text="Ask across one source or several at once." />
              <HowItWorks icon={<MessageSquareText size={16} />} title="2. Ask in plain words" text="Totals, rankings, trends, comparisons, or a full report." />
              <HowItWorks icon={<Link2 size={16} />} title="3. Combine safely" text="Different sources are joined only on links you confirmed." href="/links" />
            </div>
            <div className="rounded-3xl border border-line bg-panel p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">Questions your data can answer</p>
                  <p className="text-xs text-muted">
                    {loadingSuggestions
                      ? `Reading ${scope}…`
                      : suggestions
                        ? `Written from ${suggestions.tables.length} tables${suggestions.generated_by === "data profile" ? "" : ` by ${suggestions.generated_by}`}.`
                        : "Pick a source to see ideas."}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={loadSuggestions}
                  disabled={loadingSuggestions}
                  className="flex items-center gap-1 rounded-full border border-line px-3 py-1.5 text-xs font-semibold"
                >
                  <RefreshCw size={12} className={loadingSuggestions ? "animate-spin" : ""} /> New ideas
                </button>
              </div>
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                {loadingSuggestions && !suggestions
                  ? Array.from({ length: 4 }).map((_, index) => <div key={index} className="h-12 animate-pulse rounded-2xl bg-paper" />)
                  : (suggestions?.questions ?? []).map((item) => (
                      <button
                        key={item}
                        type="button"
                        onClick={() => ask(item)}
                        className="rounded-2xl border border-transparent bg-paper px-4 py-3 text-left text-sm leading-5 hover:border-tide/40 hover:bg-tide/5"
                      >
                        {item}
                      </button>
                    ))}
              </div>
            </div>
          </section>
        ) : null}

        {turns.map((turn, index) => (
          <article key={`${turn.question}-${index}`} className="space-y-3">
            <p className="ml-auto w-fit max-w-xl rounded-3xl rounded-br-md bg-tide px-4 py-2.5 text-sm text-white">{turn.question}</p>
            {turn.error ? <p className="max-w-2xl rounded-2xl bg-bad/10 px-4 py-3 text-sm text-bad">{turn.error}</p> : null}
            {turn.result ? <AnswerCard result={turn.result} onAsk={ask} /> : null}
          </article>
        ))}
        {busy ? (
          <div className="flex w-fit items-center gap-2 rounded-full border border-line bg-panel px-4 py-2 text-sm text-muted">
            <Loader2 size={14} className="animate-spin text-tide" />
            {THINKING[phase]}
          </div>
        ) : null}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          ask(question);
        }}
        className="sticky bottom-0 mt-6 bg-gradient-to-t from-paper via-paper to-paper/0 pt-6 pb-2"
      >
        <div className="flex items-center gap-2 rounded-full border border-line bg-panel py-1.5 pr-1.5 pl-5 shadow-[0_12px_32px_-18px_rgba(28,36,48,0.45)] focus-within:border-tide">
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={`Ask about ${scope}, or say "make a report on…"`}
            className="min-w-0 flex-1 bg-transparent py-2 text-sm outline-none"
          />
          <button
            type="submit"
            disabled={busy || question.trim().length < 3 || enabled.length === 0}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-tide text-white"
            aria-label="Send question"
          >
            <ArrowUp size={16} />
          </button>
        </div>
      </form>
    </div>
  );
}

function HowItWorks({ icon, title, text, href }: { icon: React.ReactNode; title: string; text: string; href?: string }) {
  const body = (
    <>
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-tide/10 text-tide">{icon}</span>
      <p className="mt-3 text-sm font-semibold">{title}</p>
      <p className="mt-1 text-xs leading-5 text-muted">{text}</p>
    </>
  );
  const style = "block rounded-2xl border border-line bg-panel p-4";
  return href ? (
    <Link href={href} className={`${style} hover:border-tide/40`}>
      {body}
    </Link>
  ) : (
    <div className={style}>{body}</div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Loading assistant…</p>}>
      <ChatWorkspace />
    </Suspense>
  );
}
