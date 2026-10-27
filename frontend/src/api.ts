import { useCallback, useEffect, useState } from "react";
const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";

function reviewerAuthorization(): string | undefined {
  const password = sessionStorage.getItem("dak_reviewer_password");
  if (!password) return undefined;
  const bytes = new TextEncoder().encode(`reviewer:${password}`);
  const binary = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");
  return `Basic ${btoa(binary)}`;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const authorization = reviewerAuthorization();
  const r = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(authorization ? { Authorization: authorization } : {}),
      ...init?.headers,
    },
  });
  if (!r.ok) {
    let detail = "";
    try {
      const data = await r.json();
      detail =
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail ?? data);
    } catch {
      /* response may have no JSON */
    }
    throw Error(`${r.status}: ${detail || r.statusText || "Request failed"}`);
  }
  return r.json();
}
export function useResource<T>(path: string | null) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((x) => x + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    setData(undefined);
    setError("");
    setLoading(!!path);
    if (path)
      api<T>(path, { signal: controller.signal })
        .then(setData)
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    return () => controller.abort();
  }, [path, revision]);
  return { data, error, loading, reload };
}
export type Run = {
  id: number;
  status: string;
  category: string | null;
  confidence: number | null;
  route: string | null;
  escalation_reason: string | null;
  duration_ms?: number | null;
  started_at?: string;
  token?: string;
  subject?: string;
  from?: string;
};
export type Email = {
  subject: string;
  body_plain: string;
  from: string;
  received_at: string;
};
export type TraceEvent = {
  seq: number;
  node: string;
  event_type: string;
  payload: Record<string, unknown>;
  duration_ms: number | null;
  created_at: string;
};
export type Draft = {
  attempt: number;
  rendered_text: string;
  sentences: { text: string; kind: string; cite: string | null }[];
  validation_passed: boolean;
  violations: unknown[];
};
export type Citation = {
  clause_id: string;
  clause_title: string;
  content: string;
  used_in_sentences: number[];
};
export type Review = {
  run: Run;
  email: Email;
  triage: Record<string, unknown>;
  drafts: Draft[];
  citations: Citation[];
  case_file: unknown;
  internal_note: unknown;
  escalation_brief: unknown;
  events: TraceEvent[];
};
export type QueueItem = {
  run_id: number;
  token: string;
  category: string | null;
  confidence: number | null;
  subject: string;
  from: string;
  waiting_since: string;
  validation_passed: boolean | null;
};
export type Demo = {
  product_name: string;
  inbound_address: string | null;
  repository_url: string | null;
  sample_policies: {
    policy_number: string;
    product_code: string;
    product_name: string;
    status?: string;
    scenario?: "active" | "lapsed" | "waiting_period";
  }[];
  samples: { label: string; sender: string; subject: string; body: string }[];
};
export type Metrics = {
  window: string;
  emails_processed: number;
  escalation_rate: number | null;
  validator_block_rate: number | null;
  citation_grounding_rate: number | null;
  latency_ms: { p50: number | null; p95: number | null };
  tokens: { prompt: number; completion: number };
};
export const pct = (x: number | null | undefined) =>
  x == null ? "N/A" : `${Math.round(x * 100)}%`;
export const duration = (x: number | null | undefined) =>
  x == null ? "—" : x < 1000 ? `${x} ms` : `${(x / 1000).toFixed(1)} s`;
export const date = (x: string | undefined) =>
  x ? new Date(x).toLocaleString() : "—";
export const terminal = new Set([
  "pending_review",
  "approved",
  "rejected",
  "escalated",
  "failed",
]);
