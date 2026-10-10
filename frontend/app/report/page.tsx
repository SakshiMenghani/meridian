"use client";

import { useEffect, useState } from "react";
import { DataTable } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { ResultChart } from "@/components/result-chart";
import { api } from "@/lib/api";
import { downloadReport } from "@/lib/report-html";
import type { AskResult, ChartSpec, Source } from "@/lib/types";

const TEMPLATES = [
  "Write a weekly marketing report with a pie chart of the mix.",
  "Create a briefing of campaign performance with downloadable charts.",
  "Report sessions by channel and show the trend over time.",
];

export default function ReportPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [question, setQuestion] = useState(TEMPLATES[0]);
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [kinds, setKinds] = useState<Record<number, ChartSpec["type"]>>({});

  useEffect(() => {
    api<Source[]>("/api/sources")
      .then((rows) => {
        setSources(rows);
        const marketing = rows.find((row) => row.source_type === "google_analytics") || rows.find((row) => row.enabled);
        setSourceId((current) => current || marketing?.id || "");
      })
      .catch(() => setSources([]));
  }, []);

  async function generate(event: React.FormEvent) {
    event.preventDefault();
    if (!sourceId || question.trim().length < 3) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api<AskResult>("/api/report", {
        method: "POST",
        body: JSON.stringify({ question, source_ids: [sourceId], as_report: true }),
      });
      setResult(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The report could not be generated.");
    } finally {
      setBusy(false);
    }
  }

  const sections = result?.report?.sections ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Reports"
        title="Marketing briefing"
        description="Ask for a report. Meridian reads the attached source through MCP, then builds a pie, a ranking, and a trend you can download."
      />
      <form onSubmit={generate} className="mb-8 rounded-3xl border border-line bg-panel p-5">
        <div className="flex flex-wrap gap-3">
          <label className="text-sm">
            <span className="mr-2 text-muted">Source</span>
            <select
              value={sourceId}
              onChange={(event) => setSourceId(event.target.value)}
              className="rounded-full border border-line bg-paper px-3 py-2"
            >
              {sources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {TEMPLATES.map((item) => (
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
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          className="mt-4 min-h-24 w-full rounded-2xl border border-line bg-paper px-4 py-3 text-sm"
        />
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="submit" disabled={busy || !sourceId} className="rounded-full bg-tide px-4 py-2 text-sm font-semibold text-white">
            {busy ? "Building report…" : "Generate report"}
          </button>
          {result ? (
            <button type="button" onClick={() => downloadReport(result)} className="rounded-full border border-line px-4 py-2 text-sm font-semibold">
              Download HTML
            </button>
          ) : null}
        </div>
        {error ? <p className="mt-3 text-sm text-bad">{error}</p> : null}
      </form>

      {result?.report ? (
        <article className="space-y-6">
          <header className="rounded-3xl bg-tide px-6 py-8 text-white">
            <p className="text-xs tracking-[0.16em] uppercase text-white/70">Report</p>
            <h2 className="font-display mt-2 text-4xl">{result.report.title}</h2>
            <p className="mt-4 max-w-3xl text-sm leading-6 text-white/90">{result.report.summary}</p>
          </header>
          {sections.map((section, index) => {
            const chart = section.chart
              ? { ...section.chart, type: kinds[index] ?? section.chart.type }
              : null;
            return (
              <section key={section.title} className="rounded-3xl border border-line bg-panel p-6">
                <h3 className="font-display text-2xl">{section.title}</h3>
                <p className="mt-2 text-sm text-muted">{section.body}</p>
                {chart ? (
                  <div className="mt-4">
                    <div className="mb-3 flex flex-wrap gap-2">
                      {(["pie", "bar", "line"] as const).map((kind) => (
                        <button
                          key={kind}
                          type="button"
                          onClick={() => setKinds((current) => ({ ...current, [index]: kind }))}
                          className={`rounded-full px-3 py-1.5 text-xs font-semibold ${
                            chart.type === kind ? "bg-tide text-white" : "bg-paper"
                          }`}
                        >
                          {kind === "pie" ? "Pie" : kind === "bar" ? "Bar" : "Line"}
                        </button>
                      ))}
                    </div>
                    <ResultChart spec={chart} rows={section.rows} />
                  </div>
                ) : null}
                <div className="mt-4">
                  <DataTable columns={section.columns} rows={section.rows} />
                </div>
              </section>
            );
          })}
        </article>
      ) : null}
    </div>
  );
}
