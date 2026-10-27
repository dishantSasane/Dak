"""JSON-serializable checkpoint state; agents communicate only through this state."""

from typing import Any, TypedDict


class RunState(TypedDict, total=False):
    run_id: int
    email_id: int
    case_id: int
    token: str
    subject: str
    body: str
    raw_payload: dict[str, Any]
    triage: dict[str, Any]
    policy_found: bool | None
    policy_record: dict[str, Any] | None
    product_code: str | None
    draft: dict[str, Any] | None
    retrieved_chunks: list[dict[str, Any]]
    reject_route: dict[str, str] | None
    originating_agent: str
    route_history: list[dict[str, str]]
    next_node: str
    reroute_count: int
    validator_retry_count: int
    validation: dict[str, Any]
    violations: list[dict[str, Any]]
    used_customer_tools: bool
    numbers_from_policy_record: bool
    tool_error: str | None
    error: str | None
    internal_note: str | None
    case_file: dict[str, Any] | None
    escalation_reason: str | None
    escalation_brief: dict[str, Any]
    escalate_flag: bool
    cache_hit: bool
    status: str
