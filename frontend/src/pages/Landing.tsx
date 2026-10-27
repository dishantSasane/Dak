import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, useResource, type Demo } from "../api";
import { State } from "../ui";
import { Icon } from "../icons";
import { MailIllustration } from "../MailIllustration";
export function Landing() {
  const { data, error, loading, reload } =
    useResource<Demo>("/api/demo/config");
  const navigate = useNavigate();
  const [sender, setSender] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState("");
  const [copied, setCopied] = useState(false);
  const [selectedSample, setSelectedSample] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setFailure("");
    try {
      const result = await api<{ run_id: number }>("/api/manual-email", {
        method: "POST",
        body: JSON.stringify({ sender, subject, body }),
      });
      navigate(`/runs/${result.run_id}`);
    } catch (e) {
      setFailure((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow hero-kicker">
            <span /> YOUR INTELLIGENT MAILROOM
          </span>
          <h1>
            Less sorting.
            <br />
            More <em>understanding.</em>
          </h1>
          <p>
            Give every insurance email the attention it deserves. Dak finds the
            context, gathers the evidence, and prepares a thoughtful response.
          </p>
          <div className="hero-links">
            <Link to="/review" className="button primary">
              Open the review desk <Icon name="arrow" size={17} />
            </Link>
            <a href="#compose">
              Try a sample <span aria-hidden="true">↘</span>
            </a>
          </div>
          <div className="hero-assurance">
            <Icon name="shield" size={16} />
            <span>AI assisted. Evidence backed. Human approved.</span>
          </div>
        </div>
        <MailIllustration />
      </section>
      <div className="process-strip" aria-label="How Dak works">
        <span>
          <i>01</i> Read & classify
        </span>
        <b aria-hidden="true">→</b>
        <span>
          <i>02</i> Find policy evidence
        </span>
        <b aria-hidden="true">→</b>
        <span>
          <i>03</i> Prepare a draft
        </span>
        <b aria-hidden="true">→</b>
        <span>
          <i className="process-final">
            <Icon name="check" size={12} />
          </i>{" "}
          You review & decide
        </span>
      </div>
      <section
        className="compose-workspace"
        id="compose"
        aria-labelledby="compose-title"
      >
        <div className="scenario-desk">
          <span className="eyebrow">START WITH A SCENARIO</span>
          <h2>
            A little context. <br />A better response.
          </h2>
          <p className="muted">
            Pick a synthetic email, or write your own. See how Dak connects the
            dots.
          </p>
          {loading || error ? (
            <State loading={loading} error={error} retry={reload} />
          ) : data ? (
            <div className="samples">
              {data.samples.map((s, i) => (
                <button
                  key={s.label}
                  className={`sample ${selectedSample === s.label ? "selected" : ""}`}
                  aria-pressed={selectedSample === s.label}
                  onClick={() => {
                    setSender(s.sender);
                    setSubject(s.subject);
                    setBody(s.body);
                    setSelectedSample(s.label);
                    document.getElementById("sender")?.focus();
                  }}
                >
                  <span className={`scenario-icon scenario-${i}`}>
                    <Icon
                      name={i === 0 ? "mail" : i === 1 ? "activity" : "shield"}
                    />
                  </span>
                  <span className="sample-text">
                    <strong>{s.label}</strong>
                    <span>{s.subject}</span>
                  </span>
                  <span className="sample-arrow" aria-hidden="true">
                    {selectedSample === s.label ? "✓" : "↗"}
                  </span>
                </button>
              ))}
            </div>
          ) : null}
          <div className="synthetic-notice">
            <Icon name="shield" size={17} />
            <div>
              <strong>A safe space to explore.</strong>
              <span>
                All sample data is synthetic. Please use fictional personal and
                policy details.
              </span>
            </div>
          </div>
        </div>
        <div className="compose-sheet">
          <div className="sheet-heading">
            <span className="compose-heading-label">
              <Icon name="compose" size={17} /> NEW CORRESPONDENCE
            </span>
            <span className="draft-indicator">
              <span />
              Draft
            </span>
          </div>
          <h2 id="compose-title">Good correspondence starts here.</h2>
          <p className="muted">Your message in. A considered response out.</p>
          <form onSubmit={submit}>
            <label htmlFor="sender">From</label>
            <input
              id="sender"
              type="email"
              required
              maxLength={254}
              placeholder="demo@example.com"
              value={sender}
              onChange={(e) => setSender(e.target.value)}
            />
            <label htmlFor="subject">Subject</label>
            <input
              id="subject"
              required
              maxLength={500}
              placeholder="A question about my policy"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
            <label htmlFor="body">Message</label>
            <textarea
              id="body"
              required
              maxLength={30000}
              rows={5}
              placeholder="Include one of the sample policy numbers below…"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
            {failure && (
              <p role="alert" className="error">
                {failure}
              </p>
            )}
            <button className="primary submit" disabled={pending}>
              {pending ? "Entering the mailroom…" : "Submit for triage"}{" "}
              <Icon name="arrow" size={17} />
            </button>
            <small>For your review only. No email is sent.</small>
          </form>
        </div>
      </section>
      <section className="reference-section">
        <div>
          <span className="eyebrow">YOUR REFERENCE SHELF</span>
          <h2>
            Sample policies. <br />
            Real possibilities.
          </h2>
        </div>
        <div>
          {data?.sample_policies.map((p) => (
            <div className="policy-row" key={p.policy_number}>
              <code>{p.policy_number}</code>
              <span>{p.product_name}</span>
              <span className="muted">
                {p.scenario
                  ? {
                      active: "Active cover",
                      lapsed: "Lapsed cover",
                      waiting_period: "Within initial waiting period",
                    }[p.scenario]
                  : p.product_code}
              </span>
            </div>
          ))}
          {data?.inbound_address ? (
            <button
              className="address"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(data.inbound_address!);
                  setCopied(true);
                } catch {
                  setFailure(
                    "Clipboard unavailable. Select and copy the address manually.",
                  );
                }
              }}
            >
              {data.inbound_address}{" "}
              <span>{copied ? "Copied ✓" : "Copy ↗"}</span>
            </button>
          ) : (
            <p className="muted">
              Public email delivery is not configured. The compose form uses the
              same local pipeline.
            </p>
          )}
          {data?.repository_url && /^https:\/\//.test(data.repository_url) && (
            <a href={data.repository_url} target="_blank" rel="noreferrer">
              View the repository ↗
            </a>
          )}
        </div>
      </section>
    </div>
  );
}
