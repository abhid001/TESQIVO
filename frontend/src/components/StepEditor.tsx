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
    <div>
      <label>Steps</label>
      <div className="stack">
        {steps.map((s, i) => (
          <div key={i} className="card" style={{ padding: 10 }}>
            <div className="row">
              <strong>#{i + 1}</strong>
              <button type="button" onClick={() => move(i, -1)} aria-label="Move up">
                ↑
              </button>
              <button type="button" onClick={() => move(i, 1)} aria-label="Move down">
                ↓
              </button>
              <label style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
                <input
                  type="checkbox"
                  style={{ width: "auto" }}
                  checked={s.is_required}
                  onChange={(e) => update(i, { is_required: e.target.checked })}
                />
                required
              </label>
              <button
                type="button"
                className="danger"
                onClick={() => onChange(steps.filter((_, idx) => idx !== i))}
              >
                Remove
              </button>
            </div>
            <input
              placeholder="Action"
              value={s.action}
              onChange={(e) => update(i, { action: e.target.value })}
            />
            <input
              placeholder="Expected result"
              style={{ marginTop: 6 }}
              value={s.expected_result}
              onChange={(e) => update(i, { expected_result: e.target.value })}
            />
          </div>
        ))}
      </div>
      <button
        type="button"
        style={{ marginTop: 8 }}
        onClick={() => onChange([...steps, { action: "", expected_result: "", is_required: true }])}
      >
        Add step
      </button>
    </div>
  );
}
