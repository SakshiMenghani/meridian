"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { SourceIcon } from "@/components/source-icon";
import { StatusPill } from "@/components/status-pill";
import { Switch } from "@/components/switch";
import { api } from "@/lib/api";
import { connectionSummary, formatWhen, originLabel, sourceLabel } from "@/lib/format";
import type { Source } from "@/lib/types";

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    setSources(await api<Source[]>("/api/sources"));
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
    const detail =
      source.source_type === "spreadsheet"
        ? "The uploaded copy of the file is deleted from this machine."
        : "Nothing changes in the original system; Meridian just stops reading it.";
    if (!window.confirm(`Remove "${source.name}" from Meridian? ${detail}`)) return;
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

  const attention = (sources ?? []).filter((source) => source.enabled && source.status === "error").length;

  return (
    <div>
      <PageHeader
        eyebrow="Your data"
        title="Data sources"
        description="Everything Meridian can read. Switch a source off to leave it out of answers without deleting it."
        action={
          <Link href="/sources/new" className="btn btn-primary">
            <Plus size={16} /> Add a source
          </Link>
        }
      />
      {error ? <p className="mb-4 rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</p> : null}
      {sources && sources.length > 0 ? (
        <p className="mb-3 text-sm text-muted">
          {sources.length} source{sources.length === 1 ? "" : "s"} · {sources.filter((source) => source.enabled).length} used in answers
          {attention ? <span className="font-semibold text-bad"> · {attention} need attention</span> : null}
        </p>
      ) : null}

      {sources === null && !error ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-[84px] animate-pulse rounded-2xl bg-panel" />
          ))}
        </div>
      ) : null}

      {sources?.length === 0 ? (
        <div className="card px-6 py-12 text-center">
          <p className="font-display text-2xl">No sources yet</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            Connect PostgreSQL or MongoDB, upload a CSV or Excel file, or attach Google Analytics and Google Ads.
          </p>
          <Link href="/sources/new" className="btn btn-primary mt-5">
            <Plus size={16} /> Add your first source
          </Link>
        </div>
      ) : null}

      {sources?.length ? (
      <ul className="card divide-y divide-line overflow-hidden">
        {sources.map((source) => (
          <li
            key={source.id}
            className={`flex flex-wrap items-center gap-4 px-5 py-4 transition hover:bg-paper/40 ${source.enabled ? "" : "bg-paper/30"}`}
          >
            <Link href={`/sources/${source.id}`} className={`flex min-w-0 flex-1 items-center gap-4 ${source.enabled ? "" : "opacity-60"}`}>
              <SourceIcon type={source.source_type} size="lg" />
              <span className="min-w-0">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="truncate font-semibold hover:text-tide">{source.name}</span>
                  <StatusPill status={source.status} enabled={source.enabled} />
                  {source.origin === "sample" ? (
                    <span className="rounded-full bg-paper px-2 py-0.5 text-[11px] font-semibold text-muted">{originLabel(source.origin)} data</span>
                  ) : null}
                </span>
                <span className="mt-0.5 block truncate text-sm text-muted">
                  {sourceLabel(source.source_type)} · {connectionSummary(source.config)}
                </span>
                {source.status === "error" && source.status_message ? (
                  <span className="mt-1 block text-sm text-bad">{source.status_message}</span>
                ) : (
                  <span className="mt-0.5 block text-xs text-muted/80">Checked {formatWhen(source.last_checked_at)}</span>
                )}
              </span>
            </Link>
            <div className="flex items-center gap-1">
              <label className="mr-2 flex items-center gap-2 text-xs text-muted">
                <span className="hidden lg:inline">Use in answers</span>
                <Switch
                  checked={source.enabled}
                  disabled={busyId === source.id}
                  onChange={() => toggle(source)}
                  label={source.enabled ? `Stop using ${source.name} in answers` : `Use ${source.name} in answers`}
                />
              </label>
              <Link href={`/sources/${source.id}?edit=1`} className="btn btn-ghost btn-sm" aria-label={`Edit ${source.name}`} title="Edit">
                <Pencil size={14} /> <span className="hidden sm:inline">Edit</span>
              </Link>
              <button
                type="button"
                disabled={busyId === source.id}
                onClick={() => remove(source)}
                className="btn btn-ghost btn-sm hover:!bg-bad/5 hover:!text-bad"
                aria-label={`Remove ${source.name}`}
                title="Remove"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </li>
        ))}
      </ul>
      ) : null}
    </div>
  );
}
