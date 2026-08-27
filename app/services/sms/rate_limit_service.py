import logging
from datetime import datetime, timezone, timedelta, time
import zoneinfo
from sqlalchemy.orm import Session
from ...models.sms_account import SmsAccount
from ...models.sms_message import SmsMessage

logger = logging.getLogger(__name__)

def check_rate_limit_and_quiet_hours(db: Session, account: SmsAccount) -> bool:
    """
    Checks if the account is allowed to send messages based on quiet hours and throughput limits.
    Returns:
        bool: True if allowed to send (passes checks), False if deferred (fails checks).
    """
    # 1. Quiet Hours check
    if account.quiet_hours_start and account.quiet_hours_end:
        try:
            tenant = account.tenant
            tenant_tz = tenant.timezone if tenant else "UTC"
            try:
                tz = zoneinfo.ZoneInfo(tenant_tz)
            except Exception:
                tz = zoneinfo.ZoneInfo("UTC")
            
            now_in_tz = datetime.now(timezone.utc).astimezone(tz)
            current_time = now_in_tz.time()

            sh, sm = map(int, account.quiet_hours_start.split(":"))
            eh, em = map(int, account.quiet_hours_end.split(":"))
            start_time = time(sh, sm)
            end_time = time(eh, em)

            if start_time <= end_time:
                in_quiet = start_time <= current_time <= end_time
            else:
                in_quiet = current_time >= start_time or current_time <= end_time

            if in_quiet:
                logger.info(f"SMS Account {account.id} is in quiet hours ({account.quiet_hours_start} - {account.quiet_hours_end}). Deferring outbound SMS.")
                return False
        except Exception as e:
            logger.error(f"Error parsing quiet hours for SMS Account {account.id}: {e}")

    # 2. Throughput limit check
    if account.throughput_limit is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
        try:
            sent_count = db.query(SmsMessage).filter(
                SmsMessage.sms_account_id == account.id,
                SmsMessage.direction == "outbound",
                SmsMessage.status.in_(["sent", "delivered"]),
                SmsMessage.occurred_at >= cutoff
            ).count()

            if sent_count >= account.throughput_limit:
                logger.info(f"SMS Account {account.id} has reached its throughput limit of {account.throughput_limit} (sent: {sent_count} in last 60s). Deferring outbound SMS.")
                return False
        except Exception as e:
            logger.error(f"Error checking throughput limit for SMS Account {account.id}: {e}")

    return True
