"""
Alert Manager — Production alerting system for Kitty AI.
Defines alert rules, manages alert channels (console, file, webhook),
and implements alert deduplication to prevent spam.
"""

import json
import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import psutil
import requests

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status states."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SILENCED = "silenced"


@dataclass
class AlertRule:
    """Alert rule configuration."""

    id: str
    name: str
    description: str
    severity: AlertSeverity
    condition_type: str  # 'threshold', 'heartbeat', 'composite'
    condition_config: dict[str, Any]
    duration_seconds: int  # How long condition must persist before alerting
    cooldown_seconds: int  # Minimum time between alerts for same rule
    auto_resolve: bool = True  # Auto-resolve when condition clears
    channels: list[str] = field(default_factory=lambda: ["console", "file"])
    enabled: bool = True


@dataclass
class Alert:
    """An active or historical alert."""

    id: str
    rule_id: str
    name: str
    severity: AlertSeverity
    status: AlertStatus
    message: str
    details: dict[str, Any]
    started_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    last_notified_at: datetime | None = None
    notification_count: int = 0


@dataclass
class AlertChannel:
    """Alert channel configuration."""

    id: str
    type: str  # 'console', 'file', 'webhook', 'slack', 'discord'
    config: dict[str, Any]
    enabled: bool = True
    rate_limit_per_minute: int = 60


