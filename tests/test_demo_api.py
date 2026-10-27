from datetime import date

from sqlalchemy import select

from app.api.routes_demo import demo_config
from app.api.routes_metrics import metrics_summary
from app.api.routes_runs import recent_runs, run_detail
from app.db.models import Policy
from tests.test_review_api import make_run


async def test_demo_configuration_uses_persisted_policy_numbers(database):
    session, _ = database
    config = await demo_config(session)
    assert config["synthetic"] is True
    assert config["inbound_address"] is None
    # Reference seed data survives operational-table truncation.
    assert all(
        p["policy_number"] in s["body"]
        for p, s in zip(config["sample_policies"], config["samples"], strict=True)
    )


async def test_run_contract_and_empty_metrics(database):
    session, _ = database
    summary = await metrics_summary(session, window_days=7)
    assert summary["citation_grounding_rate"] is None
    assert summary["validator_block_rate"] is None
    run = await make_run(session)
    listed = await recent_runs(session, limit=10)
    assert listed["items"][0]["id"] == run.id
    assert listed["items"][0]["from"] == "demo@example.test"
    detail = await run_detail(run.id, session)
    assert detail["email"]["body_plain"] == "Synthetic email body"
    assert detail["token"] == "INS-APIT-0001"


async def test_policy_scenario_labels_match_persisted_dates(database):
    session, _ = database
    config = await demo_config(session)
    today = date.today()
    for item in config["sample_policies"]:
        policy = await session.scalar(
            select(Policy).where(Policy.policy_number == item["policy_number"])
        )
        assert item["status"] == policy.status
        if item["scenario"] == "lapsed":
            assert policy.status == "lapsed" and policy.end_date < today
        else:
            assert policy.status == "active" and policy.start_date <= today <= policy.end_date
            if item["scenario"] == "waiting_period":
                assert policy.product_code in ("ASP", "TRM")
                assert policy.waiting_period_end >= today
            else:
                assert (
                    policy.product_code == "MOT"
                    or policy.waiting_period_end is None
                    or policy.waiting_period_end < today
                )


async def test_missing_waiting_scenario_is_not_invented(database, monkeypatch):
    class FutureDate(date):
        @classmethod
        def today(cls):
            return cls(2099, 1, 1)

    monkeypatch.setattr("app.api.routes_demo.date", FutureDate)
    session, _ = database
    config = await demo_config(session)
    assert all(p["scenario"] == "lapsed" for p in config["sample_policies"])
