import type { ReactNode } from "react";
import { date, duration, type Email, type TraceEvent } from "./api";
export function Badge({ status }: { status: string | null | undefined }) {
  return (
    <span className={`badge ${status || "unknown"}`}>
      {(status || "unclassified").replaceAll("_", " ")}
    </span>
  );
}
export function State({
  loading,
  error,
  empty,
  retry,
}: {
  loading?: boolean;
  error?: string;
  empty?: string;
  retry?: () => void;
}) {
  if (loading)
    return (
      <div className="state" role="status">
        <span className="pulse" /> Loading the mailroom…
      </div>
    );
  if (error)
    return (
      <div className="state error" role="alert">
        <strong>Couldn’t load this view.</strong>
        <p>{error}</p>
        {retry && <button onClick={retry}>Try again</button>}
      </div>
    );
  return (
    <div className="state">
      <span className="empty-mark">↳</span>
      <p>{empty || "Nothing here yet."}</p>
    </div>
  );
}
export function PageTitle({
  number,
  title,
  children,
}: {
  number: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-title">
      <div>
        <span className="eyebrow">{number} / THE MAILROOM</span>
        <h1>{title}</h1>
      </div>
      {children}
    </header>
  );
}
export function EmailPanel({ email }: { email: Email }) {
  return (
    <article className="panel correspondence">
      <span className="eyebrow">INCOMING CORRESPONDENCE</span>
      {email.subject.includes("[RECORDED FIXTURE]") && (
        <p className="fixture-notice">
          Recorded fixture · generated for local verification, without live
          model inference.
        </p>
      )}
      <h2>{email.subject}</h2>
      <div className="metadata">
        <span>{email.from}</span>
        <time>{date(email.received_at)}</time>
      </div>
      <p className="email-body">{email.body_plain}</p>
    </article>
  );
}
export function JsonDetail({
  title,
  value,
}: {
  title: string;
  value: unknown;
}) {
  return value == null ? null : (
    <details className="evidence">
      <summary>{title}</summary>
      <pre>
        {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}
export function Trace({ events }: { events: TraceEvent[] }) {
  return (
    <ol className="trace">
      {events.map((e) => (
        <li
          key={e.seq}
          className={
            /block|fail/.test(e.event_type) || e.payload.passed === false
              ? "blocked"
              : ""
          }
        >
          <details>
            <summary>
              <span className="event-seq">
                {String(e.seq).padStart(2, "0")}
              </span>
              <span>
                <strong>{e.node.replaceAll("_", " ")}</strong>
                <small>{e.event_type.replaceAll("_", " ")}</small>
              </span>
              <span className="mono timing">{duration(e.duration_ms)}</span>
            </summary>
            {e.payload.provider === "recorded_fixture" && (
              <p className="fixture-notice">
                Recorded fixture provider · no live model call.
              </p>
            )}
            <pre>{JSON.stringify(e.payload, null, 2)}</pre>
            <time>{date(e.created_at)}</time>
          </details>
        </li>
      ))}
    </ol>
  );
}
