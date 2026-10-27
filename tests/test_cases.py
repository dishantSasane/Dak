from unittest.mock import AsyncMock

from app.db.models import Case
from app.services.cases import resolve_case


async def test_bracketed_message_id_resolves_thread() -> None:
    case = Case(id=1, token="INS-7K3M-2XQ9", contact_email="customer@example.com")
    session = AsyncMock()
    result = session.execute.return_value
    result.scalar_one_or_none = lambda: case
    resolved, created = await resolve_case(
        session,
        subject="Re: coverage",
        sender="customer@example.com",
        in_reply_to="<parent@example.com>",
    )
    assert resolved is case and not created
    query = session.execute.call_args.args[0]
    assert "<parent@example.com>" in query.compile().params.values()
