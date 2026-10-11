"use client";

import { Check, ChevronDown, Layers } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { SourceIcon } from "@/components/source-icon";
import { sourceLabel } from "@/lib/format";
import type { Source } from "@/lib/types";

export function scopeLabel(sources: Source[], selected: string[]): string {
  const usable = sources.filter((source) => source.enabled);
  if (selected.length === 0) return `All sources (${usable.length})`;
  const names = usable.filter((source) => selected.includes(source.id)).map((source) => source.name);
  if (names.length === 1) return names[0];
  return `${names.length} sources`;
}

export function SourcePicker({
  sources,
  selected,
  onChange,
  placement = "bottom",
}: {
  sources: Source[];
  selected: string[];
  onChange: (next: string[]) => void;
  placement?: "top" | "bottom";
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const usable = sources.filter((source) => source.enabled);
  const all = selected.length === 0;

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  function toggle(id: string) {
    const base = all ? [] : selected;
    const next = base.includes(id) ? base.filter((item) => item !== id) : [...base, id];
    onChange(next.length === usable.length ? [] : next);
  }

  const chosen = usable.filter((source) => selected.includes(source.id));

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="flex max-w-full items-center gap-2 rounded-full border border-line bg-panel py-1.5 pr-3 pl-1.5 text-sm hover:border-tide/50"
      >
        {chosen.length === 1 ? (
          <SourceIcon type={chosen[0].source_type} size="sm" />
        ) : (
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-tide/10 text-tide">
            <Layers size={13} />
          </span>
        )}
        <span className="text-muted">Answer from</span>
        <span className="truncate font-semibold">{scopeLabel(sources, selected)}</span>
        <ChevronDown size={14} className={`shrink-0 text-muted transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? (
        <div
          role="listbox"
          aria-multiselectable
          className={`absolute left-0 z-30 w-[22rem] max-w-[calc(100vw-2.5rem)] rounded-2xl border border-line bg-panel p-2 shadow-[0_24px_48px_-24px_rgba(28,36,48,0.5)] ${
            placement === "top" ? "bottom-full mb-2" : "top-full mt-2"
          }`}
        >
          <Option active={all} onClick={() => onChange([])} title="All sources" detail={`${usable.length} enabled`}>
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-tide/10 text-tide">
              <Layers size={17} />
            </span>
          </Option>
          <div className="my-1 border-t border-line" />
          <div className="max-h-72 overflow-y-auto">
            {usable.map((source) => (
              <Option
                key={source.id}
                active={!all && selected.includes(source.id)}
                onClick={() => toggle(source.id)}
                title={source.name}
                detail={source.status === "error" ? "Needs attention" : sourceLabel(source.source_type)}
                warn={source.status === "error"}
              >
                <SourceIcon type={source.source_type} />
              </Option>
            ))}
          </div>
          <div className="mt-1 flex items-center justify-between gap-3 border-t border-line px-2 pt-2 text-xs text-muted">
            <span>Pick one or more. Turned-off sources are hidden.</span>
            <Link href="/sources" className="font-semibold text-tide">
              Manage
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Option({
  active,
  onClick,
  title,
  detail,
  warn,
  children,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  detail: string;
  warn?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-xl px-2 py-1.5 text-left ${active ? "bg-tide/8" : "hover:bg-paper"}`}
    >
      {children}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold" title={title}>
          {title}
        </span>
        <span className={`block text-xs ${warn ? "text-bad" : "text-muted"}`}>{detail}</span>
      </span>
      <span
        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${
          active ? "border-tide bg-tide text-white" : "border-line bg-white"
        }`}
      >
        {active ? <Check size={12} strokeWidth={3} /> : null}
      </span>
    </button>
  );
}
