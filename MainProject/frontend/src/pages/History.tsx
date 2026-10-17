import { Link } from "react-router-dom";
import { TrendChart } from "../components/TrendChart";
import { ButtonLink, EmptyState, ErrorNote, PageLoader, Pill, SectionTitle } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate, score1, scoreTone, TYPE_LABEL } from "../lib/format";
import type { HistoryRow, Overview } from "../lib/types";
import { useLoad } from "../lib/useLoad";

export default function History() {
  const { data, error, loading, reload } = useLoad(() =>
    Promise.all([api<HistoryRow[]>("/interviews"), api<Overview>("/analytics/overview")]));

  if (loading) return <PageLoader />;
  if (error || !data) return <ErrorNote message={error ?? "Couldn't load your history."} onRetry={reload} />;
  const [rows, ov] = data;

  return (
    <div className="space-y-12">
      <div>
        <h1 className="text-3xl font-extrabold sm:text-4xl">History & progress</h1>
        <p className="mt-1 text-muted">Every interview you've done, compared only with your own earlier sessions.</p>
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No interviews yet" body="Once you finish an interview, your scores and trends show up here." action={<ButtonLink to="/interview/new">Start an interview</ButtonLink>} />
      ) : (
        <>
          <section>
            <SectionTitle>Progress by dimension</SectionTitle>
            <div className="rounded-xl border border-line bg-surface p-4">
              {ov.trend.length > 1
                ? <TrendChart data={ov.trend} series={["score", "technical_knowledge", "problem_solving", "communication"]} height={300} />
                : <p className="py-16 text-center text-muted">Two or more completed interviews are needed to show a trend.</p>}
            </div>
            <p className="mt-2 text-sm text-muted">All scores are AI estimates on a 0–10 scale.</p>
          </section>

          <section>
            <SectionTitle>All interviews</SectionTitle>
            <div className="overflow-x-auto rounded-xl border border-line bg-surface">
              <table className="w-full min-w-[640px] text-left">
                <thead className="border-b border-line text-sm text-muted">
                  <tr>{["Date", "Role", "Type", "Difficulty", "Questions", "Score", ""].map((h) => <th key={h} className="px-4 py-2.5 font-bold">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {rows.map((r) => (
                    <tr key={r.id} className="hover:bg-surface-2">
                      <td className="px-4 py-3 whitespace-nowrap">{fmtDate(r.started_at)}</td>
                      <td className="px-4 py-3 font-bold">{r.role_label}</td>
                      <td className="px-4 py-3">{TYPE_LABEL[r.interview_type]}</td>
                      <td className="px-4 py-3 capitalize">{r.difficulty_mode}</td>
                      <td className="px-4 py-3">{r.questions}</td>
                      <td className="px-4 py-3">{r.status === "active" ? <Pill tone="info">In progress</Pill> : <Pill tone={scoreTone(r.overall_score)}>{score1(r.overall_score)}</Pill>}</td>
                      <td className="px-4 py-3 text-right">
                        <Link className="font-bold text-accent" to={r.status === "active" ? `/interview/${r.id}` : `/results/${r.id}`}>{r.status === "active" ? "Resume" : "Report"}</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
