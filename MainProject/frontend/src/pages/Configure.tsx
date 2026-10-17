import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, ChoiceGroup, ErrorNote, Field, inputCls, PageLoader, Pill } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Profile, SessionState } from "../lib/types";
import { getRecognitionCtor } from "../lib/useSpeech";

type Upload = { text: string; skills: string[] };

const TYPE_NOTES: Record<string, string> = {
  technical: "Concepts and practical scenarios", hr: "Behavioural, STAR-style", project: "Deep-dive on your work",
  coding: "Problem solving and complexity", mixed: "A blend of everything",
};
const DIFF_NOTES: Record<string, string> = {
  beginner: "Fundamentals", intermediate: "Working knowledge", advanced: "Scenarios and trade-offs", adaptive: "Moves with your answers",
};

function DocInput({ id, label, hint, value, onChange }: { id: string; label: string; hint: string; value: Upload; onChange: (u: Upload) => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const upload = async (f: File) => {
    setBusy(true); setErr(null);
    const fd = new FormData();
    fd.append("file", f);
    try { onChange(await api<Upload>("/uploads/extract", { method: "POST", body: fd })); }
    catch (e) { setErr(e instanceof Error ? e.message : "Upload failed."); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  };
  return (
    <Field label={label} hint={hint} htmlFor={id}>
      <textarea id={id} rows={4} className={`${inputCls} resize-y text-sm`} placeholder="Paste text here, or upload a file"
                value={value.text} onChange={(e) => onChange({ text: e.target.value, skills: value.skills })} />
      <div className="flex flex-wrap items-center gap-3">
        <input ref={fileRef} type="file" accept=".pdf,.txt,.md" className="hidden" id={`${id}-file`}
               onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        <Button type="button" variant="secondary" loading={busy} onClick={() => fileRef.current?.click()} className="py-1.5 text-sm">
          Upload PDF or text
        </Button>
        {value.text && <button type="button" className="text-sm text-muted underline" onClick={() => onChange({ text: "", skills: [] })}>Clear</button>}
        {value.skills.length > 0 && <span className="flex flex-wrap gap-1.5">{value.skills.slice(0, 8).map((s) => <Pill key={s} tone="info">{s}</Pill>)}</span>}
      </div>
      {err && <p className="text-sm text-bad" role="alert">{err}</p>}
    </Field>
  );
}

export default function Configure() {
  const { meta } = useAuth();
  const nav = useNavigate();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [role, setRole] = useState("java_developer");
  const [customRole, setCustomRole] = useState("");
  const [type, setType] = useState("technical");
  const [difficulty, setDifficulty] = useState("adaptive");
  const [duration, setDuration] = useState(20);
  const [num, setNum] = useState(8);
  const [language, setLanguage] = useState<"en" | "hi">("en");
  const [mode, setMode] = useState<"text" | "voice">("text");
  const [resume, setResume] = useState<Upload>({ text: "", skills: [] });
  const [jd, setJd] = useState<Upload>({ text: "", skills: [] });
  const [useProfileResume, setUseProfileResume] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const voiceSupported = !!getRecognitionCtor();

  useEffect(() => {
    api<Profile>("/profile").then((p) => { setProfile(p); setLanguage(p.preferred_language); }).catch(() => setProfile(null));
  }, []);

  if (!meta) return <PageLoader />;

  // Rough guide: ~2.5 minutes per question incl. follow-ups.
  const fits = Math.floor(duration / 2.5);
  const start = async () => {
    setError(null);
    if (role === "custom" && !customRole.trim()) { setError("Enter the role you're preparing for."); return; }
    setBusy(true);
    try {
      const s = await api<SessionState>("/interviews", {
        method: "POST",
        json: { role, custom_role: customRole, interview_type: type, difficulty, duration_minutes: duration,
                num_questions: num, language, mode, resume_text: resume.text, job_description: jd.text,
                use_profile_resume: useProfileResume },
      });
      nav(`/interview/${s.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start the interview.");
      setBusy(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <h1 className="text-3xl font-extrabold sm:text-4xl">Set up an interview</h1>
      <p className="mt-1 text-muted">The interviewer adapts from the first answer; these settings set the starting point and the limits.</p>

      <div className="mt-8 space-y-8">
        <Field label="Role">
          <ChoiceGroup name="Role" value={role} onChange={setRole} options={meta.roles.map((r) => ({ value: r.value, label: r.label }))} />
          {role === "custom" && (
            <input aria-label="Custom role name" className={`${inputCls} mt-2`} placeholder="e.g. React Native developer, DevOps engineer"
                   value={customRole} onChange={(e) => setCustomRole(e.target.value)} maxLength={120} />
          )}
        </Field>

        <Field label="Interview type">
          <ChoiceGroup name="Interview type" value={type} onChange={setType}
                       options={meta.interview_types.map((t) => ({ value: t.value, label: t.label, note: TYPE_NOTES[t.value] }))} />
        </Field>

        <Field label="Difficulty">
          <ChoiceGroup name="Difficulty" value={difficulty} onChange={setDifficulty} columns="grid-cols-2 sm:grid-cols-4"
                       options={meta.difficulties.map((d) => ({ value: d.value, label: d.label, note: DIFF_NOTES[d.value] }))} />
        </Field>

        <div className="grid gap-8 sm:grid-cols-2">
          <Field label="Duration">
            <ChoiceGroup name="Duration" value={duration} onChange={setDuration} columns="grid-cols-4"
                         options={meta.durations.map((d) => ({ value: d, label: `${d} min` }))} />
          </Field>
          <Field label={`Questions: ${num}`} htmlFor="num" hint={num > fits ? `That's a lot for ${duration} minutes. The timer may end the interview first.` : "Follow-ups count toward this number."}>
            <input id="num" type="range" min={3} max={20} value={num} onChange={(e) => setNum(+e.target.value)} className="w-full accent-[var(--accent)]" />
          </Field>
        </div>

        <div className="grid gap-8 sm:grid-cols-2">
          <Field label="Language">
            <ChoiceGroup name="Language" value={language} onChange={(v) => setLanguage(v as "en" | "hi")} columns="grid-cols-2"
                         options={meta.languages.map((l) => ({ value: l.value, label: l.label }))} />
          </Field>
          <Field label="Answer by" hint={mode === "voice" && !voiceSupported ? "This browser has no speech recognition; you'll be able to type instead." : undefined}>
            <ChoiceGroup name="Answer by" value={mode} onChange={(v) => setMode(v as "text" | "voice")} columns="grid-cols-2"
                         options={[{ value: "text", label: "Typing" }, { value: "voice", label: "Voice", note: "Questions read aloud" }]} />
          </Field>
        </div>
        {language === "hi" && meta.demo_mode && (
          <p className="rounded-lg bg-info-soft px-4 py-3 text-sm text-info">
            In demo mode the question bank is in English with Hindi transitions. Full Hindi questions and feedback need an LLM key on the server. You can answer in Hindi or Hinglish either way.
          </p>
        )}

        <details className="rounded-xl border border-line bg-surface p-5" open={!!(resume.text || jd.text)}>
          <summary className="cursor-pointer font-bold">Resume and job description <span className="font-normal text-muted">(optional)</span></summary>
          <div className="mt-5 space-y-6">
            <DocInput id="resume" label="Resume" hint="Skills and projects shape which topics come up. Used for this interview only unless you save it in your profile."
                      value={resume} onChange={setResume} />
            {!resume.text && profile?.resume_text && (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={useProfileResume} onChange={(e) => setUseProfileResume(e.target.checked)} className="accent-[var(--accent)]" />
                Use the resume saved in my profile ({profile.resume_skills.slice(0, 4).join(", ") || "no skills detected"})
              </label>
            )}
            <DocInput id="jd" label="Job description" hint="Questions lean toward the skills this role asks for." value={jd} onChange={setJd} />
          </div>
        </details>

        {error && <ErrorNote message={error} />}
        <div className="flex flex-wrap items-center gap-4 border-t border-line pt-6">
          <Button onClick={start} loading={busy} className="px-6 py-3 text-base">Start interview</Button>
          <span className="text-sm text-muted">The timer starts with the first question.</span>
        </div>
      </div>
    </div>
  );
}
