"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Profile, Source } from "@/lib/types";
import { TransformReview } from "./transform-review";

export function UploadPanel() {
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ source: Source; profile: Profile } | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a CSV or Excel file.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = new FormData();
      body.set("file", file);
      if (name.trim()) body.set("name", name.trim());
      const uploaded = await api<{ source: Source; profile: Profile }>("/api/uploads", {
        method: "POST",
        body,
      });
      setResult(uploaded);
      setFile(null);
      setName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={onSubmit} className="rounded-2xl border border-line bg-panel p-5">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="block text-sm">
            <span className="font-medium">Display name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Optional. Defaults to the file name."
              className="mt-1 w-full rounded-lg border border-line bg-white px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium">CSV or Excel file</span>
            <input
              type="file"
              accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="mt-1 block w-full text-sm"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={busy}
          className="mt-4 rounded-full bg-tide px-4 py-2 text-sm font-semibold text-white hover:bg-tide-deep"
        >
          {busy ? "Reading file…" : "Upload and review"}
        </button>
        {error ? <p className="mt-3 text-sm text-bad">{error}</p> : null}
      </form>
      {result ? <TransformReview source={result.source} profile={result.profile} /> : null}
    </div>
  );
}
