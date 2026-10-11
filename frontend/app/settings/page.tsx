"use client";

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
    <div>
      <PageHeader
        eyebrow="Configuration"
        title="Settings"
        description="Environment flags plus the in-process MCP tools the assistant is allowed to call."
      />
      {error ? <p className="text-sm text-bad">{error}</p> : null}
      {meta ? (
        <dl className="max-w-xl divide-y divide-line rounded-2xl border border-line bg-panel">
          <Row label="Application" value={`${meta.app_name} ${meta.version}`} />
          <Row label="Phase" value={meta.phase} />
          <Row label="API" value={apiBase} />
          <Row label="Demo seed" value={meta.seed_demo_data ? "On" : "Off"} />
          <Row
            label="OpenAI key"
            value={meta.openai_configured ? "Present" : "Not configured. Set OPENAI_API_KEY in the .env file next to docker-compose.yml, then restart the API."}
          />
          <Row
            label="Question planner"
            value={meta.openai_configured ? `${meta.openai_model} plans the SQL; every query is checked before it runs.` : "Offline planner for simple questions."}
          />
          <Row label="Upload limit" value={`${meta.upload_limit_mb} MB`} />
          <Row label="Connectors" value={meta.supported_sources.join(", ")} />
          <Row label="Text-to-SQL embeddings" value={meta.embedding_model} />
        </dl>
      ) : null}
      {mcp ? (
        <div className="mt-8 space-y-4">
          <h2 className="font-display text-2xl">MCP registry</h2>
          <ul className="space-y-2">
            {mcp.servers.map((server) => (
              <li key={`${server.name}-${server.transport}`} className="rounded-2xl border border-line bg-panel px-5 py-3">
                <p className="text-sm font-semibold">
                  {server.name}
                  <span className="ml-2 font-normal text-muted">
                    {server.transport}
                    {server.data_origin ? ` · ${server.data_origin}` : ""}
                    {server.enabled ? "" : " · not connected"}
                  </span>
                </p>
                {server.note ? <p className="mt-1 text-sm text-muted">{server.note}</p> : null}
              </li>
            ))}
          </ul>
          <ul className="divide-y divide-line rounded-2xl border border-line bg-panel">
            {mcp.tools.map((tool) => (
              <li key={tool.name} className="px-5 py-3">
                <p className="text-sm font-semibold">{tool.name}</p>
                <p className="text-sm text-muted">{tool.description}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 px-5 py-3 sm:grid-cols-[160px_1fr]">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  );
}
