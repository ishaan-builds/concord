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

@dataclass
class InboxResponse:
    """Response object for inbox operations."""
    inbox_id: str
    display_name: str
    email_address: str
    created_at: datetime

@dataclass
class MessageResponse:
    """Response object for message operations."""
    message_id: str
    thread_id: Optional[str]
    sender: str
    recipient: str
    subject: str
    body: str
    created_at: datetime
    message_type: str

@dataclass
class MessagesListResponse:
    """Response object for listing messages."""
    messages: List['MessageResponse']
    count: int
    
    def __iter__(self):
        return iter(self.messages)
    
    def __len__(self):
        return self.count

@dataclass
class ThreadResponse:
    """Response object for thread operations with messages."""
    id: str
    subject: str
    participants: List[str]
    message_count: int
    last_message_at: datetime
    inbox_id: str
    messages: List['MessageResponse']

class InboxMessagesManager:
    """Manager for inbox-specific message operations."""
    
    def __init__(self, client: 'AgentMail'):
        self.client = client
    
    def send(self, inbox_id: str, to: str, subject: str, text: str, html: Optional[str] = None, labels: Optional[List[str]] = None) -> 'MessageResponse':
        """Send a new message from an inbox."""
        data = {
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
            "text": text,
            "html": html or self.client._convert_text_to_html(text)
        }
        if labels:
            data["labels"] = labels
            
        response = self.client._make_request("POST", f"/inboxes/{inbox_id}/messages/send", data)
        
        return MessageResponse(
            message_id=response.get("message_id") or response.get("id", "unknown"),
            thread_id=response.get("thread_id"),
            sender=response.get("sender", inbox_id),
            recipient=response.get("recipient", to), 
            subject=response.get("subject", subject),
            body=response.get("body", text),
            created_at=datetime.now(),
            message_type=response.get("type", "email")
        )
    
    def reply(self, inbox_id: str, message_id: str, text: str, html: Optional[str] = None, attachments: Optional[List] = None) -> 'MessageResponse':
        """Reply to a message."""
        data = {
            "message_id": message_id,
            "text": text,
            "html": html or self.client._convert_text_to_html(text)
        }
        if attachments:
            data["attachments"] = attachments
            
        response = self.client._make_request("POST", f"/inboxes/{inbox_id}/messages/reply", data)
        
        return MessageResponse(
            message_id=response.get("message_id") or response.get("id", "unknown"),
            thread_id=response.get("thread_id"),
            sender=response.get("sender", inbox_id),
            recipient=response.get("recipient"),
            subject=response.get("subject"),
            body=response.get("body", text),
            created_at=datetime.now(),
            message_type=response.get("type", "email")
        )
    
    def list(self, inbox_id: str) -> 'MessagesListResponse':
        """List all messages in an inbox."""
        response = self.client._make_request("GET", f"/inboxes/{inbox_id}/messages")
        
        messages = []
        for message_data in response.get("messages", []):
            messages.append(MessageResponse(
                message_id=message_data["id"],
                thread_id=message_data.get("thread_id"),
                sender=message_data["sender"],
                recipient=message_data["recipient"],
                subject=message_data.get("subject", ""),
                body=message_data.get("body", ""),
                created_at=datetime.fromisoformat(message_data["created_at"]),
                message_type=message_data.get("type", "email")
            ))
        return MessagesListResponse(messages=messages, count=len(messages))
    
    def get(self, inbox_id: str, message_id: str) -> Optional[Message]:
        """Get a specific message."""
        try:
            response = self.client._make_request("GET", f"/inboxes/{inbox_id}/messages/{message_id}")
            return Message(
                id=response["id"],
                thread_id=response.get("thread_id"),
                sender=response["sender"],
                recipient=response["recipient"],
                subject=response.get("subject", ""),
                body=response.get("body", ""),
                created_at=datetime.fromisoformat(response["created_at"]),
                message_type=response.get("type", "email")
            )
        except Exception as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            return None

class InboxThreadsManager:
    """Manager for inbox-specific thread operations."""
    
    def __init__(self, client: 'AgentMail'):
        self.client = client
    
    def list(self, inbox_id: str) -> List[Thread]:
        """List all threads in an inbox."""
        response = self.client._make_request("GET", f"/inboxes/{inbox_id}/threads")
        
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

class InboxesManager:
    """Manager for inbox operations."""
    
    def __init__(self, client: 'AgentMail'):
        self.client = client
        self.messages = InboxMessagesManager(client)
        self.threads = InboxThreadsManager(client)
    
    def create(self, username: Optional[str] = None, domain: Optional[str] = None, display_name: Optional[str] = None) -> 'InboxResponse':
        """Create a new inbox."""
        data = {}
        if username:
            data["username"] = username
        if domain:
            data["domain"] = domain
        if display_name:
            data["display_name"] = display_name
            
        response = self.client._make_request("POST", "/inboxes", data)
        
        return InboxResponse(
            inbox_id=response["inbox_id"],
            display_name=response.get("display_name", ""),
            email_address=response["inbox_id"],
            created_at=datetime.fromisoformat(response["created_at"])
        )
    
    def get(self, inbox_id: str) -> Optional['InboxResponse']:
        """Get a specific inbox by ID."""
        try:
            response = self.client._make_request("GET", f"/inboxes/{inbox_id}")
            return InboxResponse(
                inbox_id=response["inbox_id"],
                display_name=response.get("display_name", ""),
                email_address=response["inbox_id"],
                created_at=datetime.fromisoformat(response["created_at"])
            )
        except Exception as e:
            logger.error(f"Failed to get inbox {inbox_id}: {e}")
            return None
    
    def list(self) -> List['InboxResponse']:
        """List all inboxes."""
        response = self.client._make_request("GET", "/inboxes")
        
        inboxes = []
        for inbox_data in response.get("inboxes", []):
            inboxes.append(InboxResponse(
                inbox_id=inbox_data["inbox_id"],
                display_name=inbox_data.get("display_name", ""),
                email_address=inbox_data["inbox_id"],
                created_at=datetime.fromisoformat(inbox_data["created_at"])
            ))
        return inboxes

