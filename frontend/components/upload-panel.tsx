"use client";

import { FileSpreadsheet, Loader2, UploadCloud, X } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Profile, Source } from "@/lib/types";
import { TransformReview } from "./transform-review";

const ACCEPT = ".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export function UploadPanel() {
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ source: Source; profile: Profile } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function pick(next: File | null | undefined) {
    if (!next) return;
    if (!/\.(csv|xlsx)$/i.test(next.name)) {
      setError("Only .csv and .xlsx files are supported.");
      return;
    }
    setError(null);
    setFile(next);
  }

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
      <form onSubmit={onSubmit} className="card space-y-5 p-6">
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(event) => (event.key === "Enter" || event.key === " ") && inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            pick(event.dataTransfer.files?.[0]);
          }}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
            dragging ? "border-tide bg-tide/5" : "border-line hover:border-tide/50 hover:bg-paper/50"
          }`}
        >
          {file ? (
            <div className="flex items-center gap-3 rounded-xl bg-paper px-4 py-3 text-left">
              <FileSpreadsheet size={22} className="text-good" />
              <span>
                <span className="block text-sm font-semibold">{file.name}</span>
                <span className="block text-xs text-muted">{(file.size / 1024).toFixed(0)} KB · ready to upload</span>
              </span>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  setFile(null);
                }}
                className="ml-2 rounded-full p-1 text-muted hover:bg-line hover:text-ink"
                aria-label="Remove file"
              >
                <X size={14} />
              </button>
            </div>
          ) : (
            <>
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-tide/10 text-tide">
                <UploadCloud size={22} />
              </span>
              <p className="mt-3 text-sm font-semibold">Drop a file here, or click to choose</p>
              <p className="mt-1 text-xs text-muted">CSV or Excel (.xlsx). The first sheet is used.</p>
            </>
          )}
          <input ref={inputRef} type="file" accept={ACCEPT} onChange={(event) => pick(event.target.files?.[0])} className="hidden" />
        </div>
        <label className="block max-w-md">
          <span className="field-label">Display name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Optional. Defaults to the file name." className="input" />
        </label>
        {error ? <p className="rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</p> : null}
        <button type="submit" disabled={busy || !file} className="btn btn-primary">
          {busy ? <Loader2 size={15} className="animate-spin" /> : null}
          {busy ? "Reading file…" : "Upload and review"}
        </button>
      </form>
      {result ? <TransformReview source={result.source} profile={result.profile} /> : null}
    </div>
  );
}
