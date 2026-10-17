export const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";

export const fmtShortDate = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "";

export const fmtClock = (secs: number) => {
  const s = Math.max(0, Math.floor(secs));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

export const fmtDuration = (secs: number | null | undefined) => {
  if (secs == null) return "–";
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return m ? `${m} min ${s} s` : `${s} s`;
};

export const score1 = (n: number | null | undefined) => (n == null ? "–" : n.toFixed(1));

export const pct = (n: number | null | undefined) => (n == null ? "–" : `${Math.round(n * 100)}%`);

export const TYPE_LABEL: Record<string, string> = {
  technical: "Technical", hr: "HR / Behavioural", project: "Project-based", coding: "Coding", mixed: "Mixed",
};

export const KIND_LABEL: Record<string, string> = {
  core: "Opening question", followup: "Follow-up", diagnostic: "Diagnostic", scenario: "Scenario",
  behavioral: "Behavioural", project: "Project", coding: "Coding",
};

export const VERDICT: Record<string, { label: string; tone: "good" | "warn" | "bad" }> = {
  correct: { label: "Solid", tone: "good" },
  partial: { label: "Partly there", tone: "warn" },
  incorrect: { label: "Needs work", tone: "bad" },
  off_topic: { label: "Off target", tone: "bad" },
  skipped: { label: "Skipped", tone: "bad" },
};

export const scoreTone = (n: number | null | undefined): "good" | "warn" | "bad" =>
  n == null ? "warn" : n >= 7.5 ? "good" : n >= 5 ? "warn" : "bad";

export const DIMENSION_LABEL: Record<string, string> = {
  technical_knowledge: "Technical knowledge",
  problem_solving: "Problem solving",
  communication: "Communication",
  behavioral: "Behavioural answers",
};

export const END_REASON: Record<string, string> = {
  question_limit: "All planned questions were asked.",
  time: "The time limit was reached.",
  ended_by_candidate: "You ended the interview early.",
  abandoned: "This interview was closed when you started a new one.",
  completed: "Interview complete.",
};
