import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Logo } from "../components/AppShell";
import { DemoBanner } from "../components/DemoBanner";
import { DifficultyLadder } from "../components/DifficultyLadder";
import { Button, ErrorNote, EstimateTag, Meter, PageLoader, Pill, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { fmtClock, KIND_LABEL, pct, TYPE_LABEL, VERDICT } from "../lib/format";
import type { Evaluation, SessionState, StepResult, TranscriptItem } from "../lib/types";
import { useSpeechToText, useTextToSpeech } from "../lib/useSpeech";

const draftKey = (qid: number) => `draft-${qid}`;
const loadDraft = (qid: number) => { try { return sessionStorage.getItem(draftKey(qid)) ?? ""; } catch { return ""; } };
const saveDraft = (qid: number, v: string) => { try { sessionStorage.setItem(draftKey(qid), v); } catch { /* ignore */ } };
const clearDraft = (qid: number) => { try { sessionStorage.removeItem(draftKey(qid)); } catch { /* ignore */ } };

function evaluatorLabel(e: string) {
  if (e.startsWith("llm:")) return "AI evaluator";
  if (e === "fallback-heuristic") return "Keyword rubric (AI was unavailable)";
  return "Keyword rubric (demo mode)";
}

function FeedbackBlock({ ev }: { ev: Evaluation }) {
  const v = VERDICT[ev.verdict];
  return (
    <div className="mt-3 rounded-xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone={v.tone}>{v.label}</Pill>
        <span className="font-display text-lg font-extrabold">{ev.score.toFixed(1)}<span className="text-sm font-normal text-muted">/10</span></span>
        <EstimateTag />
      </div>
      <dl className="mt-3 space-y-2 text-[15px]">
        <div><dt className="inline font-bold">Did well: </dt><dd className="inline">{ev.did_well}</dd></div>
        <div><dt className="inline font-bold">{ev.held_back ? "Missing: " : "Missing or incorrect: "}</dt><dd className={`inline ${ev.held_back ? "text-muted" : ""}`}>{ev.missing}</dd></div>
        {ev.improvement && <div><dt className="inline font-bold">Try: </dt><dd className="inline">{ev.improvement}</dd></div>}
      </dl>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-muted hover:text-ink">Score breakdown</summary>
        <div className="mt-3 grid gap-x-6 gap-y-2.5 sm:grid-cols-2">
          {([["Correctness", ev.correctness], ["Relevance", ev.relevance], ["Depth of understanding", ev.depth], ["Communication clarity", ev.clarity]] as const).map(([l, n]) => (
            <div key={l}><div className="mb-1 flex justify-between"><span>{l}</span><span className="text-muted">{n.toFixed(1)}</span></div><Meter value={n} label={l} /></div>
          ))}
        </div>
        <p className="mt-3 text-muted">
          {evaluatorLabel(ev.evaluator)} · evaluator confidence {pct(ev.confidence)} · {ev.topic_name} mastery now {pct(ev.mastery_estimate)}.
          Clarity is scored separately and doesn't affect mastery.
        </p>
      </details>
    </div>
  );
}

function PastTurn({ item }: { item: TranscriptItem }) {
  const q = item.question;
  return (
    <li className="border-b border-line pb-6">
      <p className="text-sm text-muted">Q{q.seq} · {KIND_LABEL[q.kind] ?? q.kind} · {q.topic_name}</p>
      <p className="mt-1 font-display text-lg font-bold leading-snug">{q.text}</p>
      {item.answer ? (
        <div className="ml-auto mt-3 max-w-[92%] whitespace-pre-wrap rounded-xl rounded-tr-sm bg-surface-2 px-4 py-3">{item.answer.text}</div>
      ) : q.status === "skipped" ? <p className="mt-2 text-sm text-muted">Skipped</p> : null}
      {item.evaluation && <FeedbackBlock ev={item.evaluation} />}
    </li>
  );
}

export default function InterviewRoom() {
  const { id } = useParams();
  const nav = useNavigate();
  const [s, setS] = useState<SessionState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState<null | "answer" | "skip" | "hint" | "repeat" | "end">(null);
  const [hints, setHints] = useState<string[]>([]);
  const [confirm, setConfirm] = useState<null | "skip" | "end">(null);
  const [now, setNow] = useState(Date.now());
  const [readAloud, setReadAloud] = useState(false);
  const [flash, setFlash] = useState(false);
  const shownAt = useRef(Date.now());
  const lastSpoken = useRef<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const usedVoice = useRef(false);

  const lang = s?.language ?? "en";
  const tts = useTextToSpeech(lang);
  const stt = useSpeechToText(lang, (t) => { usedVoice.current = true; setAnswer((a) => (a ? `${a} ${t}` : t)); });
  const q = s?.current_question ?? null;

  const load = useCallback(async () => {
    try {
      const data = await api<SessionState>(`/interviews/${id}`);
      if (data.status !== "active") { nav(`/results/${id}`, { replace: true }); return; }
      setS(data);
      setReadAloud(data.mode === "voice");
    } catch (e) { setError(e instanceof Error ? e.message : "Couldn't load this interview."); }
  }, [id, nav]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);

  // New question: restore its draft, reset per-question state, read it aloud in voice mode.
  useEffect(() => {
    if (!q) return;
    setAnswer(loadDraft(q.id));
    setHints([]);
    setConfirm(null);
    setActionError(null);
    shownAt.current = Date.now();
    usedVoice.current = false;
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    if (readAloud && tts.supported && lastSpoken.current !== q.id) {
      lastSpoken.current = q.id;
      tts.speak(`${q.acknowledgement ? q.acknowledgement + " " : ""}${q.text}`);
    }
  }, [q?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const remaining = s ? Math.max(0, Math.round((new Date(s.ends_at).getTime() - now) / 1000)) : 0;
  useEffect(() => {
    // Client timer hit zero: the server enforces the limit; re-fetch so it can close the session.
    if (s && remaining === 0) { const t = setTimeout(() => { void load(); }, 1500); return () => clearTimeout(t); }
  }, [remaining === 0]); // eslint-disable-line react-hooks/exhaustive-deps

  const applyStep = (r: StepResult) => {
    if (r.finished) { nav(`/results/${id}`, { replace: true }); return; }
    setS(r.session);
  };

  const run = async <T,>(kind: NonNullable<typeof busy>, fn: () => Promise<T>) => {
    setBusy(kind); setActionError(null);
    try { return await fn(); }
    catch (e) { setActionError(e instanceof Error ? e.message : "That didn't work. Please try again."); return undefined; }
    finally { setBusy(null); }
  };

  const submit = async () => {
    if (!q || !answer.trim() || busy) return;
    if (stt.listening) stt.stop();
    tts.cancel();
    const r = await run("answer", () => api<StepResult>(`/interviews/${id}/answer`, {
      method: "POST",
      json: { question_id: q.id, answer: answer.trim(), response_seconds: (Date.now() - shownAt.current) / 1000,
              input_mode: usedVoice.current ? "voice" : "text" },
    }));
    if (r) { clearDraft(q.id); applyStep(r); }
  };

  const skip = async () => {
    if (!q) return;
    if (confirm !== "skip") { setConfirm("skip"); return; }
    setConfirm(null);
    const r = await run("skip", () => api<StepResult>(`/interviews/${id}/skip`, { method: "POST", json: { question_id: q.id } }));
    if (r) { clearDraft(q.id); applyStep(r); }
  };

  const hint = async () => {
    if (!q) return;
    const r = await run("hint", () => api<{ hint: string; hints_used: number }>(`/interviews/${id}/hint`, { method: "POST", json: { question_id: q.id } }));
    if (r && s) {
      setHints((h) => [...h, r.hint]);
      setS({ ...s, current_question: { ...q, hints_used: r.hints_used } });
    }
  };

  const repeat = async () => {
    if (!q) return;
    await run("repeat", () => api(`/interviews/${id}/repeat`, { method: "POST", json: { question_id: q.id } }));
    setFlash(true); setTimeout(() => setFlash(false), 900);
    if (tts.supported) tts.speak(q.text);
  };

  const end = async () => {
    if (confirm !== "end") { setConfirm("end"); return; }
    const r = await run("end", () => api(`/interviews/${id}/end`, { method: "POST" }));
    if (r) nav(`/results/${id}`, { replace: true });
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void submit(); }
    if (e.key === "Tab" && q?.kind === "coding" && !e.shiftKey) {
      e.preventDefault();
      const t = e.currentTarget, st = t.selectionStart;
      const v = answer.slice(0, st) + "    " + answer.slice(t.selectionEnd);
      setAnswer(v);
      requestAnimationFrame(() => { t.selectionStart = t.selectionEnd = st + 4; });
    }
  };

  if (error) return <div className="mx-auto max-w-3xl p-6"><ErrorNote message={error} onRetry={load} /><Link to="/dashboard" className="mt-4 inline-block text-accent">Back to dashboard</Link></div>;
  if (!s) return <PageLoader label="Preparing your interviewer…" />;

  const past = s.transcript.filter((t) => t.question.status !== "pending");
  const lowTime = remaining <= 120;
  const isCode = q?.kind === "coding" || s.interview_type === "coding";
  const progress = Math.min(1, s.question_number / s.max_questions);
  const voiceMode = s.mode === "voice";

  return (
    <div className="min-h-screen">
      <DemoBanner compact />
      <header className="sticky top-0 z-10 border-b border-line bg-bg/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-4 gap-y-1.5 px-4 py-2.5 sm:gap-x-6 sm:py-3">
          <div className="hidden lg:block"><Logo to="/dashboard" /></div>
          <div className="hidden min-w-0 md:block">
            <p className="truncate font-bold">{s.role_label}</p>
            <p className="text-sm text-muted">{TYPE_LABEL[s.interview_type]}</p>
          </div>
          <div className="min-w-[8rem] flex-1 md:order-2">
            <p className="text-sm"><span className="font-bold">Question {s.question_number}</span> <span className="text-muted">of up to {s.max_questions}</span></p>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={s.question_number} aria-valuemin={0} aria-valuemax={s.max_questions} aria-label="Interview progress">
              <div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${progress * 100}%` }} />
            </div>
          </div>
                    <p className={`font-display text-xl font-extrabold tabular-nums md:order-4 ${remaining <= 30 ? "text-bad" : lowTime ? "text-warn" : ""}`}
             aria-label={`Time remaining ${fmtClock(remaining)}`} role="timer">{fmtClock(remaining)}</p>
          <Button variant={confirm === "end" ? "danger" : "secondary"} onClick={end} loading={busy === "end"} className="px-3 py-1.5 text-sm md:order-5">
            {confirm === "end" ? "Confirm end" : "End"}
          </Button>
          <div className="w-full sm:w-auto md:order-3"><DifficultyLadder level={q?.level ?? s.current_level} adaptive={s.difficulty_mode === "adaptive"} /></div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 pb-24 pt-8">
        {s.question_number === 1 && past.length === 0 && (
          <div className="mb-8 rounded-xl bg-surface-2 px-5 py-4 text-[15px]">
            <p>
              Hello! I'll be interviewing you for the <strong>{s.role_label}</strong> role. Answer as you would in a real interview;
              I'll follow up based on what you say. You can ask for a hint, hear a question again, or skip.
            </p>
            {(s.focus_topics.length > 0 || s.skill_topics.length > 0) && (
              <p className="mt-2 text-muted">
                {s.focus_topics.length > 0 && <>From your earlier sessions I'll revisit <strong className="text-ink">{s.focus_topics.join(", ")}</strong>. </>}
                {s.skill_topics.length > 0 && <>Your resume / job description points to <strong className="text-ink">{s.skill_topics.join(", ")}</strong>.</>}
              </p>
            )}
          </div>
        )}

        {past.length > 1 && (
          <details className="mb-6">
            <summary className="mb-4 cursor-pointer text-muted hover:text-ink">Earlier in this interview ({past.length - 1})</summary>
            <ol className="space-y-6">{past.slice(0, -1).map((t) => <PastTurn key={t.question.id} item={t} />)}</ol>
          </details>
        )}
        {past.length > 0 && (
          <ol className="mb-8" aria-label="Your last answer and feedback"><PastTurn item={past[past.length - 1]} /></ol>
        )}

        {q && (
          <section key={q.id} className="speak-in" aria-live="polite">
            {q.acknowledgement && <p className="text-muted">{q.acknowledgement}</p>}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Pill tone={q.kind === "diagnostic" ? "warn" : q.kind === "scenario" ? "info" : q.kind === "followup" ? "good" : "neutral"}>{KIND_LABEL[q.kind] ?? q.kind}</Pill>
              <span className="text-sm text-muted">{q.topic_name}</span>
            </div>
            <h1 className={`mt-3 font-display text-[1.65rem] font-bold leading-tight sm:text-[2rem] ${flash ? "rounded-lg bg-accent-soft" : ""} transition-colors`}>
              {q.text}
            </h1>
            <details className="mt-3 text-sm text-muted">
              <summary className="cursor-pointer hover:text-ink">Why this question?</summary>
              <p className="mt-1">{q.why}{q.source === "llm" ? " Written by the AI interviewer for this decision." : q.source === "fallback" ? " The AI was unavailable, so this came from the question bank." : ""}</p>
            </details>

            {hints.length > 0 && (
              <ul className="mt-4 space-y-2">
                {hints.map((h, i) => <li key={i} className="rounded-lg border-l-[3px] border-info bg-info-soft px-4 py-2.5 text-info"><strong>Hint {i + 1}:</strong> {h}</li>)}
              </ul>
            )}

            <div className="mt-6">
              <label htmlFor="answer" className="sr-only">Your answer</label>
              <textarea
                id="answer" value={answer} rows={isCode ? 10 : 6} onKeyDown={onKey} disabled={busy === "answer"}
                onChange={(e) => { setAnswer(e.target.value); saveDraft(q.id, e.target.value); }}
                placeholder={isCode ? "Explain your approach, then write the code. Mention complexity and edge cases." : voiceMode ? "Press the microphone and speak, or type here." : "Type your answer as you'd say it in the interview."}
                className={`w-full resize-y rounded-xl border border-line bg-surface px-4 py-3 focus:border-accent focus:outline-none ${isCode ? "font-mono text-[14px] leading-6" : "text-[16px]"}`}
              />
              {stt.listening && stt.interim && <p className="mt-1 text-sm italic text-muted">{stt.interim}</p>}
              {stt.error && <p className="mt-2 text-sm text-warn" role="alert">{stt.error}</p>}
              {actionError && <div className="mt-3"><ErrorNote message={actionError} /></div>}

              <div className="mt-3 flex flex-wrap items-center gap-2">
                {stt.supported ? (
                  <Button variant={stt.listening ? "danger" : "secondary"} onClick={stt.listening ? stt.stop : () => { stt.clearError(); stt.start(); }}
                          className={stt.listening ? "recording" : ""} aria-pressed={stt.listening}>
                    {stt.listening ? "Stop recording" : "Speak answer"}
                  </Button>
                ) : voiceMode ? <span className="text-sm text-muted">Voice input isn't available in this browser; please type.</span> : null}
                {tts.supported && (
                  <Button variant="ghost" onClick={() => { const v = !readAloud; setReadAloud(v); if (!v) tts.cancel(); else tts.speak(q.text); }} aria-pressed={readAloud}>
                    {readAloud ? "Read aloud: on" : "Read aloud: off"}
                  </Button>
                )}
                <span className="flex-1" />
                <Button variant="ghost" onClick={hint} loading={busy === "hint"} disabled={q.hints_used >= 2 || !!busy}>
                  Hint {q.hints_used > 0 ? `(${q.hints_used}/2)` : ""}
                </Button>
                <Button variant="ghost" onClick={repeat} loading={busy === "repeat"} disabled={!!busy}>Repeat</Button>
                <Button variant={confirm === "skip" ? "danger" : "ghost"} onClick={skip} loading={busy === "skip"} disabled={!!busy && busy !== "skip"}>
                  {confirm === "skip" ? "Confirm skip" : "Skip"}
                </Button>
                <Button onClick={submit} loading={busy === "answer"} disabled={!answer.trim() || (!!busy && busy !== "answer")} className="px-6">
                  Submit answer
                </Button>
              </div>
              <p className="mt-2 text-right text-xs text-muted">
                {confirm === "skip" ? "Skipping records this topic as a gap for your roadmap." : "Ctrl + Enter to submit"}
              </p>
            </div>
          </section>
        )}
        {busy === "answer" && (
          <div className="mt-6"><Spinner label="Evaluating your answer and choosing the next question…" /></div>
        )}
        <div ref={bottomRef} />
      </main>
    </div>
  );
}
