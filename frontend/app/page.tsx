"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { StatusPill } from "@/components/status-pill";
import { api } from "@/lib/api";
import { formatWhen, sourceLabel } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Dashboard>("/api/dashboard")
      .then(setData)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "The API is not reachable."));
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="Overview"
        title="Connected sources"
        description="Meridian keeps connection secrets on the server and reads the Northline Outfitters sample through read-only roles."
        action={
          <div className="flex flex-wrap gap-2">
            <Link href="/sources/marketing" className="rounded-full border border-line bg-panel px-4 py-2 text-sm font-semibold">
              Attach marketing
            </Link>
            <Link href="/report" className="rounded-full bg-tide px-4 py-2 text-sm font-semibold text-white">
              Generate a report
            </Link>
          </div>
        }
      />
      {error ? <p className="rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</p> : null}
      {!data && !error ? <p className="text-sm text-muted">Loading workspace…</p> : null}
      {data ? (
        <div className="space-y-8">
          <section className="grid gap-4 lg:grid-cols-2">
            <Link href="/sources/marketing" className="rounded-3xl bg-tide px-6 py-6 text-white">
              <p className="text-xs tracking-[0.16em] uppercase text-white/70">Marketing</p>
              <h2 className="font-display mt-2 text-3xl">Attach Analytics or Ads</h2>
              <p className="mt-3 text-sm leading-6 text-white/85">
                Google Analytics sample traffic is ready. Ask about channels, then download a pie chart.
              </p>
            </Link>
            <Link href="/report" className="rounded-3xl border border-line bg-panel px-6 py-6">
              <p className="text-xs tracking-[0.16em] uppercase text-muted">Reports</p>
              <h2 className="font-display mt-2 text-3xl">Build a briefing</h2>
              <p className="mt-3 text-sm leading-6 text-muted">
                Request a weekly mix, ranking, and trend. Switch pie, bar, or line, then download HTML.
              </p>
            </Link>
          </section>
          <section className="grid gap-3 sm:grid-cols-4">
            <Metric label="Sources" value={data.counts.total} />
            <Metric label="Healthy" value={data.counts.healthy} />
            <Metric label="Enabled" value={data.counts.enabled} />
            <Metric label="Need attention" value={data.counts.attention} />
          </section>
          <section className="rounded-2xl border border-line bg-panel">
            <header className="border-b border-line px-5 py-4">
              <h2 className="font-display text-2xl">Source status</h2>
            </header>
            <ul>
              {data.sources.map((source) => (
                <li key={source.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4 last:border-b-0">
                  <div>
                    <Link href={`/sources/${source.id}`} className="font-semibold hover:text-tide">
                      {source.name}
                    </Link>
                    <p className="text-sm text-muted">
                      {sourceLabel(source.source_type)} · {source.enabled ? "Enabled" : "Disabled"} · checked {formatWhen(source.last_checked_at)}
                    </p>
                  </div>
                  <StatusPill status={source.status} />
                </li>
              ))}
              {data.sources.length === 0 ? <li className="px-5 py-6 text-sm text-muted">No sources yet.</li> : null}
            </ul>
          </section>
          <div className="grid gap-6 lg:grid-cols-2">
            <section className="rounded-2xl border border-line bg-panel">
              <header className="border-b border-line px-5 py-4">
                <h2 className="font-display text-2xl">Recent activity</h2>
              </header>
              <ul>
                {data.activity.map((item) => (
                  <li key={item.id} className="border-b border-line px-5 py-3 last:border-b-0">
                    <p className="text-sm">
                      <span className="font-semibold">{item.action}</span>
                      {item.source_name ? ` · ${item.source_name}` : ""}
                    </p>
                    <p className="text-sm text-muted">{item.detail}</p>
                    <p className="text-xs text-muted">{formatWhen(item.created_at)}</p>
                  </li>
                ))}
                {data.activity.length === 0 ? <li className="px-5 py-6 text-sm text-muted">No activity yet.</li> : null}
              </ul>
            </section>
            <section className="rounded-2xl border border-line bg-panel">
              <header className="border-b border-line px-5 py-4">
                <h2 className="font-display text-2xl">Confirmed join keys</h2>
              </header>
              <ul>
                {data.mappings.map((mapping) => (
                  <li key={mapping.id} className="border-b border-line px-5 py-3 last:border-b-0">
                    <p className="text-sm font-semibold">
                      {mapping.left_object}.{mapping.left_field}
                      <span className="font-normal text-muted"> = </span>
                      {mapping.right_object}.{mapping.right_field}
                    </p>
                    <p className="text-sm text-muted">{mapping.description}</p>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-line bg-panel px-4 py-4">
      <p className="text-xs tracking-wide text-muted uppercase">{label}</p>
      <p className="font-display mt-2 text-4xl">{value}</p>
    </div>
  );
}
