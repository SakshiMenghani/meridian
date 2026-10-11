import type { ChartSpec } from "@/lib/types";

const COLORS = ["#0e6e68", "#c45c26", "#2b6cb0", "#8a5a12", "#5c4d7a", "#1c7a4d"];

export function ResultChart({
  spec,
  rows,
}: {
  spec: ChartSpec;
  rows: Record<string, unknown>[];
}) {
  const values = rows
    .map((row) => ({
      label: String(row[spec.category] ?? "—"),
      value: Number(row[spec.value] ?? 0),
    }))
    .filter((item) => Number.isFinite(item.value));
  if (values.length === 0) {
    return <p className="text-sm text-muted">This result does not have numbers to chart.</p>;
  }
  const max = Math.max(...values.map((item) => item.value), 1);
  const width = 640;
  const height = spec.type === "line" || spec.type === "pie" ? 280 : Math.max(160, values.length * 36);
  const left = 140;
  const right = width - 24;

  if (spec.type === "pie") {
    const total = values.reduce((sum, item) => sum + Math.max(item.value, 0), 0) || 1;
    let angle = -Math.PI / 2;
    const cx = 170;
    const cy = 130;
    const radius = 96;
    const slices = values.map((item, index) => {
      const share = Math.max(item.value, 0) / total;
      const start = angle;
      angle += share * Math.PI * 2;
      const large = share > 0.5 ? 1 : 0;
      const x1 = cx + radius * Math.cos(start);
      const y1 = cy + radius * Math.sin(start);
      const x2 = cx + radius * Math.cos(angle);
      const y2 = cy + radius * Math.sin(angle);
      return { ...item, color: COLORS[index % COLORS.length], d: `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${large} 1 ${x2} ${y2} Z`, share };
    });
    return (
      <figure>
        <svg viewBox={`0 0 ${width} 280`} className="w-full rounded-xl bg-paper" role="img" aria-label={spec.title}>
          {slices.map((slice) => (
            <path key={slice.label} d={slice.d} fill={slice.color} />
          ))}
          {slices.map((slice, index) => (
            <g key={`${slice.label}-legend`}>
              <rect x="320" y={28 + index * 28} width="12" height="12" rx="2" fill={slice.color} />
              <text x="340" y={38 + index * 28} className="fill-ink" fontSize="12">
                {slice.label.slice(0, 28)} · {(slice.share * 100).toFixed(1)}%
              </text>
            </g>
          ))}
        </svg>
        <figcaption className="mt-2 text-xs text-muted">{spec.title}</figcaption>
      </figure>
    );
  }

  if (spec.type === "line") {
    const points = values.map((item, index) => {
      const x = left + ((right - left) * index) / Math.max(values.length - 1, 1);
      const y = 28 + (180 * (max - item.value)) / max;
      return `${x},${y}`;
    });
    return (
      <figure>
        <svg viewBox={`0 0 ${width} 240`} className="w-full rounded-xl bg-paper" role="img" aria-label={spec.title}>
          <polyline fill="none" stroke="#0e6e68" strokeWidth="3" points={points.join(" ")} />
          {values.map((item, index) => {
            const [x, y] = points[index].split(",");
            return (
              <g key={item.label}>
                <circle cx={x} cy={y} r="4" fill="#0e6e68" />
                <text x={x} y="228" textAnchor="middle" className="fill-muted" fontSize="10">
                  {item.label.slice(0, 12)}
                </text>
              </g>
            );
          })}
        </svg>
        <figcaption className="mt-2 text-xs text-muted">{spec.title}</figcaption>
      </figure>
    );
  }

  return (
    <figure>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full rounded-xl bg-paper" role="img" aria-label={spec.title}>
        {values.map((item, index) => {
          const y = 12 + index * 36;
          const bar = ((right - left - 64) * item.value) / max;
          return (
            <g key={`${item.label}-${index}`}>
              <text x={left - 8} y={y + 14} textAnchor="end" className="fill-ink" fontSize="12">
                {item.label.slice(0, 22)}
              </text>
              <rect x={left} y={y} width={bar} height="20" rx="4" fill={COLORS[index % COLORS.length]} />
              <text x={left + bar + 8} y={y + 14} className="fill-muted" fontSize="11">
                {item.value.toLocaleString()}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="mt-2 text-xs text-muted">{spec.title}</figcaption>
    </figure>
  );
}
