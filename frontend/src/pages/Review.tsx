import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  api,
  date,
  pct,
  useResource,
  type QueueItem,
  type Review,
} from "../api";
import { Badge, EmailPanel, JsonDetail, PageTitle, State } from "../ui";
export function ReviewPage() {
  const [params, setParams] = useSearchParams();
  const status =
    params.get("status") === "escalated" ? "escalated" : "pending_review";
  const queue = useResource<{ items: QueueItem[]; total: number }>(
    `/api/review/queue?status=${status}`,
  );
  const selected = params.get("run");
  const id = selected ? Number(selected) : queue.data?.items[0]?.run_id;
  return (
    <>
      <PageTitle number="02" title="The review desk.">
        <div className="segmented">
          <button
            aria-pressed={status === "pending_review"}
            onClick={() => setParams({ status: "pending_review" })}
          >
            Drafts
          </button>
          <button
            aria-pressed={status === "escalated"}
            onClick={() => setParams({ status: "escalated" })}
          >
            Escalations
          </button>
          <button onClick={queue.reload}>Refresh ↻</button>
        </div>
      </PageTitle>
      <div className="review-layout">
        <aside className="queue">
          <div className="queue-heading">
            <span>AWAITING YOUR JUDGEMENT</span>
            <span>{queue.data?.total ?? "—"}</span>
          </div>
          {queue.loading || queue.error ? (
            <State
              loading={queue.loading}
              error={queue.error}
              retry={queue.reload}
            />
          ) : !queue.data?.items.length ? (
            <State empty="The desk is clear. New drafts appear here after triage." />
          ) : (
            queue.data.items.map((q) => (
              <button
                className={`queue-item ${id === q.run_id ? "selected" : ""}`}
                key={q.run_id}
                onClick={() => setParams({ status, run: String(q.run_id) })}
              >
                <div>
                  <Badge status={q.category} />
                  <span className="mono">{pct(q.confidence)}</span>
                </div>
                <strong>{q.subject}</strong>
                <span>{q.from}</span>
                <small>{date(q.waiting_since)}</small>
                {q.validation_passed === false && (
                  <span className="blocked-label">
                    Validator blocked an attempt
                  </span>
                )}
              </button>
            ))
          )}
        </aside>
        <section className="review-content" aria-label="Selected case">
          {id ? (
            <ReviewDetail
              key={id}
              id={id}
              onAction={() => {
                setParams({ status });
                queue.reload();
              }}
            />
          ) : (
            <State empty="Select a case when a draft is ready, or submit a synthetic email from Compose." />
          )}
        </section>
      </div>
    </>
  );
}
function ReviewDetail({ id, onAction }: { id: number; onAction: () => void }) {
  const { data, error, loading, reload } = useResource<Review>(
    `/api/review/${id}`,
  );
  const [cite, setCite] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [failure, setFailure] = useState("");
  const latest = data?.drafts.at(-1);
  useEffect(() => {
    setText(latest?.rendered_text ?? "");
  }, [latest?.rendered_text]);
  if (loading || error || !data)
    return <State loading={loading} error={error} retry={reload} />;
  async function act(action: "approved" | "edited" | "rejected") {
    setPending(true);
    setFailure("");
    try {
      await api(`/api/review/${id}/action`, {
        method: "POST",
        body: JSON.stringify({
          action,
          reviewer_note: note || null,
          edited_text: action === "edited" ? text : null,
        }),
      });
      setMessage("Decision recorded. No email was sent.");
      setTimeout(onAction, 1800);
    } catch (e) {
      setFailure((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  const actionable = ["pending_review", "escalated"].includes(data.run.status);
  return (
    <>
      <div className="detail-heading">
        <Badge status={data.run.status} />
        <Link to={`/runs/${id}`}>Open run trace ↗</Link>
      </div>
      <EmailPanel email={data.email} />
      <section className="assessment">
        <span className="eyebrow">TRIAGE ASSESSMENT</span>
        <div className="assessment-row">
          <h2>{data.run.category || "Unclassified"}</h2>
          <strong className="mono">{pct(data.run.confidence)}</strong>
        </div>
        <meter
          min="0"
          max="1"
          value={data.run.confidence ?? 0}
          aria-label="Triage confidence"
        />
        <p>
          {typeof data.triage.reasoning === "string"
            ? data.triage.reasoning
            : "The recorded assessment is available in the trace."}
        </p>
        <JsonDetail title="Assessment evidence" value={data.triage} />
      </section>
      {latest ? (
        <section className="draft-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                PROPOSED RESPONSE · ATTEMPT {latest.attempt}
              </span>
              <h2>A draft, with receipts.</h2>
            </div>
            <Badge status={latest.validation_passed ? "passed" : "blocked"} />
          </div>
          {editing ? (
            <>
              <label htmlFor="edited-draft">Edited response</label>
              <textarea
                id="edited-draft"
                rows={12}
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            </>
          ) : (
            <div className="draft-copy">
              {latest.sentences.length ? (
                latest.sentences.map((s, i) => (
                  <div key={i}>
                    <p>
                      {s.text}
                      {s.cite && (
                        <button
                          className="citation"
                          aria-expanded={cite === s.cite}
                          onClick={() =>
                            setCite(cite === s.cite ? null : s.cite)
                          }
                        >
                          {s.cite} ↗
                        </button>
                      )}
                    </p>
                    {s.cite && cite === s.cite && (
                      <aside className="clause">
                        <strong>
                          {data.citations.find((c) => c.clause_id === s.cite)
                            ?.clause_title || s.cite}
                        </strong>
                        <p>
                          {data.citations.find((c) => c.clause_id === s.cite)
                            ?.content ||
                            "Clause text unavailable. Inspect the trace before approving."}
                        </p>
                      </aside>
                    )}
                  </div>
                ))
              ) : (
                <p className="email-body">{latest.rendered_text}</p>
              )}
            </div>
          )}
          {latest.violations.length > 0 && (
            <JsonDetail
              title="Current validation violations"
              value={latest.violations}
            />
          )}
        </section>
      ) : (
        <State empty="No customer draft was produced. Review the escalation brief and recorded evidence." />
      )}
      {data.drafts.slice(0, -1).map((d) => (
        <details className="blocked-attempt" key={d.attempt}>
          <summary>
            Attempt {d.attempt} · {d.validation_passed ? "passed" : "BLOCKED"} ·
            inspect original and violations
          </summary>
          <p className="email-body">{d.rendered_text}</p>
          <pre>{JSON.stringify(d.violations, null, 2)}</pre>
        </details>
      ))}
      <JsonDetail title="Claim case file" value={data.case_file} />
      <JsonDetail
        title="Internal note · reviewer only"
        value={data.internal_note}
      />
      <JsonDetail title="Escalation brief" value={data.escalation_brief} />
      <section className="review-actions">
        <label htmlFor="review-note">Reviewer note</label>
        <textarea
          id="review-note"
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={!actionable || !!message}
        />
        <p className="muted">
          Your decision is recorded with the original draft. No outgoing email
          is enabled.
        </p>
        {failure && (
          <p className="error" role="alert">
            {failure}
          </p>
        )}
        {message && (
          <p className="success" role="status">
            {message}
          </p>
        )}
        <div className="action-buttons">
          <button
            className="primary"
            disabled={
              pending ||
              !actionable ||
              !!message ||
              !latest?.validation_passed ||
              editing
            }
            onClick={() => act("approved")}
          >
            Approve
          </button>
          <button
            disabled={
              pending ||
              !actionable ||
              !!message ||
              !latest ||
              (editing && !text.trim())
            }
            onClick={() => (editing ? act("edited") : setEditing(true))}
          >
            {editing ? "Save edit & approve" : "Edit & approve"}
          </button>
          {editing && (
            <button disabled={pending} onClick={() => setEditing(false)}>
              Cancel edit
            </button>
          )}
          <button
            className="danger"
            disabled={pending || !actionable || !!message}
            onClick={() => act("rejected")}
          >
            Reject
          </button>
        </div>
      </section>
    </>
  );
}
