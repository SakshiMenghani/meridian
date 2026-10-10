"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import type { TestResult } from "@/lib/types";

const initial = {
  name: "",
  source_type: "postgresql" as "postgresql" | "mongodb",
  host: "localhost",
  port: "5432",
  database: "",
  username: "",
  password: "",
  sslmode: "disable",
  auth_source: "admin",
};

export default function NewSourcePage() {
  const router = useRouter();
  const [form, setForm] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function set<K extends keyof typeof initial>(key: K, value: (typeof initial)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const config =
      form.source_type === "postgresql"
        ? {
            host: form.host,
            port: Number(form.port),
            database: form.database,
            username: form.username,
            sslmode: form.sslmode,
          }
        : {
            host: form.host,
            port: Number(form.port),
            database: form.database,
            username: form.username,
            auth_source: form.auth_source,
          };
    try {
      const result = await api<TestResult>("/api/sources", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          source_type: form.source_type,
          secret: form.password,
          config,
        }),
      });
      router.push(`/sources/${result.source.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the connection.");
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Connections"
        title="Add a database"
        description="The password is encrypted before it is stored and is not returned to this page."
      />
      <form onSubmit={onSubmit} className="max-w-xl space-y-4 rounded-2xl border border-line bg-panel p-5">
        <label className="block text-sm">
          <span className="font-medium">Name</span>
          <input
            required
            value={form.name}
            onChange={(event) => set("name", event.target.value)}
            className="mt-1 w-full rounded-lg border border-line px-3 py-2"
          />
        </label>
        <label className="block text-sm">
          <span className="font-medium">Type</span>
          <select
            value={form.source_type}
            onChange={(event) => {
              const source_type = event.target.value as "postgresql" | "mongodb";
              setForm((current) => ({
                ...current,
                source_type,
                port: source_type === "postgresql" ? "5432" : "27017",
              }));
            }}
            className="mt-1 w-full rounded-lg border border-line px-3 py-2"
          >
            <option value="postgresql">PostgreSQL</option>
            <option value="mongodb">MongoDB</option>
          </select>
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Host" value={form.host} onChange={(value) => set("host", value)} />
          <Field label="Port" value={form.port} onChange={(value) => set("port", value)} />
          <Field label="Database" value={form.database} onChange={(value) => set("database", value)} />
          <Field label="Username" value={form.username} onChange={(value) => set("username", value)} />
        </div>
        <label className="block text-sm">
          <span className="font-medium">Password</span>
          <input
            required
            type="password"
            autoComplete="off"
            value={form.password}
            onChange={(event) => set("password", event.target.value)}
            className="mt-1 w-full rounded-lg border border-line px-3 py-2"
          />
        </label>
        {form.source_type === "postgresql" ? (
          <label className="block text-sm">
            <span className="font-medium">SSL mode</span>
            <select
              value={form.sslmode}
              onChange={(event) => set("sslmode", event.target.value)}
              className="mt-1 w-full rounded-lg border border-line px-3 py-2"
            >
              <option value="disable">disable</option>
              <option value="require">require</option>
              <option value="verify-ca">verify-ca</option>
              <option value="verify-full">verify-full</option>
            </select>
          </label>
        ) : (
          <Field label="Auth database" value={form.auth_source} onChange={(value) => set("auth_source", value)} />
        )}
        {error ? <p className="text-sm text-bad">{error}</p> : null}
        <button
          type="submit"
          disabled={busy}
          className="rounded-full bg-tide px-4 py-2 text-sm font-semibold text-white"
        >
          {busy ? "Testing connection…" : "Save and test"}
        </button>
      </form>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block text-sm">
      <span className="font-medium">{label}</span>
      <input
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-lg border border-line px-3 py-2"
      />
    </label>
  );
}
