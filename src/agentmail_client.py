"""
AgentMail API Client for managing inboxes, threads, and webhooks.
"""
import requests
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class Inbox:
    """Represents an AgentMail inbox"""
    id: str
    display_name: str
    email_address: str
    created_at: datetime

@dataclass
class Thread:
    """Represents a message thread."""
    id: str
    subject: str
    participants: List[str]
    message_count: int
    last_message_at: datetime
    inbox_id: str

@dataclass
class Message:
    """Represents a single message."""
    id: str
    thread_id: str
    sender: str
    recipient: str
    subject: str
    body: str
    created_at: datetime
    message_type: str

@dataclass
class Webhook:
    """Represents a webhook configuration."""
    id: str
    event_type: str
    target_url: str
    is_active: bool
    created_at: datetime

class AgentMailClient:
    """Client for interacting with AgentMail API."""
    
    def __init__(self, api_token: str, base_url: str = "https://api.agentmail.to/v0"):
        """
        Initialize the AgentMail client.
        
        Args:
            api_token: Your AgentMail API token
            base_url: Base URL for AgentMail API (default production URL)
        """
        self.api_token = api_token
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_token}"}
        
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, headers_override: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to AgentMail API."""
        url = f"{self.base_url}{endpoint}"
        headers = self.headers.copy()
        if headers_override:
            headers.update(headers_override)
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                response = requests.post(url, json=data, headers=headers)
            elif method.upper() == "PUT":
                response = requests.put(url, json=data, headers=headers)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"AgentMail API request failed: {e}")
            logger.error(f"Request URL: {url}")
            logger.error(f"Request data: {data}")
            logger.error(f"Response status: {getattr(e.response, 'status_code', 'N/A')}")
            logger.error(f"Response text: {getattr(e.response, 'text', 'N/A')}")
            raise
    
    # Inbox Management
    def create_inbox(self, display_name: str) -> Inbox:
        """
        Create a new inbox.
        
        Args:
            display_name: Display name for the inbox
            
        Returns:
            Inbox object with details
        """
        data = {"display_name": display_name}
        response = self._make_request("POST", "/inboxes", data)
        
        return Inbox(
            id=response["inbox_id"],
            display_name=response["display_name"],
            email_address=response["inbox_id"],  # The inbox_id IS the email address
            created_at=datetime.fromisoformat(response["created_at"])
        )
    
    def list_inboxes(self) -> List[Inbox]:
        """
        List all inboxes.
        
        Returns:
            List of Inbox objects
        """
        response = self._make_request("GET", "/inboxes")
        
        inboxes = []
        for inbox_data in response.get("inboxes", []):
            inboxes.append(Inbox(
                id=inbox_data["inbox_id"],
                display_name=inbox_data["display_name"],
                email_address=inbox_data["inbox_id"],  # The inbox_id IS the email address
                created_at=datetime.fromisoformat(inbox_data["created_at"])
            ))
        
        return inboxes
    
    def get_inbox(self, inbox_id: str) -> Optional[Inbox]:
        """
        Get specific inbox by ID.
        
        Args:
            inbox_id: The inbox ID
            
        Returns:
            Inbox object or None if not found
        """
        try:
            response = self._make_request("GET", f"/inboxes/{inbox_id}")
            return Inbox(
                id=response["inbox_id"],
                display_name=response["display_name"],
                email_address=response["inbox_id"],  # The inbox_id IS the email address
                created_at=datetime.fromisoformat(response["created_at"])
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    # Thread Management
    def list_threads(self, inbox_id: Optional[str] = None) -> List[Thread]:
        """
        List all threads, optionally filtered by inbox.
        
        Args:
            inbox_id: Optional inbox ID to filter threads
            
        Returns:
            List of Thread objects
        """
        endpoint = "/threads"
        if inbox_id:
            endpoint += f"?inbox_id={inbox_id}"
            
        response = self._make_request("GET", endpoint)
        
        threads = []
        for thread_data in response.get("threads", []):
            threads.append(Thread(
                id=thread_data["id"],
                subject=thread_data["subject"],
                participants=thread_data["participants"],
                message_count=thread_data["message_count"],
                last_message_at=datetime.fromisoformat(thread_data["last_message_at"]),
                inbox_id=thread_data["inbox_id"]
            ))
        
        return threads
    
    def get_thread_messages(self, thread_id: str) -> List[Message]:
        """
        Get all messages in a thread.
        
        Note: This method is disabled due to AgentMail API limitations.
        The /threads/{id}/messages endpoint returns 404 errors.
        
        Args:
            thread_id: The thread ID
            
        Returns:
            Empty list (functionality disabled)
        """
        # Return empty list to avoid 404 errors
        # The chatbot works fine without message history
        return []
    
    def send_message(self, inbox_id: str, to: str, subject: str, body: str, 
                    message_id: Optional[str] = None) -> Message:
        """
        Send a message from an inbox or reply to an existing message.
        
        Args:
            inbox_id: The sending inbox ID
            to: Recipient email address  
            subject: Message subject
            body: Message body (text)
            message_id: Optional message ID to reply to (uses messages.reply)
            
        Returns:
            Message object for the sent message
        """
        if message_id:
            # Use the reply endpoint as documented: /inboxes/{inbox_id}/messages/reply
            data = {
                "message_id": message_id,
                "text": body,
                "html": f"<p>{body.replace('\n', '<br>')}</p>"  # Simple HTML conversion
            }
            response = self._make_request("POST", f"/inboxes/{inbox_id}/messages/reply", data)
        else:
            # Use the send endpoint for new messages: /inboxes/{inbox_id}/messages/send
            data = {
                "to": [to],
                "subject": subject,
                "text": body,
                "html": f"<p>{body.replace('\n', '<br>')}</p>"  # Simple HTML conversion
            }
            response = self._make_request("POST", f"/inboxes/{inbox_id}/messages/send", data)
            
        return Message(
            id=response.get("message_id") or response.get("id", "unknown"),
            thread_id=response.get("thread_id"),
            sender=response.get("sender", inbox_id),
            recipient=response.get("recipient", to), 
            subject=response.get("subject", subject),
            body=response.get("body", body),
            created_at=datetime.now(),  # Use current time if not provided
            message_type=response.get("type", "email")
        )
    
    # Webhook Management
    def create_webhook(self, event_type: str, target_url: str) -> Webhook:
        """
        Create a new webhook.
        
        Args:
            event_type: Type of event to listen for (e.g., "message.received")
            target_url: URL to send webhook events to
            
        Returns:
            Webhook object
        """
        data = {
            "event_types": [event_type],  # API expects array
            "url": target_url
        }
        
        response = self._make_request("POST", "/webhooks", data)
        
        return Webhook(
            id=response["webhook_id"],
            event_type=response["event_types"][0],  # Take first event type
            target_url=response["url"],
            is_active=response["enabled"],
            created_at=datetime.fromisoformat(response["created_at"])
        )
    
    def list_webhooks(self) -> List[Webhook]:
        """
        List all webhooks.
        
        Returns:
            List of Webhook objects
        """
        response = self._make_request("GET", "/webhooks")
        
        webhooks = []
        for webhook_data in response.get("webhooks", []):
            webhooks.append(Webhook(
                id=webhook_data["webhook_id"],
                event_type=webhook_data["event_types"][0] if webhook_data["event_types"] else "unknown",  # Take first event type
                target_url=webhook_data["url"],
                is_active=webhook_data["enabled"],
                created_at=datetime.fromisoformat(webhook_data["created_at"])
            ))
        
        return webhooks
    
    def delete_webhook(self, webhook_id: str) -> bool:
        """
        Delete a webhook.
        
        Args:
            webhook_id: The webhook ID to delete
            
        Returns:
            True if successful
        """
        try:
            self._make_request("DELETE", f"/webhooks/{webhook_id}")
            return True
        except requests.exceptions.HTTPError:
            return False