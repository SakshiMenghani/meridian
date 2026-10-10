"use client";

import { ArrowUp } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { DataTable } from "@/components/data-table";
import { ResultChart } from "@/components/result-chart";
import { api } from "@/lib/api";
import { sourceLabel } from "@/lib/format";
import { downloadReport } from "@/lib/report-html";
import type { AskResult, CatalogObject, ChartSpec, Source } from "@/lib/types";

type View = "chart" | "table" | "sql" | null;

type Turn = {
  question: string;
  result?: AskResult;
  error?: string;
  view: View;
  chartType?: ChartSpec["type"];
};

function ChatWorkspace() {
  const search = useSearchParams();
  const preset = search.get("source");
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceId, setSourceId] = useState(preset ?? "");
  const [objects, setObjects] = useState<CatalogObject[]>([]);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<Source[]>("/api/sources")
      .then((rows) => {
        setSources(rows);
        setSourceId((current) => current || preset || rows.find((row) => row.enabled)?.id || "");
      })
      .catch(() => setSources([]));
  }, [preset]);

  useEffect(() => {
    if (!sourceId) {
      setObjects([]);
      return;
    }
    api<{ objects: CatalogObject[] }>(`/api/sources/${sourceId}/catalog`)
      .then((catalog) => setObjects(catalog.objects))
      .catch(() => setObjects([]));
  }, [sourceId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  const source = sources.find((item) => item.id === sourceId);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || !sourceId) return;
    setQuestion("");
    setTurns((current) => [...current, { question: text, view: null }]);
    setBusy(true);
    try {
      const wantsReport = /report|briefing|download/i.test(text);
      const result = await api<AskResult>(wantsReport ? "/api/report" : "/api/ask", {
        method: "POST",
        body: JSON.stringify({ question: text, source_ids: [sourceId], as_report: wantsReport }),
      });
      setTurns((current) =>
        current.map((turn, index) =>
          index === current.length - 1
            ? { ...turn, result, view: result.chart || result.report ? "chart" : "table", chartType: result.chart?.type }
            : turn,
        ),
      );
    } catch (err) {
      setTurns((current) =>
        current.map((turn, index) =>
          index === current.length - 1
            ? { ...turn, error: err instanceof Error ? err.message : "The question could not be answered." }
            : turn,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  function setView(index: number, view: View) {
    setTurns((current) => current.map((turn, i) => (i === index ? { ...turn, view: turn.view === view ? null : view } : turn)));
  }

  return (
    <div className="grid min-h-[calc(100vh-4rem)] gap-6 xl:grid-cols-[minmax(0,1fr)_260px]">
      <section className="flex min-w-0 flex-col">
        <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold tracking-[0.16em] text-tide uppercase">Assistant</p>
            <h1 className="font-display mt-2 text-4xl">Chats</h1>
            <p className="mt-2 text-sm text-muted">Ask a question or request a report. Switch the chart to pie, bar, or line, then download it.</p>
          </div>
          <label className="text-sm">
            <span className="mr-2 text-muted">Current source</span>
            <select
              value={sourceId}
              onChange={(event) => setSourceId(event.target.value)}
              className="rounded-full border border-line bg-panel px-3 py-2"
            >
              {sources.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        </header>

        <div className="flex-1 space-y-5">
          {turns.length === 0 ? (
            <div className="rounded-2xl border border-line bg-panel p-5">
              <p className="text-sm text-muted">Try a question about {source?.name ?? "the selected source"}.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {suggestions(source?.source_type, source?.name).map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setQuestion(item)}
                    className="rounded-full bg-paper px-3 py-1.5 text-left text-sm"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {turns.map((turn, index) => (
            <article key={`${turn.question}-${index}`} className="space-y-3">
              <p className="ml-auto max-w-xl rounded-full bg-tide px-4 py-2 text-sm text-white">{turn.question}</p>
              {turn.error ? <p className="max-w-2xl rounded-2xl bg-bad/10 px-4 py-3 text-sm text-bad">{turn.error}</p> : null}
              {turn.result ? (
                <div className="max-w-3xl rounded-2xl border border-line bg-panel p-5">
                  <p className="text-sm leading-6 whitespace-pre-wrap">{turn.result.answer}</p>
                  {turn.result.points.length > 0 ? (
                    <ul className="mt-3 space-y-1 text-sm">
                      {turn.result.points.map((point) => (
                        <li key={point}>{point}</li>
                      ))}
                    </ul>
                  ) : null}
                  <div className="mt-4 flex flex-wrap gap-2">
                    {turn.result.chart ? (
                      <ViewButton active={turn.view === "chart"} onClick={() => setView(index, "chart")} label="View chart" />
                    ) : null}
                    <ViewButton active={turn.view === "table"} onClick={() => setView(index, "table")} label="View table" />
                    {turn.result.query ? (
                      <ViewButton active={turn.view === "sql"} onClick={() => setView(index, "sql")} label="View query" />
                    ) : null}
                    <button
                      type="button"
                      onClick={() => downloadReport(turn.result!)}
                      className="rounded-full bg-paper px-3 py-1.5 text-xs font-semibold"
                    >
                      Download
                    </button>
                  </div>
                  {turn.view === "chart" && turn.result.chart ? (
                    <div className="mt-4">
                      <div className="mb-3 flex flex-wrap gap-2">
                        {(["pie", "bar", "line"] as const).map((kind) => (
                          <ViewButton
                            key={kind}
                            active={(turn.chartType ?? turn.result!.chart!.type) === kind}
                            onClick={() =>
                              setTurns((current) =>
                                current.map((item, i) => (i === index ? { ...item, chartType: kind, view: "chart" } : item)),
                              )
                            }
                            label={kind === "pie" ? "Pie" : kind === "bar" ? "Bar" : "Line"}
                          />
                        ))}
                      </div>
                      <ResultChart
                        spec={{ ...turn.result.chart, type: turn.chartType ?? turn.result.chart.type }}
                        rows={turn.result.rows}
                      />
                      {turn.result.report?.sections.slice(1).map((section) =>
                        section.chart ? (
                          <div key={section.title} className="mt-6">
                            <p className="mb-2 text-sm font-semibold">{section.title}</p>
                            <ResultChart spec={section.chart} rows={section.rows} />
                          </div>
                        ) : null,
                      )}
                    </div>
                  ) : null}
                  {turn.view === "table" ? (
                    <div className="mt-4">
                      <DataTable columns={turn.result.columns} rows={turn.result.rows} />
                    </div>
                  ) : null}
                  {turn.view === "sql" && turn.result.query ? (
                    <pre className="mt-4 overflow-x-auto rounded-xl bg-sidebar p-4 text-xs leading-5 text-mist">
                      {turn.result.query}
                    </pre>
                  ) : null}
                  <p className="mt-3 text-xs text-muted">
                    From {turn.result.sources_used.join(", ")}
                    {turn.result.tools_used?.length ? ` · ${turn.result.tools_used.join(", ")}` : ""}
                  </p>
                </div>
              ) : null}
            </article>
          ))}
          {busy ? <p className="text-sm text-muted">Reading the selected source…</p> : null}
          <div ref={endRef} />
        </div>

        <form onSubmit={onSubmit} className="sticky bottom-0 mt-6 bg-paper pt-3 pb-1">
          <div className="flex items-end gap-2 rounded-full border border-line bg-panel px-4 py-2">
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question about your data"
              className="min-w-0 flex-1 bg-transparent py-2 text-sm outline-none"
            />
            <button
              type="submit"
              disabled={busy || !sourceId || question.trim().length < 3}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-tide text-white"
              aria-label="Send question"
            >
              <ArrowUp size={16} />
            </button>
          </div>
        </form>
      </section>

      <aside className="rounded-2xl border border-line bg-panel p-4">
        <p className="text-xs font-semibold tracking-[0.16em] text-muted uppercase">Data explorer</p>
        <p className="mt-2 text-sm font-semibold">{source?.name ?? "No source"}</p>
        <p className="text-xs text-muted">{source ? sourceLabel(source.source_type) : "Choose a source to see its tables."}</p>
        <ul className="mt-4 space-y-2">
          {objects.map((object) => (
            <li key={`${object.schema_name ?? ""}-${object.name}`}>
              <p className="text-sm font-medium break-all">{object.name}</p>
              <p className="text-xs text-muted">
                {object.kind}
                {object.row_count != null ? ` · ${object.row_count}` : ""} · {object.columns.length} columns
              </p>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

function ViewButton({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-3 py-1.5 text-xs font-semibold ${active ? "bg-tide text-white" : "bg-paper text-ink"}`}
    >
      {label}
    </button>
  );
}

function suggestions(type: string | undefined, name: string | undefined): string[] {
  const lowered = `${type ?? ""} ${name ?? ""}`.toLowerCase();
  if (lowered.includes("loan") || lowered.includes("spreadsheet") || lowered.includes("import")) {
    return [
      "Break down loan applications by loan type",
      "Which loan type had the most applications?",
      "How many rows are in this source?",
    ];
  }
  if (lowered.includes("postgres") || lowered.includes("commerce")) {
    return [
      "Show the top 5 customers based on total purchases.",
      "How many orders are in the commerce database?",
      "Which products are in the catalog?",
    ];
  }
  if (lowered.includes("mongo") || lowered.includes("crm")) {
    return ["How many customer profiles are in the CRM?", "List the product reviews.", "Which customers are VIP?"];
  }
  if (lowered.includes("analytics") || lowered.includes("traffic") || lowered.includes("session")) {
    return [
      "What kind of overall analysis is this data giving?",
      "Write a weekly marketing report with a pie chart of the mix.",
      "Which channel brought the most sessions?",
    ];
  }
  if (lowered.includes("google_ads") || lowered.includes("ads") || lowered.includes("campaign")) {
    return [
      "What is this data about?",
      "What kind of overall analysis is this data giving?",
      "How many clicks did Ridge Apparel receive last week?",
    ];
  }
  return ["How many rows are in this source?", "Show a preview of the data."];
}

export default function ChatPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Loading assistant…</p>}>
      <ChatWorkspace />
    </Suspense>
  );
}
