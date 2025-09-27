"""
FastAPI webhook server for handling AgentMail events and processing messages.
"""
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio

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
        
        @self.app.post("/webhook")
        async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
            """
            Handle incoming webhook events from AgentMail.
            
            Args:
                request: Raw request object to handle any payload format
                background_tasks: FastAPI background tasks
                
            Returns:
                Acknowledgment response
            """
            try:
                # Get raw payload and log it for debugging
                raw_body = await request.body()
                logger.info(f"Raw webhook payload: {raw_body}")
                
                # Try to parse JSON
                try:
                    payload_data = await request.json()
                    logger.info(f"Parsed webhook JSON: {json.dumps(payload_data, indent=2)}")
                except Exception as parse_error:
                    logger.error(f"Failed to parse webhook JSON: {parse_error}")
                    return {"status": "error", "message": "Invalid JSON payload"}
                
                # Handle different payload formats
                event_type = payload_data.get("event_type") or payload_data.get("type")
                
                if not event_type:
                    # Maybe the payload IS the message data directly
                    if "sender" in payload_data or "from" in payload_data:
                        logger.info("Treating payload as direct message data")
                        background_tasks.add_task(
                            self._process_incoming_message,
                            payload_data
                        )
                        return {"status": "accepted", "message": "Direct message queued for processing"}
                
                logger.info(f"Received webhook event: {event_type}")
                
                if event_type == "message.received":
                    # Extract message data from AgentMail webhook format
                    message_data = payload_data.get("message", payload_data.get("data", payload_data))
                    background_tasks.add_task(
                        self._process_incoming_message,
                        message_data
                    )
                    return {"status": "accepted", "message": "Message queued for processing"}
                
                elif event_type == "message.sent":
                    logger.info(f"Message sent confirmation: {payload_data.get('data', {}).get('id')}")
                    return {"status": "acknowledged"}
                
                else:
                    logger.warning(f"Unhandled event type: {event_type}")
                    return {"status": "ignored", "reason": "Unhandled event type"}
                    
            except Exception as e:
                logger.error(f"Error processing webhook: {e}")
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
            body = message_data.get("text") or message_data.get("body") or message_data.get("content")
            inbox_id = message_data.get("inbox_id")
            
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
            
            # Get message history for context (disabled due to API limitations)
            message_history = []
            # Note: AgentMail thread messages API returns 404, so we skip message history for now
            # This doesn't affect functionality as the AI can still generate good responses
            
            # Generate AI response
            ai_response = self.chatbot_engine.generate_response(
                query=body,
                itinerary_id=self.default_itinerary_id,
                message_history=message_history,
                sender_email=sender
            )
            
            # Format response with suggestions
            formatted_response = self.chatbot_engine.format_response_with_suggestions(
                ai_response, body
            )
            
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

# Standalone webhook handler functions for use with other frameworks
class FlaskWebhookHandler:
    """Flask-compatible webhook handler."""
    
    def __init__(self, agentmail_client: AgentMailClient, chatbot_engine: ChatbotEngine,
                 default_itinerary_id: str):
        """
        Initialize Flask webhook handler.
        
        Args:
            agentmail_client: AgentMail API client
            chatbot_engine: AI chatbot engine
            default_itinerary_id: Default itinerary ID
        """
        self.agentmail_client = agentmail_client
        self.chatbot_engine = chatbot_engine
        self.default_itinerary_id = default_itinerary_id
        self.processed_messages = set()
    
    def handle_webhook_request(self, request_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle webhook request in Flask.
        
        Args:
            request_json: JSON payload from webhook request
            
        Returns:
            Response dictionary
        """
        try:
            event_type = request_json.get("event_type")
            data = request_json.get("data", {})
            
            if event_type == "message.received":
                # Process message synchronously in Flask
                self._process_message_sync(data)
                return {"status": "processed"}
            
            return {"status": "acknowledged"}
            
        except Exception as e:
            logger.error(f"Flask webhook error: {e}")
            return {"status": "error", "message": str(e)}
    
    def _process_message_sync(self, message_data: Dict[str, Any]):
        """Process message synchronously (for Flask)."""
        message_id = message_data.get("id")
        
        if message_id in self.processed_messages:
            return
        
        self.processed_messages.add(message_id)
        
        try:
            # Similar processing logic as FastAPI version
            thread_id = message_data.get("thread_id")
            sender = message_data.get("sender")
            body = message_data.get("body")
            subject = message_data.get("subject")
            inbox_id = message_data.get("inbox_id")
            
            # Skip bot messages
            inboxes = self.agentmail_client.list_inboxes()
            bot_addresses = [inbox.email_address for inbox in inboxes]
            if sender in bot_addresses:
                return
            
            # Get message history
            message_history = []
            if thread_id:
                try:
                    messages = self.agentmail_client.get_thread_messages(thread_id)
                    message_history = [msg for msg in messages if msg.id != message_id][-10:]
                except:
                    pass
            
            # Generate and send response
            ai_response = self.chatbot_engine.generate_response(
                query=body,
                itinerary_id=self.default_itinerary_id,
                message_history=message_history,
                sender_email=sender
            )
            
            formatted_response = self.chatbot_engine.format_response_with_suggestions(
                ai_response, body
            )
            
            response_subject = f"Re: {subject}" if not subject.lower().startswith("re:") else subject
            
            self.agentmail_client.send_message(
                inbox_id=inbox_id,
                to=sender,
                subject=response_subject,
                body=formatted_response,
                thread_id=thread_id
            )
            
            logger.info(f"Processed and responded to message from {sender}")
            
        except Exception as e:
            logger.error(f"Error in sync message processing: {e}")

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