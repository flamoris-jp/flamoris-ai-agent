from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from test_scoped_service import shared_http

from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.principals import PrincipalBinding, PrincipalKeys
from flamoris_ai_agent.scoped_service import ScopedAgentService


@pytest.mark.parametrize("project", ["example.project", "example.ai.helper", "a.b", "a" * 64])
def test_existing_project_keys_preserve_exact_identity(project):
    assert PrincipalKeys("person", "helper", project).project == project


@pytest.mark.parametrize(
    "project", ["", ".a", "a.", "a..b", "../a", "a/b", "a:b", "a b", "a" * 65, 1, None]
)
def test_project_keys_reject_malformed_values(project):
    with pytest.raises(IntelligenceError, match="principal_unavailable"):
        PrincipalKeys("person", "helper", project)


@pytest.mark.parametrize("field", ["human", "agent"])
def test_dotted_project_support_does_not_relax_other_principals(field):
    values = {"human": "person", "agent": "helper", "project": "example.project"}
    values[field] = "dotted.name"
    with pytest.raises(IntelligenceError, match="principal_unavailable"):
        PrincipalKeys(**values)


async def test_real_http_session_preserves_dotted_project_for_exact_grant_lookup():
    principals = Mock()
    keys = PrincipalKeys("person", "helper", "example.project")
    binding = PrincipalBinding(
        uuid4(),
        "backend",
        keys,
        uuid4(),
        uuid4(),
        uuid4(),
        datetime.now(UTC) + timedelta(minutes=15),
    )
    principals.open.return_value = binding
    service = ScopedAgentService(principals)
    async with shared_http(service) as client:
        result = await client.call_tool(
            "sessions.open",
            {
                "request": {
                    "human": keys.human,
                    "agent": keys.agent,
                    "project": keys.project,
                }
            },
        )
        assert not result.is_error
        assert result.structured_content["session_id"] == str(binding.session_id)
    principals.open.assert_called_once_with("backend", keys)
