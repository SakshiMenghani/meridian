export function StatusPill({ status }: { status: string }) {
  const styles =
    status === "healthy" || status === "ok"
      ? "bg-good/10 text-good"
      : status === "error"
        ? "bg-bad/10 text-bad"
        : "bg-warn/10 text-warn";
  const label = status === "healthy" ? "Healthy" : status === "error" ? "Needs attention" : status === "ok" ? "OK" : "Unknown";
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${styles}`}>{label}</span>;
}
