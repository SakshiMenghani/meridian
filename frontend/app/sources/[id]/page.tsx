"use client";

import { AlertTriangle, MessageSquareText, Pencil, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { DataTable } from "@/components/data-table";
import { EditSource } from "@/components/edit-source";
import { SourceIcon } from "@/components/source-icon";
import { StatusPill } from "@/components/status-pill";
import { Switch } from "@/components/switch";
import { TransformReview } from "@/components/transform-review";
import { api } from "@/lib/api";
import { connectionSummary, formatWhen, sourceLabel } from "@/lib/format";
import type { CatalogObject, Profile, Sample, Source, TestResult } from "@/lib/types";

export default function SourceDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [source, setSource] = useState<Source | null>(null);
  const [objects, setObjects] = useState<CatalogObject[]>([]);
  const [selected, setSelected] = useState<CatalogObject | null>(null);
  const [sample, setSample] = useState<Sample | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("edit") === "1") setEditing(true);
  }, []);

  async function loadSample(object: CatalogObject) {
    setSelected(object);
    const query = new URLSearchParams({ name: object.name, limit: "20" });
    if (object.schema_name) query.set("schema", object.schema_name);
    const rows = await api<Sample>(`/api/sources/${id}/sample?${query.toString()}`);
    setSample(rows);
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setError(null);
      const current = await api<Source>(`/api/sources/${id}`);
      if (cancelled) return;
      setSource(current);
      setObjects([]);
      setSelected(null);
      setSample(null);
      const catalog = await api<{ objects: CatalogObject[] }>(`/api/sources/${id}/catalog`);
      if (cancelled) return;
      setObjects(catalog.objects);
      if (current.source_type === "spreadsheet") {
        setProfile(await api<Profile>(`/api/sources/${id}/profile`));
      }
      if (catalog.objects[0]) await loadSample(catalog.objects[0]);
    }
    load().catch((err: unknown) => {
      if (!cancelled) setError(err instanceof Error ? err.message : "Could not open this source.");
    });
    return () => {
      cancelled = true;
    };
    // loadSample closes over id, which is the only changing input we need.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, version]);

  async function retest() {
    setBusy(true);
    setError(null);
    try {
      const result = await api<TestResult>(`/api/sources/${id}/test`, { method: "POST" });
      setSource(result.source);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleEnabled() {
    if (!source) return;
    setBusy(true);
    try {
      setSource(await api<Source>(`/api/sources/${id}`, { method: "PATCH", body: JSON.stringify({ enabled: !source.enabled }) }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update the source.");
    } finally {
      setBusy(false);
    }
  }

  const noun = source ? objectNoun(source.source_type) : "Tables";

  return (
    <div>
      <Link href="/sources" className="text-sm font-semibold text-tide">
        ← Data sources
      </Link>
      {!source && !error ? <div className="mt-6 h-24 animate-pulse rounded-2xl bg-panel" /> : null}
      {error ? <p className="mt-4 rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</p> : null}
      {source ? (
        <div className="mt-5 space-y-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex min-w-0 items-start gap-4">
              <SourceIcon type={source.source_type} size="lg" />
              <div className="min-w-0">
                <p className="eyebrow">{sourceLabel(source.source_type)}</p>
                <h1 className="font-display mt-1 text-4xl break-words">{source.name}</h1>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
                  <StatusPill status={source.status} enabled={source.enabled} />
                  <span>{connectionSummary(source.config)}</span>
                  <span>· Checked {formatWhen(source.last_checked_at)}</span>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="mr-1 flex items-center gap-2 text-xs text-muted">
                Use in answers
                <Switch checked={source.enabled} disabled={busy} onChange={toggleEnabled} label="Use in answers" />
              </label>
              <button type="button" onClick={retest} disabled={busy} className="btn btn-secondary">
                <RefreshCw size={14} className={busy ? "animate-spin" : ""} /> {busy ? "Testing…" : "Test"}
              </button>
              <button type="button" onClick={() => setEditing((value) => !value)} className="btn btn-secondary" aria-expanded={editing}>
                <Pencil size={14} /> {editing ? "Close editor" : "Edit"}
              </button>
              <Link
                href={`/chat?source=${source.id}`}
                aria-disabled={!source.enabled}
                onClick={(event) => !source.enabled && event.preventDefault()}
                className="btn btn-primary"
              >
                <MessageSquareText size={15} /> Ask about this
              </Link>
            </div>
          </div>
          {source.status === "error" ? (
            <div className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-bad/30 bg-bad/5 px-4 py-3">
              <p className="flex items-start gap-2 text-sm text-bad">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                <span>
                  <span className="font-semibold">Meridian can’t reach this source. </span>
                  {source.status_message}
                </span>
              </p>
              {!editing ? (
                <button type="button" onClick={() => setEditing(true)} className="btn btn-sm btn-danger">
                  Fix connection
                </button>
              ) : null}
            </div>
          ) : null}
          {editing ? (
            <div className="max-w-2xl">
              <EditSource
                key={source.updated_at}
                source={source}
                onCancel={() => setEditing(false)}
                onSaved={(saved) => {
                  setSource(saved);
                  setEditing(saved.status === "error");
                  setVersion((value) => value + 1);
                }}
              />
            </div>
          ) : null}
          {profile ? <TransformReview source={source} profile={profile} /> : null}
          <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
            <aside className="card self-start p-2">
              <h2 className="flex items-center justify-between px-3 pt-2 pb-2 text-xs font-semibold tracking-wide text-muted uppercase">
                {noun} <span className="font-normal normal-case">{objects.length}</span>
              </h2>
              {objects.length === 0 ? (
                <p className="px-3 pb-3 text-sm text-muted">
                  {source.status === "error" ? "Fix the connection to see what is inside." : `No ${noun.toLowerCase()} found.`}
                </p>
              ) : null}
              <ul className="max-h-[28rem] overflow-y-auto">
                {objects.map((object) => {
                  const active = selected?.name === object.name && selected?.schema_name === object.schema_name;
                  return (
                    <li key={`${object.schema_name ?? ""}-${object.name}`}>
                      <button
                        type="button"
                        aria-current={active}
                        onClick={() => loadSample(object).catch((err: unknown) => setError(err instanceof Error ? err.message : "Sample failed."))}
                        className={`w-full rounded-xl px-3 py-2 text-left transition ${active ? "bg-tide/8 text-tide-deep" : "hover:bg-paper"}`}
                      >
                        <span className="block text-sm font-semibold break-all">{object.name}</span>
                        <span className="block text-xs text-muted">
                          {object.row_count != null ? `${object.row_count.toLocaleString()} rows` : object.kind}
                          {object.columns?.length ? ` · ${object.columns.length} columns` : ""}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </aside>
            <section className="card min-w-0 space-y-4 p-5">
              {selected ? (
                <div>
                  <h2 className="font-display text-2xl break-all">{selected.name}</h2>
                  {selected.columns?.length ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {selected.columns.map((column) => (
                        <span key={column.name} className="rounded-lg bg-paper px-2 py-1 text-xs">
                          <span className="font-semibold">{column.name}</span> <span className="text-muted">{column.data_type}</span>
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="text-sm text-muted">Pick one on the left to preview its rows.</p>
              )}
              {selected?.note && !profile ? <p className="text-sm text-muted">{selected.note}</p> : null}
              {sample ? (
                <>
                  <DataTable columns={sample.columns} rows={sample.rows} />
                  <p className="text-xs text-muted">
                    Preview of {sample.row_count} rows{sample.truncated ? "; the full data has more." : "."}
                  </p>
                </>
              ) : null}
            </section>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function objectNoun(type: string): string {
  if (type === "mongodb") return "Collections";
  if (type === "spreadsheet") return "Sheets";
  if (type === "google_ads" || type === "google_analytics") return "Reports";
  return "Tables";
}
