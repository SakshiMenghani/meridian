"use client";

import { AlertTriangle, BarChart3, ChevronDown, Code2, Download, HelpCircle, Lightbulb, Sparkles, Table2 } from "lucide-react";
import { useState } from "react";
import { DataTable } from "@/components/data-table";
import { ResultChart } from "@/components/result-chart";
import { downloadReport } from "@/lib/report-html";
import type { AskResult, ChartSpec, ReportSection } from "@/lib/types";

type View = "chart" | "table" | "sql";

export function AnswerCard({ result, onAsk }: { result: AskResult; onAsk?: (question: string) => void }) {
  const sections = sectionsOf(result);
  const [active, setActive] = useState(0);
  const section = sections[active];
  const [view, setView] = useState<View>(section?.chart ? "chart" : "table");
  const [kinds, setKinds] = useState<Record<number, ChartSpec["type"]>>({});
  const [showSteps, setShowSteps] = useState(false);
  const clarifying = result.status === "needs_clarification";
  const failed = result.status === "error";

  return (
    <div
      className={`max-w-3xl rounded-3xl border bg-panel p-5 shadow-[0_1px_0_rgba(28,36,48,0.04),0_12px_32px_-20px_rgba(28,36,48,0.35)] ${
        clarifying ? "border-warn/40" : failed ? "border-bad/40" : "border-line"
      }`}
    >
      <div className="flex items-start gap-3">
        <span
          className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
            clarifying ? "bg-warn/10 text-warn" : failed ? "bg-bad/10 text-bad" : "bg-tide/10 text-tide"
          }`}
        >
          {clarifying ? <HelpCircle size={16} /> : failed ? <AlertTriangle size={16} /> : <Sparkles size={16} />}
        </span>
        <div className="min-w-0 flex-1">
          {clarifying ? <p className="text-xs font-semibold tracking-wide text-warn uppercase">Needs your choice</p> : null}
          <p className="text-[15px] leading-7 whitespace-pre-wrap text-ink">{result.answer}</p>
          {result.points.length > 0 ? (
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {result.points.map((point) => (
                <li key={point} className="rounded-xl bg-paper px-3 py-2 text-sm text-ink">
                  {point}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>

      {result.options.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2 pl-11">
          {result.options.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => onAsk?.(option)}
              className="rounded-full border border-tide/40 bg-tide/5 px-3 py-1.5 text-left text-sm font-medium text-tide-deep hover:bg-tide hover:text-white"
            >
              {option}
            </button>
          ))}
        </div>
      ) : null}

      {result.assumptions.length > 0 && !clarifying ? (
        <div className="mt-4 flex gap-2 rounded-2xl border border-dashed border-line px-3 py-2 text-xs leading-5 text-muted">
          <Lightbulb size={14} className="mt-0.5 shrink-0 text-warn" />
          <p>
            <span className="font-semibold text-ink">Assumed: </span>
            {result.assumptions.join(" ")}
          </p>
        </div>
      ) : null}

      {section ? (
        <div className="mt-5">
          {sections.length > 1 ? (
            <div className="mb-3 flex flex-wrap gap-1 rounded-full bg-paper p-1">
              {sections.map((item, index) => (
                <button
                  key={`${item.title}-${index}`}
                  type="button"
                  onClick={() => {
                    setActive(index);
                    setView(item.chart ? "chart" : "table");
                  }}
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    index === active ? "bg-panel text-ink shadow-sm" : "text-muted hover:text-ink"
                  }`}
                >
                  {item.title}
                </button>
              ))}
            </div>
          ) : null}
          {section.body && sections.length > 1 ? <p className="mb-3 text-sm text-muted">{section.body}</p> : null}
          <div className="flex flex-wrap items-center gap-2">
            {section.chart ? <Toggle icon={<BarChart3 size={14} />} label="Chart" active={view === "chart"} onClick={() => setView("chart")} /> : null}
            <Toggle icon={<Table2 size={14} />} label={`Table · ${section.rows.length}`} active={view === "table"} onClick={() => setView("table")} />
            {section.sql ? <Toggle icon={<Code2 size={14} />} label="SQL" active={view === "sql"} onClick={() => setView("sql")} /> : null}
            {view === "chart" && section.chart ? (
              <div className="ml-auto flex gap-1 rounded-full bg-paper p-1">
                {(["bar", "line", "pie"] as const).map((kind) => (
                  <button
                    key={kind}
                    type="button"
                    onClick={() => setKinds((current) => ({ ...current, [active]: kind }))}
                    className={`rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${
                      (kinds[active] ?? section.chart!.type) === kind ? "bg-panel text-ink shadow-sm" : "text-muted"
                    }`}
                  >
                    {kind}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <div className="mt-3">
            {view === "chart" && section.chart ? (
              <ResultChart spec={{ ...section.chart, type: kinds[active] ?? section.chart.type }} rows={section.rows} />
            ) : null}
            {view === "table" ? <DataTable columns={section.columns} rows={section.rows} /> : null}
            {view === "sql" && section.sql ? (
              <pre className="overflow-x-auto rounded-2xl bg-sidebar p-4 text-xs leading-5 text-mist">{section.sql}</pre>
            ) : null}
          </div>
          {result.truncated && active === 0 ? <p className="mt-2 text-xs text-muted">Showing the first 200 rows.</p> : null}
        </div>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-line pt-3 text-xs text-muted">
        <button type="button" onClick={() => setShowSteps((value) => !value)} className="flex items-center gap-1 font-semibold text-ink">
          <ChevronDown size={14} className={`transition ${showSteps ? "rotate-180" : ""}`} />
          How I answered
        </button>
        <span>From {result.sources_used.length > 3 ? `${result.sources_used.length} sources` : result.sources_used.join(", ")}</span>
        {sections.length > 0 ? (
          <button
            type="button"
            onClick={() => downloadReport(result)}
            className="ml-auto flex items-center gap-1 rounded-full border border-line px-3 py-1 font-semibold text-ink hover:border-tide"
          >
            <Download size={13} /> Download
          </button>
        ) : null}
      </div>
      {showSteps ? (
        <ol className="mt-3 space-y-2 border-l-2 border-line pl-4">
          {result.steps.map((step, index) => (
            <li key={`${step.name}-${index}`} className="relative text-xs leading-5">
              <span
                className={`absolute top-1.5 -left-[21px] h-2.5 w-2.5 rounded-full ${step.status === "ok" ? "bg-tide" : "bg-bad"}`}
              />
              <span className="font-semibold text-ink">{step.name}. </span>
              <span className={step.status === "ok" ? "text-muted" : "text-bad"}>{step.detail}</span>
            </li>
          ))}
          {result.note ? <li className="text-xs leading-5 text-muted">{result.note}</li> : null}
        </ol>
      ) : null}
    </div>
  );
}

function sectionsOf(result: AskResult): ReportSection[] {
  if (result.report?.sections.length) return result.report.sections;
  if (result.columns.length === 0) return [];
  return [
    {
      title: result.chart?.title ?? "Result",
      body: "",
      columns: result.columns,
      rows: result.rows,
      chart: result.chart,
      sql: result.query,
    },
  ];
}

function Toggle({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold ${
        active ? "bg-ink text-white" : "bg-paper text-ink hover:bg-line"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
