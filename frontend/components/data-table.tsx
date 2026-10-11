export function DataTable({ columns, rows }: { columns: string[]; rows: Record<string, unknown>[] }) {
  if (rows.length === 0) {
    return <p className="rounded-xl border border-dashed border-line px-4 py-6 text-center text-sm text-muted">No rows to show.</p>;
  }
  return (
    <div className="max-h-[32rem] overflow-auto rounded-xl border border-line">
      <table className="min-w-full text-left text-sm">
        <thead className="sticky top-0 z-10 bg-paper text-xs text-muted">
          <tr>
            {columns.map((column) => (
              <th key={column} className="px-3 py-2.5 font-semibold whitespace-nowrap">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-t border-line bg-panel hover:bg-paper/40">
              {columns.map((column) => {
                const value = row[column];
                const text = value == null || value === "" ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);
                const numeric = typeof value === "number";
                return (
                  <td key={column} className={`max-w-[22rem] min-w-[7rem] px-3 py-2 align-top text-ink ${numeric ? "text-right tabular-nums" : ""}`}>
                    <span className="line-clamp-3 break-words" title={text.length > 60 ? text : undefined}>
                      {numeric ? value.toLocaleString() : text}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
