"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { SourceIcon } from "@/components/source-icon";
import { api } from "@/lib/api";
import type { Source } from "@/lib/types";

export default function MarketingPage() {
  const [sources, setSources] = useState<Source[] | null>(null);

  useEffect(() => {
    api<Source[]>("/api/sources")
      .then(setSources)
      .catch(() => setSources([]));
  }, []);

  const ads = sources?.find((source) => source.source_type === "google_ads");
  const analytics = sources?.find((source) => source.source_type === "google_analytics");

  return (
    <div>
      <Link href="/sources/new" className="text-sm font-semibold text-tide">
        ← Add a source
      </Link>
      <div className="mt-4">
        <PageHeader
          eyebrow="Marketing"
          title="Google Analytics and Google Ads"
          description="Sample Northline Outfitters data is ready to explore now. Live accounts plug into the same tools once credentials are added."
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card
          type="google_analytics"
          title="Google Analytics"
          body="Website sessions, channels and landing pages for the Northline Outfitters site."
          badge={sources === null ? "Checking…" : analytics ? "Sample connected" : "Not set up"}
          href={analytics ? `/chat?source=${analytics.id}` : "/sources"}
          action={analytics ? "Ask about traffic" : "See sources"}
          ready={Boolean(analytics)}
        />
        <Card
          type="google_ads"
          title="Google Ads"
          body="Campaign impressions, clicks, cost and conversions for the same August–September weeks."
          badge={sources === null ? "Checking…" : ads ? "Sample connected" : "Not set up"}
          href={ads ? `/chat?source=${ads.id}` : "/sources"}
          action={ads ? "Ask about campaigns" : "See sources"}
          ready={Boolean(ads)}
        />
        <Card
          type="spreadsheet"
          title="Upload a marketing export"
          body="Have a CSV or Excel export from Analytics, Ads or another tool? Upload it, review the columns, then ask questions."
          href="/transform"
          action="Upload a file"
          ready
        />
        <Card
          type="google_analytics"
          title="Connect a live account"
          body="Live GA4 properties and Ads accounts need credentials on the server. The connectors are registered and switch on once those are added."
          badge="Coming soon"
          href="/settings"
          action="See connector status"
          ready={false}
        />
      </div>
    </div>
  );
}

function Card({
  type,
  title,
  body,
  badge,
  href,
  action,
  ready,
}: {
  type: string;
  title: string;
  body: string;
  badge?: string;
  href: string;
  action: string;
  ready: boolean;
}) {
  return (
    <article className="card flex flex-col p-6">
      <div className="flex items-start justify-between gap-3">
        <SourceIcon type={type} size="lg" />
        {badge ? (
          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${ready ? "bg-good/10 text-good" : "bg-paper text-muted"}`}>{badge}</span>
        ) : null}
      </div>
      <h2 className="font-display mt-4 text-2xl">{title}</h2>
      <p className="mt-2 flex-1 text-sm leading-6 text-muted">{body}</p>
      <Link href={href} className={`btn mt-5 w-fit ${ready ? "btn-primary" : "btn-secondary"}`}>
        {action} <ArrowRight size={14} />
      </Link>
    </article>
  );
}
