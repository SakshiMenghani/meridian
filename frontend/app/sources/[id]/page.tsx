"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { DataTable } from "@/components/data-table";
import { StatusPill } from "@/components/status-pill";
import { TransformReview } from "@/components/transform-review";
import { api } from "@/lib/api";
import { formatWhen, sourceLabel } from "@/lib/format";
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
  }, [id]);

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

  return (
    <div>
      <Link href="/sources" className="text-sm font-semibold text-tide">
        All sources
      </Link>
      {!source && !error ? <p className="mt-6 text-sm text-muted">Loading source…</p> : null}
      {error ? <p className="mt-4 rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</p> : null}
      {source ? (
        <div className="mt-4 space-y-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold tracking-[0.16em] text-tide uppercase">{sourceLabel(source.source_type)}</p>
              <h1 className="font-display mt-2 text-4xl">{source.name}</h1>
              <p className="mt-2 text-sm text-muted">
                {source.enabled ? "Enabled for questions." : "Disabled. The assistant will skip this source."} Last check{" "}
                {formatWhen(source.last_checked_at)}.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <StatusPill status={source.status} />
              <button
                type="button"
                onClick={retest}
                disabled={busy}
                className="rounded-full bg-tide px-4 py-2 text-sm font-semibold text-white"
              >
                {busy ? "Testing…" : "Test again"}
              </button>
            </div>
          </div>
          {source.status_message ? <p className="text-sm text-muted">{source.status_message}</p> : null}
          {profile ? <TransformReview source={source} profile={profile} /> : null}
          <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
            <aside className="rounded-2xl border border-line bg-panel p-3">
              <h2 className="px-2 py-2 text-sm font-semibold">Objects</h2>
              <ul>
                {objects.map((object) => {
                  const active = selected?.name === object.name && selected?.schema_name === object.schema_name;
                  return (
                    <li key={`${object.schema_name ?? ""}-${object.name}`}>
                      <button
                        type="button"
                        onClick={() => loadSample(object).catch((err: unknown) => setError(err instanceof Error ? err.message : "Sample failed."))}
                        className={`w-full rounded-xl px-3 py-2 text-left ${active ? "bg-paper" : "hover:bg-paper/70"}`}
                      >
                        <span className="block text-sm font-semibold break-all">{object.name}</span>
                        <span className="block text-xs text-muted">
                          {object.kind}
                          {object.row_count != null ? ` · ${object.row_count} rows` : ""}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </aside>
            <section className="min-w-0 space-y-3">
              {selected?.columns?.length ? (
                <p className="text-sm text-muted">{selected.columns.map((column) => `${column.name} ${column.data_type}`).join(" · ")}</p>
              ) : null}
              {selected?.note && !profile ? <p className="text-sm text-muted">{selected.note}</p> : null}
              {sample ? (
                <>
                  <p className="text-sm text-muted">
                    Showing {sample.row_count} rows{sample.truncated ? ". More rows exist." : "."}
                  </p>
                  <DataTable columns={sample.columns} rows={sample.rows} />
                </>
              ) : null}
            </section>
          </div>
        </div>
      ) : null}
    </div>
  );
}