class AlertManager:
    """
    Production-grade alert manager for Kitty AI.
    Manages alert rules, channels, deduplication, and state tracking.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str | None = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str | None = None):
        if self._initialized:
            return

        self._initialized = True
        self.data_dir = Path(__file__).parent.parent.parent / "data" / "observability"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or str(self.data_dir / "alerts.json")

        self._lock = threading.RLock()
        self._running = False
        self._check_thread: threading.Thread | None = None

        # Alert storage
        self._rules: dict[str, AlertRule] = {}
        self._channels: dict[str, AlertChannel] = {}
        self._active_alerts: dict[str, Alert] = {}
        self._alert_history: list[Alert] = []
        self._state_history: dict[str, list[dict]] = defaultdict(list)  # For rule evaluation

        # Deduplication tracking
        self._last_alert_time: dict[str, datetime] = {}
        self._rule_last_state: dict[str, bool] = {}

        # Callbacks for external integrations
        self._on_alert_callbacks: list[Callable] = []
        self._on_resolve_callbacks: list[Callable] = []

        # Initialize default configuration
        self._init_default_rules()
        self._init_default_channels()
        self._load_state()

    def _init_default_rules(self):
        """Initialize default alert rules."""
        default_rules = [
            # Error rate alerts
            AlertRule(
                id="error_rate_warning",
                name="High Error Rate (Warning)",
                description="Error rate exceeds 5% for 5 minutes",
                severity=AlertSeverity.WARNING,
                condition_type="threshold",
                condition_config={
                    "metric": "error_rate_percent",
                    "operator": ">",
                    "threshold": 5.0,
                    "source": "api_metrics",
                    "window_minutes": 5,
                },
                duration_seconds=300,  # 5 minutes
                cooldown_seconds=600,  # 10 minutes between alerts
                channels=["console", "file", "webhook"],
            ),
            AlertRule(
                id="error_rate_critical",
                name="Critical Error Rate",
                description="Error rate exceeds 10% for 5 minutes",
                severity=AlertSeverity.CRITICAL,
                condition_type="threshold",
                condition_config={
                    "metric": "error_rate_percent",
                    "operator": ">",
                    "threshold": 10.0,
                    "source": "api_metrics",
                    "window_minutes": 5,
                },
                duration_seconds=300,
                cooldown_seconds=300,  # 5 minutes between critical alerts
                channels=["console", "file", "webhook"],
            ),
            # API latency alert
            AlertRule(
                id="api_latency_warning",
                name="High API Latency",
                description="Average API latency exceeds 2 seconds",
                severity=AlertSeverity.WARNING,
                condition_type="threshold",
                condition_config={
                    "metric": "avg_response_time_ms",
                    "operator": ">",
                    "threshold": 2000.0,
                    "source": "api_metrics",
                    "window_minutes": 5,
                },
                duration_seconds=180,  # 3 minutes
                cooldown_seconds=600,
                channels=["console", "file"],
            ),
            # LLM cost alert
            AlertRule(
                id="llm_cost_budget",
                name="Daily LLM Budget Alert",
                description="LLM costs exceed $50 per day",
                severity=AlertSeverity.WARNING,
                condition_type="threshold",
                condition_config={
                    "metric": "daily_cost_usd",
                    "operator": ">",
                    "threshold": 50.0,
                    "source": "llm_metrics",
                },
                duration_seconds=60,
                cooldown_seconds=3600,  # 1 hour between budget alerts
                channels=["console", "file", "webhook"],
            ),
            # Disk space alert
            AlertRule(
                id="disk_space_critical",
                name="Low Disk Space",
                description="Available disk space below 10%",
                severity=AlertSeverity.CRITICAL,
                condition_type="system",
                condition_config={
                    "check": "disk_space_percent",
                    "operator": "<",
                    "threshold": 10.0,
                },
                duration_seconds=60,
                cooldown_seconds=1800,  # 30 minutes
                channels=["console", "file", "webhook"],
            ),
            # Ollama health alert
            AlertRule(
                id="ollama_down_critical",
                name="Ollama Service Down",
                description="Ollama service not responding for 2+ minutes",
                severity=AlertSeverity.CRITICAL,
                condition_type="heartbeat",
                condition_config={
                    "service": "ollama",
                    "url": "http://localhost:11434/api/tags",
                    "timeout_seconds": 5,
                },
                duration_seconds=120,  # 2 minutes
                cooldown_seconds=300,
                channels=["console", "file", "webhook"],
            ),
            # Memory alert
            AlertRule(
                id="memory_warning",
                name="High Memory Usage",
                description="System memory usage exceeds 90%",
                severity=AlertSeverity.WARNING,
                condition_type="system",
                condition_config={
                    "check": "memory_percent",
                    "operator": ">",
                    "threshold": 90.0,
                },
                duration_seconds=120,
                cooldown_seconds=600,
                channels=["console", "file"],
            ),
            # CPU alert
            AlertRule(
                id="cpu_warning",
                name="High CPU Usage",
                description="System CPU usage exceeds 95%",
                severity=AlertSeverity.WARNING,
                condition_type="system",
                condition_config={
                    "check": "cpu_percent",
                    "operator": ">",
                    "threshold": 95.0,
                },
                duration_seconds=180,
                cooldown_seconds=600,
                channels=["console", "file"],
            ),
        ]

        for rule in default_rules:
            self._rules[rule.id] = rule

    def _init_default_channels(self):
        """Initialize default alert channels."""
        default_channels = [
            AlertChannel(
                id="console",
                type="console",
                config={},
                enabled=True,
            ),
            AlertChannel(
                id="file",
                type="file",
                config={
                    "log_path": str(self.data_dir / "alerts.log"),
                    "json_path": str(self.data_dir / "alerts.json"),
                },
                enabled=True,
            ),
            AlertChannel(
                id="webhook",
                type="webhook",
                config={
                    "url": "",
                    "headers": {},
                    "timeout": 10,
                },
                enabled=False,  # Disabled by default - needs configuration
            ),
        ]

        for channel in default_channels:
            self._channels[channel.id] = channel

    def _load_state(self):
        """Load alert state from disk."""
        state_path = Path(self.db_path)
        if state_path.exists():
            try:
                with open(state_path) as f:
                    state = json.load(f)

                # Load custom rules if present
                if "rules" in state:
                    for rule_data in state["rules"]:
                        rule = AlertRule(**rule_data)
                        self._rules[rule.id] = rule

                # Load custom channels if present
                if "channels" in state:
                    for ch_data in state["channels"]:
                        channel = AlertChannel(**ch_data)
                        self._channels[channel.id] = channel

            except Exception as e:
                logger.error(f"Failed to load alert state: {e}")

    def _save_state(self):
        """Save alert state to disk."""
        try:
            state = {
                "rules": [asdict(r) for r in self._rules.values()],
                "channels": [asdict(c) for c in self._channels.values()],
                "saved_at": datetime.now().isoformat(),
            }
            with open(self.db_path, "w") as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save alert state: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Rule Management
    # ═══════════════════════════════════════════════════════════════════════════

    def add_rule(self, rule: AlertRule) -> AlertRule:
        """Add a new alert rule."""
        with self._lock:
            self._rules[rule.id] = rule
            self._save_state()
        return rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an alert rule."""
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                self._save_state()
                return True
        return False

    def update_rule(self, rule_id: str, **kwargs) -> AlertRule | None:
        """Update an alert rule."""
        with self._lock:
            if rule_id not in self._rules:
                return None

            rule = self._rules[rule_id]
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)

            self._save_state()
            return rule

    def get_rule(self, rule_id: str) -> AlertRule | None:
        """Get an alert rule by ID."""
        return self._rules.get(rule_id)

    def list_rules(self) -> list[AlertRule]:
        """List all alert rules."""
        return list(self._rules.values())

    def enable_rule(self, rule_id: str) -> bool:
        """Enable an alert rule."""
        return self.update_rule(rule_id, enabled=True) is not None

    def disable_rule(self, rule_id: str) -> bool:
        """Disable an alert rule."""
        return self.update_rule(rule_id, enabled=False) is not None

    # ═══════════════════════════════════════════════════════════════════════════
    # Channel Management
    # ═══════════════════════════════════════════════════════════════════════════

    def add_channel(self, channel: AlertChannel) -> AlertChannel:
        """Add a new alert channel."""
        with self._lock:
            self._channels[channel.id] = channel
            self._save_state()
        return channel

    def remove_channel(self, channel_id: str) -> bool:
        """Remove an alert channel."""
        with self._lock:
            if channel_id in self._channels:
                del self._channels[channel_id]
                self._save_state()
                return True
        return False

    def update_channel(self, channel_id: str, **kwargs) -> AlertChannel | None:
        """Update an alert channel."""
        with self._lock:
            if channel_id not in self._channels:
                return None

            channel = self._channels[channel_id]
            for key, value in kwargs.items():
                if hasattr(channel, key):
                    setattr(channel, key, value)
                elif key in channel.config:
                    channel.config[key] = value

            self._save_state()
            return channel

    def get_channel(self, channel_id: str) -> AlertChannel | None:
        """Get an alert channel by ID."""
        return self._channels.get(channel_id)

    def list_channels(self) -> list[AlertChannel]:
        """List all alert channels."""
        return list(self._channels.values())

    def enable_channel(self, channel_id: str) -> bool:
        """Enable an alert channel."""
        return self.update_channel(channel_id, enabled=True) is not None

    def disable_channel(self, channel_id: str) -> bool:
        """Disable an alert channel."""
        return self.update_channel(channel_id, enabled=False) is not None

    def configure_webhook(self, url: str, headers: dict | None = None):
        """Configure webhook channel for external integrations (Slack/Discord)."""
        self.update_channel(
            "webhook",
            enabled=True,
            config={
                "url": url,
                "headers": headers or {"Content-Type": "application/json"},
                "timeout": 10,
            },
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Alert Evaluation
    # ═══════════════════════════════════════════════════════════════════════════

    def evaluate_rules(self, metrics_data: dict | None = None):
        """Evaluate all alert rules against current metrics."""
        now = datetime.now()

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            try:
                condition_met = self._evaluate_condition(rule, metrics_data)

                # Track state history
                self._state_history[rule.id].append(
                    {
                        "timestamp": now.isoformat(),
                        "condition_met": condition_met,
                    }
                )

                # Keep only last hour of history
                cutoff = now - timedelta(hours=1)
                self._state_history[rule.id] = [
                    h
                    for h in self._state_history[rule.id]
                    if datetime.fromisoformat(h["timestamp"]) > cutoff
                ]

                # Check if condition has persisted for duration
                if condition_met:
                    if self._check_duration(rule, now):
                        self._trigger_alert(rule, metrics_data)
                elif rule.auto_resolve:
                    self._check_auto_resolve(rule, now)

            except Exception as e:
                logger.error(f"Error evaluating rule {rule.id}: {e}")

    def _evaluate_condition(self, rule: AlertRule, metrics_data: dict | None) -> bool:
        """Evaluate a single rule's condition."""
        config = rule.condition_config

        if rule.condition_type == "threshold":
            # Get metric value from provided data or query
            metric_value = self._get_metric_value(
                config["metric"],
                config.get("source"),
                config.get("window_minutes", 5),
                metrics_data,
            )

            if metric_value is None:
                return False

            operator = config["operator"]
            threshold = config["threshold"]

            if operator == ">":
                return metric_value > threshold
            elif operator == ">=":
                return metric_value >= threshold
            elif operator == "<":
                return metric_value < threshold
            elif operator == "<=":
                return metric_value <= threshold
            elif operator == "==":
                return metric_value == threshold

        elif rule.condition_type == "system":
            return self._evaluate_system_condition(config)

        elif rule.condition_type == "heartbeat":
            return self._evaluate_heartbeat_condition(config)

        return False

    def _get_metric_value(
        self, metric: str, source: str | None, window_minutes: int, metrics_data: dict | None
    ) -> float | None:
        """Get metric value from data or query metrics collector."""
        # First try provided data
        if metrics_data:
            if source and source in metrics_data:
                return metrics_data[source].get(metric)
            return metrics_data.get(metric)

        # Try to import and query metrics collector
        try:
            from .metrics_collector import metrics_collector

            if source == "api_metrics":
                stats = metrics_collector.get_api_stats(minutes=window_minutes)
                return stats.get(metric)
            elif source == "llm_metrics":
                stats = metrics_collector.get_llm_stats(hours=max(1, window_minutes // 60))
                if metric == "daily_cost_usd":
                    # Calculate daily cost
                    daily = metrics_collector.get_llm_stats(hours=24)
                    return daily.get("total_cost_usd", 0)
                return stats.get(metric)
        except Exception as e:
            logger.debug(f"Could not query metrics collector: {e}")

        return None

    def _evaluate_system_condition(self, config: dict) -> bool:
        """Evaluate system resource condition."""
        check = config["check"]

        try:
            if check == "disk_space_percent":
                disk = psutil.disk_usage("/")
                free_percent = 100 - disk.percent
                return free_percent < config["threshold"]

            elif check == "memory_percent":
                mem = psutil.virtual_memory()
                return mem.percent > config["threshold"]

            elif check == "cpu_percent":
                cpu = psutil.cpu_percent(interval=0.1)
                return cpu > config["threshold"]

        except Exception as e:
            logger.error(f"Error checking system condition: {e}")

        return False

    def _evaluate_heartbeat_condition(self, config: dict) -> bool:
        """Evaluate service heartbeat condition."""
        url = config["url"]
        timeout = config["timeout_seconds"]

        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code != 200
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            return True
        except Exception as e:
            logger.error(f"Error checking heartbeat: {e}")
            return True

    def _check_duration(self, rule: AlertRule, now: datetime) -> bool:
        """Check if condition has persisted for required duration."""
        history = self._state_history.get(rule.id, [])
        if not history:
            return False

        # Find how long condition has been continuously met
        duration_needed = timedelta(seconds=rule.duration_seconds)

        # Check from most recent back
        condition_start = None
        for entry in reversed(history):
            if entry["condition_met"]:
                condition_start = datetime.fromisoformat(entry["timestamp"])
            else:
                break

        if condition_start is None:
            return False

        elapsed = now - condition_start
        return elapsed >= duration_needed

    def _trigger_alert(self, rule: AlertRule, metrics_data: dict | None):
        """Trigger an alert for a rule."""
        now = datetime.now()

        # Check cooldown
        last_alert = self._last_alert_time.get(rule.id)
        if last_alert:
            cooldown = timedelta(seconds=rule.cooldown_seconds)
            if now - last_alert < cooldown:
                return  # Still in cooldown

        # Check if already active
        for alert in self._active_alerts.values():
            if alert.rule_id == rule.id and alert.status == AlertStatus.ACTIVE:
                # Update last notified
                alert.last_notified_at = now
                alert.notification_count += 1
                return

        # Create new alert
        alert_id = f"{rule.id}_{now.strftime('%Y%m%d_%H%M%S')}"

        # Build alert message
        message = self._build_alert_message(rule, metrics_data)

        alert = Alert(
            id=alert_id,
            rule_id=rule.id,
            name=rule.name,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            message=message,
            details={
                "rule_config": asdict(rule),
                "metrics_snapshot": metrics_data,
            },
            started_at=now,
            last_notified_at=now,
            notification_count=1,
        )

        with self._lock:
            self._active_alerts[alert_id] = alert
            self._last_alert_time[rule.id] = now

        # Send notifications
        self._send_notifications(alert, rule.channels)

        # Trigger callbacks
        for callback in self._on_alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    def _build_alert_message(self, rule: AlertRule, metrics_data: dict | None) -> str:
        """Build human-readable alert message."""
        config = rule.condition_config

        if rule.condition_type == "threshold":
            metric = config.get("metric", "unknown")
            threshold = config.get("threshold", 0)
            operator = config.get("operator", ">")
            return f"{rule.name}: {metric} {operator} {threshold}"
        elif rule.condition_type == "system":
            check = config.get("check", "unknown")
            return f"{rule.name}: {check} threshold exceeded"
        elif rule.condition_type == "heartbeat":
            service = config.get("service", "unknown")
            return f"{rule.name}: {service} is not responding"

        return rule.description

    def _check_auto_resolve(self, rule: AlertRule, now: datetime):
        """Check if an alert should be auto-resolved."""
        for alert in list(self._active_alerts.values()):
            if alert.rule_id == rule.id and alert.status == AlertStatus.ACTIVE:
                # Check if condition has been clear for some time
                history = self._state_history.get(rule.id, [])
                if not history:
                    continue

                # Condition has cleared (we're in this method)
                # Give it a grace period (30 seconds) before resolving
                timedelta(seconds=30)

                # Resolve immediately for now (can be made more sophisticated)
                self.resolve_alert(alert.id, "auto", "Condition cleared")

    def _send_notifications(self, alert: Alert, channel_ids: list[str]):
        """Send alert notifications to configured channels."""
        for channel_id in channel_ids:
            channel = self._channels.get(channel_id)
            if not channel or not channel.enabled:
                continue

            try:
                if channel.type == "console":
                    self._send_console_notification(alert)
                elif channel.type == "file":
                    self._send_file_notification(alert, channel.config)
                elif channel.type == "webhook":
                    self._send_webhook_notification(alert, channel.config)
            except Exception as e:
                logger.error(f"Failed to send notification to {channel_id}: {e}")

    def _send_console_notification(self, alert: Alert):
        """Send alert to console."""
        severity_colors = {
            AlertSeverity.INFO: "\033[94m",  # Blue
            AlertSeverity.WARNING: "\033[93m",  # Yellow
            AlertSeverity.CRITICAL: "\033[91m",  # Red
        }
        reset = "\033[0m"
        color = severity_colors.get(alert.severity, "")

        print(f"\n{color}[ALERT - {alert.severity.value.upper()}] {alert.name}{reset}")
        print(f"  Time: {alert.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Message: {alert.message}")
        print(f"  Alert ID: {alert.id}")

    def _send_file_notification(self, alert: Alert, config: dict):
        """Send alert to log file."""
        log_path = config.get("log_path")
        json_path = config.get("json_path")

        if log_path:
            with open(log_path, "a") as f:
                f.write(
                    f"{alert.started_at.isoformat()} | {alert.severity.value.upper()} | {alert.name} | {alert.message}\n"
                )

        if json_path:
            alerts = []
            if Path(json_path).exists():
                with open(json_path) as f:
                    try:
                        alerts = json.load(f)
                    except json.JSONDecodeError:
                        alerts = []

            alerts.append(asdict(alert))

            # Keep only last 1000 alerts
            alerts = alerts[-1000:]

            with open(json_path, "w") as f:
                json.dump(alerts, f, indent=2, default=str)

    def _send_webhook_notification(self, alert: Alert, config: dict):
        """Send alert to webhook (Slack/Discord)."""
        url = config.get("url")
        if not url:
            return

        # Format payload based on webhook type
        headers = config.get("headers", {"Content-Type": "application/json"})
        timeout = config.get("timeout", 10)

        # Determine if Slack or Discord based on URL
        if "slack.com" in url:
            payload = self._format_slack_payload(alert)
        elif "discord.com" in url or "discordapp.com" in url:
            payload = self._format_discord_payload(alert)
        else:
            # Generic webhook
            payload = {
                "alert_id": alert.id,
                "rule_name": alert.name,
                "severity": alert.severity.value,
                "message": alert.message,
                "timestamp": alert.started_at.isoformat(),
            }

        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()

    def _format_slack_payload(self, alert: Alert) -> dict:
        """Format alert for Slack webhook."""
        colors = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9900",
            AlertSeverity.CRITICAL: "#ff0000",
        }

        return {
            "attachments": [
                {
                    "color": colors.get(alert.severity, "#808080"),
                    "title": f"[{alert.severity.value.upper()}] {alert.name}",
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "Alert ID",
                            "value": alert.id,
                            "short": True,
                        },
                        {
                            "title": "Started At",
                            "value": alert.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                            "short": True,
                        },
                    ],
                    "footer": "Kitty AI Observability",
                    "ts": int(alert.started_at.timestamp()),
                }
            ]
        }

    def _format_discord_payload(self, alert: Alert) -> dict:
        """Format alert for Discord webhook."""
        colors = {
            AlertSeverity.INFO: 3447003,  # Blue
            AlertSeverity.WARNING: 16776960,  # Yellow
            AlertSeverity.CRITICAL: 15158332,  # Red
        }

        return {
            "embeds": [
                {
                    "title": f"[{alert.severity.value.upper()}] {alert.name}",
                    "description": alert.message,
                    "color": colors.get(alert.severity, 808080),
                    "fields": [
                        {
                            "name": "Alert ID",
                            "value": alert.id,
                            "inline": True,
                        },
                        {
                            "name": "Started At",
                            "value": alert.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                            "inline": True,
                        },
                    ],
                    "footer": {
                        "text": "Kitty AI Observability",
                    },
                    "timestamp": alert.started_at.isoformat(),
                }
            ]
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # Alert Management
    # ═══════════════════════════════════════════════════════════════════════════

    def get_active_alerts(self, severity: AlertSeverity | None = None) -> list[Alert]:
        """Get all active alerts, optionally filtered by severity."""
        alerts = [a for a in self._active_alerts.values() if a.status == AlertStatus.ACTIVE]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda a: (a.severity.value, a.started_at), reverse=True)

    def get_alert(self, alert_id: str) -> Alert | None:
        """Get a specific alert by ID."""
        return self._active_alerts.get(alert_id)

    def acknowledge_alert(self, alert_id: str, user: str, notes: str | None = None) -> bool:
        """Acknowledge an active alert."""
        with self._lock:
            alert = self._active_alerts.get(alert_id)
            if not alert or alert.status != AlertStatus.ACTIVE:
                return False

            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now()
            alert.acknowledged_by = user

            if notes:
                alert.details["acknowledgment_notes"] = notes

            return True

    def resolve_alert(
        self, alert_id: str, user: str, resolution_notes: str | None = None
    ) -> bool:
        """Resolve an alert."""
        with self._lock:
            alert = self._active_alerts.get(alert_id)
            if not alert:
                return False

            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()
            alert.resolved_by = user

            if resolution_notes:
                alert.details["resolution_notes"] = resolution_notes

            # Move to history
            self._alert_history.append(alert)
            del self._active_alerts[alert_id]

            # Trigger callbacks
            for callback in self._on_resolve_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Resolve callback error: {e}")

            return True

    def silence_alert(self, alert_id: str, duration_minutes: int) -> bool:
        """Silence an alert for a specified duration."""
        with self._lock:
            alert = self._active_alerts.get(alert_id)
            if not alert:
                return False

            alert.status = AlertStatus.SILENCED
            alert.details["silenced_until"] = (
                datetime.now() + timedelta(minutes=duration_minutes)
            ).isoformat()

            return True

    def get_alert_history(self, limit: int = 100) -> list[Alert]:
        """Get alert history."""
        return sorted(
            self._alert_history,
            key=lambda a: a.started_at,
            reverse=True,
        )[:limit]

    # ═══════════════════════════════════════════════════════════════════════════
    # Background Processing
    # ═══════════════════════════════════════════════════════════════════════════

    def start_monitoring(self, interval_seconds: int = 30):
        """Start background monitoring thread."""
        if self._running:
            return

        self._running = True

        def monitoring_loop():
            while self._running:
                try:
                    self.evaluate_rules()
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")

                # Sleep with interruption check
                for _ in range(interval_seconds):
                    if not self._running:
                        break
                    time.sleep(1)

        self._check_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self._check_thread.start()

        logger.info(f"Alert monitoring started (interval: {interval_seconds}s)")

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._running = False
        if self._check_thread:
            self._check_thread.join(timeout=5)
        logger.info("Alert monitoring stopped")

    # ═══════════════════════════════════════════════════════════════════════════
    # Callbacks
    # ═══════════════════════════════════════════════════════════════════════════

    def on_alert(self, callback: Callable[[Alert], None]):
        """Register a callback for when alerts are triggered."""
        self._on_alert_callbacks.append(callback)

    def on_resolve(self, callback: Callable[[Alert], None]):
        """Register a callback for when alerts are resolved."""
        self._on_resolve_callbacks.append(callback)

    # ═══════════════════════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════════════════════

    def get_statistics(self) -> dict[str, Any]:
        """Get alert manager statistics."""
        active = self.get_active_alerts()

        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
            "total_channels": len(self._channels),
            "enabled_channels": sum(1 for c in self._channels.values() if c.enabled),
            "active_alerts": len(active),
            "active_by_severity": {
                "critical": sum(1 for a in active if a.severity == AlertSeverity.CRITICAL),
                "warning": sum(1 for a in active if a.severity == AlertSeverity.WARNING),
                "info": sum(1 for a in active if a.severity == AlertSeverity.INFO),
            },
            "total_resolved": len(self._alert_history),
        }


# Global singleton instance
alert_manager = AlertManager()


def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    return alert_manager


if __name__ == "__main__":
    # Demo/test
    print("Alert Manager Demo")
    print("=" * 50)

    manager = AlertManager()

    # Show default rules
    print("\nDefault Alert Rules:")
    for rule in manager.list_rules():
        status = "✓" if rule.enabled else "✗"
        print(f"  [{status}] {rule.name} ({rule.severity.value})")

    # Show channels
    print("\nAlert Channels:")
    for channel in manager.list_channels():
        status = "✓" if channel.enabled else "✗"
        print(f"  [{status}] {channel.id} ({channel.type})")

    # Show statistics
    stats = manager.get_statistics()
    print(f"\nStatistics: {stats}")