class ThreadsManager:
    """Manager for organization-wide thread operations."""
    
    def __init__(self, client: 'AgentMail'):
        self.client = client
    
    def get(self, thread_id: str) -> 'ThreadResponse':
        """Get thread details including all messages."""
        response = self.client._make_request("GET", f"/threads/{thread_id}")
        
        messages = []
        for message_data in response.get("messages", []):
            messages.append(MessageResponse(
                message_id=message_data["id"],
                thread_id=message_data.get("thread_id", thread_id),
                sender=message_data["sender"],
                recipient=message_data["recipient"],
                subject=message_data.get("subject", ""),
                body=message_data.get("body", ""),
                created_at=datetime.fromisoformat(message_data["created_at"]),
                message_type=message_data.get("type", "email")
            ))
        
        return ThreadResponse(
            id=response["id"],
            subject=response["subject"],
            participants=response["participants"],
            message_count=response["message_count"],
            last_message_at=datetime.fromisoformat(response["last_message_at"]),
            inbox_id=response["inbox_id"],
            messages=messages
        )
    
    def list(self) -> List[Thread]:
        """List all threads across the organization."""
        response = self.client._make_request("GET", "/threads")
        
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

class AgentMail:
    """Client for interacting with AgentMail API."""
    
    def __init__(self, api_key: Optional[str] = None, api_token: Optional[str] = None, base_url: str = "https://api.agentmail.to/v0"):
        """
        Initialize the AgentMail client.
        
        Args:
            api_key: Your AgentMail API key (preferred)
            api_token: Your AgentMail API token (legacy, for backward compatibility)
            base_url: Base URL for AgentMail API (default production URL)
        """
        # Support both api_key (new) and api_token (legacy) for backward compatibility
        token = api_key or api_token
        if not token:
            raise ValueError("Either api_key or api_token must be provided")
            
        self.api_token = token
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}
        
        # Initialize nested managers
        self.inboxes = InboxesManager(self)
        self.threads = ThreadsManager(self)
        
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
            
            # Handle empty responses (common with DELETE requests)
            if not response.text.strip():
                return None
            
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
        Get all messages in a thread using the threads endpoint.
        
        Args:
            thread_id: The thread ID
            
        Returns:
            List of Message objects
        """
        try:
            # Use the threads.get() method which should include messages
            thread_data = self.threads.get(thread_id)
            
            messages = []
            # Extract messages from the thread response
            messages_data = thread_data.get("messages", [])
            
            for message_data in messages_data:
                messages.append(Message(
                    id=message_data["id"],
                    thread_id=message_data.get("thread_id", thread_id),
                    sender=message_data["sender"],
                    recipient=message_data["recipient"],
                    subject=message_data.get("subject", ""),
                    body=message_data.get("body", ""),
                    created_at=datetime.fromisoformat(message_data["created_at"]),
                    message_type=message_data.get("type", "email")
                ))
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get thread messages for {thread_id}: {e}")
            return []
    
    def _convert_text_to_html(self, text: str) -> str:
        """
        Convert plain text to HTML with proper formatting.
        
        Args:
            text: Plain text message
            
        Returns:
            HTML formatted message
        """
        import re
        
        # Handle different types of newlines and escape sequences
        html = text
        
        # Replace various newline representations
        html = html.replace('\\n', '\n')  # Convert literal \n to actual newlines
        html = html.replace('\r\n', '\n')  # Normalize Windows line endings
        
        # Split into paragraphs (double newlines)
        paragraphs = html.split('\n\n')
        formatted_paragraphs = []
        
        for paragraph in paragraphs:
            if paragraph.strip():
                # Convert single newlines within paragraphs to <br>
                paragraph_html = paragraph.replace('\n', '<br>')
                
                # Handle markdown-style bold text
                paragraph_html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', paragraph_html)
                
                # Wrap in paragraph tags
                formatted_paragraphs.append(f'<p>{paragraph_html}</p>')
        
        return ''.join(formatted_paragraphs)
    
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
            html_body = self._convert_text_to_html(body)
            data = {
                "message_id": message_id,
                "text": body,
                "html": html_body
            }
            response = self._make_request("POST", f"/inboxes/{inbox_id}/messages/reply", data)
        else:
            # Use the send endpoint for new messages: /inboxes/{inbox_id}/messages/send
            html_body = self._convert_text_to_html(body)
            data = {
                "to": [to],
                "subject": subject,
                "text": body,
                "html": html_body
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
            result = self._make_request("DELETE", f"/webhooks/{webhook_id}")
            return True
        except requests.exceptions.HTTPError:
            return False

# Backward compatibility alias
AgentMailClient = AgentMail