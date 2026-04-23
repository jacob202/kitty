#!/usr/bin/env python3
"""
Webhook Notifications for Kitty
Send notifications to external services
"""

import logging
from enum import Enum

import requests

logger = logging.getLogger(__name__)


class WebhookType(Enum):
    """Types of webhooks"""

    SLACK = "slack"
    DISCORD = "discord"
    GENERIC = "generic"


class WebhookNotifier:
    """Send webhook notifications"""

    def __init__(self):
        self.webhooks: dict[str, str] = {}

    def register(self, name: str, url: str, webhook_type: WebhookType = WebhookType.GENERIC):
        """Register a webhook"""
        self.webhooks[name] = {"url": url, "type": webhook_type}

    def send(self, name: str, message: str, **kwargs) -> bool:
        """Send notification to webhook"""
        if name not in self.webhooks:
            return False

        webhook = self.webhooks[name]
        url = webhook["url"]
        webhook_type = webhook["type"]

        try:
            if webhook_type == WebhookType.SLACK:
                payload = {"text": message}
            elif webhook_type == WebhookType.DISCORD:
                payload = {"content": message}
            else:
                payload = {"message": message, **kwargs}

            response = requests.post(url, json=payload, timeout=10)
            return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return False

    def notify_task_complete(self, task_name: str, success: bool, details: str = ""):
        """Notify task completion"""
        status = "✅" if success else "❌"
        message = f"{status} Task completed: {task_name}\n{details}"

        for name in self.webhooks:
            self.send(name, message)

    def notify_error(self, error: str, context: str = ""):
        """Notify error"""
        message = f"❌ Error: {error}\nContext: {context}"

        for name in self.webhooks:
            self.send(name, message)


# Global instance
_notifier = None


def get_notifier() -> WebhookNotifier:
    """Get global notifier"""
    global _notifier
    if _notifier is None:
        _notifier = WebhookNotifier()
    return _notifier


# CLI
def main():
    """Webhook CLI"""
    import typer

    app = typer.Typer(help="Webhook Notifications")

    @app.command("register")
    def register(
        name: str = typer.Argument(..., help="Webhook name"),
        url: str = typer.Argument(..., help="Webhook URL"),
        webhook_type: str = typer.Option("generic", "--type", "-t"),
    ):
        """Register a webhook"""
        notifier = get_notifier()
        wt = WebhookType(webhook_type)
        notifier.register(name, url, wt)
        typer.echo(f"Registered webhook: {name}")

    @app.command("send")
    def send(
        name: str = typer.Argument(..., help="Webhook name"),
        message: str = typer.Argument(..., help="Message"),
    ):
        """Send test notification"""
        notifier = get_notifier()
        success = notifier.send(name, message)
        typer.echo(f"Sent: {'✓' if success else '✗'}")

    app()


if __name__ == "__main__":
    main()
