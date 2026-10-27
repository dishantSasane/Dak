import { useState } from "react";
import { Link } from "react-router-dom";
import { date, pct, useResource } from "../api";
import { PageTitle, State } from "../ui";
type EvalRun = {
  id: number;
  started_at: string;
  corpus_version: string;
  model_triage: string;
  model_draft: string;
};
type Result = {
  email_id: number;
  run_id: number | null;
  subject: string;
  difficulty: string;
  expected_category: string;
  predicted_category: string | null;
  confidence: number | null;
  category_correct: boolean;
  route_correct: boolean;
};
type EvalMetrics = {
  error?: string;
  accuracy_overall: number | null;
  accuracy_by_difficulty: Record<string, number>;
  confusion_matrix: Record<string, Record<string, number>>;
  route_accuracy: number | null;
  escalation_precision: number | null;
  escalation_recall: number | null;
  out_of_scope_refusal_rate: number | null;
  calibration: {
    ece: number | null;
    bins: { range: string; predicted: number; observed: number; n: number }[];
  };
};
export function EvalPage() {
  const runs = useResource<{ items: EvalRun[] }>("/api/eval/runs");
  const [selected, setSelected] = useState("");
  const id = selected || String(runs.data?.items[0]?.id || "");
  return (
    <>
      <PageTitle number="05" title="Evidence over impressions.">
        {runs.data?.items.length ? (
          <label className="run-select">
            Corpus run{" "}
            <select value={id} onChange={(e) => setSelected(e.target.value)}>
              {runs.data.items.map((r) => (
                <option key={r.id} value={r.id}>
                  #{r.id} · {r.corpus_version} · {date(r.started_at)}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </PageTitle>
      <p className="page-intro">
        Recorded corpus evaluations. Difficulty splits expose where
        classification struggles; calibration shows whether confidence deserves
        trust.
      </p>
      {runs.loading || runs.error ? (
        <State loading={runs.loading} error={runs.error} retry={runs.reload} />
      ) : id ? (
        <EvalDetail
          key={id}
          id={id}
          run={runs.data?.items.find((r) => String(r.id) === id)}
        />
      ) : (
        <State empty="No evaluation runs have been recorded. Metrics and calibration appear after a labelled corpus run completes." />
      )}
    </>
  );
}
function EvalDetail({ id, run }: { id: string; run?: EvalRun }) {
  const metrics = useResource<EvalMetrics>(`/api/metrics/eval/${id}`);
  const results = useResource<{ items: Result[]; total: number }>(
    `/api/eval/runs/${id}/results`,
  );
  const [failures, setFailures] = useState(false);
  if (metrics.loading || metrics.error || !metrics.data)
    return (
      <State
        loading={metrics.loading}
        error={metrics.error}
        retry={metrics.reload}
      />
    );
  if (metrics.data.error) return <State empty={metrics.data.error} />;
  const m = metrics.data;
  const labels = [
    ...new Set([
      ...Object.keys(m.confusion_matrix),
      ...Object.values(m.confusion_matrix).flatMap(Object.keys),
    ]),
  ];
  const rows =
    results.data?.items.filter(
      (r) => !failures || !r.category_correct || !r.route_correct,
    ) || [];
  return (
    <>
      <div className="eval-provenance">
        <code>{run?.corpus_version}</code>
        <span>Triage: {run?.model_triage}</span>
        <span>Draft: {run?.model_draft}</span>
        <span>{results.data?.total ?? "—"} labelled emails</span>
      </div>
      <div className="metric-strip">
        <div>
          <span>Classification</span>
          <strong>{pct(m.accuracy_overall)}</strong>
          <small>overall accuracy</small>
        </div>
        {["easy", "medium", "hard"].map((d) => (
          <div key={d}>
            <span>{d} emails</span>
            <strong>{pct(m.accuracy_by_difficulty[d])}</strong>
            <small>classification accuracy</small>
          </div>
        ))}
      </div>
      <div className="eval-charts">
        <section className="panel">
          <span className="eyebrow">EXPECTED ↓ / PREDICTED →</span>
          <h2>Confusion matrix</h2>
          <div className="table-wrap">
            <table className="matrix">
              <thead>
                <tr>
                  <th>Category</th>
                  {labels.map((l) => (
                    <th key={l}>{l}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {labels.map((a) => (
                  <tr key={a}>
                    <th>{a}</th>
                    {labels.map((b) => (
                      <td key={b} className={a === b ? "diagonal" : ""}>
                        {m.confusion_matrix[a]?.[b] ?? 0}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className="panel">
          <div className="section-heading">
            <h2>Does confidence hold up?</h2>
            <span className="mono">
              ECE{" "}
              {m.calibration.ece == null ? "N/A" : m.calibration.ece.toFixed(3)}
            </span>
          </div>
          {m.calibration.bins.length ? (
            <svg
              viewBox="0 0 400 300"
              role="img"
              aria-label="Reliability diagram. Horizontal axis predicted confidence; vertical axis observed accuracy; circle sizes represent bin counts."
            >
              <line className="axis" x1="55" y1="245" x2="355" y2="245" />
              <line className="axis" x1="55" y1="245" x2="55" y2="35" />
              <line className="ideal" x1="55" y1="245" x2="355" y2="35" />
              {[0, 0.5, 1].map((v) => (
                <g key={v}>
                  <text x={55 + 300 * v} y="265" textAnchor="middle">
                    {v}
                  </text>
                  <text x="40" y={250 - 210 * v} textAnchor="end">
                    {v}
                  </text>
                </g>
              ))}
              {m.calibration.bins.map((b) => (
                <circle
                  className="calibration-point"
                  key={b.range}
                  cx={55 + b.predicted * 300}
                  cy={245 - b.observed * 210}
                  r={Math.min(18, 4 + Math.sqrt(b.n))}
                >
                  <title>
                    {b.range}: predicted {pct(b.predicted)}, observed{" "}
                    {pct(b.observed)}, n={b.n}
                  </title>
                </circle>
              ))}
              <text x="205" y="292" textAnchor="middle">
                Predicted confidence
              </text>
              <text
                transform="translate(14,140) rotate(-90)"
                textAnchor="middle"
              >
                Observed accuracy
              </text>
            </svg>
          ) : (
            <State empty="No confidence observations available." />
          )}
          <p className="muted">
            Dashed line: perfect calibration. Circle size: emails in each bin.
          </p>
        </section>
      </div>
      <div className="secondary-metrics">
        <span>
          Route accuracy <strong>{pct(m.route_accuracy)}</strong>
        </span>
        <span>
          Escalation precision <strong>{pct(m.escalation_precision)}</strong>
        </span>
        <span>
          Escalation recall <strong>{pct(m.escalation_recall)}</strong>
        </span>
        <span>
          Out-of-scope refusal{" "}
          <strong>{pct(m.out_of_scope_refusal_rate)}</strong>
        </span>
      </div>
      <div className="section-heading">
        <h2>Every email, accounted for.</h2>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={failures}
            onChange={(e) => setFailures(e.target.checked)}
          />
          Failures only
        </label>
      </div>
      {results.loading || results.error ? (
        <State
          loading={results.loading}
          error={results.error}
          retry={results.reload}
        />
      ) : rows.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Email</th>
                <th>Difficulty</th>
                <th>Expected</th>
                <th>Predicted</th>
                <th>Confidence</th>
                <th>Category / route</th>
                <th>Run</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.email_id}>
                  <td>{r.subject}</td>
                  <td>{r.difficulty}</td>
                  <td>{r.expected_category}</td>
                  <td>{r.predicted_category || "—"}</td>
                  <td className="mono">{pct(r.confidence)}</td>
                  <td>
                    {r.category_correct ? "✓" : "✕"} /{" "}
                    {r.route_correct ? "✓" : "✕"}
                  </td>
                  <td>
                    {r.run_id ? (
                      <Link to={`/runs/${r.run_id}`}>Trace ↗</Link>
                    ) : (
                      <span className="muted" title="No operational run linked">
                        No linked run
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <State
          empty={
            failures
              ? "No classification or routing failures in this run."
              : "No per-email results recorded."
          }
        />
      )}
    </>
  );
}
