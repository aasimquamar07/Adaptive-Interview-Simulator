import { Link } from "react-router-dom";
import { TrendChart } from "../components/TrendChart";
import { ButtonLink, EmptyState, ErrorNote, Meter, PageLoader, Pill, SectionTitle } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, score1, scoreTone, TYPE_LABEL } from "../lib/format";
import type { Overview } from "../lib/types";
import { useLoad } from "../lib/useLoad";

export default function Dashboard() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useLoad(() => api<Overview>("/analytics/overview"));
  const first = (user?.full_name || "").split(" ")[0];

  if (loading) return <PageLoader />;
  if (error || !data) return <ErrorNote message={error ?? "Couldn't load your dashboard."} onRetry={reload} />;

  const delta = data.recent_average != null && data.previous_average != null ? +(data.recent_average - data.previous_average).toFixed(1) : null;

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold sm:text-4xl">{first ? `Hi ${first}` : "Your practice"}</h1>
          <p className="mt-1 text-muted">
            {data.total_sessions === 0 ? "Your first interview sets the baseline everything else builds on."
              : data.weak_topics.length ? `Next time, the interviewer will start with ${data.weak_topics[0].name}.`
              : data.top_recommendations.some((r) => r.priority < 3) ? `Next up: ${data.top_recommendations.find((r) => r.priority < 3)!.name}, from your last interview.`
              : "No weak topics on record. Try a harder difficulty next."}
          </p>
        </div>
        <div className="flex gap-2">
          {data.active_session_id && <ButtonLink to={`/interview/${data.active_session_id}`} variant="secondary">Resume interview</ButtonLink>}
          <ButtonLink to="/interview/new">Start an interview</ButtonLink>
        </div>
      </div>

      {data.total_sessions === 0 ? (
        <EmptyState title="No interviews yet"
          body="Pick a role and interview type. It takes about two minutes to set up, and you can end early at any time."
          action={<ButtonLink to="/interview/new">Set up your first interview</ButtonLink>} />
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-5 border-y border-line py-6 md:grid-cols-4">
            <div><dt className="text-muted">Interviews completed</dt><dd className="font-display text-3xl font-extrabold">{data.total_sessions}</dd></div>
            <div><dt className="text-muted">Average score</dt><dd className="font-display text-3xl font-extrabold">{score1(data.average_score)}<span className="text-lg text-muted">/10</span></dd></div>
            <div>
              <dt className="text-muted">Last 5 vs previous 5</dt>
              <dd className="font-display text-3xl font-extrabold">
                {delta == null ? "–" : <span className={delta >= 0 ? "text-accent" : "text-bad"}>{delta >= 0 ? "+" : ""}{delta}</span>}
              </dd>
            </div>
            <div><dt className="text-muted">Answers given</dt><dd className="font-display text-3xl font-extrabold">{data.questions_answered}</dd></div>
          </dl>

          <div className="grid gap-10 lg:grid-cols-[1.5fr_1fr]">
            <section>
              <SectionTitle aside={<Link to="/history" className="text-sm font-bold text-accent">All sessions</Link>}>Score trend</SectionTitle>
              <div className="rounded-xl border border-line bg-surface p-4">
                {data.trend.length > 1 ? <TrendChart data={data.trend} /> :
                  <p className="py-16 text-center text-muted">Complete one more interview to see a trend.</p>}
              </div>
            </section>
            <section>
              <SectionTitle aside={<Link to="/roadmap" className="text-sm font-bold text-accent">Roadmap</Link>}>Focus next</SectionTitle>
              {data.top_recommendations.length ? (
                <ol className="space-y-3">
                  {data.top_recommendations.map((r) => (
                    <li key={r.id} className="rounded-xl border border-line bg-surface p-4">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold">{r.name}</span>
                        <Pill tone={r.priority === 1 ? "bad" : r.priority === 2 ? "warn" : "info"}>
                          {r.priority === 1 ? "High priority" : r.priority === 2 ? "Medium" : "Stretch"}
                        </Pill>
                      </div>
                      <p className="mt-1 text-sm text-muted">{r.reason}</p>
                    </li>
                  ))}
                </ol>
              ) : <p className="text-muted">Nothing flagged yet.</p>}
            </section>
          </div>

          <div className="grid gap-10 lg:grid-cols-2">
            <section>
              <SectionTitle>Topic mastery</SectionTitle>
              <ul className="space-y-3">
                {data.mastery.slice(0, 8).map((m) => (
                  <li key={m.topic}>
                    <div className="mb-1 flex justify-between text-sm"><span className="font-bold">{m.name}</span><span className="text-muted">{m.label} · {m.attempts} {m.attempts === 1 ? "answer" : "answers"}</span></div>
                    <Meter value={m.mastery} max={1} label={`${m.name} mastery`} />
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-sm text-muted">Mastery is an AI estimate built from correctness and depth only, not from how confident you sounded.</p>
            </section>
            <section>
              <SectionTitle>Recent interviews</SectionTitle>
              <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
                {data.recent_sessions.map((s) => (
                  <li key={s.id}>
                    <Link to={s.status === "active" ? `/interview/${s.id}` : `/results/${s.id}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-surface-2">
                      <span>
                        <span className="block font-bold">{s.role_label}</span>
                        <span className="text-sm text-muted">{TYPE_LABEL[s.interview_type]} · {fmtDate(s.started_at)}</span>
                      </span>
                      {s.status === "active" ? <Pill tone="info">In progress</Pill> : <Pill tone={scoreTone(s.overall_score)}>{score1(s.overall_score)}</Pill>}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </>
      )}
    </div>
  );
}
