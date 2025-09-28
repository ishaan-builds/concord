"""
FastAPI webhook server for handling AgentMail events and processing messages.
"""
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
import logging
import json
from typing import Dict, Any
from datetime import datetime
from quotequail import quote
import chromadb

from .agentmail_client import AgentMailClient
from .chatbot_engine import ChatbotEngine
from .itinerary_models import TripItinerary

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebhookServer:
    """FastAPI-based webhook server for AgentMail events."""
    
    def __init__(self, agentmail_client: AgentMailClient, chatbot_engine: ChatbotEngine,
                 default_itinerary_id: str):
        self.app = FastAPI(title="AgentMail Chatbot Webhook Server")
        self.agentmail_client = agentmail_client
        self.chatbot_engine = chatbot_engine
        self.default_itinerary_id = default_itinerary_id
        self.chroma_client = chromadb.HttpClient(host='localhost', port=8001)
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up FastAPI routes."""
        
        @self.app.get("/")
        async def health_check():
            return {"status": "healthy"}
        
        @self.app.post("/webhook/{trip_id}")
        async def handle_trip_webhook(trip_id: str, request: Request, background_tasks: BackgroundTasks):
            """Handle incoming webhook events for a specific trip."""
            try:
                payload_data = await request.json()
                logger.info(f"Received webhook for trip: {trip_id}")
                logger.info(f"Parsed webhook JSON for trip {trip_id}")
                
                event_type = payload_data.get("event_type")
                
                if event_type == "message.received":
                    # --- FIX #1: Get data from the "message" key, not "data" ---
                    message_data = payload_data.get("message") or {}
                    
                    if not message_data:
                        logger.error(f"Webhook for trip {trip_id} did not contain a 'message' object.")
                        return {"status": "error", "message": "Missing message object"}
                        
                    background_tasks.add_task(
                        self._process_trip_message,
                        trip_id,
                        message_data
                    )
                    return {"status": "accepted", "message": f"Message queued for processing for trip {trip_id}"}
                
                else:
                    logger.warning(f"Unhandled event type for trip {trip_id}: {event_type}")
                    return {"status": "ignored", "reason": "Unhandled event type"}
                    
            except Exception as e:
                logger.error(f"Error processing webhook for trip {trip_id}: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
    
    async def _process_trip_message(self, trip_id: str, message_data: Dict[str, Any]):
        """Process an incoming message for a specific trip."""
        try:
            # --- FIX #2: Use the correct keys from the raw webhook payload ---
            message_id = message_data.get("message_id")
            thread_id = message_data.get("thread_id")
            sender_raw = message_data.get("from") or message_data.get("from_")
            
            # Extract email from "Name <email>" format
            sender = sender_raw.split("<")[1].split(">")[0] if sender_raw and "<" in sender_raw else sender_raw
            
            if not sender:
                logger.error(f"No sender found in message data for trip {trip_id}: {message_data}")
                return
            
            recipient_raw = message_data.get("to", [])
            recipient = recipient_raw[0] if recipient_raw else ""
            subject = message_data.get("subject", "")
            raw_body = message_data.get("text", "") # Use "text" for the plain text body
            inbox_id = message_data.get("inbox_id")

            # Load trip data from file
            trips_file = "data/trips.json"
            with open(trips_file, 'r') as f:
                trip_data = json.load(f).get(trip_id)

            if not trip_data:
                logger.error(f"Trip {trip_id} not found in trips.json")
                return

            # Check if this message is for the correct inbox
            expected_inbox_id = trip_data['inbox_id']
            if inbox_id != expected_inbox_id:
                logger.info(f"Skipping message for trip {trip_id}: inbox_id '{inbox_id}' doesn't match expected '{expected_inbox_id}'")
                return
            
            # Skip bot's own messages to prevent loops
            if self._is_bot_message(sender):
                logger.info(f"Skipping bot's own message for trip {trip_id}")
                return

            # Use quotequail to extract only the new message content
            # query = quote(raw_body)[1][1].strip() if raw_body else ""
            raw_body = message_data.get("text", "")
            if raw_body:
                # quote() returns a list of tuples: (is_quote, text)
                # We want the text where is_quote is True (meaning it's new content)
                quote_result = quote(raw_body)
                new_content_parts = [text for is_quote, text in quote_result if is_quote]
                query = '\n'.join(new_content_parts).strip()
            else:
                query = ""

            if not query:
                logger.info(f"Message body for {message_data.get('message_id')} was empty after cleaning. Skipping.")
                return
            
            # if not query:
            #     logger.info(f"Message body for {message_id} was empty after cleaning. Skipping.")
            #     return

            logger.info(f"Processing message for trip {trip_id} from {sender} with query: '{query}'")

            # Load itinerary for context
            with open(trip_data['itinerary_file'], 'r') as f:
                itinerary = TripItinerary.from_json(f.read())
            
            self.chatbot_engine.set_itinerary(itinerary)
            
            collection = self.chroma_client.get_or_create_collection(trip_id)

            # print("Threads:\n" + str(self.agentmail_client.threads.get(thread_id=thread_id)))  # Verify thread exists

            # Generate AI response
            response = self.chatbot_engine.generate_response(
                query=query,
                itinerary_id=trip_id,
                collection=collection,
                sender_email=sender
            )
            
            ai_response = response.query_response
            
            if not response.is_pure_question and response.facts_summary:
                collection.add(
                    ids=[message_id],
                    documents=[response.facts_summary],
                    metadatas=[{'sender': sender, 'subject': subject, 'timestamp': datetime.now().isoformat()}]
                )
                logger.info(f"Stored facts from message {message_id} in ChromaDB")
            
            # Send reply using the AgentMail SDK
            sent_message = self.agentmail_client.inboxes.messages.reply(
                inbox_id=inbox_id,
                message_id=message_id,
                text=ai_response,
                html=f"<p>{ai_response.replace('\n', '<br>')}</p>" # Send a simple HTML version
            )
            
            logger.info(f"Sent response message {sent_message.message_id} to {sender} for trip {trip_id}")
            
        except Exception as e:
            logger.error(f"Error processing message for trip {trip_id}: {e}", exc_info=True)
    
    def _is_bot_message(self, sender: str) -> bool:
        """Check if a message is from one of the bot's inboxes."""
        try:
            inboxes = self.agentmail_client.inboxes.list()
            bot_addresses = [inbox.email_address for inbox in inboxes]
            return sender in bot_addresses
        except Exception as e:
            logger.warning(f"Could not check bot addresses: {e}")
            return False

def create_webhook_server(agentmail_client: AgentMailClient, 
                         chatbot_engine: ChatbotEngine,
                         default_itinerary_id: str) -> WebhookServer:
    return WebhookServer(agentmail_client, chatbot_engine, default_itinerary_id)