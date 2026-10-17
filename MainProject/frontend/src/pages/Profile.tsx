import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, ChoiceGroup, ErrorNote, Field, inputCls, PageLoader, Pill, SectionTitle } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate } from "../lib/format";
import type { Profile as P } from "../lib/types";

export default function Profile() {
  const { refreshUser, logout } = useAuth();
  const nav = useNavigate();
  const [p, setP] = useState<P | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<null | "history" | "account">(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api<P>("/profile").then(setP).catch((e) => setError(e.message)); }, []);
  if (error && !p) return <ErrorNote message={error} />;
  if (!p) return <PageLoader />;

  const act = async (key: string, fn: () => Promise<void>, ok: string) => {
    setBusy(key); setError(null); setStatus(null);
    try { await fn(); setStatus(ok); } catch (e) { setError(e instanceof Error ? e.message : "That didn't work."); }
    finally { setBusy(null); }
  };

  const save = () => act("save", async () => {
    setP(await api<P>("/profile", { method: "PUT", json: { full_name: p.full_name, target_role: p.target_role, experience_level: p.experience_level, preferred_language: p.preferred_language, resume_text: p.resume_text } }));
    await refreshUser();
  }, "Profile saved.");

  const uploadResume = (f: File) => act("upload", async () => {
    const fd = new FormData();
    fd.append("file", f);
    const r = await api<{ text: string; skills: string[] }>("/uploads/extract", { method: "POST", body: fd });
    setP({ ...p, resume_text: r.text, resume_skills: r.skills });
  }, "Resume text extracted. Save the profile to keep it.");

  const consent = (v: boolean) => act("consent", async () => {
    setP(await api<P>("/profile/consent", { method: "PUT", json: { training_consent: v } }));
  }, v ? "Thanks. You can withdraw consent at any time." : "Consent withdrawn. Your interviews won't be included in any training export.");

  const exportData = () => act("export", async () => {
    const data = await api<unknown>("/profile/export");
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "interview-room-data.json" });
    a.click();
    URL.revokeObjectURL(url);
  }, "Your data was downloaded.");

  const deleteHistory = () => {
    if (confirm !== "history") { setConfirm("history"); return; }
    setConfirm(null);
    void act("history", async () => { await api("/profile/history", { method: "DELETE" }); }, "All interviews, mastery and recommendations were deleted.");
  };

  const deleteAccount = () => {
    if (confirm !== "account") { setConfirm("account"); return; }
    void act("account", async () => { await api("/profile", { method: "DELETE" }); logout(); nav("/"); }, "Account deleted.");
  };

  return (
    <div className="max-w-3xl space-y-12">
      <div>
        <h1 className="text-3xl font-extrabold sm:text-4xl">Profile & privacy</h1>
        <p className="mt-1 text-muted">Signed in as {p.email}</p>
      </div>
      {status && <p role="status" className="rounded-lg bg-accent-soft px-4 py-3 text-accent">{status}</p>}
      {error && <ErrorNote message={error} />}

      <section className="space-y-5">
        <SectionTitle>Profile</SectionTitle>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Name" htmlFor="fn"><input id="fn" className={inputCls} value={p.full_name} onChange={(e) => setP({ ...p, full_name: e.target.value })} /></Field>
          <Field label="Target role" htmlFor="tr"><input id="tr" className={inputCls} value={p.target_role} onChange={(e) => setP({ ...p, target_role: e.target.value })} placeholder="e.g. Backend developer" /></Field>
          <Field label="Experience" htmlFor="ex">
            <select id="ex" className={inputCls} value={p.experience_level} onChange={(e) => setP({ ...p, experience_level: e.target.value })}>
              <option value="">Prefer not to say</option><option>Student / fresher</option><option>1–3 years</option><option>3–6 years</option><option>6+ years</option>
            </select>
          </Field>
          <Field label="Preferred language">
            <ChoiceGroup name="Preferred language" columns="grid-cols-2" value={p.preferred_language} onChange={(v) => setP({ ...p, preferred_language: v as "en" | "hi" })}
                         options={[{ value: "en", label: "English" }, { value: "hi", label: "हिन्दी" }]} />
          </Field>
        </div>
        <Field label="Saved resume" htmlFor="rs" hint="Used to personalise questions when you don't upload one for a specific interview.">
          <textarea id="rs" rows={5} className={`${inputCls} text-sm`} value={p.resume_text} onChange={(e) => setP({ ...p, resume_text: e.target.value })} placeholder="Paste your resume, or upload it" />
          <div className="flex flex-wrap items-center gap-3">
            <input ref={fileRef} type="file" accept=".pdf,.txt,.md" className="hidden" onChange={(e) => e.target.files?.[0] && uploadResume(e.target.files[0])} />
            <Button variant="secondary" className="py-1.5 text-sm" loading={busy === "upload"} onClick={() => fileRef.current?.click()}>Upload PDF or text</Button>
            {p.resume_skills.length > 0 && <span className="flex flex-wrap gap-1.5">{p.resume_skills.map((s) => <Pill key={s} tone="info">{s}</Pill>)}</span>}
          </div>
        </Field>
        <Button onClick={save} loading={busy === "save"}>Save profile</Button>
      </section>

      <section className="space-y-4">
        <SectionTitle>How your data is used</SectionTitle>
        <ul className="list-disc space-y-1.5 pl-5 text-muted">
          <li>Your answers and scores are stored so the interviewer can personalise future sessions for you. Nobody else can see them.</li>
          <li>The AI does not retrain itself from your answers. Personalisation comes from your saved topic mastery and history.</li>
          <li>When an AI provider is configured, your answers are sent to it for evaluation from our server; keys are never in your browser.</li>
        </ul>
        <div className="rounded-xl border border-line bg-surface p-5">
          <label className="flex items-start gap-3">
            <input type="checkbox" className="mt-1 h-5 w-5 accent-[var(--accent)]" checked={p.training_consent} disabled={busy === "consent"}
                   onChange={(e) => consent(e.target.checked)} />
            <span>
              <span className="font-bold">Allow my anonymised interviews to be used to improve future models</span>
              <span className="block text-sm text-muted">
                Off by default. If you opt in, a future, separately reviewed process may include your answers with your identity removed
                and emails/phone numbers redacted. Withdraw at any time.
                {p.training_consent && p.training_consent_at && ` Consent given on ${fmtDate(p.training_consent_at)}.`}
              </span>
            </span>
          </label>
        </div>
      </section>

      <section className="space-y-4">
        <SectionTitle>Your data</SectionTitle>
        <div className="flex flex-wrap gap-3">
          <Button variant="secondary" onClick={exportData} loading={busy === "export"}>Download my data (JSON)</Button>
          <Button variant="danger" onClick={deleteHistory} loading={busy === "history"}>{confirm === "history" ? "Confirm: delete all interviews" : "Delete interview history"}</Button>
          <Button variant="danger" onClick={deleteAccount} loading={busy === "account"}>{confirm === "account" ? "Confirm: delete my account" : "Delete account"}</Button>
        </div>
        {confirm && <p className="text-sm text-bad">This can't be undone. Click again to confirm, or <button className="underline" onClick={() => setConfirm(null)}>cancel</button>.</p>}
      </section>
    </div>
  );
}
