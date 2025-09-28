"""
AgentMail API Client for managing inboxes, threads, and webhooks.
"""
import logging
from typing import Optional

from agentmail import AgentMail as AgentMailSDK
from agentmail import Message

logger = logging.getLogger(__name__)

class AgentMail:
    """
    Client for interacting with the AgentMail API using the official SDK.
    """
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the AgentMail client.
        
        Args:
            api_key: Your AgentMail API key.
        """
        if not api_key:
            raise ValueError("API key must be provided")
            
        self.client = AgentMailSDK(api_key=api_key)
        
        # Expose the SDK's managers directly
        self.inboxes = self.client.inboxes
        self.threads = self.client.threads
        self.webhooks = self.client.webhooks

# Backward compatibility alias
AgentMailClient = AgentMail