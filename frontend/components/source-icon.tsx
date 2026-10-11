import { BarChart3, Database, FileSpreadsheet, Leaf, Megaphone, type LucideIcon } from "lucide-react";

const STYLES: Record<string, { icon: LucideIcon; tone: string }> = {
  postgresql: { icon: Database, tone: "bg-[#336791]/12 text-[#2a5579]" },
  mongodb: { icon: Leaf, tone: "bg-[#13aa52]/12 text-[#0f7d3d]" },
  spreadsheet: { icon: FileSpreadsheet, tone: "bg-[#1f7a4d]/12 text-[#1f6a45]" },
  google_ads: { icon: Megaphone, tone: "bg-[#c98a00]/14 text-[#8a5f00]" },
  google_analytics: { icon: BarChart3, tone: "bg-[#e37400]/12 text-[#a85500]" },
};

export function SourceIcon({ type, size = "md" }: { type: string; size?: "sm" | "md" | "lg" }) {
  const style = STYLES[type] ?? { icon: Database, tone: "bg-ink/10 text-ink" };
  const Icon = style.icon;
  const box = size === "sm" ? "h-6 w-6 rounded-md" : size === "lg" ? "h-11 w-11 rounded-xl" : "h-9 w-9 rounded-lg";
  const px = size === "sm" ? 13 : size === "lg" ? 20 : 17;
  return (
    <span className={`flex shrink-0 items-center justify-center ${box} ${style.tone}`} aria-hidden>
      <Icon size={px} />
    </span>
  );
}
