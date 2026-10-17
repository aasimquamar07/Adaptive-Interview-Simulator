const LABELS = ["Beginner", "Intermediate", "Advanced"];

/** Three rungs; the active rung shows the current difficulty. Moves as the adaptive engine adjusts. */
export function DifficultyLadder({ level, adaptive }: { level: number; adaptive: boolean }) {
  return (
    <div className="flex items-center gap-2" aria-label={`Difficulty: ${LABELS[level - 1]}${adaptive ? " (adaptive)" : ""}`}>
      <div className="flex items-end gap-[3px]" aria-hidden>
        {[1, 2, 3].map((r) => (
          <span key={r}
            className={`w-1.5 rounded-sm transition-all duration-500 ${r <= level ? "bg-accent" : "bg-line"}`}
            style={{ height: 6 + r * 4 }} />
        ))}
      </div>
      <span className="text-sm">
        <span className="font-bold">{LABELS[level - 1]}</span>
        {adaptive && <span className="text-muted"> · adaptive</span>}
      </span>
    </div>
  );
}
