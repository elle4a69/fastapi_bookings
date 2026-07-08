import logging
import json
import firebase_admin
from firebase_admin import credentials, messaging
from ..core.config import settings

logger = logging.getLogger(__name__)

class FCMClient:
    def __init__(self):
        self.initialized = False
        creds_json = settings.FIREBASE_CREDENTIALS_JSON
        if not creds_json:
            logger.warning("FIREBASE_CREDENTIALS_JSON is not configured. FCM push notifications are disabled.")
            return

        try:
            if creds_json.strip().startswith("{"):
                # Raw JSON string
                creds_dict = json.loads(creds_json)
                cred = credentials.Certificate(creds_dict)
            else:
                # File path
                cred = credentials.Certificate(creds_json)
            
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            self.initialized = True
            logger.info("Firebase Admin SDK successfully initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {str(e)}")

    def send_push_notification(self, token: str, title: str, body: str, data: dict = None) -> str:
        """Send a push notification to a device token."""
        if not self.initialized:
            logger.warning("FCM client is not initialized. Skipping push notification.")
            return "skipped_not_initialized"

        # Platform-specific headers to force immediate banner and sound alert
        apns = messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    alert=messaging.ApsAlert(
                        title=title,
                        body=body,
                    ),
                    sound="default",
                    content_available=True
                )
            )
        )
        android = messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                title=title,
                body=body,
                sound="default"
            )
        )

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=token,
            apns=apns,
            android=android
        )

        try:
            response = messaging.send(message)
            logger.info(f"FCM push notification sent successfully: {response}")
            return response
        except Exception as e:
            logger.error(f"Failed to send FCM push notification: {str(e)}")
            raise

fcm_client = FCMClient()
