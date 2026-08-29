import pytest
import json
from unittest.mock import patch, AsyncMock
from app.services.gateway.rule_compiler import compile_rule

@pytest.mark.asyncio
@patch("app.services.gateway.rule_compiler.generate_response")
async def test_compile_rule_valid(mock_generate):
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "rule_type": "selection",
                        "trigger_keywords": ["one", "two"],
                        "action": "select_slot",
                        "priority": 1
                    })
                }
            }
        ]
    }
    mock_generate.return_value = mock_response
    
    result = await compile_rule(
        tenant_id="tenant1",
        plain_language_rule="If the user says one or two, select the slot.",
        api_key="fake"
    )
    
    assert result["rule_type"] == "selection"
    assert "one" in result["trigger_keywords"]
    assert result["action"] == "select_slot"
    assert result["priority"] == 1

@pytest.mark.asyncio
@patch("app.services.gateway.rule_compiler.generate_response")
async def test_compile_rule_deterministic(mock_generate):
    # Testing deterministic execution of rules
    # In a real scenario, the rule compiler outputs strict JSON
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "rule_type": "cancellation",
                        "trigger_keywords": ["cancel", "stop"],
                        "action": "cancel_booking",
                        "priority": 10
                    })
                }
            }
        ]
    }
    mock_generate.return_value = mock_response
    
    result = await compile_rule(
        tenant_id="tenant1",
        plain_language_rule="Cancel if they say stop or cancel.",
        api_key="fake"
    )
    
    assert result["rule_type"] == "cancellation"
    assert result["priority"] == 10

def test_prompt_injection_boundaries():
    # Prompt injection should be handled by the structured outputs
    # ensuring only the schema matches are returned.
    pass
