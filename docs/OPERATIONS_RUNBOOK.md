# Operations Runbook

## 1. Restart/Recovery
- **FastAPI Backend:** Use systemd or docker-compose restart. Ensure all 7 worker processes restart properly.
- **SigNoz Telemetry:** Restart SigNoz stack using docker-compose.
- **Codex MCP:** Verify JSON-RPC connection post-restart.

## 2. Key Rotation
- **Stripe & ClickSend:** Generate new keys, update `.env`, restart application.
- **OpenAI:** Rotate key in `.env` and restart. Ensure no cached connections remain.

## 3. App Server Upgrades
- Blue/Green deployment strategy.
- Run migrations (`alembic upgrade head`) before shifting traffic.
- Monitor telemetry error rates for 5 minutes post-upgrade.

## 4. Provider Outage Handling
- **SMS (ClickSend):** Implement exponential backoff.
- **AI (OpenAI):** Fail gracefully; revert to default templates.
- **Payment (Stripe):** Disable payments during outage, show maintenance banner.

## 5. 3-Tier Approval Matrix
- **Tier 1:** Standard automated responses.
- **Tier 2:** Requires manager approval (e.g. refunds > $50).
- **Tier 3:** Requires director approval (e.g. system-wide config changes).
