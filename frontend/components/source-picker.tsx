"use client";

import { Check } from "lucide-react";
import { sourceLabel } from "@/lib/format";
import type { Source } from "@/lib/types";

export function SourcePicker({
  sources,
  selected,
  onChange,
}: {
  sources: Source[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const usable = sources.filter((source) => source.enabled);
  const all = selected.length === 0;

  function toggle(id: string) {
    const base = all ? [] : selected;
    const next = base.includes(id) ? base.filter((item) => item !== id) : [...base, id];
    onChange(next.length === usable.length ? [] : next);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Chip active={all} onClick={() => onChange([])} label="All sources" detail={`${usable.length}`} />
      {usable.map((source) => (
        <Chip
          key={source.id}
          active={!all && selected.includes(source.id)}
          onClick={() => toggle(source.id)}
          label={source.name}
          detail={sourceLabel(source.source_type)}
          warn={source.status === "error"}
        />
      ))}
    </div>
  );
}

function Chip({
  active,
  onClick,
  label,
  detail,
  warn,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  detail: string;
  warn?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`group flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition ${
        active ? "border-tide bg-tide text-white shadow-sm" : "border-line bg-panel text-ink hover:border-tide/50"
      }`}
    >
      <span
        className={`flex h-4 w-4 items-center justify-center rounded-full border ${
          active ? "border-white bg-white text-tide" : warn ? "border-bad" : "border-line"
        }`}
      >
        {active ? <Check size={11} strokeWidth={3} /> : null}
      </span>
      <span className="max-w-[14rem] truncate font-semibold" title={label}>
        {label}
      </span>
      <span className={active ? "text-white/70" : "text-muted"}>{detail}</span>
    </button>
  );
}
