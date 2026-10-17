import { Link, useParams } from "react-router-dom";
import { TrendChart } from "../components/TrendChart";
import { ButtonLink, EmptyState, ErrorNote, EstimateTag, Meter, PageLoader, Pill, SectionTitle } from "../components/ui";
import { api } from "../lib/api";
import { DIMENSION_LABEL, END_REASON, fmtDate, fmtDuration, KIND_LABEL, pct, score1, scoreTone, TYPE_LABEL, VERDICT } from "../lib/format";
import type { Report, SessionState } from "../lib/types";
import { useLoad } from "../lib/useLoad";

function Delta({ v }: { v: number | null | undefined }) {
  if (v == null) return <span className="text-muted">–</span>;
  return <span className={v >= 0 ? "text-accent" : "text-bad"}>{v >= 0 ? "+" : ""}{v.toFixed(1)}</span>;
}

export default function Results() {
  const { id } = useParams();
  const { data, error, loading, reload } = useLoad(() => api<{ report: Report; session: SessionState }>(`/interviews/${id}/report`), [id]);

  if (loading) return <PageLoader label="Putting your report together…" />;
  if (error) return (
    <div className="space-y-4">
      <ErrorNote message={error} onRetry={reload} />
      {error.includes("in progress") && <ButtonLink to={`/interview/${id}`}>Return to the interview</ButtonLink>}
    </div>
  );
  if (!data?.report) return <EmptyState title="No report" body="This interview doesn't have a report yet." />;
  const { report: r, session: s } = data;
  const o = r.objective;
  const strengths = r.ai_strengths?.length ? r.ai_strengths : r.strengths;
  const weaknesses = r.ai_weaknesses?.length ? r.ai_weaknesses : r.weaknesses;

  return (
    <div className="space-y-12">
      <header>
        <p className="text-muted">{TYPE_LABEL[r.interview_type]} interview · {fmtDate(s.started_at)} · {END_REASON[r.ended_reason] ?? ""}</p>
        <h1 className="mt-1 text-3xl font-extrabold sm:text-4xl">{r.role}: your report</h1>
      </header>

      {r.overall_score == null ? (
        <EmptyState title="Nothing to score" body="No answers were submitted in this interview." action={<ButtonLink to="/interview/new">Start a new interview</ButtonLink>} />
      ) : (
        <>
          <section className="grid gap-8 lg:grid-cols-[auto_1fr]">
            <div className="flex flex-col items-start">
              <div className="flex items-baseline gap-1">
                <span className={`font-display text-7xl font-extrabold ${scoreTone(r.overall_score) === "good" ? "text-accent" : scoreTone(r.overall_score) === "warn" ? "text-warn" : "text-bad"}`}>{score1(r.overall_score)}</span>
                <span className="text-2xl text-muted">/10</span>
              </div>
              <span className="mt-1 flex items-center gap-2 text-muted">Overall <EstimateTag /></span>
              {r.comparison.delta_vs_last != null && (
                <p className="mt-2 text-sm">vs your last {r.comparison.basis === "same role" ? "session for this role" : "session"}: <Delta v={r.comparison.delta_vs_last} /></p>
              )}
            </div>
            <div>
              <p className="max-w-2xl text-lg">{r.summary}</p>
              {r.summary_source === "ai" && <p className="mt-1 text-sm text-muted">Summary written by the AI evaluator from your scored answers.</p>}
              <div className="mt-6 grid gap-x-8 gap-y-4 sm:grid-cols-2">
                {Object.entries(r.dimensions).map(([k, v]) => (
                  <div key={k}>
                    <div className="mb-1 flex justify-between"><span className="font-bold">{DIMENSION_LABEL[k] ?? k}</span>
                      <span>{score1(v)} {r.comparison.dimension_deltas[k] != null && <span className="text-sm">(<Delta v={r.comparison.dimension_deltas[k]} />)</span>}</span></div>
                    <Meter value={v} label={DIMENSION_LABEL[k] ?? k} />
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-line bg-surface p-5">
            <h2 className="text-lg font-bold">Measured directly</h2>
            <p className="text-sm text-muted">Counts and timings, not judgements. Everything else on this page marked as an estimate comes from the evaluator ({r.evaluators.map((e) => e.startsWith("llm:") ? "AI model" : "keyword rubric").filter((x, i, a) => a.indexOf(x) === i).join(" + ")}).</p>
            <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[["Questions asked", o.questions_asked], ["Answered", o.answered], ["Skipped", o.skipped], ["Hints used", o.hints_used],
                ["Follow-ups", o.follow_ups_asked], ["Topics covered", o.topics_covered], ["Duration", fmtDuration(o.duration_seconds)],
                ["Avg. answer length", o.avg_answer_words != null ? `${Math.round(o.avg_answer_words)} words` : "–"]].map(([l, v]) => (
                <div key={String(l)}><dt className="text-sm text-muted">{l}</dt><dd className="font-display text-2xl font-bold">{v}</dd></div>
              ))}
            </dl>
          </section>

          <div className="grid gap-10 lg:grid-cols-2">
            <section>
              <SectionTitle>Strengths</SectionTitle>
              {strengths.length ? <ul className="list-disc space-y-1.5 pl-5">{strengths.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-muted">No topic averaged 7.5 or above this time.</p>}
            </section>
            <section>
              <SectionTitle>Weaknesses</SectionTitle>
              {weaknesses.length ? <ul className="list-disc space-y-1.5 pl-5">{weaknesses.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-muted">No weak topics this session.</p>}
            </section>
          </div>

          <section>
            <SectionTitle aside={<EstimateTag />}>Topic performance</SectionTitle>
            <div className="overflow-x-auto rounded-xl border border-line bg-surface">
              <table className="w-full min-w-[560px] text-left">
                <thead className="border-b border-line text-sm text-muted">
                  <tr><th className="px-4 py-2.5 font-bold">Topic</th><th className="px-4 py-2.5 font-bold">Questions</th><th className="px-4 py-2.5 font-bold">Avg. score</th><th className="px-4 py-2.5 font-bold">Mastery before → after</th></tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {r.topics.map((t) => (
                    <tr key={t.topic}>
                      <td className="px-4 py-3 font-bold">{t.name}</td>
                      <td className="px-4 py-3">{t.questions}{t.skipped ? <span className="text-muted"> ({t.skipped} skipped)</span> : ""}</td>
                      <td className="px-4 py-3"><Pill tone={scoreTone(t.avg_score)}>{score1(t.avg_score)}</Pill></td>
                      <td className="px-4 py-3">{t.mastery_before == null ? <span className="text-muted">new</span> : pct(t.mastery_before)} → <strong>{pct(t.mastery_after)}</strong> <span className="text-sm text-muted">{t.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {r.needs_review.length > 0 && (
            <section>
              <SectionTitle>Answers to revisit</SectionTitle>
              <ol className="space-y-4">
                {r.needs_review.map((n) => (
                  <li key={n.seq} className="rounded-xl border border-line bg-surface p-5">
                    <div className="flex flex-wrap items-center gap-2"><Pill tone={VERDICT[n.verdict]?.tone ?? "bad"}>{VERDICT[n.verdict]?.label ?? n.verdict}</Pill><span className="text-sm text-muted">Q{n.seq} · {n.topic} · {n.score.toFixed(1)}/10</span></div>
                    <p className="mt-2 font-display text-lg font-bold">{n.question}</p>
                    {n.answer && <p className="mt-2 whitespace-pre-wrap rounded-lg bg-surface-2 px-3 py-2 text-[15px]">{n.answer}</p>}
                    <p className="mt-3"><strong>Missing:</strong> {n.missing}</p>
                    <p className="mt-1"><strong>Try:</strong> {n.improvement}</p>
                    {n.strong_answer_covers.length > 0 && (
                      <div className="mt-3 text-[15px]"><strong>A strong answer covers:</strong>
                        <ul className="mt-1 list-disc pl-5 text-muted">{n.strong_answer_covers.map((c) => <li key={c}>{c}</li>)}</ul></div>
                    )}
                  </li>
                ))}
              </ol>
            </section>
          )}

          <section>
            <SectionTitle aside={<Link to="/roadmap" className="text-sm font-bold text-accent">Full roadmap</Link>}>Your learning roadmap</SectionTitle>
            <ol className="space-y-4">
              {r.roadmap.map((item, i) => (
                <li key={item.topic} className="flex gap-4">
                  <span className="font-display text-3xl font-extrabold text-accent" aria-hidden>{i + 1}</span>
                  <div className="flex-1 border-b border-line pb-4">
                    <div className="flex flex-wrap items-center gap-2"><h3 className="text-lg font-bold">{item.name}</h3>
                      <Pill tone={item.priority === 1 ? "bad" : item.priority === 2 ? "warn" : "info"}>{item.priority === 1 ? "High priority" : item.priority === 2 ? "Medium" : "Stretch"}</Pill></div>
                    <p className="text-muted">{item.reason}</p>
                    <ul className="mt-2 list-disc space-y-1 pl-5">{item.actions.map((a) => <li key={a}>{a}</li>)}</ul>
                    {item.practice_questions.length > 0 && (
                      <div className="mt-3"><p className="font-bold">Practice questions</p>
                        <ul className="mt-1 list-disc pl-5 text-muted">{item.practice_questions.map((p) => <li key={p}>{p}</li>)}</ul></div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
            {r.extra_practice.length > 0 && (
              <div className="mt-6"><p className="font-bold">More practice questions from the AI interviewer</p>
                <ul className="mt-1 list-disc pl-5 text-muted">{r.extra_practice.map((p) => <li key={p.question}>{p.question} <span className="text-sm">({p.topic})</span></li>)}</ul></div>
            )}
          </section>

          <section>
            <SectionTitle>Compared with your previous sessions</SectionTitle>
            {r.comparison.sessions_compared === 0 ? (
              <p className="text-muted">This is your first scored interview{r.comparison.basis === "none" ? "" : " for this role"}. Your next one will be compared against it.</p>
            ) : (
              <div className="grid gap-6 lg:grid-cols-[1fr_2fr]">
                <dl className="space-y-3">
                  <div><dt className="text-muted">Previous average ({r.comparison.sessions_compared} session{r.comparison.sessions_compared > 1 ? "s" : ""}, {r.comparison.basis})</dt><dd className="font-display text-2xl font-bold">{score1(r.comparison.previous_average)}</dd></div>
                  <div><dt className="text-muted">This session vs average</dt><dd className="font-display text-2xl font-bold"><Delta v={r.comparison.delta_vs_average} /></dd></div>
                </dl>
                <div className="rounded-xl border border-line bg-surface p-4"><TrendChart data={r.comparison.trend} height={200} /></div>
              </div>
            )}
          </section>
        </>
      )}

      <section>
        <details className="rounded-xl border border-line bg-surface p-5">
          <summary className="cursor-pointer font-bold">Full transcript ({s.transcript.length} questions)</summary>
          <ol className="mt-4 space-y-5">
            {s.transcript.map((t) => (
              <li key={t.question.id} className="border-b border-line pb-4">
                <p className="text-sm text-muted">Q{t.question.seq} · {KIND_LABEL[t.question.kind] ?? t.question.kind} · {t.question.topic_name} · {t.question.level_label}</p>
                <p className="font-bold">{t.question.text}</p>
                <p className="mt-1 whitespace-pre-wrap text-[15px]">{t.answer?.text ?? <span className="text-muted">{t.question.status === "skipped" ? "Skipped" : "Not answered"}</span>}</p>
                {t.evaluation && <p className="mt-1 text-sm text-muted">{t.evaluation.score.toFixed(1)}/10 · {t.evaluation.did_well}</p>}
              </li>
            ))}
          </ol>
        </details>
      </section>

      <p className="rounded-lg bg-surface-2 px-4 py-3 text-sm text-muted">{r.disclaimer}</p>
      <div className="flex flex-wrap gap-3">
        <ButtonLink to="/interview/new">Start another interview</ButtonLink>
        <ButtonLink to="/dashboard" variant="secondary">Back to dashboard</ButtonLink>
      </div>
    </div>
  );
}
