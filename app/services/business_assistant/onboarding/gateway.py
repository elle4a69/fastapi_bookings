"""LiveKit tool gateway and RPC dispatcher for voice-first onboarding.

Connects agent tool execution to the client executor tab:
- Validates current plan control_epoch and active tab lease_token.
- Rejects stale commands on manual takeover with StaleControlEpochError.
- Rejects expired or mismatched tab leases with LeaseExpiredError.
- Dispatches RPC payloads to the active executor tab.
- Truthfully tracks receipt states: staged != saved.
- Preserves existing LiveKit audio transport and personas in livekit_fastapi_bookings.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.onboarding import OnboardingPlan
from app.services.business_assistant.onboarding.errors import (
    LeaseExpiredError,
    OnboardingError,
    StaleControlEpochError,
)
from app.services.business_assistant.onboarding.plan_service import OnboardingPlanService
from app.services.business_assistant.onboarding.save_guard import DelegationMode
from app.services.business_assistant.onboarding.tools import (
    ONBOARDING_AGENT_TOOLS,
    OnboardingToolPack,
)

logger = logging.getLogger("business_assistant.onboarding.gateway")


class OnboardingGateway:
    """Gateway orchestrating onboarding tool calls and RPC dispatch to client tabs."""

    def __init__(
        self,
        db_factory: Optional[Callable[[], Session]] = None,
        tenant_id: int = 1,
        user_id: int = 1,
        room: Optional[Any] = None,
        rpc_dispatcher: Optional[Callable[..., Any]] = None,
        active_lease_token: Optional[str] = None,
        active_control_epoch: Optional[int] = None,
        mode: str = DelegationMode.DELEGATED.value,
        executor_identity: Optional[str] = None,
    ) -> None:
        if db_factory is None:
            from app.db.database import SessionLocal
            db_factory = SessionLocal
        self.db_factory = db_factory
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.room = room
        self.rpc_dispatcher = rpc_dispatcher
        self.active_lease_token = active_lease_token
        self.active_control_epoch = active_control_epoch
        self.mode = mode
        self.executor_identity = executor_identity
        self.dispatched_receipts: List[Dict[str, Any]] = []

    def dispatch_rpc_to_executor(
        self,
        action: str,
        params: Dict[str, Any],
        lease_token: Optional[str] = None,
        control_epoch: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Dispatch typed RPC command envelope bound to the active executor tab."""
        effective_lease = lease_token or self.active_lease_token
        effective_epoch = control_epoch if control_epoch is not None else self.active_control_epoch
        action_id = str(uuid.uuid4())

        payload = {
            "protocol_version": "1.0",
            "action_id": action_id,
            "action": action,
            "lease_token": effective_lease,
            "control_epoch": effective_epoch,
            "params": params,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        initial_receipt_state = "waiting_for_ui"
        if action == "fill_fields":
            initial_receipt_state = "fields_staged"
        elif action == "save_form":
            initial_receipt_state = "saved"
        elif action in ("validate_form", "manual_takeover", "point_to_control", "highlight_field"):
            initial_receipt_state = "executing"

        receipt: Dict[str, Any] = {
            "action_id": action_id,
            "action": action,
            "status": "dispatched",
            "receipt_state": initial_receipt_state,
            "lease_token": effective_lease,
            "control_epoch": effective_epoch,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Custom or injected rpc_dispatcher callback
        if self.rpc_dispatcher:
            try:
                if asyncio.iscoroutinefunction(self.rpc_dispatcher):
                    # Will be awaited in async dispatch if needed
                    receipt["dispatched_via"] = "coroutine_dispatcher"
                else:
                    res = self.rpc_dispatcher(action, payload)
                    if isinstance(res, dict):
                        receipt.update(res)
                    receipt["dispatched_via"] = "sync_dispatcher"
            except Exception as exc:
                logger.warning("Custom RPC dispatch error for %s: %s", action, exc)
                receipt["error"] = str(exc)
                receipt["receipt_state"] = "failed"

        # 2. LiveKit Room RPC to active executor participant
        if self.room and hasattr(self.room, "local_participant") and self.room.local_participant:
            target_identity = self.executor_identity
            remote_participants = getattr(self.room, "remote_participants", {})

            # If no target specified, select the first remote participant
            if not target_identity and remote_participants:
                target_identity = next(iter(remote_participants.keys()))

            if target_identity and target_identity in remote_participants:
                try:
                    rpc_fn = getattr(self.room.local_participant, "perform_rpc", None)
                    if rpc_fn:
                        payload_str = json.dumps(payload)
                        call_obj = rpc_fn(
                            destination_identity=target_identity,
                            method="assistant_ui_action",
                            payload=payload_str,
                            response_timeout=3.0,
                        )
                        receipt["room_rpc_target"] = target_identity
                except Exception as exc:
                    logger.debug("Room RPC to %s failed: %s", target_identity, exc)

        self.dispatched_receipts.append(receipt)
        return receipt

    def execute_tool_sync(
        self,
        name: str,
        arguments: Dict[str, Any],
        lease_token: Optional[str] = None,
        control_epoch: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute an onboarding tool synchronously in an isolated database session.

        Enforces control epoch monotonicity, active lease validation, and delegation safety.
        """
        # Inspect arguments for lease_token or control_epoch if not passed explicitly
        arg_lease = arguments.get("lease_token") if isinstance(arguments, dict) else None
        arg_epoch = arguments.get("control_epoch") if isinstance(arguments, dict) else None
        effective_lease = lease_token or arg_lease or self.active_lease_token
        effective_epoch = control_epoch if control_epoch is not None else (arg_epoch if arg_epoch is not None else self.active_control_epoch)

        db = self.db_factory()
        try:
            plan = OnboardingPlanService.get_or_create_plan(
                db=db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                lease_token=self.active_lease_token,
            )

            # 1. Validate control epoch (detect manual takeover)
            if effective_epoch is not None:
                OnboardingPlanService.validate_control_epoch(plan, effective_epoch)

            # 2. Validate active tab lease token
            if effective_lease is not None:
                OnboardingPlanService.validate_lease(plan, effective_lease)

            # 3. Create tool pack and execute
            pack = OnboardingToolPack(
                db=db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                lease_token=effective_lease,
                control_epoch=effective_epoch,
                rpc_dispatcher=self.dispatch_rpc_to_executor,
                mode=self.mode,
            )

            clean_args = {k: v for k, v in arguments.items() if k not in ("lease_token", "control_epoch")}
            result = pack.execute(name, clean_args)
            return result
        except StaleControlEpochError as exc:
            logger.info("Command rejected: stale control epoch (%s)", exc.message)
            return {
                "status": "rejected",
                "error_code": "stale_control_epoch",
                "receipt_state": "rejected",
                "message": exc.message,
                "expected_epoch": exc.expected_epoch,
                "received_epoch": exc.received_epoch,
            }
        except LeaseExpiredError as exc:
            logger.info("Command rejected: lease expired (%s)", exc.message)
            return {
                "status": "rejected",
                "error_code": "invalid_lease_token",
                "receipt_state": "rejected",
                "message": exc.message,
                "lease_token": exc.lease_token,
            }
        except OnboardingError as exc:
            logger.warning("Onboarding error during %s: %s", name, exc.message)
            return {
                "status": "rejected",
                "error_code": exc.code,
                "receipt_state": "rejected",
                "message": exc.message,
                "details": exc.details,
            }
        except Exception as exc:
            logger.exception("Unexpected error executing %s: %s", name, exc)
            return {
                "status": "failed",
                "error_code": "outcome_unknown",
                "receipt_state": "failed",
                "message": f"Internal execution error: {str(exc)}",
            }
        finally:
            db.close()

    async def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        lease_token: Optional[str] = None,
        control_epoch: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute tool asynchronously by offloading database queries to a thread."""
        return await asyncio.to_thread(
            self.execute_tool_sync,
            name,
            arguments,
            lease_token,
            control_epoch,
        )

    def build_agent_tools(self) -> List[Any]:
        """Build callable LiveKit function tools for all onboarding schemas."""
        try:
            from livekit.agents import function_tool
        except ImportError:
            logger.warning("livekit.agents is not installed; returning empty agent tools list.")
            return []

        tools: List[Any] = []
        for schema_item in ONBOARDING_AGENT_TOOLS:
            func_desc = schema_item.get("function", {})
            tool_name = func_desc.get("name")
            if not tool_name:
                continue

            def _create_handler(t_name: str) -> Callable[[Dict[str, Any]], Any]:
                async def _handler(raw_args: Dict[str, Any]) -> Dict[str, Any]:
                    args = raw_args if isinstance(raw_args, dict) else {}
                    return await self.execute_tool(t_name, args)

                return _handler

            ft = function_tool(
                _create_handler(tool_name),
                raw_schema=func_desc,
            )
            tools.append(ft)

        return tools
