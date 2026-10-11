"use client";

import { ArrowRight, Check } from "lucide-react";
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
        title="Your data workspace"
        description="Connect any database, spreadsheet, or marketing account, link what belongs together, then ask questions in plain words. Passwords stay encrypted on this machine and every source is read-only."
        action={
          <div className="flex flex-wrap gap-2">
            <Link href="/sources/new" className="rounded-full border border-line bg-panel px-4 py-2 text-sm font-semibold">
              Connect a source
            </Link>
            <Link href="/chat" className="rounded-full bg-tide px-4 py-2 text-sm font-semibold text-white">
              Ask a question
            </Link>
          </div>
        }
      />
      {error ? <p className="rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</p> : null}
      {!data && !error ? <p className="text-sm text-muted">Loading workspace…</p> : null}
      {data ? (
        <div className="space-y-8">
          <section className="grid gap-3 lg:grid-cols-3">
            <Step
              number={1}
              done={data.counts.total > 0}
              title="Connect your data"
              text={
                data.counts.total > 0
                  ? `${data.counts.total} sources connected, ${data.counts.healthy} healthy.`
                  : "PostgreSQL, MongoDB, Excel or CSV, Google Analytics, and Google Ads."
              }
              href="/sources"
              cta={data.counts.total > 0 ? "Manage sources" : "Connect a source"}
            />
            <Step
              number={2}
              done={data.mappings.length > 0}
              title="Link sources together"
              text={
                data.mappings.length > 0
                  ? `${data.mappings.length} confirmed links let questions combine sources.`
                  : "Confirm which columns match, such as a customer ID in two systems."
              }
              href="/links"
              cta={data.mappings.length > 0 ? "Review links" : "Find links"}
            />
            <Step
              number={3}
              done={false}
              title="Ask and share"
              text="Ask in plain words, switch charts, and download a report."
              href="/chat"
              cta="Open Ask"
              primary
            />
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
              <header className="flex items-center justify-between border-b border-line px-5 py-4">
                <h2 className="font-display text-2xl">Confirmed links</h2>
                <Link href="/links" className="text-sm font-semibold text-tide">
                  Manage links
                </Link>
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
                {data.mappings.length === 0 ? <li className="px-5 py-6 text-sm text-muted">No links yet.</li> : null}
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

function Step({
  number,
  done,
  title,
  text,
  href,
  cta,
  primary,
}: {
  number: number;
  done: boolean;
  title: string;
  text: string;
  href: string;
  cta: string;
  primary?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`group flex flex-col rounded-3xl border px-5 py-5 transition ${
        primary ? "border-tide bg-tide text-white" : "border-line bg-panel hover:border-tide/50"
      }`}
    >
      <span
        className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${
          done ? "bg-good text-white" : primary ? "bg-white text-tide" : "bg-paper text-ink"
        }`}
      >
        {done ? <Check size={15} strokeWidth={3} /> : number}
      </span>
      <h2 className="font-display mt-4 text-2xl">{title}</h2>
      <p className={`mt-2 flex-1 text-sm leading-6 ${primary ? "text-white/85" : "text-muted"}`}>{text}</p>
      <span className={`mt-4 inline-flex items-center gap-1 text-sm font-semibold ${primary ? "text-white" : "text-tide"}`}>
        {cta} <ArrowRight size={14} className="transition group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}
