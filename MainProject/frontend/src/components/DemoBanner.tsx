import { useAuth } from "../lib/auth";

export function DemoBanner({ compact }: { compact?: boolean }) {
  const { meta } = useAuth();
  if (!meta?.demo_mode) return null;
  return (
    <div role="note" className="border-b border-warn/30 bg-warn-soft text-warn">
      <p className={`mx-auto max-w-6xl px-4 ${compact ? "py-1.5 text-sm" : "py-2"}`}>
        <strong>Demo mode.</strong> No LLM API key is configured, so answers are scored by a transparent keyword
        rubric and questions come from the built-in bank. Add a key on the server for full AI evaluation.
      </p>
    </div>
  );
}
