"use client";

import { ArrowLeftRight, Check, Loader2, Plus, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import type { CatalogObject, LinkSuggestion, Mapping, Source } from "@/lib/types";

type Side = { sourceId: string; object: string; field: string };
const EMPTY: Side = { sourceId: "", object: "", field: "" };

export default function LinksPage() {
  const [links, setLinks] = useState<Mapping[]>([]);
  const [suggestions, setSuggestions] = useState<LinkSuggestion[] | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<Mapping[]>("/api/mappings").then(setLinks).catch(() => setLinks([]));
    setSuggestions(null);
    api<LinkSuggestion[]>("/api/mappings/suggestions")
      .then(setSuggestions)
      .catch(() => setSuggestions([]));
  }, []);

  useEffect(() => {
    refresh();
    api<Source[]>("/api/sources").then(setSources).catch(() => setSources([]));
  }, [refresh]);

  async function confirm(left: Side, right: Side, key: string) {
    setSaving(key);
    setError(null);
    try {
      await api<Mapping>("/api/mappings", {
        method: "POST",
        body: JSON.stringify({
          left_source_id: left.sourceId,
          left_object: left.object,
          left_field: left.field,
          right_source_id: right.sourceId,
          right_object: right.object,
          right_field: right.field,
        }),
      });
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The link could not be saved.");
    } finally {
      setSaving(null);
    }
  }

  async function remove(id: string) {
    setSaving(id);
    try {
      await api<void>(`/api/mappings/${id}`, { method: "DELETE" });
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The link could not be removed.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Links"
        title="Connect your sources"
        description="A link tells Meridian that two columns in different sources mean the same thing, like a customer ID in your store database and in your CRM. Questions that combine sources only ever join on links you confirmed here."
      />
      {error ? <p className="mb-4 rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</p> : null}

      <section className="mb-8">
        <div className="mb-3 flex items-center gap-2">
          <Sparkles size={16} className="text-tide" />
          <h2 className="font-display text-2xl">Suggested links</h2>
        </div>
        <p className="mb-4 text-sm text-muted">Found by comparing the actual values in each column. Confirm only the ones that are true.</p>
        {suggestions === null ? (
          <div className="flex items-center gap-2 rounded-2xl border border-line bg-panel px-4 py-4 text-sm text-muted">
            <Loader2 size={14} className="animate-spin text-tide" /> Comparing columns across sources…
          </div>
        ) : suggestions.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-line px-4 py-4 text-sm text-muted">
            No new matches found. Add a link below if you know two columns match.
          </p>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {suggestions.map((item) => {
              const key = `${item.left_source_id}.${item.left_object}.${item.left_field}-${item.right_source_id}.${item.right_object}.${item.right_field}`;
              return (
                <li key={key} className="flex flex-col rounded-2xl border border-line bg-panel p-4">
                  <Pair
                    left={[item.left_source_name, item.left_object, item.left_field]}
                    right={[item.right_source_name, item.right_object, item.right_field]}
                  />
                  <div className="mt-3 flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-paper">
                      <div className="h-full rounded-full bg-tide" style={{ width: `${Math.round(item.overlap * 100)}%` }} />
                    </div>
                    <span className="text-xs text-muted">{Math.round(item.overlap * 100)}% match</span>
                  </div>
                  <p className="mt-2 text-xs text-muted">
                    {item.shared_values} shared values, for example {item.examples.join(", ")}
                  </p>
                  <button
                    type="button"
                    disabled={saving === key}
                    onClick={() =>
                      confirm(
                        { sourceId: item.left_source_id, object: item.left_object, field: item.left_field },
                        { sourceId: item.right_source_id, object: item.right_object, field: item.right_field },
                        key,
                      )
                    }
                    className="mt-4 flex w-fit items-center gap-1.5 rounded-full bg-tide px-3 py-1.5 text-xs font-semibold text-white"
                  >
                    <Check size={13} /> Confirm link
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="mb-8 rounded-3xl border border-line bg-panel">
        <header className="border-b border-line px-5 py-4">
          <h2 className="font-display text-2xl">Confirmed links</h2>
          <p className="text-sm text-muted">{links.length} in use for questions that combine sources.</p>
        </header>
        <ul>
          {links.map((link) => (
            <li key={link.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4 last:border-b-0">
              <div className="min-w-0">
                <Pair
                  left={[link.left_source_name, link.left_object, link.left_field]}
                  right={[link.right_source_name, link.right_object, link.right_field]}
                />
                <p className="mt-1 text-xs text-muted">{link.description}</p>
              </div>
              <button
                type="button"
                onClick={() => remove(link.id)}
                disabled={saving === link.id}
                className="flex items-center gap-1 rounded-full border border-line px-3 py-1.5 text-xs font-semibold text-bad hover:border-bad"
              >
                <Trash2 size={13} /> Remove
              </button>
            </li>
          ))}
          {links.length === 0 ? <li className="px-5 py-6 text-sm text-muted">No links yet.</li> : null}
        </ul>
      </section>

      <ManualLink sources={sources} saving={saving === "manual"} onSave={(left, right) => confirm(left, right, "manual")} />
    </div>
  );
}

function Pair({ left, right }: { left: string[]; right: string[] }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <Field parts={left} />
      <ArrowLeftRight size={14} className="text-muted" />
      <Field parts={right} />
    </div>
  );
}

function Field({ parts }: { parts: string[] }) {
  const [source, object, field] = parts;
  return (
    <span className="rounded-xl bg-paper px-2.5 py-1">
      <span className="text-xs text-muted">{source} · </span>
      <span className="font-semibold">
        {object}.{field}
      </span>
    </span>
  );
}

function ManualLink({
  sources,
  saving,
  onSave,
}: {
  sources: Source[];
  saving: boolean;
  onSave: (left: Side, right: Side) => void;
}) {
  const [left, setLeft] = useState<Side>(EMPTY);
  const [right, setRight] = useState<Side>(EMPTY);
  const ready = [left, right].every((side) => side.sourceId && side.object && side.field);

  return (
    <section className="rounded-3xl border border-line bg-panel p-5">
      <div className="flex items-center gap-2">
        <Plus size={16} className="text-tide" />
        <h2 className="font-display text-2xl">Add a link yourself</h2>
      </div>
      <p className="mt-1 text-sm text-muted">Pick a column on each side that holds the same values.</p>
      <div className="mt-4 grid items-end gap-3 md:grid-cols-[1fr_auto_1fr]">
        <SidePicker sources={sources} value={left} onChange={setLeft} />
        <ArrowLeftRight size={16} className="mx-auto mb-3 text-muted" />
        <SidePicker sources={sources} value={right} onChange={setRight} />
      </div>
      <button
        type="button"
        disabled={!ready || saving}
        onClick={() => onSave(left, right)}
        className="mt-4 rounded-full bg-tide px-4 py-2 text-sm font-semibold text-white"
      >
        {saving ? "Saving…" : "Save link"}
      </button>
    </section>
  );
}

function SidePicker({ sources, value, onChange }: { sources: Source[]; value: Side; onChange: (side: Side) => void }) {
  const [objects, setObjects] = useState<CatalogObject[]>([]);

  useEffect(() => {
    if (!value.sourceId) {
      setObjects([]);
      return;
    }
    api<{ objects: CatalogObject[] }>(`/api/sources/${value.sourceId}/catalog`)
      .then((catalog) => setObjects(catalog.objects))
      .catch(() => setObjects([]));
  }, [value.sourceId]);

  const columns = useMemo(() => objects.find((item) => item.name === value.object)?.columns ?? [], [objects, value.object]);
  const select = "w-full rounded-xl border border-line bg-paper px-3 py-2 text-sm";

  return (
    <div className="grid gap-2">
      <select value={value.sourceId} onChange={(event) => onChange({ sourceId: event.target.value, object: "", field: "" })} className={select}>
        <option value="">Source…</option>
        {sources.map((source) => (
          <option key={source.id} value={source.id}>
            {source.name}
          </option>
        ))}
      </select>
      <select
        value={value.object}
        onChange={(event) => onChange({ ...value, object: event.target.value, field: "" })}
        className={select}
        disabled={!objects.length}
      >
        <option value="">Table…</option>
        {objects.map((item) => (
          <option key={`${item.schema_name ?? ""}.${item.name}`} value={item.name}>
            {item.name}
          </option>
        ))}
      </select>
      <select value={value.field} onChange={(event) => onChange({ ...value, field: event.target.value })} className={select} disabled={!columns.length}>
        <option value="">Column…</option>
        {columns.map((column) => (
          <option key={column.name} value={column.name}>
            {column.name}
          </option>
        ))}
      </select>
    </div>
  );
}
