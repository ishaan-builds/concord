# src/__init__.py

"""
Initializes the src package and exposes key components for easier access.
"""

# Expose the main client from our custom wrapper
from .agentmail_client import AgentMailClient

# Expose the data models directly from the official agentmail SDK for type hinting
try:
    from agentmail import Message, Thread
    from agentmail.inboxes.types import Inbox
    from agentmail.webhooks import Webhook
except ImportError:
    # This allows the app to provide a more helpful error if 'agentmail' isn't installed
    print("ERROR: The 'agentmail' package is not installed. Please run 'pip install agentmail'.")
    # Define dummy classes to avoid crashing on import, allowing the real error to be seen
    class Inbox: pass
    class Thread: pass
    class Message: pass
    class Webhook: pass

# Expose other core components of the application
from .chatbot_engine import ChatbotEngine
from .itinerary_models import TripItinerary
from .config import get_settings