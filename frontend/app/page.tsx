"use client";

import {
  AlertTriangle,
  ArrowRight,
  Check,
  FileUp,
  Link2,
  MessageSquareText,
  Pencil,
  PlugZap,
  Plus,
  Power,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { SourceIcon } from "@/components/source-icon";
import { api } from "@/lib/api";
import { formatWhen, sourceLabel } from "@/lib/format";
import type { Activity, Dashboard } from "@/lib/types";

const ACTIVITY: Record<string, { label: string; icon: LucideIcon }> = {
  ask: { label: "Question asked", icon: MessageSquareText },
  test: { label: "Connection tested", icon: PlugZap },
  update: { label: "Source updated", icon: Pencil },
  upload: { label: "File uploaded", icon: FileUp },
  import: { label: "File imported", icon: FileUp },
  delete: { label: "Source removed", icon: Trash2 },
  link: { label: "Link confirmed", icon: Link2 },
  unlink: { label: "Link removed", icon: Link2 },
};

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Dashboard>("/api/dashboard")
      .then(setData)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "The API is not reachable."));
  }, []);

  const asked = Boolean(data?.activity.some((item) => item.action === "ask"));
  const steps = data
    ? [
        {
          done: data.counts.total > 0,
          title: "Connect your data",
          text:
            data.counts.total > 0
              ? `${data.counts.total} source${data.counts.total === 1 ? "" : "s"} connected.`
              : "PostgreSQL, MongoDB, Excel or CSV, Google Analytics and Google Ads.",
          href: data.counts.total > 0 ? "/sources" : "/sources/new",
          cta: data.counts.total > 0 ? "Manage sources" : "Connect a source",
        },
        {
          done: data.mappings.length > 0,
          title: "Link sources together",
          text:
            data.mappings.length > 0
              ? `${data.mappings.length} confirmed link${data.mappings.length === 1 ? "" : "s"} let questions combine sources.`
              : "Confirm which columns match, such as a customer ID in two systems.",
          href: "/links",
          cta: data.mappings.length > 0 ? "Review links" : "Find links",
        },
        {
          done: asked,
          title: "Ask and share",
          text: "Ask in plain words, switch charts, and download a report.",
          href: "/chat",
          cta: "Ask a question",
        },
      ]
    : [];
  const next = steps.findIndex((step) => !step.done);
  const highlight = next === -1 ? 2 : next;
  const broken = data?.sources.filter((source) => source.enabled && source.status === "error") ?? [];
  const activity = (data?.activity ?? [])
    .filter((item) => item.status === "error" || (ACTIVITY[item.action] && item.action !== "test"))
    .slice(0, 6);

  return (
    <div>
      <PageHeader
        eyebrow="Overview"
        title="Your data workspace"
        description="Connect your data, link what belongs together, then ask questions in plain words. Passwords stay encrypted on this machine and every source is read-only."
        action={
          <Link href="/chat" className="btn btn-primary">
            <MessageSquareText size={15} /> Ask a question
          </Link>
        }
      />
      {error ? (
        <div className="card flex items-start gap-3 border-bad/30 px-5 py-4 text-sm">
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-bad" />
          <p>
            <span className="font-semibold text-bad">Can’t reach the Meridian API.</span>{" "}
            <span className="text-muted">Make sure the backend is running, then refresh. ({error})</span>
          </p>
        </div>
      ) : null}
      {!data && !error ? (
        <div className="grid gap-3 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-44 animate-pulse rounded-3xl bg-panel" />
          ))}
        </div>
      ) : null}
      {data ? (
        <div className="space-y-8">
          {broken.length ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-bad/30 bg-bad/5 px-5 py-4">
              <p className="flex items-start gap-2 text-sm">
                <AlertTriangle size={16} className="mt-0.5 shrink-0 text-bad" />
                <span>
                  <span className="font-semibold text-bad">
                    {broken.length === 1 ? `${broken[0].name} can’t be reached.` : `${broken.length} sources can’t be reached.`}
                  </span>{" "}
                  <span className="text-muted">Questions skip it until the connection is fixed.</span>
                </span>
              </p>
              <Link href={broken.length === 1 ? `/sources/${broken[0].id}?edit=1` : "/sources"} className="btn btn-sm btn-danger">
                Fix connection
              </Link>
            </div>
          ) : null}

          <section className="grid gap-3 lg:grid-cols-3">
            {steps.map((step, index) => (
              <Step key={step.title} number={index + 1} {...step} primary={index === highlight} />
            ))}
          </section>

          <section className="card">
            <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
              <div>
                <h2 className="font-display text-2xl">Sources</h2>
                <p className="text-sm text-muted">
                  {data.counts.enabled} of {data.counts.total} used in answers
                  {data.counts.attention ? ` · ${data.counts.attention} need attention` : data.counts.total ? " · all connected" : ""}
                </p>
              </div>
              <div className="flex gap-2">
                <Link href="/sources" className="btn btn-ghost btn-sm">
                  Manage
                </Link>
                <Link href="/sources/new" className="btn btn-secondary btn-sm">
                  <Plus size={13} /> Add
                </Link>
              </div>
            </header>
            {data.sources.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-muted">
                No sources yet.{" "}
                <Link href="/sources/new" className="font-semibold text-tide">
                  Connect your first one
                </Link>
                .
              </p>
            ) : (
              <ul className="grid gap-2 p-3 sm:grid-cols-2 xl:grid-cols-3">
                {data.sources.map((source) => (
                  <li key={source.id}>
                    <Link href={`/sources/${source.id}`} className="flex h-full items-center gap-3 rounded-xl px-3 py-3 transition hover:bg-paper">
                      <SourceIcon type={source.source_type} />
                      <span className={`min-w-0 flex-1 ${source.enabled ? "" : "opacity-55"}`}>
                        <span className="block truncate text-sm font-semibold" title={source.name}>
                          {source.name}
                        </span>
                        <span className="block truncate text-xs text-muted">
                          {sourceLabel(source.source_type)}
                          {source.enabled ? "" : " · Off"}
                        </span>
                      </span>
                      <StatusDot status={source.status} enabled={source.enabled} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="card">
              <header className="border-b border-line px-5 py-4">
                <h2 className="font-display text-2xl">Recent activity</h2>
              </header>
              <ul>
                {activity.map((item) => (
                  <ActivityRow key={item.id} item={item} />
                ))}
                {activity.length === 0 ? <li className="px-5 py-6 text-sm text-muted">Nothing yet. Ask your first question.</li> : null}
              </ul>
            </section>
            <section className="card">
              <header className="flex items-center justify-between border-b border-line px-5 py-4">
                <h2 className="font-display text-2xl">Confirmed links</h2>
                <Link href="/links" className="btn btn-ghost btn-sm">
                  Manage
                </Link>
              </header>
              <ul>
                {data.mappings.slice(0, 6).map((mapping) => (
                  <li key={mapping.id} className="flex items-center gap-2 border-b border-line px-5 py-3 text-sm last:border-b-0">
                    <Link2 size={14} className="shrink-0 text-tide" />
                    <span className="min-w-0 truncate">
                      <span className="font-semibold">{mapping.left_object}</span>
                      <span className="text-muted">.{mapping.left_field}</span>
                      <span className="px-1.5 text-muted">=</span>
                      <span className="font-semibold">{mapping.right_object}</span>
                      <span className="text-muted">.{mapping.right_field}</span>
                    </span>
                  </li>
                ))}
                {data.mappings.length > 6 ? (
                  <li className="px-5 py-3 text-sm">
                    <Link href="/links" className="font-semibold text-tide">
                      See all {data.mappings.length} links
                    </Link>
                  </li>
                ) : null}
                {data.mappings.length === 0 ? (
                  <li className="px-5 py-6 text-sm text-muted">
                    No links yet.{" "}
                    <Link href="/links" className="font-semibold text-tide">
                      See suggestions
                    </Link>
                  </li>
                ) : null}
              </ul>
            </section>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function StatusDot({ status, enabled }: { status: string; enabled: boolean }) {
  const tone = !enabled ? "bg-muted/40" : status === "healthy" ? "bg-good" : status === "error" ? "bg-bad" : "bg-warn";
  const label = !enabled ? "Off" : status === "healthy" ? "Connected" : status === "error" ? "Needs attention" : "Not checked";
  return (
    <span className="flex items-center" title={label}>
      <span className={`h-2.5 w-2.5 rounded-full ${tone}`} />
      <span className="sr-only">{label}</span>
    </span>
  );
}

function ActivityRow({ item }: { item: Activity }) {
  const kind = ACTIVITY[item.action] ?? { label: item.action, icon: Power };
  const Icon = kind.icon;
  const failed = item.status === "error";
  return (
    <li className="flex gap-3 border-b border-line px-5 py-3 last:border-b-0">
      <span
        className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${failed ? "bg-bad/10 text-bad" : "bg-tide/10 text-tide"}`}
      >
        <Icon size={13} />
      </span>
      <div className="min-w-0">
        <p className="text-sm">
          <span className="font-semibold">{failed ? `${kind.label} · failed` : kind.label}</span>
          {item.source_name ? <span className="text-muted"> · {item.source_name}</span> : null}
        </p>
        <p className="truncate text-sm text-muted" title={item.detail}>
          {item.detail}
        </p>
        <p className="text-xs text-muted/80">{formatWhen(item.created_at)}</p>
      </div>
    </li>
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
      className={`group flex flex-col rounded-3xl border px-5 py-5 transition hover:-translate-y-px ${
        primary ? "border-tide bg-tide text-white shadow-[0_18px_40px_-24px_rgba(14,110,104,0.9)]" : "border-line bg-panel hover:border-tide/50"
      }`}
    >
      <div className="flex items-center justify-between">
        <span
          className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${
            done ? (primary ? "bg-white text-tide" : "bg-good text-white") : primary ? "bg-white text-tide" : "bg-paper text-ink"
          }`}
        >
          {done ? <Check size={15} strokeWidth={3} /> : number}
        </span>
        <span className={`text-xs font-semibold ${primary ? "text-white/75" : done ? "text-good" : "text-muted"}`}>
          {done ? "Done" : primary ? "Next step" : `Step ${number}`}
        </span>
      </div>
      <h2 className="font-display mt-4 text-2xl">{title}</h2>
      <p className={`mt-2 flex-1 text-sm leading-6 ${primary ? "text-white/85" : "text-muted"}`}>{text}</p>
      <span className={`mt-4 inline-flex items-center gap-1 text-sm font-semibold ${primary ? "text-white" : "text-tide"}`}>
        {cta} <ArrowRight size={14} className="transition group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}
