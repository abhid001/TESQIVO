export interface DraftStep {
  action: string;
  expected_result: string;
  is_required: boolean;
}

export function StepEditor({
  steps,
  onChange,
}: {
  steps: DraftStep[];
  onChange: (s: DraftStep[]) => void;
}) {
  const update = (i: number, patch: Partial<DraftStep>) =>
    onChange(steps.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= steps.length) return;
    const next = [...steps];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  };

  return (
    <div className="step-editor">
      <span className="field-label">Steps</span>
      <div className="stack">
        {steps.map((s, i) => (
          <div key={i} className="step-row">
            <div className="step-row-head">
              <strong>Step {i + 1}</strong>
              <div className="inline-actions">
                <button type="button" className="sm" onClick={() => move(i, -1)} disabled={i === 0} aria-label="Move up">
                  ↑
                </button>
                <button type="button" className="sm" onClick={() => move(i, 1)} disabled={i === steps.length - 1} aria-label="Move down">
                  ↓
                </button>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={s.is_required}
                    onChange={(e) => update(i, { is_required: e.target.checked })}
                  />
                  required
                </label>
                <button
                  type="button"
                  className="sm ghost"
                  style={{ color: "var(--danger)" }}
                  onClick={() => onChange(steps.filter((_, idx) => idx !== i))}
                  disabled={steps.length === 1}
                >
                  Remove
                </button>
              </div>
            </div>
            <input
              placeholder="Action — what the tester does"
              value={s.action}
              onChange={(e) => update(i, { action: e.target.value })}
            />
            <input
              placeholder="Expected result"
              value={s.expected_result}
              onChange={(e) => update(i, { expected_result: e.target.value })}
            />
          </div>
        ))}
      </div>
      <button
        type="button"
        className="sm"
        style={{ marginTop: 10 }}
        onClick={() => onChange([...steps, { action: "", expected_result: "", is_required: true }])}
      >
        + Add step
      </button>
    </div>
  );
}
