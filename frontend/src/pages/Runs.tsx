import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  api,
  date,
  duration,
  pct,
  terminal,
  useResource,
  type Email,
  type Metrics,
  type Run,
  type TraceEvent,
} from "../api";
import { Badge, EmailPanel, PageTitle, State, Trace } from "../ui";
export function RunPage() {
  const { id } = useParams();
  const detail = useResource<{ run: Run; email: Email; token: string }>(
    `/api/runs/${id}/detail`,
  );
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [status, setStatus] = useState("queued");
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    let seq = 0;
    const controller = new AbortController();
    setEvents([]);
    setError("");
    setStatus("queued");
    async function poll() {
      if (document.hidden) {
        timer = setTimeout(poll, 1500);
        return;
      }
      try {
        const result = await api<{ status: string; events: TraceEvent[] }>(
          `/api/runs/${id}/events?after_seq=${seq}`,
          { signal: controller.signal },
        );
        if (!alive) return;
        setStatus(result.status);
        setError("");
        setEvents((previous) =>
          [
            ...new Map(
              [...previous, ...result.events].map((e) => [e.seq, e]),
            ).values(),
          ].sort((a, b) => a.seq - b.seq),
        );
        seq = Math.max(seq, ...result.events.map((e) => e.seq));
        if (!terminal.has(result.status)) timer = setTimeout(poll, 1500);
      } catch (e) {
        if (alive) {
          setError((e as Error).message);
          timer = setTimeout(poll, 5000);
        }
      }
    }
    void poll();
    return () => {
      alive = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [id, retry]);
  return (
    <>
      <PageTitle number="03" title="Follow the correspondence.">
        <Badge status={status} />
      </PageTitle>
      <div className="run-layout">
        <div>
          {detail.loading || detail.error ? (
            <State
              loading={detail.loading}
              error={detail.error}
              retry={detail.reload}
            />
          ) : detail.data ? (
            <>
              <EmailPanel email={detail.data.email} />
              <div className="run-info">
                <span className="eyebrow">SYNTHETIC DEMO RUN #{id}</span>
                <p>
                  <Link to={`/t/${detail.data.token}`}>
                    {detail.data.token} · restricted case view ↗
                  </Link>
                </p>
                {terminal.has(status) && (
                  <Link
                    className="button"
                    to={`/review?run=${id}&status=${status === "escalated" ? "escalated" : "pending_review"}`}
                  >
                    Open review detail ↗
                  </Link>
                )}
              </div>
            </>
          ) : null}
        </div>
        <section className="trace-panel">
          <div className="section-heading">
            <h2>The paper trail.</h2>
            <span className="eyebrow">
              {terminal.has(status) ? "RECORDED TRACE" : "LIVE · POLLING 1.5 S"}
            </span>
          </div>
          {error && (
            <div className="error" role="alert">
              Connection interrupted: {error}{" "}
              <button onClick={() => setRetry((x) => x + 1)}>Reconnect</button>
            </div>
          )}
          {events.length ? (
            <Trace events={events} />
          ) : (
            <State
              empty={
                terminal.has(status)
                  ? "No events were recorded for this run."
                  : "Waiting for the worker to begin. Events appear here as they are persisted."
              }
            />
          )}
          <div className="trace-result">
            <Badge status={status} />
            <p>
              {status === "pending_review"
                ? "Draft prepared. A human decision is required."
                : status === "escalated"
                  ? "Human attention required. Inspect the recorded reason in review."
                  : status === "failed"
                    ? "This run could not complete. Inspect the trace for the failure."
                    : terminal.has(status)
                      ? "The run has finished. No reply was sent."
                      : "Processing continues while this tab is visible."}
            </p>
          </div>
        </section>
      </div>
    </>
  );
}
export function Dashboard() {
  const runs = useResource<{ items: Run[] }>("/api/runs?limit=50");
  const metrics = useResource<Metrics>("/api/metrics/summary");
  useEffect(() => {
    const timer = setInterval(() => {
      if (!document.hidden) {
        runs.reload();
        metrics.reload();
      }
    }, 15000);
    return () => clearInterval(timer);
  }, [runs.reload, metrics.reload]);
  return (
    <>
      <PageTitle number="04" title="The activity ledger.">
        <button
          onClick={() => {
            runs.reload();
            metrics.reload();
          }}
        >
          Refresh ↻
        </button>
      </PageTitle>
      {metrics.error ? (
        <State error={metrics.error} retry={metrics.reload} />
      ) : (
        <div className="metric-strip">
          {[
            ["Emails processed", metrics.data?.emails_processed ?? "—"],
            ["Escalated", pct(metrics.data?.escalation_rate)],
            ["Validator blocks", pct(metrics.data?.validator_block_rate)],
            ["Median duration", duration(metrics.data?.latency_ms.p50)],
          ].map(([label, value]) => (
            <div key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
              <small>{metrics.data?.window ?? "—"} window</small>
            </div>
          ))}
        </div>
      )}
      <div className="section-heading">
        <h2>Recent correspondence</h2>
        <span className="muted">
          Latest 50 runs · refreshes every 15 seconds
        </span>
      </div>
      {runs.loading || runs.error ? (
        <State loading={runs.loading} error={runs.error} retry={runs.reload} />
      ) : runs.data?.items.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Case / subject</th>
                <th>Category</th>
                <th>Confidence</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {runs.data.items.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link to={`/runs/${r.id}`}>
                      <code>{r.token || `RUN-${r.id}`}</code>
                      <strong>{r.subject || "Untitled email"}</strong>
                    </Link>
                  </td>
                  <td>{r.category || "—"}</td>
                  <td className="mono">{pct(r.confidence)}</td>
                  <td>
                    <Badge status={r.status} />
                  </td>
                  <td className="mono">{duration(r.duration_ms)}</td>
                  <td>{date(r.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <State empty="No runs yet. Submit a synthetic email to start the ledger." />
      )}
    </>
  );
}
type PublicCaseData = {
  token: string;
  status: string;
  created_at: string;
  emails: {
    subject: string;
    preview: string;
    received_at: string;
    direction: string;
  }[];
  runs: Run[];
};
export function PublicCase() {
  const { token } = useParams();
  const { data, error, loading, reload } = useResource<PublicCaseData>(
    `/api/cases/${encodeURIComponent(token || "")}`,
  );
  return (
    <>
      <PageTitle number="03" title="Your correspondence.">
        {data && <Badge status={data.status} />}
      </PageTitle>
      {loading || error ? (
        <State loading={loading} error={error} retry={reload} />
      ) : data ? (
        <div className="public-case">
          <span className="mono">{data.token}</span>
          <p className="muted">
            This link shows limited case information. Full messages, drafts and
            internal notes are restricted to the review workspace.
          </p>
          {data.emails.map((e, i) => (
            <article className="panel" key={i}>
              <span className="eyebrow">
                {e.direction} · {date(e.received_at)}
              </span>
              <h2>{e.subject}</h2>
              <p>{e.preview}</p>
            </article>
          ))}
          <h2>Processing history</h2>
          {data.runs.length ? (
            data.runs.map((r) => (
              <div className="policy-row" key={r.id}>
                <span className="mono">Run {r.id}</span>
                <span>{r.category || "Unclassified"}</span>
                <Badge status={r.status} />
                <span>{duration(r.duration_ms)}</span>
                {r.escalation_reason && (
                  <span>{r.escalation_reason.replaceAll("_", " ")}</span>
                )}
              </div>
            ))
          ) : (
            <State empty="Processing has not started." />
          )}
        </div>
      ) : null}
    </>
  );
}
