"use client";

import { BarChart3, Download, FileText, LayoutGrid, Loader2, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";
import { DataTable } from "@/components/data-table";
import { AnswerCard } from "@/components/answer-card";
import { PageHeader } from "@/components/page-header";
import { ResultChart } from "@/components/result-chart";
import { SourcePicker } from "@/components/source-picker";
import { api } from "@/lib/api";
import { downloadReport } from "@/lib/report-html";
import type { AskResult, ChartSpec, Source } from "@/lib/types";

const TEMPLATES = [
  { title: "Overview", icon: LayoutGrid, text: "Give me an overview report of this data: the biggest groups, the top items, and the trend over time." },
  { title: "Performance", icon: BarChart3, text: "Write a performance report comparing the most important measures by category." },
  { title: "Monthly trend", icon: TrendingUp, text: "Make a monthly trend report with the main changes." },
];

export default function ReportPage() {
  const [sources, setSources] = useState<Source[] | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [question, setQuestion] = useState(TEMPLATES[0].text);
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [kinds, setKinds] = useState<Record<number, ChartSpec["type"]>>({});

  useEffect(() => {
    api<Source[]>("/api/sources").then(setSources).catch(() => setSources([]));
  }, []);

  async function generate(event: React.FormEvent) {
    event.preventDefault();
    if (question.trim().length < 3) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api<AskResult>("/api/report", {
        method: "POST",
        body: JSON.stringify({ question, source_ids: selected.length ? selected : null, as_report: true }),
      });
      setResult(next);
      setKinds({});
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
        title="Build a report"
        description="Describe the report you need. Meridian plans two to four views of your data, each with a chart and its table, and you can download the whole thing as a single HTML file."
      />
      <form onSubmit={generate} className="card mb-8 space-y-5 p-6">
        <div>
          <p className="field-label">1. Pick a starting point</p>
          <div className="mt-2 grid gap-2 sm:grid-cols-3">
            {TEMPLATES.map((item) => {
              const Icon = item.icon;
              const active = question === item.text;
              return (
                <button
                  key={item.title}
                  type="button"
                  onClick={() => setQuestion(item.text)}
                  aria-pressed={active}
                  className={`rounded-2xl border p-4 text-left transition ${
                    active ? "border-tide bg-tide/5 ring-4 ring-tide/10" : "border-line hover:border-tide/40"
                  }`}
                >
                  <Icon size={18} className="text-tide" />
                  <span className="mt-2 block text-sm font-semibold">{item.title}</span>
                  <span className="mt-1 block text-xs leading-5 text-muted">{item.text}</span>
                </button>
              );
            })}
          </div>
        </div>
        <label className="block">
          <span className="field-label">2. Describe the report in your own words</span>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={3}
            className="input resize-y leading-6"
            placeholder="For example: compare ad spend and conversions by campaign for September"
          />
        </label>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
          {sources ? <SourcePicker sources={sources} selected={selected} onChange={setSelected} /> : <span className="h-9 w-48 animate-pulse rounded-full bg-paper" />}
          <div className="flex flex-wrap gap-2">
            {result ? (
              <button type="button" onClick={() => downloadReport(result)} className="btn btn-secondary">
                <Download size={14} /> Download HTML
              </button>
            ) : null}
            <button type="submit" disabled={busy || question.trim().length < 3} className="btn btn-primary">
              {busy ? <Loader2 size={15} className="animate-spin" /> : <FileText size={15} />}
              {busy ? "Building report…" : "Generate report"}
            </button>
          </div>
        </div>
        {error ? <p className="rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</p> : null}
      </form>

      {busy ? (
        <div className="space-y-4" aria-live="polite">
          <div className="h-36 animate-pulse rounded-3xl bg-tide/15" />
          <div className="h-64 animate-pulse rounded-3xl bg-panel" />
          <p className="text-sm text-muted">Planning the views, running each query and writing the summary. This usually takes 10–30 seconds.</p>
        </div>
      ) : null}

      {result && !result.report && !busy ? (
        <div className="mb-8">
          <AnswerCard result={result} onAsk={(text) => setQuestion(text)} />
        </div>
      ) : null}

      {result?.report && !busy ? (
        <article className="space-y-6">
          <header className="rounded-3xl bg-tide px-6 py-8 text-white">
            <p className="text-xs tracking-[0.16em] uppercase text-white/70">Report</p>
            <h2 className="font-display mt-2 text-4xl">{result.report.title}</h2>
            <p className="mt-4 max-w-3xl text-sm leading-6 text-white/90">{result.report.summary}</p>
            {result.assumptions.length ? (
              <p className="mt-3 max-w-3xl text-xs leading-5 text-white/70">Assumed: {result.assumptions.join(" ")}</p>
            ) : null}
          </header>
          {sections.map((section, index) => {
            const chart = section.chart
              ? { ...section.chart, type: kinds[index] ?? section.chart.type }
              : null;
            return (
              <section key={section.title} className="card p-6">
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
