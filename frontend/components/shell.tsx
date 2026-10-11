"use client";

import {
  Compass,
  Database,
  FileText,
  FileUp,
  LayoutDashboard,
  Link2,
  MessageSquareText,
  Settings,
  Sparkles,
  WifiOff,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import type { Meta } from "@/lib/types";

const groups = [
  { label: null, links: [{ href: "/", label: "Dashboard", icon: LayoutDashboard }] },
  {
    label: "Your data",
    links: [
      { href: "/sources", label: "Data sources", icon: Database },
      { href: "/transform", label: "Upload a file", icon: FileUp },
      { href: "/links", label: "Links", icon: Link2 },
    ],
  },
  {
    label: "Insights",
    links: [
      { href: "/chat", label: "Ask", icon: MessageSquareText },
      { href: "/report", label: "Reports", icon: FileText },
    ],
  },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    api<Meta>("/api/meta").then(setMeta).catch(() => setMeta(null));
  }, []);

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <div className="min-h-screen md:grid md:grid-cols-[232px_1fr]">
      <aside className="border-b border-white/10 bg-sidebar text-mist md:sticky md:top-0 md:flex md:h-screen md:flex-col md:border-r md:border-b-0">
        <Link href="/" className="flex items-center gap-3 px-5 pt-5 pb-4">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-tide text-white">
            <Compass size={18} />
          </span>
          <span>
            <span className="font-display block text-xl leading-none text-white">Meridian</span>
            <span className="mt-1 block text-xs tracking-wide text-mist/60">Data workspace</span>
          </span>
        </Link>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:gap-0 md:overflow-visible">
          {groups.map((group) => (
            <div key={group.label ?? "top"} className="flex gap-1 md:mb-4 md:flex-col">
              {group.label ? (
                <p className="hidden px-3 pt-1 pb-1.5 text-[11px] font-semibold tracking-[0.14em] text-mist/40 uppercase md:block">
                  {group.label}
                </p>
              ) : null}
              {group.links.map((link) => (
                <NavLink key={link.href} {...link} active={isActive(link.href)} />
              ))}
            </div>
          ))}
          <div className="flex gap-1 md:mt-auto md:flex-col">
            <NavLink href="/settings" label="Settings" icon={Settings} active={isActive("/settings")} />
          </div>
        </nav>
        {meta ? (
          <Link
            href="/settings"
            className="mx-3 mb-4 hidden items-start gap-2 rounded-xl border border-white/10 px-3 py-2.5 text-xs hover:bg-white/5 md:flex"
          >
            {meta.openai_configured ? (
              <Sparkles size={14} className="mt-0.5 shrink-0 text-[#7fd1c4]" />
            ) : (
              <WifiOff size={14} className="mt-0.5 shrink-0 text-[#e5b567]" />
            )}
            <span>
              <span className="block font-semibold text-white">{meta.openai_configured ? "AI planner on" : "Offline mode"}</span>
              <span className="block text-mist/60">
                {meta.openai_configured ? meta.openai_model : "Add an OpenAI key for open questions"}
              </span>
            </span>
          </Link>
        ) : null}
      </aside>
      <main className="min-w-0 px-5 py-8 md:px-10 md:py-10">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}

function NavLink({
  href,
  label,
  icon: Icon,
  active,
}: {
  href: string;
  label: string;
  icon: typeof Database;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`relative flex items-center gap-2.5 rounded-full px-3 py-2 text-sm whitespace-nowrap transition md:rounded-lg ${
        active ? "bg-white/10 font-semibold text-white" : "text-mist/75 hover:bg-white/5 hover:text-white"
      }`}
    >
      {active ? <span className="absolute top-2 bottom-2 left-0 hidden w-0.5 rounded-full bg-[#7fd1c4] md:block" /> : null}
      <Icon size={16} />
      {label}
    </Link>
  );
}
