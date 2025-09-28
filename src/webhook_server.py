from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
import logging
import json
import re
from typing import Dict, Any
from quotequail import quote

from .agentmail_client import AgentMailClient
from .message_processor import process_message_and_get_reply
from .markdown_converter import format_ai_response_for_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebhookServer:
    """FastAPI-based webhook server for AgentMail events."""
    
    def __init__(self, agentmail_client: AgentMailClient, **kwargs): # Removed unused args
        self.app = FastAPI(title="AgentMail Chatbot Webhook Server")
        self.agentmail_client = agentmail_client
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
                event_type = payload_data.get("event_type")
                
                if event_type == "message.received":
                    message_data = payload_data.get("message", {})
                    if message_data:
                        background_tasks.add_task(self._process_email, trip_id, message_data)
                    return {"status": "accepted"}
                else:
                    return {"status": "ignored"}
                    
            except Exception as e:
                logger.error(f"Error in webhook handler for trip {trip_id}: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
    
    async def _process_email(self, trip_id: str, message_data: Dict[str, Any]):
        """Parses an email and delegates to the central message processor."""
        try:
            # 1. Check if message is for the correct inbox for this trip
            with open("data/trips.json", 'r') as f:
                trip_data = json.load(f).get(trip_id, {})
            
            inbox_id = message_data.get("inbox_id")
            if inbox_id != trip_data.get("inbox_id"):
                logger.info(f"Skipping message: inbox '{inbox_id}' does not match trip '{trip_id}' inbox.")
                return

            # 2. Extract key info from the email payload
            sender_raw = message_data.get("from")
            sender = sender_raw.split('<')[1].split('>')[0].strip() if sender_raw and '<' in sender_raw else sender_raw
            message_id = message_data.get("message_id")

            if not sender or not message_id:
                logger.error("Message missing sender or message_id.")
                return
            
            # 3. Clean the email body to get just the new text
            raw_body = message_data.get("text", "")
            pattern = r'^On\s+(.+?),\s+(.+?)\s+wrote:\s*$'
            if raw_body:
                quote_result = quote(raw_body)
                new_content_parts = [text for is_quote, text in quote_result if is_quote]
                query = '\n'.join(new_content_parts).strip()
                query = re.sub(pattern, "", query, flags=re.MULTILINE | re.DOTALL)
            else:
                query = ""

            if not query:
                logger.info(f"Message {message_id} had no new text. Skipping.")
                return
            
            thread = self.agentmail_client.threads.get(thread_id=message_data.get("thread_id"))

            # 4. Delegate all the core logic to the central processor
            ai_reply_text = process_message_and_get_reply(trip_id, query, sender, message_id, thread)
            
            # 5. Format the AI response with markdown-to-HTML conversion for email
            formatted_reply = format_ai_response_for_email(ai_reply_text)
            
            # 6. Send the reply via AgentMail (try HTML first, fallback to text)
            try:
                self.agentmail_client.inboxes.messages.reply(
                    inbox_id=inbox_id,
                    message_id=message_id,
                    html=formatted_reply,
                    text=ai_reply_text  # Fallback plain text
                )
                logger.info(f"Sent formatted AI reply (HTML) to {sender} for trip {trip_id}")
            except Exception as html_error:
                logger.warning(f"HTML email failed, falling back to plain text: {html_error}")
                # Fallback to plain text if HTML isn't supported
                self.agentmail_client.inboxes.messages.reply(
                    inbox_id=inbox_id,
                    message_id=message_id,
                    text=ai_reply_text
                )
                logger.info(f"Sent plain text AI reply to {sender} for trip {trip_id}")
            logger.info(f"Sent AI reply to {sender} for trip {trip_id}")

        except Exception as e:
            logger.error(f"Error processing email for trip {trip_id}: {e}", exc_info=True)

def create_webhook_server(agentmail_client: AgentMailClient, **kwargs) -> WebhookServer:
    return WebhookServer(agentmail_client=agentmail_client)