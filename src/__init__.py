"""
AgentMail AI Chatbot Package

A personalized AI-powered chatbot using AgentMail's infrastructure for group coordination.
"""

from .agentmail_client import AgentMailClient, Inbox, Thread, Message, Webhook
from .chatbot_engine import ChatbotEngine
from .itinerary_models import (
    TripItinerary, ItineraryEvent, GroupMember, Location, Contact,
    EventType, Priority, ItineraryManager
)
from .webhook_server import WebhookServer, FlaskWebhookHandler, create_webhook_server
from .config import Settings, get_settings

__version__ = "1.0.0"
__all__ = [
    "AgentMailClient", "Inbox", "Thread", "Message", "Webhook",
    "ChatbotEngine",
    "TripItinerary", "ItineraryEvent", "GroupMember", "Location", "Contact",
    "EventType", "Priority", "ItineraryManager",
    "WebhookServer", "FlaskWebhookHandler", "create_webhook_server",
    "Settings", "get_settings"
]