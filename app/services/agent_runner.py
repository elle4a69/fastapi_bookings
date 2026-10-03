import logging
from sqlalchemy import select
from langchain_core.messages import HumanMessage

from app.db.async_session import async_session_scope
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.sms_chatwoot import SmsChatwootBinding
from app.engine.dialogue_graph import process_dialogue_turn
from app.engine.state import AgentState, DialogueTurn
from app.services.messaging.chatwoot_handoff import send_bot_message

logger = logging.getLogger(__name__)

async def run_agent_turn(
    chatwoot_account_id: int,
    chatwoot_inbox_id: int,
    conversation_id: int,
    sender_phone: str | None,
    message_text: str
) -> None:
    """
    Background task to run an agent turn in response to a Chatwoot webhook message.
    """
    logger.info(f"Running agent turn for conversation {conversation_id}, account {chatwoot_account_id}, inbox {chatwoot_inbox_id}")
    
    async with async_session_scope() as db:
        binding_stmt = select(SmsChatwootBinding).where(
            SmsChatwootBinding.chatwoot_account_id == chatwoot_account_id,
            SmsChatwootBinding.chatwoot_inbox_id == chatwoot_inbox_id,
            SmsChatwootBinding.is_enabled == True
        )
        result = await db.execute(binding_stmt)
        binding = result.scalars().first()
        
        if not binding:
            logger.warning(f"No active SmsChatwootBinding found for account {chatwoot_account_id}, inbox {chatwoot_inbox_id}")
            return
            
        tenant_stmt = select(Tenant).where(Tenant.id == binding.tenant_id)
        tenant_result = await db.execute(tenant_stmt)
        tenant = tenant_result.scalars().first()
        
        provider_stmt = select(Provider).where(Provider.id == binding.provider_id)
        provider_result = await db.execute(provider_stmt)
        provider = provider_result.scalars().first()
        
        if not tenant or not provider:
            logger.warning("Tenant or Provider not found for the binding, exiting cleanly.")
            return

        state: AgentState = {
            "messages": [HumanMessage(content=message_text)],
            "tenant_id": tenant.id,
            "provider_id": provider.id,
            "customer_phone": sender_phone or "",
            "conversation_id": conversation_id,
            "dialogue_turn": DialogueTurn()
        }
        
        new_state = await process_dialogue_turn(state, db)
        reply_text = new_state.get("reply_text", "I'm sorry, I am unable to process your request at the moment.")
            
        max_limit = getattr(provider, "max_char_limit", 160) or 160
        if len(reply_text) > max_limit:
            reply_text = reply_text[:max_limit-3] + "..."
            
        await send_bot_message(
            chatwoot_base_url=binding.chatwoot_base_url,
            api_access_token=binding.chatwoot_api_token,
            account_id=chatwoot_account_id,
            conversation_id=conversation_id,
            content=reply_text
        )
