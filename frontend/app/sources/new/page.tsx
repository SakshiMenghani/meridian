"use client";

import { ArrowRight, Loader2, Lock, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { SourceIcon } from "@/components/source-icon";
import { api } from "@/lib/api";
import type { TestResult } from "@/lib/types";

type DbType = "postgresql" | "mongodb";

const initial = {
  name: "",
  source_type: "postgresql" as DbType,
  host: "localhost",
  port: "5432",
  database: "",
  username: "",
  password: "",
  sslmode: "disable",
  auth_source: "admin",
  srv: false,
};

const SSL_MODES = [
  { value: "disable", label: "Off (local or private network)" },
  { value: "require", label: "Required (most cloud databases)" },
  { value: "verify-ca", label: "Required, verify certificate" },
  { value: "verify-full", label: "Required, verify certificate and host" },
];

function fromConnectionString(value: string): Partial<typeof initial> | null {
  const match = value.trim().match(/^(mongodb(?:\+srv)?):\/\/(?:([^:@/]+)(?::([^@/]*))?@)?([^/?]+)(?:\/([^?]*))?(?:\?(.*))?$/);
  if (!match) return null;
  const [, scheme, user, password, hostPart, database, query] = match;
  const params = new URLSearchParams(query ?? "");
  const [host, port] = hostPart.split(",")[0].split(":");
  return {
    srv: scheme === "mongodb+srv",
    host,
    ...(port ? { port } : {}),
    ...(user ? { username: decodeURIComponent(user) } : {}),
    ...(password && password !== "<db_password>" ? { password: decodeURIComponent(password) } : {}),
    ...(database ? { database: decodeURIComponent(database) } : {}),
    ...(params.get("authSource") ? { auth_source: params.get("authSource")! } : {}),
  };
}

export default function NewSourcePage() {
  const router = useRouter();
  const [form, setForm] = useState(initial);
  const [uri, setUri] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function set<K extends keyof typeof initial>(key: K, value: (typeof initial)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function chooseType(source_type: DbType) {
    setForm((current) => ({ ...current, source_type, port: source_type === "postgresql" ? "5432" : "27017", srv: false }));
    setError(null);
  }

  function applyUri(value: string) {
    setUri(value);
    const parsed = fromConnectionString(value);
    if (parsed) setForm((current) => ({ ...current, ...parsed }));
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const base = { host: form.host.trim(), port: Number(form.port), database: form.database.trim(), username: form.username.trim() };
    const config =
      form.source_type === "postgresql"
        ? { ...base, sslmode: form.sslmode }
        : { ...base, auth_source: form.auth_source.trim(), srv: form.srv };
    try {
      const result = await api<TestResult>("/api/sources", {
        method: "POST",
        body: JSON.stringify({ name: form.name.trim(), source_type: form.source_type, secret: form.password, config }),
      });
      router.push(`/sources/${result.source.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the connection.");
      setBusy(false);
    }
  }

  const mongo = form.source_type === "mongodb";

  return (
    <div>
      <Link href="/sources" className="text-sm font-semibold text-tide">
        ← Data sources
      </Link>
      <div className="mt-4">
        <PageHeader eyebrow="Your data" title="Add a source" description="Choose what you want to connect. Every source is read-only: Meridian never writes to it." />
      </div>

      <div className="mb-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <TypeTile type="postgresql" title="PostgreSQL" text="Tables from a Postgres database" active={form.source_type === "postgresql"} onClick={() => chooseType("postgresql")} />
        <TypeTile type="mongodb" title="MongoDB" text="Collections, including Atlas clusters" active={mongo} onClick={() => chooseType("mongodb")} />
        <TypeTile type="spreadsheet" title="Spreadsheet" text="Upload a CSV or Excel file" href="/transform" />
        <TypeTile type="google_analytics" title="Marketing" text="Google Analytics and Google Ads" href="/sources/marketing" />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <form onSubmit={onSubmit} className="card space-y-5 p-6">
          <div className="flex items-center gap-3">
            <SourceIcon type={form.source_type} />
            <div>
              <h2 className="font-display text-2xl">Connect {mongo ? "MongoDB" : "PostgreSQL"}</h2>
              <p className="text-sm text-muted">We test the connection as soon as you save.</p>
            </div>
          </div>

          {mongo ? (
            <label className="block rounded-2xl border border-dashed border-tide/40 bg-tide/5 p-4">
              <span className="field-label">Have a connection string? Paste it here</span>
              <input
                value={uri}
                onChange={(event) => applyUri(event.target.value)}
                placeholder="mongodb+srv://user:password@cluster0.abcde.mongodb.net/mydb"
                className="input font-mono text-xs"
                autoComplete="off"
              />
              <span className="field-hint">
                {uri && fromConnectionString(uri) ? "Filled in the fields below. Check them, then save." : "Optional. In Atlas: Connect → Drivers. We fill in the fields below for you."}
              </span>
            </label>
          ) : null}

          <Field label="Name" hint="How this source appears in Meridian, for example “Store database”." value={form.name} onChange={(value) => set("name", value)} placeholder={mongo ? "Customer CRM" : "Store database"} />
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_140px]">
            <Field
              label={mongo && form.srv ? "Cluster address" : "Host"}
              value={form.host}
              placeholder={mongo ? "cluster0.abcde.mongodb.net" : "db.example.com"}
              onChange={(value) =>
                setForm((current) => ({
                  ...current,
                  host: value,
                  srv: mongo && value.toLowerCase().endsWith(".mongodb.net") ? true : current.srv,
                }))
              }
            />
            {mongo && form.srv ? (
              <div>
                <span className="field-label">Port</span>
                <p className="mt-1.5 rounded-xl border border-dashed border-line px-3 py-2.5 text-sm text-muted">Not needed</p>
              </div>
            ) : (
              <Field label="Port" value={form.port} onChange={(value) => set("port", value)} inputMode="numeric" />
            )}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Database" value={form.database} onChange={(value) => set("database", value)} hint={mongo ? "The database that holds your collections, not admin." : undefined} />
            <Field label="Username" value={form.username} onChange={(value) => set("username", value)} autoComplete="off" hint="A read-only user is best." />
          </div>
          <label className="block">
            <span className="field-label">Password</span>
            <input
              required
              type="password"
              autoComplete="new-password"
              value={form.password}
              onChange={(event) => set("password", event.target.value)}
              className="input"
            />
            <span className="field-hint">Encrypted before it is saved and never shown again.</span>
          </label>

          <details className="group rounded-2xl border border-line px-4 py-3">
            <summary className="cursor-pointer text-sm font-semibold text-ink marker:text-muted">Advanced settings</summary>
            <div className="mt-4 space-y-4">
              {mongo ? (
                <>
                  <Field label="Auth database" value={form.auth_source} onChange={(value) => set("auth_source", value)} hint="Where the user was created. Usually admin." />
                  <label className="flex items-start gap-3 text-sm">
                    <input type="checkbox" checked={form.srv} onChange={(event) => set("srv", event.target.checked)} className="mt-1 h-4 w-4 accent-tide" />
                    <span>
                      <span className="font-medium">MongoDB Atlas / SRV address (mongodb+srv)</span>
                      <span className="field-hint">Turned on automatically for addresses ending in .mongodb.net.</span>
                    </span>
                  </label>
                </>
              ) : (
                <label className="block">
                  <span className="field-label">Encryption (SSL)</span>
                  <select value={form.sslmode} onChange={(event) => set("sslmode", event.target.value)} className="input">
                    {SSL_MODES.map((mode) => (
                      <option key={mode.value} value={mode.value}>
                        {mode.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          </details>

          {error ? <p className="rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</p> : null}
          <div className="flex items-center gap-3 border-t border-line pt-5">
            <button type="submit" disabled={busy} className="btn btn-primary">
              {busy ? <Loader2 size={15} className="animate-spin" /> : null}
              {busy ? "Testing connection…" : "Save and test connection"}
            </button>
            <Link href="/sources" className="btn btn-ghost">
              Cancel
            </Link>
          </div>
        </form>

        <aside className="space-y-4 text-sm">
          <div className="card p-5">
            <h3 className="font-semibold">What you’ll need</h3>
            <ul className="mt-3 space-y-2 text-muted">
              <li>• The host address{mongo ? " or an Atlas connection string" : " and port"}</li>
              <li>• The database name</li>
              <li>• A username and password, ideally read-only</li>
              {mongo ? <li>• Atlas: allow this machine’s IP under Network Access</li> : <li>• For cloud databases, set Encryption to Required</li>}
            </ul>
          </div>
          <div className="card space-y-3 p-5">
            <p className="flex items-start gap-2">
              <ShieldCheck size={16} className="mt-0.5 shrink-0 text-tide" />
              <span>Meridian only reads. It runs checked, read-only queries and never changes your data.</span>
            </p>
            <p className="flex items-start gap-2">
              <Lock size={16} className="mt-0.5 shrink-0 text-tide" />
              <span>Your password is encrypted on this machine and is never sent back to the browser.</span>
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}

function TypeTile({
  type,
  title,
  text,
  active,
  onClick,
  href,
}: {
  type: string;
  title: string;
  text: string;
  active?: boolean;
  onClick?: () => void;
  href?: string;
}) {
  const className = `group flex items-center gap-3 rounded-2xl border p-4 text-left transition ${
    active ? "border-tide bg-panel ring-4 ring-tide/10" : "border-line bg-panel/70 hover:border-tide/40 hover:bg-panel"
  }`;
  const body = (
    <>
      <SourceIcon type={type} size="lg" />
      <span className="min-w-0 flex-1">
        <span className="block font-semibold">{title}</span>
        <span className="block text-xs text-muted">{text}</span>
      </span>
      {href ? <ArrowRight size={15} className="text-muted transition group-hover:translate-x-0.5 group-hover:text-tide" /> : null}
    </>
  );
  return href ? (
    <Link href={href} className={className}>
      {body}
    </Link>
  ) : (
    <button type="button" onClick={onClick} aria-pressed={active} className={className}>
      {body}
    </button>
  );
}

function Field({
  label,
  value,
  onChange,
  hint,
  placeholder,
  autoComplete,
  inputMode,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  placeholder?: string;
  autoComplete?: string;
  inputMode?: "numeric";
}) {
  return (
    <label className="block">
      <span className="field-label">{label}</span>
      <input
        required
        value={value}
        placeholder={placeholder}
        autoComplete={autoComplete}
        inputMode={inputMode}
        onChange={(event) => onChange(event.target.value)}
        className="input"
      />
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}
