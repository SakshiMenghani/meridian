export function StatusPill({ status, enabled = true }: { status: string; enabled?: boolean }) {
  if (!enabled) {
    return <Pill tone="bg-ink/5 text-muted" dot="bg-muted/60" label="Off" />;
  }
  if (status === "healthy" || status === "ok") return <Pill tone="bg-good/10 text-good" dot="bg-good" label="Connected" />;
  if (status === "error") return <Pill tone="bg-bad/10 text-bad" dot="bg-bad" label="Needs attention" />;
  return <Pill tone="bg-warn/10 text-warn" dot="bg-warn" label="Not checked" />;
}

function Pill({ tone, dot, label }: { tone: string; dot: string; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold whitespace-nowrap ${tone}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
