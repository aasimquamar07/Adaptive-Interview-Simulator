import { useState } from "react";
import { Link } from "react-router-dom";
import { ButtonLink, EmptyState, ErrorNote, EstimateTag, Meter, PageLoader, Pill, SectionTitle } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate } from "../lib/format";
import type { MasteryRow, Recommendation } from "../lib/types";
import { useLoad } from "../lib/useLoad";

export default function Roadmap() {
  const { data, setData, error, loading, reload } = useLoad(() => api<{ recommendations: Recommendation[]; mastery: MasteryRow[] }>("/roadmap"));
  const [saving, setSaving] = useState<number | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  if (loading) return <PageLoader />;
  if (error || !data) return <ErrorNote message={error ?? "Couldn't load your roadmap."} onRetry={reload} />;

  const toggle = async (r: Recommendation) => {
    setSaving(r.id); setSaveError(null);
    try {
      const upd = await api<Recommendation>(`/roadmap/${r.id}`, { method: "PATCH", json: { status: r.status === "open" ? "done" : "open" } });
      setData({ ...data, recommendations: data.recommendations.map((x) => (x.id === r.id ? upd : x)) });
    } catch (e) { setSaveError(e instanceof Error ? e.message : "Couldn't save."); }
    finally { setSaving(null); }
  };

  const open = data.recommendations.filter((r) => r.status === "open");
  const done = data.recommendations.filter((r) => r.status === "done");
  const byCat = (c: string) => data.mastery.filter((m) => m.category === c);

  return (
    <div className="space-y-12">
      <div>
        <h1 className="text-3xl font-extrabold sm:text-4xl">Learning roadmap</h1>
        <p className="mt-1 max-w-2xl text-muted">Built from every interview you've done. Weak topics here are scheduled first in your next adaptive interview.</p>
      </div>

      {data.recommendations.length === 0 ? (
        <EmptyState title="Your roadmap is empty" body="Finish an interview and the topics you found hardest will appear here with study actions and practice questions."
          action={<ButtonLink to="/interview/new">Start an interview</ButtonLink>} />
      ) : (
        <section>
          <SectionTitle>To work on ({open.length})</SectionTitle>
          {saveError && <div className="mb-3"><ErrorNote message={saveError} /></div>}
          <ul className="space-y-4">
            {open.map((r) => (
              <li key={r.id} className="rounded-xl border border-line bg-surface p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2"><h3 className="text-lg font-bold">{r.name}</h3>
                      <Pill tone={r.priority === 1 ? "bad" : r.priority === 2 ? "warn" : "info"}>{r.priority === 1 ? "High priority" : r.priority === 2 ? "Medium" : "Stretch"}</Pill></div>
                    <p className="text-sm text-muted">{r.reason} {r.session_id && <>From <Link className="underline" to={`/results/${r.session_id}`}>the interview on {fmtDate(r.created_at)}</Link>.</>}</p>
                  </div>
                  <button onClick={() => toggle(r)} disabled={saving === r.id}
                          className="rounded-lg border border-line px-3 py-1.5 text-sm font-bold hover:border-accent hover:text-accent disabled:opacity-50">
                    Mark as practised
                  </button>
                </div>
                <ul className="mt-3 list-disc space-y-1 pl-5">{r.actions.map((a) => <li key={a}>{a}</li>)}</ul>
                {r.practice_questions.length > 0 && (
                  <div className="mt-3"><p className="font-bold">Practice questions</p>
                    <ul className="mt-1 list-disc pl-5 text-muted">{r.practice_questions.map((p) => <li key={p}>{p}</li>)}</ul></div>
                )}
              </li>
            ))}
          </ul>
          {done.length > 0 && (
            <details className="mt-6">
              <summary className="cursor-pointer text-muted">Practised ({done.length})</summary>
              <ul className="mt-3 space-y-2">
                {done.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-3 rounded-lg bg-surface-2 px-4 py-2.5">
                    <span className="line-through decoration-muted">{r.name}</span>
                    <button onClick={() => toggle(r)} className="text-sm text-muted underline">Reopen</button>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}

      {data.mastery.length > 0 && (
        <section>
          <SectionTitle aside={<EstimateTag />}>Topic mastery</SectionTitle>
          <div className="grid gap-10 md:grid-cols-2">
            {[["technical", "Technical"], ["coding", "Coding"], ["hr", "Behavioural"], ["project", "Projects"]].map(([c, label]) =>
              byCat(c).length ? (
                <div key={c}>
                  <h3 className="mb-3 font-bold text-muted">{label}</h3>
                  <ul className="space-y-3">
                    {byCat(c).map((m) => (
                      <li key={m.topic}>
                        <div className="mb-1 flex justify-between text-sm"><span className="font-bold">{m.name}</span><span className="text-muted">{m.label} · {m.correct}/{m.attempts} solid</span></div>
                        <Meter value={m.mastery} max={1} label={`${m.name} mastery`} />
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null)}
          </div>
        </section>
      )}
    </div>
  );
}
