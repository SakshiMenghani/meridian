"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import type { Source } from "@/lib/types";

export default function MarketingPage() {
  const [sources, setSources] = useState<Source[]>([]);

  useEffect(() => {
    api<Source[]>("/api/sources")
      .then(setSources)
      .catch(() => setSources([]));
  }, []);

  const ads = sources.find((source) => source.source_type === "google_ads");
  const analytics = sources.find((source) => source.source_type === "google_analytics");

  return (
    <div>
      <PageHeader
        eyebrow="Marketing"
        title="Attach Analytics and Ads"
        description="Connect Google Analytics or Google Ads. Sample Northline data is ready now. Live accounts use the same MCP tools once credentials are added."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card
          title="Google Analytics"
          body="Website sessions, channels, and landing pages. The sample property is Northline Outfitters site."
          href={analytics ? `/chat?source=${analytics.id}` : "/sources"}
          action={analytics ? "Open in assistant" : "Sample not seeded yet"}
          ready={Boolean(analytics)}
        />
        <Card
          title="Google Ads"
          body="Campaign impressions, clicks, and cost. The sample account matches the same August–September weeks."
          href={ads ? `/chat?source=${ads.id}` : "/sources"}
          action={ads ? "Open in assistant" : "Sample not seeded yet"}
          ready={Boolean(ads)}
        />
        <Card
          title="Upload a marketing export"
          body="Drop a Google Analytics or Ads CSV or Excel file. Review it, then ask questions or generate a report."
          href="/transform"
          action="Upload a file"
          ready
        />
        <Card
          title="Live Google Analytics"
          body="A live GA4 property needs a property id and credentials. That path is registered and left unwired, same as live Ads."
          href="/settings"
          action="See MCP registry"
          ready
        />
      </div>
    </div>
  );
}

function Card({
  title,
  body,
  href,
  action,
  ready,
}: {
  title: string;
  body: string;
  href: string;
  action: string;
  ready: boolean;
}) {
  return (
    <article className="rounded-3xl border border-line bg-panel p-6">
      <h2 className="font-display text-2xl">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-muted">{body}</p>
      <Link
        href={href}
        className={`mt-5 inline-flex rounded-full px-4 py-2 text-sm font-semibold ${ready ? "bg-tide text-white" : "bg-paper text-muted"}`}
      >
        {action}
      </Link>
    </article>
  );
}
