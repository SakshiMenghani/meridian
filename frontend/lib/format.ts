export function formatWhen(value: string | null): string {
  if (!value) return "Not checked yet";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function sourceLabel(type: string): string {
  if (type === "postgresql") return "PostgreSQL";
  if (type === "mongodb") return "MongoDB";
  if (type === "spreadsheet") return "Spreadsheet";
  if (type === "google_ads") return "Google Ads";
  if (type === "google_analytics") return "Google Analytics";
  return type;
}

export function originLabel(origin: string): string {
  if (origin === "sample") return "Sample";
  if (origin === "upload") return "Upload";
  return "External";
}

export function connectionSummary(config: Record<string, string | number | boolean | null>): string {
  if (typeof config.customer_name === "string") {
    const origin = config.data_origin === "live" ? "live" : "sample";
    return `${config.customer_name} · ${origin}`;
  }
  if (typeof config.property_name === "string") {
    const origin = config.data_origin === "live" ? "live" : "sample";
    return `${config.property_name} · ${origin}`;
  }
  if (typeof config.original_name === "string") return config.original_name;
  const host = config.host ?? "";
  const port = config.port ?? "";
  const database = config.database ?? "";
  if (!host) return "File";
  return `${host}:${port}/${database}`;
}
