"""Synchronize clean numbered mock data (Client 1..5 scenarios) from FastAPI Bookings into Chatwoot.

This script:
1. Validates connection to the local Chatwoot instance.
2. Ensures an API inbox exists (e.g. 'SMS Line - Provider 1') and adds the admin as member.
3. Registers/updates the SmsChatwootBinding in FastAPI Bookings.
4. Reads the seeded conversations and messages for Client 1..5 from FastAPI Bookings.
5. Idempotently creates contacts and conversations in Chatwoot.
6. Synchronizes inbound customer messages and AI autoresponder/draft/sent messages into the conversation threads.
7. Saves Chatwoot IDs back to the database for full bidirectional linkage.
"""

import os
import sys
import json
import logging
import argparse
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import SessionLocal
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.client import Client
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_chatwoot import SmsChatwootBinding

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_mock_to_chatwoot")


class ChatwootClient:
    """Lightweight HTTP client for Chatwoot REST API v1."""

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.headers = {
            "api_access_token": self.api_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, endpoint: str, data: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                content = resp.read().decode("utf-8")
                if content:
                    return json.loads(content)
                return {"status": status}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else ""
            logger.error(f"Chatwoot API error [{e.code}] {method} {url}: {err_body}")
            raise RuntimeError(f"Chatwoot API {method} {endpoint} returned {e.code}: {err_body}") from e
        except Exception as e:
            logger.error(f"Network error connecting to Chatwoot at {url}: {e}")
            raise

    def get_profile(self) -> dict:
        return self._request("GET", "/api/v1/profile")

    def get_inboxes(self, account_id: int) -> List[dict]:
        res = self._request("GET", f"/api/v1/accounts/{account_id}/inboxes")
        return res.get("payload", [])

    def create_api_inbox(self, account_id: int, name: str, webhook_url: str = "") -> dict:
        payload = {
            "name": name,
            "channel": {
                "type": "api",
                "webhook_url": webhook_url
            }
        }
        return self._request("POST", f"/api/v1/accounts/{account_id}/inboxes", payload)

    def add_inbox_member(self, account_id: int, inbox_id: int, user_id: int) -> dict:
        payload = {"inbox_id": inbox_id, "user_ids": [user_id]}
        return self._request("POST", f"/api/v1/accounts/{account_id}/inbox_members", payload)

    def search_contacts(self, account_id: int, query: str) -> List[dict]:
        from urllib.parse import quote
        endpoint = f"/api/v1/accounts/{account_id}/contacts/search?q={quote(query)}"
        res = self._request("GET", endpoint)
        return res.get("payload", [])

    def create_contact(self, account_id: int, inbox_id: int, name: str, phone: str, email: str) -> dict:
        payload = {
            "inbox_id": inbox_id,
            "name": name,
            "phone_number": phone,
            "email": email
        }
        res = self._request("POST", f"/api/v1/accounts/{account_id}/contacts", payload)
        return res.get("payload", {}).get("contact", res)

    def get_contact_conversations(self, account_id: int, contact_id: int) -> List[dict]:
        res = self._request("GET", f"/api/v1/accounts/{account_id}/contacts/{contact_id}/conversations")
        return res.get("payload", [])

    def create_conversation(self, account_id: int, inbox_id: int, contact_id: int, source_id: Optional[str] = None) -> dict:
        payload = {
            "inbox_id": inbox_id,
            "contact_id": contact_id
        }
        if source_id:
            payload["source_id"] = source_id
        return self._request("POST", f"/api/v1/accounts/{account_id}/conversations", payload)

    def get_conversation_messages(self, account_id: int, conversation_id: int) -> List[dict]:
        res = self._request("GET", f"/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages")
        return res.get("payload", [])

    def send_message(self, account_id: int, conversation_id: int, content: str, message_type: str = "incoming") -> dict:
        payload = {
            "content": content,
            "message_type": message_type
        }
        return self._request("POST", f"/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages", payload)

    def delete_conversation(self, account_id: int, conversation_id: int) -> None:
        self._request("DELETE", f"/api/v1/accounts/{account_id}/conversations/{conversation_id}")

    def delete_contact(self, account_id: int, contact_id: int) -> None:
        self._request("DELETE", f"/api/v1/accounts/{account_id}/contacts/{contact_id}")


def format_e164(phone: str) -> str:
    """Format an Australian phone number into E.164 (+614...)."""
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        return f"+61{digits[1:]}"
    elif digits.startswith("61") and len(digits) == 11:
        return f"+{digits}"
    elif phone.startswith("+"):
        return phone
    return f"+{digits}"


def sync_scenarios_to_chatwoot(
    chatwoot_base_url: str = "http://127.0.0.1:3000",
    chatwoot_api_token: str = "4ULEfYYtAJAbPZmZYaVcr9Lb",
    chatwoot_account_id: Optional[int] = None,
    tenant_subdomain: str = "simplydemo",
    inbox_name: str = "SMS Line - Provider 1",
    clear_existing_chatwoot: bool = False,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """Execute complete synchronization of Client 1..5 mock data to Chatwoot."""
    cw = ChatwootClient(base_url=chatwoot_base_url, api_token=chatwoot_api_token)

    # 1. Verify Chatwoot Connection & Identity
    logger.info(f"Connecting to Chatwoot at {chatwoot_base_url}...")
    profile = cw.get_profile()
    user_id = profile["id"]
    user_name = profile.get("name", "Admin")
    user_email = profile.get("email", "")
    accounts = profile.get("accounts", [])
    
    if chatwoot_account_id is None:
        if accounts:
            chatwoot_account_id = accounts[0]["id"]
        else:
            chatwoot_account_id = 2

    account_name = next((a["name"] for a in accounts if a["id"] == chatwoot_account_id), "Default Account")
    logger.info(f"Connected to Chatwoot as '{user_name}' ({user_email}) on Account {chatwoot_account_id} ('{account_name}')")

    # 2. Ensure API Inbox exists
    inboxes = cw.get_inboxes(chatwoot_account_id)
    api_inbox = next((i for i in inboxes if i.get("channel_type") == "Channel::Api" and i.get("name") == inbox_name), None)
    if not api_inbox:
        # Check any API inbox
        api_inbox = next((i for i in inboxes if i.get("channel_type") == "Channel::Api"), None)

    if not api_inbox:
        logger.info(f"Creating API inbox '{inbox_name}' in Chatwoot account {chatwoot_account_id}...")
        api_inbox = cw.create_api_inbox(chatwoot_account_id, name=inbox_name)
        logger.info(f"Created API inbox ID {api_inbox['id']}")
    else:
        logger.info(f"Using existing API inbox ID {api_inbox['id']} ('{api_inbox.get('name')}')")

    inbox_id = api_inbox["id"]

    # Ensure Frank/Admin is member of this inbox
    try:
        cw.add_inbox_member(chatwoot_account_id, inbox_id, user_id)
        logger.info(f"Ensured user {user_id} is a member of inbox {inbox_id}")
    except Exception as e:
        logger.debug(f"Inbox membership note: {e}")

    # 3. Database operations in FastAPI Bookings
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    synced_summary = []
    try:
        tenant = db.query(Tenant).filter(Tenant.subdomain == tenant_subdomain).first()
        if not tenant:
            raise RuntimeError(f"Tenant with subdomain '{tenant_subdomain}' not found in database.")

        # Find Provider 1
        provider_1 = db.query(Provider).filter(
            Provider.tenant_id == tenant.id,
            Provider.name.like("Provider 1%")
        ).order_by(Provider.id.desc()).first()

        if not provider_1:
            provider_1 = db.query(Provider).filter(Provider.tenant_id == tenant.id).first()

        logger.info(f"Resolved Provider 1 in database: ID {provider_1.id} ('{provider_1.name}')")

        # Register or update SmsChatwootBinding
        # Also bind for any provider that owns the SMS conversations
        conv_providers = db.query(SmsConversation.provider_id).filter(
            SmsConversation.tenant_id == tenant.id,
            SmsConversation.customer_address.in_(["0411000001", "0411000002", "0411000003", "0411000004", "0411000005"])
        ).distinct().all()
        target_provider_ids = set([p[0] for p in conv_providers if p[0]] + ([provider_1.id] if provider_1 else []))

        import secrets
        for prov_id in target_provider_ids:
            binding = db.query(SmsChatwootBinding).filter(
                SmsChatwootBinding.tenant_id == tenant.id,
                SmsChatwootBinding.provider_id == prov_id
            ).first()

            if not binding:
                binding = SmsChatwootBinding(
                    tenant_id=tenant.id,
                    provider_id=prov_id,
                    chatwoot_account_id=chatwoot_account_id,
                    chatwoot_inbox_id=inbox_id,
                    chatwoot_base_url=chatwoot_base_url,
                    chatwoot_api_token=chatwoot_api_token,
                    webhook_secret=secrets.token_hex(32),
                    is_enabled=True
                )
                db.add(binding)
                logger.info(f"Registered new SmsChatwootBinding for provider {prov_id}")
            else:
                binding.chatwoot_account_id = chatwoot_account_id
                binding.chatwoot_inbox_id = inbox_id
                binding.chatwoot_base_url = chatwoot_base_url
                binding.chatwoot_api_token = chatwoot_api_token
                binding.is_enabled = True
                if not binding.webhook_secret:
                    binding.webhook_secret = secrets.token_hex(32)
                logger.info(f"Updated existing SmsChatwootBinding ID {binding.id} for provider {prov_id}")

        db.commit()

        # 4. Sync Client 1..5 Conversations and Messages
        target_clients = [
            {"num": 1, "name": "Client 1 - Alice Walker", "phone": "0411000001", "email": "client1@example.com"},
            {"num": 2, "name": "Client 2 - Bob Taylor", "phone": "0411000002", "email": "client2@example.com"},
            {"num": 3, "name": "Client 3 - Charlie Evans", "phone": "0411000003", "email": "client3@example.com"},
            {"num": 4, "name": "Client 4 - Diana Prince", "phone": "0411000004", "email": "client4@example.com"},
            {"num": 5, "name": "Client 5 - Evan Wright", "phone": "0411000005", "email": "client5@example.com"},
        ]

        for spec in target_clients:
            phone_raw = spec["phone"]
            phone_e164 = format_e164(phone_raw)
            client_name = spec["name"]
            client_email = spec["email"]

            logger.info(f"\n--- Synchronizing {client_name} ({phone_e164}) ---")

            # A. Find or create contact in Chatwoot
            cw_contact = None
            search_results = cw.search_contacts(chatwoot_account_id, query=phone_e164)
            if not search_results:
                search_results = cw.search_contacts(chatwoot_account_id, query=client_name)

            if search_results:
                cw_contact = search_results[0]
                logger.info(f"Found existing Chatwoot contact ID {cw_contact['id']} for {client_name}")
            else:
                cw_contact = cw.create_contact(
                    account_id=chatwoot_account_id,
                    inbox_id=inbox_id,
                    name=client_name,
                    phone=phone_e164,
                    email=client_email
                )
                logger.info(f"Created new Chatwoot contact ID {cw_contact['id']} for {client_name}")

            cw_contact_id = cw_contact["id"]

            # B. Find or create conversation in Chatwoot
            contact_convs = cw.get_contact_conversations(chatwoot_account_id, cw_contact_id)
            cw_conv = next((c for c in contact_convs if c.get("inbox_id") == inbox_id), None)

            if not cw_conv:
                contact_inboxes = cw_contact.get("contact_inboxes", [])
                source_id = None
                for ci in contact_inboxes:
                    if ci.get("inbox", {}).get("id") == inbox_id:
                        source_id = ci.get("source_id")
                        break

                cw_conv = cw.create_conversation(
                    account_id=chatwoot_account_id,
                    inbox_id=inbox_id,
                    contact_id=cw_contact_id,
                    source_id=source_id
                )
                logger.info(f"Created Chatwoot conversation ID {cw_conv['id']} for contact {cw_contact_id}")
            else:
                logger.info(f"Using existing Chatwoot conversation ID {cw_conv['id']} for contact {cw_contact_id}")

            cw_conv_id = cw_conv["id"]

            # C. Link SmsConversation in FastAPI Bookings
            db_conv = db.query(SmsConversation).filter(
                SmsConversation.tenant_id == tenant.id,
                SmsConversation.customer_address == phone_raw
            ).first()

            if db_conv:
                db_conv.chatwoot_conversation_id = cw_conv_id
                db_conv.chatwoot_contact_id = cw_contact_id
                db_conv.chatwoot_inbox_id = inbox_id
                db.commit()
                db.refresh(db_conv)

            # D. Push Messages into Chatwoot Conversation
            existing_cw_msgs = cw.get_conversation_messages(chatwoot_account_id, cw_conv_id)
            existing_cw_contents = set(m.get("content", "").strip() for m in existing_cw_msgs if m.get("content"))

            db_messages = []
            if db_conv:
                db_messages = db.query(SmsMessage).filter(
                    SmsMessage.conversation_id == db_conv.id
                ).order_by(SmsMessage.id.asc()).all()

            messages_pushed = 0
            for m in db_messages:
                content = m.body.strip()
                if content in existing_cw_contents:
                    # Already in Chatwoot
                    continue

                # Map message type: customer inbound -> "incoming", system/ai/staff -> "outgoing"
                if m.direction == "inbound":
                    cw_msg_type = "incoming"
                else:
                    cw_msg_type = "outgoing"

                cw_msg = cw.send_message(
                    account_id=chatwoot_account_id,
                    conversation_id=cw_conv_id,
                    content=content,
                    message_type=cw_msg_type
                )
                messages_pushed += 1
                existing_cw_contents.add(content)

                # Save chatwoot message ID back to DB
                if isinstance(cw_msg, dict) and "id" in cw_msg:
                    m.chatwoot_message_id = cw_msg["id"]

            db.commit()
            logger.info(f"Pushed {messages_pushed} new messages into Chatwoot conversation {cw_conv_id} (Total in Chatwoot: {len(existing_cw_contents)})")

            synced_summary.append({
                "client_num": spec["num"],
                "name": client_name,
                "phone": phone_e164,
                "chatwoot_contact_id": cw_contact_id,
                "chatwoot_conversation_id": cw_conv_id,
                "fastapi_conversation_id": db_conv.id if db_conv else None,
                "messages_synced_count": len(existing_cw_contents),
            })

        logger.info("\n=== SYNCHRONIZATION COMPLETED SUCCESSFULLY ===")
        return {
            "success": True,
            "chatwoot_base_url": chatwoot_base_url,
            "chatwoot_account_id": chatwoot_account_id,
            "chatwoot_inbox_id": inbox_id,
            "inbox_name": inbox_name,
            "clients_synced": synced_summary
        }

    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synchronize FastAPI Bookings mock data to Chatwoot")
    parser.add_argument("--chatwoot-url", default=os.getenv("CHATWOOT_BASE_URL", "http://127.0.0.1:3000"), help="Chatwoot base URL")
    parser.add_argument("--token", default=os.getenv("CHATWOOT_API_TOKEN", "4ULEfYYtAJAbPZmZYaVcr9Lb"), help="Chatwoot User API Access Token")
    parser.add_argument("--account-id", type=int, default=int(os.getenv("CHATWOOT_ACCOUNT_ID", "2")), help="Chatwoot Account ID")
    parser.add_argument("--tenant", default="simplydemo", help="FastAPI Bookings tenant subdomain")
    parser.add_argument("--inbox-name", default="SMS Line - Provider 1", help="Chatwoot API inbox name")
    parser.add_argument("--clear", action="store_true", help="Clear existing Chatwoot conversations before sync")

    args = parser.parse_args()

    result = sync_scenarios_to_chatwoot(
        chatwoot_base_url=args.chatwoot_url,
        chatwoot_api_token=args.token,
        chatwoot_account_id=args.account_id,
        tenant_subdomain=args.tenant,
        inbox_name=args.inbox_name,
        clear_existing_chatwoot=args.clear
    )

    print("\n--- SYNC SUMMARY ---")
    print(f"Chatwoot URL: {result['chatwoot_base_url']}")
    print(f"Account ID:   {result['chatwoot_account_id']}")
    print(f"Inbox:        ID {result['chatwoot_inbox_id']} ('{result['inbox_name']}')")
    print("\nSynced Clients:")
    for item in result["clients_synced"]:
        print(f"  • {item['name']} ({item['phone']}) -> Chatwoot Conv #{item['chatwoot_conversation_id']}, Contact #{item['chatwoot_contact_id']} [{item['messages_synced_count']} messages]")
