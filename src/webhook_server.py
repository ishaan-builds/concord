"""
FastAPI webhook server for handling AgentMail events and processing messages.
"""
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from quotequail import quote
import asyncio
import chromadb

from .agentmail_client import AgentMailClient
from .chatbot_engine import ChatbotEngine
from .itinerary_models import TripItinerary

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for webhook payloads
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

class WebhookServer:
    """FastAPI-based webhook server for AgentMail events."""
    
    def __init__(self, agentmail_client: AgentMailClient, chatbot_engine: ChatbotEngine,
                 default_itinerary_id: str):
        """
        Initialize the webhook server.
        
        Args:
            agentmail_client: AgentMail API client
            chatbot_engine: AI chatbot engine
            default_itinerary_id: Default itinerary ID to use for responses
        """
        self.app = FastAPI(title="AgentMail Chatbot Webhook Server")
        self.agentmail_client = agentmail_client
        self.chatbot_engine = chatbot_engine
        self.default_itinerary_id = default_itinerary_id
        self.chroma_client = chromadb.HttpClient(host='localhost', port=8001)
        
        # Store processing status to avoid duplicate processing
        self.processed_messages = set()
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up FastAPI routes."""
        
        @self.app.get("/")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "service": "AgentMail Chatbot Webhook"}
        
        @self.app.get("/status")
        async def get_status():
            """Get server status and statistics."""
            return {
                "status": "running",
                "processed_messages_count": len(self.processed_messages),
                "default_itinerary_id": self.default_itinerary_id,
                "timestamp": datetime.now().isoformat()
            }
        

        
        @self.app.post("/webhook/{trip_id}")
        async def handle_trip_webhook(trip_id: str, request: Request, background_tasks: BackgroundTasks):
            """
            Handle incoming webhook events for a specific trip.
            
            Args:
                trip_id: ID of the trip
                request: Raw request object to handle any payload format
                background_tasks: FastAPI background tasks
                
            Returns:
                Acknowledgment response
            """
            try:
                logger.info(f"Received webhook for trip: {trip_id}")
                
                # Get raw payload and log it for debugging
                raw_body = await request.body()
                logger.info(f"Raw webhook payload for trip {trip_id}: {raw_body}")
                
                # Try to parse JSON
                try:
                    payload_data = json.loads(raw_body.decode('utf-8'))
                    logger.info(f"Parsed webhook JSON for trip {trip_id}: {json.dumps(payload_data, indent=2)}")
                except json.JSONDecodeError as je:
                    logger.error(f"Failed to parse JSON payload for trip {trip_id}: {je}")
                    return {"status": "error", "message": "Invalid JSON payload"}
                
                # Extract event type
                event_type = payload_data.get("event_type")
                
                if not event_type:
                    # Maybe the payload IS the message data directly
                    if "sender" in payload_data or "from" in payload_data:
                        logger.info(f"Treating payload as direct message data for trip {trip_id}")
                        background_tasks.add_task(
                            self._process_trip_message,
                            trip_id,
                            payload_data
                        )
                        return {"status": "accepted", "message": "Direct message queued for processing"}
                
                logger.info(f"Received webhook event for trip {trip_id}: {event_type}")
                
                if event_type == "message.received":
                    # Extract message data from AgentMail webhook format
                    message_data = payload_data.get("message", payload_data.get("data", payload_data))
                    background_tasks.add_task(
                        self._process_trip_message,
                        trip_id,
                        message_data
                    )
                    return {"status": "accepted", "message": f"Message queued for processing for trip {trip_id}"}
                
                elif event_type == "message.sent":
                    logger.info(f"Message sent confirmation for trip {trip_id}: {payload_data.get('data', {}).get('id')}")
                    return {"status": "acknowledged"}
                
                else:
                    logger.warning(f"Unhandled event type for trip {trip_id}: {event_type}")
                    return {"status": "ignored", "reason": "Unhandled event type"}
                    
            except Exception as e:
                logger.error(f"Error processing webhook for trip {trip_id}: {e}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=str(e))
    
    async def _process_incoming_message(self, message_data: Dict[str, Any]):
        """
        Process an incoming message and generate a response.
        
        Args:
            message_data: Message data from webhook payload
        """
        try:
            # Extract message information from AgentMail format
            # Use the original message_id (email format) for replies
            message_id = message_data.get("message_id") or message_data.get("id")
            thread_id = message_data.get("thread_id")
            sender = message_data.get("from") or message_data.get("from_") or message_data.get("sender")
            # Extract email from "Name <email>" format
            if sender and "<" in sender and ">" in sender:
                sender = sender.split("<")[1].split(">")[0]
            
            # Ensure we have a valid sender email
            if not sender:
                logger.error(f"No sender found in message data: {message_data}")
                return
            
            recipient = message_data.get("to")
            if isinstance(recipient, list) and len(recipient) > 0:
                recipient = recipient[0]
            
            subject = message_data.get("subject") or "No Subject"
            raw_body = message_data.get("text") or message_data.get("body") or message_data.get("content")
            # Use quotequail to extract only the new message content, removing quoted replies
            if raw_body:
                lines = raw_body.split('\n')
                
                # Additional aggressive cleanup for attribution lines
                import re
                cleaned_lines = []
                
                for line in lines:
                    line_stripped = line.strip()
                    # Skip various quote attribution patterns
                    if (
                        re.match(r'^On .+ at .+ wrote:$', line_stripped, re.IGNORECASE) or
                        re.match(r'^On .+, .+ wrote:$', line_stripped, re.IGNORECASE) or
                        re.match(r'^.+ wrote:$', line_stripped, re.IGNORECASE) or
                        re.match(r'^From: .+', line_stripped, re.IGNORECASE) or
                        re.match(r'^Sent: .+', line_stripped, re.IGNORECASE) or
                        re.match(r'^To: .+', line_stripped, re.IGNORECASE) or
                        re.match(r'^Subject: .+', line_stripped, re.IGNORECASE) or
                        line_stripped.startswith('>') or
                        re.match(r'^_{5,}', line_stripped) or  # Long underscores
                        re.match(r'^-{5,}', line_stripped)     # Long dashes
                    ):
                        break  # Stop at first quote attribution/header
                    
                    if line_stripped:  # Only keep non-empty lines
                        cleaned_lines.append(line_stripped)
                
                body = '\n'.join(cleaned_lines).strip()
            else:
                body = ""
            inbox_id = message_data.get("inbox_id")
            labels = str(message_data.get("labels") or [])
            
            # Ensure we have a valid message_id
            if not message_id:
                logger.error(f"No message_id found in message data: {message_data}")
                return
                
            logger.info(f"Extracted: id={message_id}, sender={sender}, subject={subject}, body={body[:50] if body else None}...")
            
            # Skip if already processed
            if message_id in self.processed_messages:
                logger.info(f"Message {message_id} already processed, skipping")
                return
            
            # Mark as processing
            self.processed_messages.add(message_id)
            
            logger.info(f"Processing message from {sender}: {subject}")
            
            # Skip if this is our own message (avoid loops)
            if self._is_bot_message(sender, recipient):
                logger.info("Skipping bot's own message")
                return
            
            logger.info(f"Message stored in database with id: {message_id}")
            
            # Get message history for context (disabled due to API limitations)
            message_history = []
            # Note: AgentMail thread messages API returns 404, so we skip message history for now
            # This doesn't affect functionality as the AI can still generate good responses
            
            # Generate AI response
            response = self.chatbot_engine.generate_response(
                query=body,
                itinerary_id=self.default_itinerary_id,
                message_history=message_history,
                sender_email=sender,
            )

            ai_response = response.query_response
            
            # Use raw AI response
            formatted_response = ai_response
            
            # Send response via AgentMail - send new message for now (reply endpoints seem to have issues)
            response_subject = self._generate_response_subject(subject)
            
            sent_message = self.agentmail_client.send_message(
                inbox_id=inbox_id,
                to=sender,
                subject=response_subject,
                body=formatted_response,
                message_id=None  # Send as new message instead of reply for now
            )
            
            logger.info(f"Sent response message {sent_message.id} to {sender}")
            
        except Exception as e:
            message_id = message_data.get('message_id') or message_data.get('id', 'unknown')
            logger.error(f"Error processing message {message_id}: {e}")
            import traceback
            traceback.print_exc()
            
            # Try to send error response
            try:
                error_response = ("I'm sorry, I encountered an error processing your request. "
                                "Please try again later or contact the trip organizer directly.")
                
                # Extract sender properly for error response
                error_sender = message_data.get("from") or message_data.get("from_") or message_data.get("sender")
                if error_sender and "<" in error_sender and ">" in error_sender:
                    error_sender = error_sender.split("<")[1].split(">")[0]
                
                if error_sender:
                    self.agentmail_client.send_message(
                        inbox_id=message_data.get("inbox_id"),
                        to=error_sender,
                        subject="Re: " + message_data.get("subject", ""),
                        body=error_response,
                        message_id=None  # Send as new message for error responses too
                    )
            except Exception as send_error:
                logger.error(f"Failed to send error response: {send_error}")
    
    async def _process_trip_message(self, trip_id: str, message_data: Dict[str, Any]):
        """
        Process an incoming message for a specific trip.
        
        Args:
            trip_id: ID of the trip
            message_data: Message data from webhook payload
        """
        try:
            import os
            import json
            
            # Load trip data
            trips_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'trips.json')
            if not os.path.exists(trips_file):
                logger.error(f"Trips file not found: {trips_file}")
                return
                
            with open(trips_file, 'r') as f:
                trips_data = json.load(f)
            
            if trip_id not in trips_data:
                logger.error(f"Trip {trip_id} not found in trips data")
                return
                
            trip_data = trips_data[trip_id]
            itinerary_file = trip_data.get('itinerary_file')
            
            if not itinerary_file or not os.path.exists(itinerary_file):
                logger.error(f"Itinerary file not found for trip {trip_id}: {itinerary_file}")
                return
            
            # Load trip-specific itinerary
            with open(itinerary_file, 'r') as f:
                itinerary_data = f.read()
            
            from .itinerary_models import TripItinerary
            trip_itinerary = TripItinerary.from_json(itinerary_data)
            
            # Create a new chatbot engine instance for this trip
            from .chatbot_engine import ChatbotEngine
            from .config import get_settings
            
            settings = get_settings()
            trip_chatbot_engine = ChatbotEngine(
                ai_provider=settings.ai.provider,
                openai_api_key=settings.ai.openai_api_key,
                google_api_key=settings.ai.google_api_key,
                model=settings.ai.google_model if settings.ai.provider == 'google' else settings.ai.openai_model,
                max_tokens=settings.ai.max_tokens,
                temperature=settings.ai.temperature
            )
            trip_chatbot_engine.set_itinerary(trip_itinerary)
            
            logger.info(f"Loaded itinerary for trip {trip_id}: {trip_itinerary.title}")
            
            # Extract message information from AgentMail format
            message_id = message_data.get("message_id") or message_data.get("id")
            thread_id = message_data.get("thread_id")
            sender = message_data.get("from") or message_data.get("from_") or message_data.get("sender")
            
            # Extract email from "Name <email>" format
            if sender and "<" in sender and ">" in sender:
                sender = sender.split("<")[1].split(">")[0]
            
            if not sender:
                logger.error(f"No sender found in message data for trip {trip_id}: {message_data}")
                return
            
            recipient = message_data.get("to")
            if isinstance(recipient, list) and len(recipient) > 0:
                recipient = recipient[0]
            elif isinstance(recipient, list):
                recipient = ""
            subject = message_data.get("subject", "")
            raw_body = message_data.get("body") or message_data.get("text", "")

            thread = 
            # Use quotequail to extract only the new message content, removing quoted replies
            if raw_body:
                quote_result = quote(raw_body)  # quotequail's quote function extracts new content
                
                # Handle quotequail return value (returns list of tuples: (is_quote, text))
                if isinstance(quote_result, list):
                    # Extract only the non-quoted text (where is_quote is True)
                    new_content_parts = []
                    for is_quote, text in quote_result:
                        if is_quote:  # True means it's new content, not a quote
                            new_content_parts.append(text)
                    body = '\n'.join(new_content_parts)
                else:
                    body = quote_result or ''
                
                # Additional aggressive cleanup for attribution lines
                import re
                lines = body.split('\n')
                cleaned_lines = []
                
                for line in lines:
                    line_stripped = line.strip()
                    # Skip various quote attribution patterns
                    if (
                        re.match(r'^On .+ at .+ wrote:$', line_stripped, re.IGNORECASE) or
                        re.match(r'^On .+, .+ wrote:$', line_stripped, re.IGNORECASE) or
                        re.match(r'^.+ wrote:$', line_stripped, re.IGNORECASE) or
                        re.match(r'^From: .+', line_stripped, re.IGNORECASE) or
                        re.match(r'^Sent: .+', line_stripped, re.IGNORECASE) or
                        re.match(r'^To: .+', line_stripped, re.IGNORECASE) or
                        re.match(r'^Subject: .+', line_stripped, re.IGNORECASE) or
                        line_stripped.startswith('>') or
                        re.match(r'^_{5,}', line_stripped) or  # Long underscores
                        re.match(r'^-{5,}', line_stripped)     # Long dashes
                    ):
                        break  # Stop at first quote attribution/header
                    
                    if line_stripped:  # Only keep non-empty lines
                        cleaned_lines.append(line_stripped)
                
                query = '\n'.join(cleaned_lines).strip()
            else:
                query = ""
            inbox_id = message_data.get("inbox_id") or trip_data['inbox_id']
            labels = str(message_data.get("labels") or [])
            
            # Check if this message is actually for this trip's inbox
            expected_inbox_id = trip_data['inbox_id']
            if inbox_id != expected_inbox_id:
                logger.info(f"Skipping message for trip {trip_id}: inbox_id '{inbox_id}' doesn't match expected '{expected_inbox_id}'")
                return
            
            logger.info(f"Processing message for trip {trip_id} from {sender}: {subject}")
            
            # Skip if this is a bot message (avoid loops)
            if self._is_bot_message(sender, recipient):
                logger.info(f"Skipping bot's own message for trip {trip_id}")
                return
            
            collection = self.chroma_client.get_or_create_collection(trip_id)

            # Generate AI response using trip-specific chatbot
            response = trip_chatbot_engine.generate_response(
                query=query,
                itinerary_id=trip_id,
                collection=collection,
                message_history=[],
                sender_email=sender
            )
            
            ai_response = response.query_response
            
            if not response.is_pure_question:
                collection.add(
                    ids=message_id,
                    documents=response.facts_summary,
                    metadatas={'sender': sender, 'recipient': recipient, 'subject': subject, 'labels': labels}
                )

            logger.info(f"Stored message {message_id} in database")

            # Use raw AI response
            formatted_response = ai_response
            
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
    
    def _is_bot_message(self, sender: str, recipient: str) -> bool:
        """
        Check if a message is from the bot itself to avoid response loops.
        
        Args:
            sender: Message sender email
            recipient: Message recipient email
            
        Returns:
            True if this is a bot message
        """
        # Get bot's inbox addresses
        try:
            inboxes = self.agentmail_client.list_inboxes()
            bot_addresses = [inbox.email_address for inbox in inboxes]
            return sender in bot_addresses
        except Exception as e:
            logger.warning(f"Could not check bot addresses: {e}")
            return False
    
    def _generate_response_subject(self, original_subject: str) -> str:
        """
        Generate appropriate response subject line.
        
        Args:
            original_subject: Original message subject
            
        Returns:
            Response subject line
        """
        # Remove common prefixes
        subject = original_subject.strip()
        prefixes_to_remove = ["re:", "fwd:", "fw:"]
        
        for prefix in prefixes_to_remove:
            if subject.lower().startswith(prefix):
                subject = subject[len(prefix):].strip()
        
        # Add "Re:" if not already there
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        
        return subject
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self.app

def create_webhook_server(agentmail_client: AgentMailClient, 
                         chatbot_engine: ChatbotEngine,
                         default_itinerary_id: str) -> WebhookServer:
    """
    Factory function to create webhook server.
    
    Args:
        agentmail_client: AgentMail API client
        chatbot_engine: AI chatbot engine
        default_itinerary_id: Default itinerary ID
        
    Returns:
        Configured webhook server
    """
    return WebhookServer(agentmail_client, chatbot_engine, default_itinerary_id)