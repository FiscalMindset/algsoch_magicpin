import time
from datetime import datetime


class BotState:
    """Global state management for the bot."""

    def __init__(self):
        self.start_time = time.time()
        self.context_store = None
        self.conversation_manager = None
        self.composition_service = None
        self.groq_api_key = None
        self.last_healthz = datetime.utcnow()
        self.sent_suppression_keys = set()

    def get_uptime_seconds(self) -> int:
        """Get uptime in seconds."""
        return int(time.time() - self.start_time)

    def update_healthz(self):
        """Update last healthz timestamp."""
        self.last_healthz = datetime.utcnow()


# Global bot state instance
bot_state = BotState()
