import logging
import json
import apprise
from app import models

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    async def send_notification(channel: models.NotificationChannel, title: str, body: str):
        """Send a notification via the specified channel using Apprise."""
        if not channel.is_active:
            logger.info(f"Channel {channel.name} is inactive, skipping notification.")
            return False

        apobj = apprise.Apprise()
        
        # Construct Apprise URL based on channel type and configuration
        config_url = NotificationService._get_config_url(channel)
        
        if not config_url:
            logger.error(f"Failed to construct Apprise URL for channel {channel.name}")
            return False

        apobj.add(config_url)
        
        try:
            await apobj.async_notify(
                body=body,
                title=title,
            )
            logger.info(f"Notification sent to {channel.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to send notification to {channel.name}: {e}")
            return False

    @staticmethod
    def _get_config_url(channel: models.NotificationChannel) -> str | None:
        """Construct Apprise URL from channel configuration."""
        try:
            # If configuration is already a URL (e.g. for simple webhooks), use it
            if channel.configuration.startswith("http") or "://" in channel.configuration:
                return channel.configuration
            
            # If it's JSON, parse it
            config = json.loads(channel.configuration)
            
            if channel.type == "email":
                # mailto://user:password@smtp.example.com:2525
                user = config.get("user", "")
                password = config.get("password", "")
                host = config.get("host", "")
                port = config.get("port", "")
                
                auth = f"{user}:{password}@" if user and password else ""
                port_str = f":{port}" if port else ""
                
                return f"mailto://{auth}{host}{port_str}"
            
            elif channel.type == "discord":
                # discord://webhook_id/webhook_token
                # Or just the full webhook URL which Apprise supports
                return config.get("webhook_url")
                
            elif channel.type == "mattermost":
                # mattermost://hostname/token
                # Or the full webhook URL
                return config.get("webhook_url")
                
            return None
            
        except Exception as e:
            logger.error(f"Error parsing configuration for channel {channel.name}: {e}")
            return None

    @staticmethod
    async def send_test_notification(channel: models.NotificationChannel):
        return await NotificationService.send_notification(
            channel,
            title="Test Priceflow",
            body="Ceci est une notification de test de Priceflow ! 🚀"
        )
