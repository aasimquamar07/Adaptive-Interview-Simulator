import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtShortDate } from "../lib/format";

type Row = Record<string, string | number | null | boolean | undefined>;

const SERIES: Record<string, { label: string; color: string; dash?: string }> = {
  score: { label: "Overall", color: "var(--accent)" },
  technical_knowledge: { label: "Technical", color: "var(--info)", dash: "5 4" },
  problem_solving: { label: "Problem solving", color: "var(--warn)", dash: "2 3" },
  communication: { label: "Communication", color: "var(--muted)", dash: "8 3" },
};

/** Score trend across the candidate's own sessions. Dashes distinguish series without relying on colour. */
export function TrendChart({ data, series = ["score"], height = 240 }: { data: Row[]; series?: string[]; height?: number }) {
  const rows = data.map((d, i) => ({ ...d, x: `${fmtShortDate(d.date as string)} #${i + 1}` }));
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="var(--line)" vertical={false} />
          <XAxis dataKey="x" tick={{ fill: "var(--muted)", fontSize: 12 }} tickLine={false} axisLine={{ stroke: "var(--line)" }} />
          <YAxis domain={[0, 10]} ticks={[0, 2.5, 5, 7.5, 10]} tick={{ fill: "var(--muted)", fontSize: 12 }} tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--ink)" }}
            formatter={(v: unknown, name: unknown) => [typeof v === "number" ? v.toFixed(1) : String(v), SERIES[String(name)]?.label ?? String(name)]}
          />
          {series.length > 1 && <Legend formatter={(v: string) => <span style={{ color: "var(--muted)" }}>{SERIES[v]?.label ?? v}</span>} />}
          {series.map((s) => (
            <Line key={s} type="monotone" dataKey={s} stroke={SERIES[s]?.color} strokeDasharray={SERIES[s]?.dash}
                  strokeWidth={s === "score" ? 2.5 : 1.75} dot={{ r: s === "score" ? 3.5 : 2.5 }} connectNulls isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
