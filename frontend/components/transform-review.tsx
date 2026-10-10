"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ColumnTransform, ImportResult, PreviewTransform, Profile, Source } from "@/lib/types";
import { DataTable } from "./data-table";

const TYPES = ["text", "bigint", "numeric", "boolean", "date", "timestamp"] as const;

export function TransformReview({ source, profile }: { source: Source; profile: Profile }) {
  const [columns, setColumns] = useState<ColumnTransform[]>(
    profile.columns.map((column) => ({
      name: column.name,
      suggested_name: column.suggested_name,
      inferred_type: column.inferred_type as ColumnTransform["inferred_type"],
      include: true,
    })),
  );
  const [dropDuplicates, setDropDuplicates] = useState(profile.duplicate_rows > 0);
  const [missing, setMissing] = useState<"keep" | "drop_rows">("keep");
  const [tableName, setTableName] = useState(profile.table_name);
  const [destination, setDestination] = useState<"spreadsheet" | "postgresql" | "mongodb">("spreadsheet");
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [preview, setPreview] = useState<PreviewTransform | null>(null);
  const [imported, setImported] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"preview" | "save" | null>(null);

  const payload = useMemo(
    () => ({
      drop_duplicates: dropDuplicates,
      missing,
      columns,
      table_name: tableName,
    }),
    [columns, dropDuplicates, missing, tableName],
  );

  async function runPreview() {
    setBusy("preview");
    setError(null);
    try {
      setPreview(await api<PreviewTransform>(`/api/sources/${source.id}/preview-transform`, {
        method: "POST",
        body: JSON.stringify(payload),
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed.");
    } finally {
      setBusy(null);
    }
  }

  async function runSave() {
    if (!window.confirm(`Save ${tableName} to ${destinationLabel(destination)}? This writes data.`)) {
      return;
    }
    setBusy("save");
    setError(null);
    try {
      const result = await api<ImportResult>(`/api/sources/${source.id}/import`, {
        method: "POST",
        body: JSON.stringify({
          ...payload,
          confirm: true,
          destination,
          replace_existing: replaceExisting,
        }),
      });
      setImported(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setBusy(null);
    }
  }

  function updateColumn(index: number, patch: Partial<ColumnTransform>) {
    setColumns((current) => current.map((column, i) => (i === index ? { ...column, ...patch } : column)));
    setPreview(null);
  }

  return (
    <section className="space-y-5 rounded-2xl border border-line bg-panel p-5">
      <div>
        <h2 className="font-display text-2xl">Clean and save</h2>
        <p className="mt-1 text-sm text-muted">{profile.note}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Rows" value={String(profile.row_count)} />
        <Stat label="Columns" value={String(profile.column_count)} />
        <Stat label="Duplicate rows" value={String(profile.duplicate_rows)} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={dropDuplicates}
            onChange={(event) => {
              setDropDuplicates(event.target.checked);
              setPreview(null);
            }}
          />
          Drop duplicate rows
        </label>
        <label className="block text-sm">
          <span className="font-medium">Empty cells</span>
          <select
            value={missing}
            onChange={(event) => {
              setMissing(event.target.value as "keep" | "drop_rows");
              setPreview(null);
            }}
            className="mt-1 w-full rounded-lg border border-line px-3 py-2"
          >
            <option value="keep">Keep rows, leave cells blank</option>
            <option value="drop_rows">Drop any row with a blank cell</option>
          </select>
        </label>
        <label className="block text-sm">
          <span className="font-medium">Table or collection name</span>
          <input
            value={tableName}
            onChange={(event) => {
              setTableName(event.target.value);
              setPreview(null);
            }}
            className="mt-1 w-full rounded-lg border border-line px-3 py-2"
          />
        </label>
        <label className="block text-sm">
          <span className="font-medium">Save to</span>
          <select
            value={destination}
            onChange={(event) => setDestination(event.target.value as typeof destination)}
            className="mt-1 w-full rounded-lg border border-line px-3 py-2"
          >
            <option value="spreadsheet">This spreadsheet (cleaned file)</option>
            <option value="postgresql">Imported PostgreSQL</option>
            <option value="mongodb">Imported MongoDB</option>
          </select>
        </label>
      </div>
      {destination !== "spreadsheet" ? (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={replaceExisting} onChange={(event) => setReplaceExisting(event.target.checked)} />
          Replace the table or collection if that name already exists
        </label>
      ) : null}
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs tracking-wide text-muted uppercase">
            <tr>
              <th className="py-2 pr-3">Keep</th>
              <th className="py-2 pr-3">Original</th>
              <th className="py-2 pr-3">Name after save</th>
              <th className="py-2 pr-3">Type</th>
              <th className="py-2">Missing</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((column, index) => {
              const stats = profile.columns.find((item) => item.name === column.name);
              return (
                <tr key={column.name} className="border-t border-line">
                  <td className="py-2 pr-3">
                    <input
                      type="checkbox"
                      checked={column.include}
                      onChange={(event) => updateColumn(index, { include: event.target.checked })}
                    />
                  </td>
                  <td className="py-2 pr-3">{column.name}</td>
                  <td className="py-2 pr-3">
                    <input
                      value={column.suggested_name}
                      onChange={(event) => updateColumn(index, { suggested_name: event.target.value })}
                      className="w-full rounded-lg border border-line px-2 py-1"
                    />
                  </td>
                  <td className="py-2 pr-3">
                    <select
                      value={column.inferred_type}
                      onChange={(event) =>
                        updateColumn(index, { inferred_type: event.target.value as ColumnTransform["inferred_type"] })
                      }
                      className="rounded-lg border border-line px-2 py-1"
                    >
                      {TYPES.map((type) => (
                        <option key={type} value={type}>
                          {type}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-2">{stats?.missing ?? 0}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy !== null}
          onClick={runPreview}
          className="rounded-full border border-line px-4 py-2 text-sm font-semibold"
        >
          {busy === "preview" ? "Previewing…" : "Preview cleaned data"}
        </button>
        <button
          type="button"
          disabled={busy !== null}
          onClick={runSave}
          className="rounded-full bg-tide px-4 py-2 text-sm font-semibold text-white"
        >
          {busy === "save" ? "Saving…" : "Approve and save"}
        </button>
        <Link
          href={`/chat?source=${source.id}`}
          className="rounded-full border border-line px-4 py-2 text-sm font-semibold"
        >
          Ask a question
        </Link>
      </div>
      {error ? <p className="text-sm text-bad">{error}</p> : null}
      {preview ? (
        <div className="space-y-3">
          <p className="text-sm text-muted">
            Cleaned preview: {preview.row_count} rows, dropped {preview.dropped_duplicates} duplicates
            {preview.dropped_empty_rows ? ` and ${preview.dropped_empty_rows} incomplete rows` : ""}.
          </p>
          <DataTable columns={preview.profile.columns.map((column) => column.suggested_name)} rows={preview.profile.preview} />
          <pre className="overflow-x-auto rounded-xl bg-sidebar p-4 text-xs leading-5 text-mist">{preview.profile.suggested_ddl}</pre>
        </div>
      ) : (
        <DataTable columns={profile.columns.map((column) => column.name)} rows={profile.preview} />
      )}
      {imported ? (
        <p className="rounded-xl bg-good/10 px-4 py-3 text-sm text-good">
          {imported.message}{" "}
          <Link href={`/sources/${imported.destination_source.id}`} className="font-semibold underline">
            Open {imported.destination_source.name}
          </Link>
          {" · "}
          <Link href={`/chat?source=${imported.destination_source.id}`} className="font-semibold underline">
            Ask about the saved data
          </Link>
        </p>
      ) : null}
    </section>
  );
}

function destinationLabel(destination: string): string {
  if (destination === "postgresql") return "Imported PostgreSQL";
  if (destination === "mongodb") return "Imported MongoDB";
  return "this spreadsheet";
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-paper px-3 py-3">
      <p className="text-xs tracking-wide text-muted uppercase">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}
