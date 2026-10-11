"use client";

import { KeyRound, Plug, Sparkles, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { api, apiBase } from "@/lib/api";
import type { McpRegistry, Meta } from "@/lib/types";

export default function SettingsPage() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [mcp, setMcp] = useState<McpRegistry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api<Meta>("/api/meta"), api<McpRegistry>("/api/mcp/tools")])
      .then(([nextMeta, nextMcp]) => {
        setMeta(nextMeta);
        setMcp(nextMcp);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load settings."));
  }, []);

  return (
    <div className="max-w-3xl">
      <PageHeader eyebrow="Configuration" title="Settings" description="How the assistant is set up on this machine." />
      {error ? <p className="rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</p> : null}
      {!meta && !error ? <div className="h-40 animate-pulse rounded-2xl bg-panel" /> : null}
      {meta ? (
        <div className="space-y-6">
          <section className="card p-6">
            <div className="flex items-start gap-4">
              <span
                className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${
                  meta.openai_configured ? "bg-tide/10 text-tide" : "bg-warn/10 text-warn"
                }`}
              >
                {meta.openai_configured ? <Sparkles size={20} /> : <WifiOff size={20} />}
              </span>
              <div className="min-w-0">
                <h2 className="font-display text-2xl">AI assistant</h2>
                <p className="mt-1 text-sm text-muted">
                  {meta.openai_configured
                    ? `On. ${meta.openai_model} plans each query, and every query is checked to be read-only before it runs.`
                    : "Offline. Simple totals, rankings and reports work. Open-ended questions and questions across sources need an OpenAI key."}
                </p>
                {!meta.openai_configured ? (
                  <div className="mt-4 rounded-xl bg-paper p-4 text-sm">
                    <p className="flex items-center gap-2 font-semibold">
                      <KeyRound size={14} className="text-warn" /> Turn it on
                    </p>
                    <ol className="mt-2 list-decimal space-y-1 pl-5 text-muted">
                      <li>
                        Open the <code className="rounded bg-panel px-1 py-0.5 text-xs text-ink">.env</code> file next to{" "}
                        <code className="rounded bg-panel px-1 py-0.5 text-xs text-ink">docker-compose.yml</code>.
                      </li>
                      <li>
                        Add <code className="rounded bg-panel px-1 py-0.5 text-xs text-ink">OPENAI_API_KEY=…</code> with your key.
                      </li>
                      <li>Restart the API.</li>
                    </ol>
                  </div>
                ) : null}
              </div>
            </div>
          </section>

          <section className="card">
            <h2 className="font-display border-b border-line px-6 py-4 text-2xl">Workspace</h2>
            <dl className="divide-y divide-line">
              <Row label="Version" value={`${meta.app_name} ${meta.version}`} />
              <Row label="Connectors" value={meta.supported_sources.join(", ")} />
              <Row label="Upload limit" value={`${meta.upload_limit_mb} MB per file`} />
              <Row label="Sample data" value={meta.seed_demo_data ? "Loaded on start" : "Off"} />
              <Row label="Offline matching model" value={meta.embedding_model} />
              <Row label="API address" value={apiBase} />
            </dl>
          </section>

          {mcp ? (
            <details className="card group">
              <summary className="flex cursor-pointer items-center gap-3 px-6 py-4 marker:content-none">
                <Plug size={18} className="text-tide" />
                <span className="flex-1">
                  <span className="font-display block text-2xl">Connectors</span>
                  <span className="block text-sm text-muted">
                    {mcp.servers.filter((server) => server.enabled).length} of {mcp.servers.length} connected · {mcp.tools.length} read-only
                    tools. For technical users.
                  </span>
                </span>
                <span className="text-sm font-semibold text-tide group-open:hidden">Show</span>
                <span className="hidden text-sm font-semibold text-tide group-open:inline">Hide</span>
              </summary>
              <div className="space-y-4 border-t border-line px-6 py-5">
                <ul className="space-y-2">
                  {mcp.servers.map((server) => (
                    <li key={`${server.name}-${server.transport}`} className="flex items-start gap-3 rounded-xl bg-paper px-4 py-3">
                      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${server.enabled ? "bg-good" : "bg-muted/40"}`} />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold">
                          {server.name}
                          <span className="ml-2 font-normal text-muted">
                            {server.transport}
                            {server.data_origin ? ` · ${server.data_origin}` : ""}
                            {server.enabled ? "" : " · not connected"}
                          </span>
                        </p>
                        {server.note ? <p className="mt-0.5 text-sm text-muted">{server.note}</p> : null}
                      </div>
                    </li>
                  ))}
                </ul>
                <ul className="divide-y divide-line rounded-xl border border-line">
                  {mcp.tools.map((tool) => (
                    <li key={tool.name} className="px-4 py-3">
                      <p className="font-mono text-xs font-semibold">{tool.name}</p>
                      <p className="mt-0.5 text-sm text-muted">{tool.description}</p>
                    </li>
                  ))}
                </ul>
              </div>
            </details>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 px-6 py-3 sm:grid-cols-[180px_1fr]">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="text-sm font-medium break-words">{value}</dd>
    </div>
  );
}
