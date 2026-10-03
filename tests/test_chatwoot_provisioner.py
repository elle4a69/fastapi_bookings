import pytest
from unittest.mock import patch, MagicMock
import httpx
from app.services.chatwoot_provisioner import provision_chatwoot_tenant, TenantProvisionResult, ChatwootProvisionError
from app.core.config import settings

@pytest.fixture
def mock_config():
    old_platform_token = settings.CHATWOOT_PLATFORM_ACCESS_TOKEN
    old_base_url = settings.CHATWOOT_BASE_URL
    old_webhook = settings.AGENT_WEBHOOK_URL
    
    settings.CHATWOOT_PLATFORM_ACCESS_TOKEN = "test-token"
    settings.CHATWOOT_BASE_URL = "http://test-chatwoot.local"
    settings.AGENT_WEBHOOK_URL = "http://test-agent.local/webhook"
    
    yield
    
    settings.CHATWOOT_PLATFORM_ACCESS_TOKEN = old_platform_token
    settings.CHATWOOT_BASE_URL = old_base_url
    settings.AGENT_WEBHOOK_URL = old_webhook

@pytest.fixture
def mock_config_no_token():
    old_platform_token = settings.CHATWOOT_PLATFORM_ACCESS_TOKEN
    old_api_token = settings.CHATWOOT_PLATFORM_API_TOKEN
    
    settings.CHATWOOT_PLATFORM_ACCESS_TOKEN = ""
    settings.CHATWOOT_PLATFORM_API_TOKEN = ""
    
    yield
    
    settings.CHATWOOT_PLATFORM_ACCESS_TOKEN = old_platform_token
    settings.CHATWOOT_PLATFORM_API_TOKEN = old_api_token

@patch("httpx.Client.post")
def test_provision_chatwoot_tenant_success(mock_post, mock_config):
    # Setup mock responses
    account_response = MagicMock()
    account_response.status_code = 200
    account_response.json.return_value = {"id": 42, "name": "Test Business"}
    
    webhook_response = MagicMock()
    webhook_response.status_code = 200
    webhook_response.json.return_value = {"payload": {"webhook": {"id": 100}}}
    
    # Mock post calls
    def side_effect(url, **kwargs):
        if url == "/platform/api/v1/accounts":
            return account_response
        elif url == "/api/v1/accounts/42/webhooks":
            return webhook_response
        raise ValueError(f"Unexpected url: {url}")
        
    mock_post.side_effect = side_effect
    
    result = provision_chatwoot_tenant("Test Business")
    
    assert isinstance(result, TenantProvisionResult)
    assert result.chatwoot_account_id == 42
    assert result.webhook_id == 100
    assert mock_post.call_count == 2
    webhook_call = mock_post.call_args_list[1]
    assert webhook_call[0][0] == "/api/v1/accounts/42/webhooks"
    assert webhook_call[1]["json"] == {
        "webhook": {
            "url": "http://test-agent.local/webhook",
            "subscriptions": ["message_created", "conversation_status_changed"],
        }
    }

@patch("httpx.Client.post")
def test_provision_chatwoot_tenant_account_creation_fails(mock_post, mock_config):
    account_response = MagicMock()
    account_response.status_code = 401
    
    def raise_status():
        raise httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=account_response)
    
    account_response.raise_for_status.side_effect = raise_status
    account_response.text = "Unauthorized"
    
    mock_post.return_value = account_response
    
    with pytest.raises(ChatwootProvisionError, match="HTTP error during provisioning"):
        provision_chatwoot_tenant("Test Business")

@patch("httpx.Client.post")
def test_provision_chatwoot_tenant_webhook_creation_fails(mock_post, mock_config):
    account_response = MagicMock()
    account_response.status_code = 200
    account_response.json.return_value = {"id": 42}
    
    webhook_response = MagicMock()
    webhook_response.status_code = 500
    webhook_response.text = "Internal Server Error"
    
    def raise_status():
        raise httpx.HTTPStatusError("Server Error", request=MagicMock(), response=webhook_response)
        
    webhook_response.raise_for_status.side_effect = raise_status
    
    def side_effect(url, **kwargs):
        if url == "/platform/api/v1/accounts":
            return account_response
        return webhook_response
        
    mock_post.side_effect = side_effect
    
    with pytest.raises(ChatwootProvisionError, match="HTTP error during provisioning"):
        provision_chatwoot_tenant("Test Business")

def test_provision_chatwoot_tenant_missing_token(mock_config_no_token):
    with pytest.raises(ChatwootProvisionError, match="Chatwoot platform access token is not configured"):
        provision_chatwoot_tenant("Test Business")
