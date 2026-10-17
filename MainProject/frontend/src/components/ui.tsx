import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";

type Variant = "primary" | "secondary" | "ghost" | "danger";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-ink hover:bg-accent-strong",
  secondary: "bg-surface text-ink border border-line hover:border-accent hover:text-accent",
  ghost: "text-muted hover:text-ink hover:bg-surface-2",
  danger: "bg-surface text-bad border border-bad/40 hover:bg-bad-soft",
};

export function Button({ variant = "primary", loading, className = "", children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-[15px] font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-55 ${VARIANTS[variant]} ${className}`}
    >
      {loading && <Spinner small />}
      {children}
    </button>
  );
}

export function ButtonLink({ to, variant = "primary", className = "", children }:
  { to: string; variant?: Variant; className?: string; children: ReactNode }) {
  return (
    <Link to={to} className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-[15px] font-bold transition-colors ${VARIANTS[variant]} ${className}`}>
      {children}
    </Link>
  );
}

export function Spinner({ small, label }: { small?: boolean; label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-muted">
      <span className={`${small ? "h-4 w-4 border-2" : "h-6 w-6 border-[3px]"} animate-spin rounded-full border-current border-t-transparent`} />
      {label && <span>{label}</span>}
      {!label && <span className="sr-only">Loading</span>}
    </span>
  );
}

export function PageLoader({ label = "Loading…" }: { label?: string }) {
  return <div className="flex min-h-[40vh] items-center justify-center"><Spinner label={label} /></div>;
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-bad/30 bg-bad-soft px-4 py-3 text-bad">
      <span className="flex-1">{message}</span>
      {onRetry && <button onClick={onRetry} className="font-bold underline underline-offset-2">Try again</button>}
    </div>
  );
}

export function Field({ label, hint, children, htmlFor }: { label: string; hint?: string; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block font-bold">{label}</label>
      {children}
      {hint && <p className="text-sm text-muted">{hint}</p>}
    </div>
  );
}

export const inputCls = "w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-ink placeholder:text-muted/70 focus:border-accent focus:outline-none";

/** Single-choice group rendered as selectable chips (radio semantics). */
export function ChoiceGroup<T extends string | number>({ name, options, value, onChange, columns }: {
  name: string; options: { value: T; label: string; note?: string }[]; value: T; onChange: (v: T) => void; columns?: string;
}) {
  return (
    <div role="radiogroup" aria-label={name} className={`grid gap-2 ${columns ?? "grid-cols-2 sm:grid-cols-3"}`}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            type="button" role="radio" aria-checked={active} key={String(o.value)} onClick={() => onChange(o.value)}
            className={`rounded-lg border px-3 py-2.5 text-left transition-colors ${active ? "border-accent bg-accent-soft text-ink" : "border-line bg-surface hover:border-muted"}`}
          >
            <span className="block font-bold">{o.label}</span>
            {o.note && <span className="block text-sm text-muted">{o.note}</span>}
          </button>
        );
      })}
    </div>
  );
}

const TONE: Record<string, string> = {
  good: "bg-accent-soft text-accent",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  info: "bg-info-soft text-info",
  neutral: "bg-surface-2 text-muted",
};

export function Pill({ tone = "neutral", children, className = "" }: { tone?: keyof typeof TONE; children: ReactNode; className?: string }) {
  return <span className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-sm font-bold ${TONE[tone]} ${className}`}>{children}</span>;
}

/** Horizontal meter for 0..1 or 0..10 values. */
export function Meter({ value, max = 10, tone, label }: { value: number | null; max?: number; tone?: "good" | "warn" | "bad"; label: string }) {
  const v = value == null ? 0 : Math.max(0, Math.min(1, value / max));
  const t = tone ?? (v >= 0.75 ? "good" : v >= 0.5 ? "warn" : "bad");
  const color = t === "good" ? "bg-accent" : t === "warn" ? "bg-warn" : "bg-bad";
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2" role="meter" aria-label={label}
         aria-valuenow={value ?? 0} aria-valuemin={0} aria-valuemax={max}>
      <div className={`h-full rounded-full ${color}`} style={{ width: `${v * 100}%` }} />
    </div>
  );
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-line px-6 py-10 text-center">
      <h3 className="text-xl font-bold">{title}</h3>
      <p className="mx-auto mt-2 max-w-md text-muted">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-4">
      <h2 className="text-xl font-bold">{children}</h2>
      {aside}
    </div>
  );
}

/** Tag that marks a number as an AI estimate (vs. a direct measurement). */
export function EstimateTag() {
  return (
    <span title="Generated by the evaluator; it can be wrong." className="rounded border border-line px-1.5 text-xs text-muted">
      AI estimate
    </span>
  );
}
