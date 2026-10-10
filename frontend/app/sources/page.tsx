"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { StatusPill } from "@/components/status-pill";
import { api } from "@/lib/api";
import { connectionSummary, originLabel, sourceLabel } from "@/lib/format";
import type { Source } from "@/lib/types";

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    const rows = await api<Source[]>("/api/sources");
    setSources(rows);
  }

  useEffect(() => {
    load().catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load sources."));
  }, []);

  async function toggle(source: Source) {
    setBusyId(source.id);
    setError(null);
    try {
      await api(`/api/sources/${source.id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: !source.enabled }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update the source.");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(source: Source) {
    if (!window.confirm(`Remove ${source.name}?`)) return;
    setBusyId(source.id);
    setError(null);
    try {
      await api(`/api/sources/${source.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove the source.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Connections"
        title="Data sources"
        description="Test a connection, browse its tables or collections, and turn a source off when the assistant should ignore it."
        action={
          <div className="flex gap-2">
            <Link href="/sources/marketing" className="rounded-full border border-line bg-panel px-4 py-2 text-sm font-semibold">
              Attach marketing
            </Link>
            <Link href="/transform" className="rounded-full border border-line bg-panel px-4 py-2 text-sm font-semibold">
              Upload a file
            </Link>
            <Link href="/sources/new" className="rounded-full bg-tide px-4 py-2 text-sm font-semibold text-white">
              Add database
            </Link>
          </div>
        }
      />
      {error ? <p className="mb-4 rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</p> : null}
      <div className="space-y-3">
        {sources.map((source) => (
          <article key={source.id} className="rounded-2xl border border-line bg-panel px-5 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <Link href={`/sources/${source.id}`} className="text-lg font-semibold hover:text-tide">
                    {source.name}
                  </Link>
                  <StatusPill status={source.status} />
                  <span className="rounded-full bg-paper px-2 py-1 text-xs font-semibold text-muted">
                    {originLabel(source.origin)}
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted">
                  {sourceLabel(source.source_type)} · {connectionSummary(source.config)}
                </p>
                {source.status_message ? <p className="mt-2 text-sm text-muted">{source.status_message}</p> : null}
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busyId === source.id}
                  onClick={() => toggle(source)}
                  className="rounded-full border border-line px-3 py-1.5 text-sm font-semibold"
                >
                  {source.enabled ? "Disable" : "Enable"}
                </button>
                <button
                  type="button"
                  disabled={busyId === source.id}
                  onClick={() => remove(source)}
                  className="rounded-full border border-line px-3 py-1.5 text-sm font-semibold text-bad"
                >
                  Remove
                </button>
              </div>
            </div>
          </article>
        ))}
        {sources.length === 0 && !error ? <p className="text-sm text-muted">Loading sources…</p> : null}
      </div>
    </div>
  );
}
