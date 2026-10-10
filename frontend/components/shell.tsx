"use client";

import {
  Compass,
  Database,
  FileText,
  LayoutDashboard,
  MessageSquareText,
  Settings,
  Shuffle,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const links = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/sources", label: "Data sources", icon: Database },
  { href: "/chat", label: "Assistant", icon: MessageSquareText },
  { href: "/report", label: "Reports", icon: FileText },
  { href: "/transform", label: "Transform", icon: Shuffle },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]">
      <aside className="border-b border-white/10 bg-sidebar text-mist md:min-h-screen md:border-b-0 md:border-r">
        <div className="flex items-center gap-3 px-5 py-5">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-tide text-white">
            <Compass size={18} />
          </span>
          <div>
            <p className="font-display text-xl leading-none text-white">Meridian</p>
            <p className="mt-1 text-xs tracking-wide text-mist/70">Data workspace</p>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:px-3">
          {links.map((link) => {
            const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-2 rounded-full px-3 py-2 text-sm whitespace-nowrap md:rounded-lg ${
                  active ? "bg-white/10 text-white" : "text-mist/80 hover:bg-white/5 hover:text-white"
                }`}
              >
                <Icon size={16} />
                {link.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="px-5 py-8 md:px-10">{children}</main>
    </div>
  );
}
