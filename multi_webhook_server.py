#!/usr/bin/env python3
"""
Multi-trip webhook server for handling AgentMail events for multiple trips.
"""
import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
import uvicorn

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.config import get_settings
from src.agentmail_client import AgentMailClient
from src.chatbot_engine import ChatbotEngine
from src.itinerary_models import TripItinerary

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global storage for trips (in production, use a database)
TRIPS_FILE = os.path.join(project_root, 'data', 'trips.json')

def load_trips_from_file():
    """Load trips from persistent storage."""
    try:
        if os.path.exists(TRIPS_FILE):
            with open(TRIPS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading trips: {e}")
    return {}

class WebhookMessage(BaseModel):
    """Webhook message data model."""
    id: str
    thread_id: str
    sender: str
    recipient: str
    subject: str
    body: str
    created_at: str
    message_type: str = "email"

class WebhookPayload(BaseModel):
    """Webhook event payload model."""
    event_type: str
    timestamp: str
    data: Dict[str, Any]

class MultiTripWebhookServer:
    """FastAPI-based webhook server for handling multiple trip inboxes."""
    
    def __init__(self):
        """Initialize the multi-trip webhook server."""
        self.app = FastAPI(title="AgentMail Multi-Trip Webhook Server")
        self.trips_store = load_trips_from_file()
        
        # Initialize settings and clients
        try:
            self.settings = get_settings()
            self.agentmail_client = AgentMailClient(self.settings.agentmail.api_token)
        except Exception as e:
            logger.error(f"Failed to initialize AgentMail client: {e}")
            raise
        
        # Set up routes
        self._setup_routes()
        
        # Cache for chatbot engines (trip_id -> ChatbotEngine)
        self.chatbot_engines = {}
        
    def _setup_routes(self):
        """Set up FastAPI routes."""
        
        @self.app.post("/webhook/{trip_id}")
        async def webhook_handler(trip_id: str, request: Request, background_tasks: BackgroundTasks):
            """Handle incoming webhook events for a specific trip."""
            try:
                # Load current trips data
                self.trips_store = load_trips_from_file()
                
                if trip_id not in self.trips_store:
                    logger.error(f"Trip {trip_id} not found in trips store")
                    raise HTTPException(status_code=404, detail="Trip not found")
                
                # Parse webhook payload
                payload = await request.json()
                logger.info(f"Received webhook for trip {trip_id}: {payload.get('event_type', 'unknown')}")
                
                # Handle message.received events
                if payload.get("event_type") == "message.received":
                    message_data = payload.get("data", {})
                    background_tasks.add_task(self._process_trip_message, trip_id, message_data)
                
                return {"status": "success", "trip_id": trip_id}
                
            except Exception as e:
                logger.error(f"Error handling webhook for trip {trip_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "trips_count": len(self.trips_store)}
        
        @self.app.get("/")
        async def root():
            """Root endpoint with server info."""
            return {
                "service": "AgentMail Multi-Trip Webhook Server",
                "trips_count": len(self.trips_store),
                "status": "running"
            }
    
    async def _process_trip_message(self, trip_id: str, message_data: Dict[str, Any]):
        """
        Process an incoming message for a specific trip.
        
        Args:
            trip_id: ID of the trip
            message_data: Message data from webhook payload
        """
        try:
            # Get trip data
            trip = self.trips_store.get(trip_id)
            if not trip:
                logger.error(f"Trip {trip_id} not found")
                return
            
            # Extract message information
            message_id = message_data.get("message_id") or message_data.get("id")
            thread_id = message_data.get("thread_id")
            sender = message_data.get("from") or message_data.get("from_") or message_data.get("sender")
            
            # Extract email from "Name <email>" format
            if sender and "<" in sender and ">" in sender:
                sender = sender.split("<")[1].split(">")[0]
            
            if not sender:
                logger.error(f"No sender found in message data: {message_data}")
                return
            
            recipient = message_data.get("to")
            subject = message_data.get("subject", "")
            body = message_data.get("body", "")
            inbox_id = message_data.get("inbox_id") or trip['inbox_id']
            
            logger.info(f"Processing message for trip {trip_id} from {sender}: {subject}")
            
            # Skip if this is a bot message (avoid loops)
            if self._is_bot_message(sender, recipient):
                logger.info("Skipping bot's own message")
                return
            
            # Get or create chatbot engine for this trip
            chatbot_engine = await self._get_chatbot_engine(trip_id)
            if not chatbot_engine:
                logger.error(f"Could not initialize chatbot engine for trip {trip_id}")
                return
            
            # Generate AI response
            ai_response = chatbot_engine.generate_response(
                query=body,
                itinerary_id=trip_id,
                message_history=[],  # TODO: Implement message history
                sender_email=sender
            )
            
            # Format response with suggestions
            formatted_response = chatbot_engine.format_response_with_suggestions(
                ai_response, body
            )
            
            # Send response
            response_subject = self._generate_response_subject(subject)
            
            sent_message = self.agentmail_client.send_message(
                inbox_id=inbox_id,
                to=sender,
                subject=response_subject,
                body=formatted_response,
                message_id=None  # Send as new message
            )
            
            logger.info(f"Sent response message {sent_message.id} to {sender} for trip {trip_id}")
            
        except Exception as e:
            logger.error(f"Error processing message for trip {trip_id}: {e}")
            import traceback
            traceback.print_exc()
            
            # Try to send error response
            try:
                error_response = ("I'm sorry, I encountered an error processing your request. "
                                "Please try again later or contact the trip organizer directly.")
                
                self.agentmail_client.send_message(
                    inbox_id=message_data.get("inbox_id"),
                    to=sender,
                    subject="Re: " + message_data.get("subject", ""),
                    body=error_response,
                    message_id=None
                )
            except Exception as send_error:
                logger.error(f"Failed to send error response: {send_error}")
    
    async def _get_chatbot_engine(self, trip_id: str) -> Optional[ChatbotEngine]:
        """
        Get or create a chatbot engine for a specific trip.
        
        Args:
            trip_id: ID of the trip
            
        Returns:
            ChatbotEngine instance or None if failed
        """
        try:
            # Check if we already have a cached engine
            if trip_id in self.chatbot_engines:
                return self.chatbot_engines[trip_id]
            
            # Get trip data
            trip = self.trips_store.get(trip_id)
            if not trip:
                logger.error(f"Trip {trip_id} not found")
                return None
            
            # Load itinerary
            itinerary_file = trip.get('itinerary_file')
            if not itinerary_file or not os.path.exists(itinerary_file):
                logger.error(f"Itinerary file not found for trip {trip_id}: {itinerary_file}")
                return None
            
            with open(itinerary_file, 'r') as f:
                itinerary_data = f.read()
            
            itinerary = TripItinerary.from_json(itinerary_data)
            
            # Create chatbot engine
            chatbot_engine = ChatbotEngine(
                ai_provider=self.settings.ai.provider,
                openai_api_key=self.settings.ai.openai_api_key,
                google_api_key=self.settings.ai.google_api_key,
                model=self.settings.ai.google_model if self.settings.ai.provider == 'google' else self.settings.ai.openai_model,
                max_tokens=self.settings.ai.max_tokens,
                temperature=self.settings.ai.temperature
            )
            
            chatbot_engine.set_itinerary(itinerary)
            
            # Cache the engine
            self.chatbot_engines[trip_id] = chatbot_engine
            
            return chatbot_engine
            
        except Exception as e:
            logger.error(f"Error creating chatbot engine for trip {trip_id}: {e}")
            return None
    
    def _is_bot_message(self, sender: str, recipient: str) -> bool:
        """Check if a message is from the bot itself."""
        if not sender:
            return False
        
        # Check if sender matches any of our known inbox addresses
        for trip_data in self.trips_store.values():
            if sender == trip_data.get('inbox_email') or sender == trip_data.get('inbox_id'):
                return True
        
        return False
    
    def _generate_response_subject(self, original_subject: str) -> str:
        """Generate appropriate response subject line."""
        subject = original_subject.strip()
        prefixes_to_remove = ["re:", "fwd:", "fw:"]
        
        for prefix in prefixes_to_remove:
            if subject.lower().startswith(prefix):
                subject = subject[len(prefix):].strip()
        
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        
        return subject
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self.app

def create_multi_trip_webhook_server() -> MultiTripWebhookServer:
    """Create and configure the multi-trip webhook server."""
    return MultiTripWebhookServer()

if __name__ == "__main__":
    # Create the webhook server
    webhook_server = create_multi_trip_webhook_server()
    
    # Get settings
    settings = get_settings()
    
    # Run server on different port to avoid conflicts
    port = int(os.environ.get('MULTI_WEBHOOK_PORT', 8001))
    
    print("🤖 Starting Multi-Trip AgentMail Webhook Server...")
    print(f"🔗 Server will run on {settings.webhook.host}:{port}")
    print(f"📧 Ready to handle webhooks for multiple trips")
    print("🔄 Use Ctrl+C to stop the server")
    print("-" * 50)
    
    # Run server on different port to avoid conflicts
    port = int(os.environ.get('MULTI_WEBHOOK_PORT', 8001))
    uvicorn.run(
        webhook_server.get_app(),
        host=settings.webhook.host,
        port=port,
        log_level=settings.app.log_level.lower()
    )