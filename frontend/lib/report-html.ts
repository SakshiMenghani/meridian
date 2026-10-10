import type { AskResult, ChartSpec } from "@/lib/types";

export function downloadReport(result: AskResult) {
  const report = result.report;
  const title = report?.title || "Meridian report";
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(title)}</title>
  <style>
    body { font-family: Georgia, serif; background: #f3efe6; color: #1c2430; margin: 0; }
    main { max-width: 860px; margin: 0 auto; padding: 40px 24px 80px; }
    h1 { font-size: 36px; margin: 0 0 12px; }
    h2 { font-size: 22px; margin: 36px 0 8px; }
    p, li { line-height: 1.55; }
    .meta { color: #5c6b7a; font-size: 14px; }
    .card { background: #fffdf8; border: 1px solid #e3dacb; border-radius: 16px; padding: 20px; margin-top: 16px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e3dacb; }
    .pie { display: flex; gap: 24px; align-items: center; flex-wrap: wrap; }
  </style>
</head>
<body>
  <main>
    <p class="meta">Meridian report</p>
    <h1>${escapeHtml(title)}</h1>
    <p>${escapeHtml(report?.summary || result.answer)}</p>
    <p class="meta">From ${(report?.sources_used || result.sources_used).join(", ")}</p>
    ${(report?.sections || fallbackSections(result)).map(sectionHtml).join("")}
  </main>
</body>
</html>`;
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.html`;
  link.click();
  URL.revokeObjectURL(url);
}

function fallbackSections(result: AskResult) {
  return [
    {
      title: "Result",
      body: result.answer,
      columns: result.columns,
      rows: result.rows,
      chart: result.chart,
    },
  ];
}

function sectionHtml(section: {
  title: string;
  body: string;
  columns: string[];
  rows: Record<string, unknown>[];
  chart: ChartSpec | null;
}) {
  const chart = section.chart ? chartHtml(section.chart, section.rows) : "";
  const head = section.columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("");
  const body = section.rows
    .slice(0, 20)
    .map((row) => `<tr>${section.columns.map((column) => `<td>${escapeHtml(String(row[column] ?? ""))}</td>`).join("")}</tr>`)
    .join("");
  return `<section class="card">
    <h2>${escapeHtml(section.title)}</h2>
    <p>${escapeHtml(section.body)}</p>
    ${chart}
    <table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>
  </section>`;
}

function chartHtml(spec: ChartSpec, rows: Record<string, unknown>[]) {
  const values = rows
    .map((row) => ({ label: String(row[spec.category] ?? ""), value: Number(row[spec.value] ?? 0) }))
    .filter((item) => Number.isFinite(item.value));
  if (!values.length) return "";
  const colors = ["#0e6e68", "#c45c26", "#2b6cb0", "#8a5a12", "#5c4d7a", "#1c7a4d"];
  if (spec.type === "pie") {
    const total = values.reduce((sum, item) => sum + Math.max(item.value, 0), 0) || 1;
    let angle = -Math.PI / 2;
    const slices = values.map((item, index) => {
      const share = Math.max(item.value, 0) / total;
      const start = angle;
      angle += share * Math.PI * 2;
      const large = share > 0.5 ? 1 : 0;
      const x1 = 110 + 80 * Math.cos(start);
      const y1 = 110 + 80 * Math.sin(start);
      const x2 = 110 + 80 * Math.cos(angle);
      const y2 = 110 + 80 * Math.sin(angle);
      return `<path d="M 110 110 L ${x1} ${y1} A 80 80 0 ${large} 1 ${x2} ${y2} Z" fill="${colors[index % colors.length]}"></path>`;
    });
    const legend = values
      .map((item, index) => `<li>${escapeHtml(item.label)} — ${item.value.toLocaleString()}</li>`)
      .join("");
    return `<div class="pie"><svg width="220" height="220" viewBox="0 0 220 220">${slices.join("")}</svg><ul>${legend}</ul></div>`;
  }
  const max = Math.max(...values.map((item) => item.value), 1);
  const bars = values
    .map((item, index) => {
      const width = Math.max(4, (320 * item.value) / max);
      const y = 16 + index * 28;
      return `<text x="120" y="${y + 12}" text-anchor="end" font-size="11">${escapeHtml(item.label.slice(0, 18))}</text>
        <rect x="128" y="${y}" width="${width}" height="16" rx="3" fill="${colors[index % colors.length]}"></rect>`;
    })
    .join("");
  return `<svg width="640" height="${Math.max(120, values.length * 28 + 20)}" viewBox="0 0 640 ${Math.max(120, values.length * 28 + 20)}">${bars}</svg>`;
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
