"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Source } from "@/lib/types";

type Form = {
  name: string;
  host: string;
  port: string;
  database: string;
  username: string;
  sslmode: string;
  auth_source: string;
  srv: boolean;
  password: string;
};

function initialForm(source: Source): Form {
  const config = source.config;
  const host = String(config.host ?? "");
  return {
    name: source.name,
    host,
    port: String(config.port ?? (source.source_type === "postgresql" ? 5432 : 27017)),
    database: String(config.database ?? ""),
    username: String(config.username ?? ""),
    sslmode: String(config.sslmode ?? "disable"),
    auth_source: String(config.auth_source ?? "admin"),
    srv: typeof config.srv === "boolean" ? config.srv : host.toLowerCase().endsWith(".mongodb.net"),
    password: "",
  };
}

export function EditSource({
  source,
  onSaved,
  onCancel,
}: {
  source: Source;
  onSaved: (source: Source) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<Form>(() => initialForm(source));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isDatabase = source.source_type === "postgresql" || source.source_type === "mongodb";

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const body: Record<string, unknown> = { name: form.name.trim() };
    if (isDatabase) {
      body.config =
        source.source_type === "postgresql"
          ? {
              host: form.host.trim(),
              port: Number(form.port),
              database: form.database.trim(),
              username: form.username.trim(),
              sslmode: form.sslmode,
            }
          : {
              host: form.host.trim(),
              port: Number(form.port),
              database: form.database.trim(),
              username: form.username.trim(),
              auth_source: form.auth_source.trim(),
              srv: form.srv,
            };
      if (form.password) body.secret = form.password;
    }
    try {
      const saved = await api<Source>(`/api/sources/${source.id}`, { method: "PATCH", body: JSON.stringify(body) });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The changes could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  const mongoSrv = source.source_type === "mongodb" && form.srv;

  return (
    <form onSubmit={save} className="card space-y-4 border-tide/30 p-6">
      <div>
        <h2 className="font-display text-2xl">Edit source</h2>
        <p className="mt-1 text-sm text-muted">
          {isDatabase
            ? "Saving re-tests the connection. Leave the password empty to keep the saved one."
            : "Only the name can be changed here. Upload a new file to replace a spreadsheet."}
        </p>
      </div>
      <Field label="Name" value={form.name} onChange={(value) => set("name", value)} />
      {isDatabase ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Host" value={form.host} onChange={(value) => set("host", value)} />
            {mongoSrv ? (
              <div>
                <span className="field-label">Port</span>
                <p className="mt-1.5 rounded-xl border border-dashed border-line px-3 py-2.5 text-sm text-muted">Not needed for Atlas</p>
              </div>
            ) : (
              <Field label="Port" value={form.port} onChange={(value) => set("port", value)} />
            )}
            <Field label="Database" value={form.database} onChange={(value) => set("database", value)} />
            <Field label="Username" value={form.username} onChange={(value) => set("username", value)} />
          </div>
          {source.source_type === "postgresql" ? (
            <label className="block">
              <span className="field-label">Encryption (SSL)</span>
              <select
                value={form.sslmode}
                onChange={(event) => set("sslmode", event.target.value)}
                className="input"
              >
                {["disable", "require", "verify-ca", "verify-full"].map((mode) => (
                  <option key={mode} value={mode}>
                    {mode}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <>
              <Field label="Auth database" value={form.auth_source} onChange={(value) => set("auth_source", value)} />
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="h-4 w-4 accent-tide" checked={form.srv} onChange={(event) => set("srv", event.target.checked)} />
                <span className="font-medium">MongoDB Atlas / SRV connection (mongodb+srv)</span>
              </label>
            </>
          )}
          <label className="block">
            <span className="field-label">New password</span>
            <input
              type="password"
              autoComplete="new-password"
              value={form.password}
              placeholder={source.has_secret ? "Unchanged" : ""}
              onChange={(event) => set("password", event.target.value)}
              className="input"
            />
          </label>
        </>
      ) : null}
      {error ? <p className="rounded-xl bg-bad/10 px-3 py-2 text-sm text-bad">{error}</p> : null}
      <div className="flex gap-2">
        <button type="submit" disabled={busy || !form.name.trim()} className="btn btn-primary">
          {busy ? (isDatabase ? "Saving and testing…" : "Saving…") : isDatabase ? "Save and test" : "Save"}
        </button>
        <button type="button" onClick={onCancel} className="btn btn-ghost">
          Cancel
        </button>
      </div>
    </form>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="field-label">{label}</span>
      <input
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="input"
      />
    </label>
  );
}
