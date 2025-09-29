"""
AI-powered chatbot engine for processing group itinerary queries.
"""
import logging
import os
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from chromadb import Collection  
from pydantic import BaseModel, Field
import re
import json

from .itinerary_models import TripItinerary, ItineraryManager
from ..clients.agentmail_client import Message

logger = logging.getLogger(__name__)

class LocationData(BaseModel):
    """Location information for events."""
    name: str = Field(description="Name of the location")
    city: Optional[str] = Field(description="City name", default=None)

class EventData(BaseModel):
    """Event data structure."""
    title: str = Field(description="Event title")
    event_type: str = Field(description="Type of event: restaurant, activity, hotel, flight, transport, meeting, free_time, other")
    start_datetime: str = Field(description="Start date and time in YYYY-MM-DD HH:MM:SS format")
    end_datetime: str = Field(description="End date and time in YYYY-MM-DD HH:MM:SS format")
    location: LocationData = Field(description="Location information")
    description: str = Field(description="Event description")
    cost: float = Field(description="Cost of the event", default=0.0)
    priority: str = Field(description="Priority level: high, medium, low", default="medium")

class ItineraryAction(BaseModel):
    """Represents an action to take on the itinerary."""
    action_type: str = Field(description="Type of action: add_event, remove_event, modify_event, or none")
    event_data: Optional[EventData] = Field(description="Event data for add/modify actions", default=None)
    removal_criteria: Optional[str] = Field(description="Criteria for removing events", default=None)
    reasoning: str = Field(description="AI's reasoning for this scheduling decision")

class EmailAnalysis(BaseModel):
    """Enhanced email analysis with itinerary management capabilities."""
    is_pure_question: bool = Field(description="True if this is only a question with no facts to store")
    facts_summary: str = Field(description="Summary of factual information to store. Empty if pure question.")
    query_response: str = Field(description="Response to send back to the user")
    itinerary_actions: List[ItineraryAction] = Field(description="List of itinerary actions to perform", default=[])

class ChatbotEngine:
    """AI-powered chatbot for group itinerary management."""
    
    def __init__(self, ai_provider: str = "openai", openai_api_key: str = None, 
                 google_api_key: str = None, model: str = "gpt-3.5-turbo", 
                 max_tokens: int = 500, temperature: float = 0.7):
        """
        Initialize the chatbot engine.
        
        Args:
            ai_provider: AI provider to use ("openai" or "google")
            openai_api_key: OpenAI API key (if using OpenAI)
            google_api_key: Google AI API key (if using Google)
            model: Model to use (varies by provider)
            max_tokens: Maximum tokens for responses
            temperature: Response creativity (0-1)
        """
        self.ai_provider = ai_provider.lower()
        self.openai_api_key = openai_api_key
        self.google_api_key = google_api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.itinerary_manager = ItineraryManager()
        
        # Initialize the appropriate AI client
        if self.ai_provider == "google" and google_api_key:
            from google import genai
            from google.genai import types
            self.google_client = genai.Client(api_key=google_api_key)
            self.genai_types = types
        
    def set_itinerary(self, itinerary: TripItinerary) -> None:
        """Set the current itinerary for the chatbot."""
        self.itinerary_manager.create_itinerary(itinerary)
        
    def get_itinerary_context(self, itinerary_id: str) -> str:
        """
        Generate context string from itinerary data.
        
        Args:
            itinerary_id: ID of the itinerary to use as context
            
        Returns:
            Formatted string with itinerary information
        """
        itinerary = self.itinerary_manager.get_itinerary(itinerary_id)
        if not itinerary:
            return "No itinerary information available."
        
        context_parts = [
            f"# Trip: {itinerary.title}",
            f"**Dates**: {itinerary.start_date} to {itinerary.end_date}",
        ]
        
        if itinerary.destination:
            context_parts.append(f"**Destination**: {itinerary.destination.name}, {itinerary.destination.city}, {itinerary.destination.country}")
        
        if itinerary.description:
            context_parts.append(f"**Description**: {itinerary.description}")
        
        # Group members
        if itinerary.members:
            members_list = [f"{m.name} ({m.email})" for m in itinerary.members]
            context_parts.append(f"**Group Members**: {', '.join(members_list)}")
        
        # Budget information
        if itinerary.budget_total:
            context_parts.append(f"**Total Budget**: {itinerary.currency} {itinerary.budget_total}")
        if itinerary.budget_per_person:
            context_parts.append(f"**Budget per Person**: {itinerary.currency} {itinerary.budget_per_person}")
        
        # Events organized by date
        context_parts.append("\n## Itinerary Events")
        
        # Group events by date
        events_by_date = {}
        for event in sorted(itinerary.events, key=lambda e: e.start_datetime):
            event_date = event.start_datetime.date()
            if event_date not in events_by_date:
                events_by_date[event_date] = []
            events_by_date[event_date].append(event)
        
        for event_date, events in events_by_date.items():
            context_parts.append(f"\n### {event_date.strftime('%A, %B %d, %Y')}")
            for event in events:
                time_str = event.start_datetime.strftime('%H:%M')
                if event.end_datetime:
                    time_str += f" - {event.end_datetime.strftime('%H:%M')}"
                
                event_info = f"- **{time_str}**: {event.title} ({event.event_type.value})"
                
                if event.location:
                    event_info += f" at {event.location.name}"
                
                if event.description:
                    event_info += f" - {event.description}"
                
                if event.confirmation_number:
                    event_info += f" (Confirmation: {event.confirmation_number})"
                
                context_parts.append(event_info)
        
        # Emergency contacts
        if itinerary.emergency_contacts:
            context_parts.append("\n## Emergency Contacts")
            for contact in itinerary.emergency_contacts:
                contact_info = f"- **{contact.name}**"
                if contact.phone:
                    contact_info += f" - Phone: {contact.phone}"
                if contact.email:
                    contact_info += f" - Email: {contact.email}"
                context_parts.append(contact_info)
        
        # Important information
        if itinerary.important_info:
            context_parts.append("\n## Important Information")
            for key, value in itinerary.important_info.items():
                context_parts.append(f"- **{key}**: {value}")
        
        return "\n".join(context_parts)
    
    def get_message_history_context(self, messages: List[Message], limit: int = 10) -> str:
        """
        Generate context from recent message history.
        
        Args:
            messages: List of recent messages
            limit: Maximum number of messages to include
            
        Returns:
            Formatted string with message history
        """
        if not messages:
            return "No previous conversation history."
        
        # Sort messages by timestamp and take the most recent
        recent_messages = sorted(messages, key=lambda m: m.created_at)[-limit:]
        
        context_parts = ["## Recent Conversation History"]
        
        for message in recent_messages:
            timestamp = message.created_at.strftime('%Y-%m-%d %H:%M')
            sender = message.sender.split('@')[0]  # Just the name part of email
            
            # Truncate long messages
            body = message.body
            if len(body) > 200:
                body = body[:200] + "..."
            
            context_parts.append(f"**{sender}** ({timestamp}): {body}")
        
        return "\n".join(context_parts)
    
    def extract_query_intent(self, query: str) -> Tuple[str, Dict[str, Any]]:
        """
        Analyze the user query to determine intent and extract relevant information.
        
        Args:
            query: User's query text
            
        Returns:
            Tuple of (intent, extracted_data)
        """
        query_lower = query.lower()
        
        # Define intent patterns
        intent_patterns = {
            "schedule": [r"schedule", r"itinerary", r"what.*doing", r"when.*", r"time"],
            "location": [r"where", r"location", r"address", r"directions"],
            "contact": [r"contact", r"phone", r"email", r"call", r"reach"],
            "cost": [r"cost", r"price", r"budget", r"money", r"expense"],
            "weather": [r"weather", r"temperature", r"rain", r"forecast"],
            "transport": [r"transport", r"flight", r"train", r"bus", r"car", r"uber"],
            "accommodation": [r"hotel", r"accommodation", r"stay", r"room"],
            "food": [r"restaurant", r"food", r"eat", r"meal", r"dinner", r"lunch"],
            "activity": [r"activity", r"tour", r"attraction", r"visit", r"see"],
            "emergency": [r"emergency", r"help", r"urgent", r"problem"],
            "update": [r"change", r"update", r"modify", r"cancel", r"reschedule"],
            "general": [r".*"]  # Catch-all
        }
        
        # Extract dates
        date_patterns = [
            r"today", r"tomorrow", r"yesterday",
            r"\\d{1,2}/\\d{1,2}", r"\\d{1,2}-\\d{1,2}",
            r"monday|tuesday|wednesday|thursday|friday|saturday|sunday",
            r"january|february|march|april|may|june|july|august|september|october|november|december"
        ]
        
        extracted_data = {}
        
        # Look for dates
        for pattern in date_patterns:
            matches = re.findall(pattern, query_lower)
            if matches:
                extracted_data["dates"] = matches
                break
        
        # Look for times
        time_pattern = r"\\d{1,2}:\\d{2}|\\d{1,2}\\s*(?:am|pm)"
        time_matches = re.findall(time_pattern, query_lower)
        if time_matches:
            extracted_data["times"] = time_matches
        
        # Determine intent
        for intent, patterns in intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return intent, extracted_data
        
        return "general", extracted_data
    
    def generate_response(self, query: str, history: str, itinerary_id: str,
                            collection: Collection, 
                            sender_email: str = None) -> EmailAnalysis:
        """
        Generate AI response to user query.
        
        Args:
            query: User's question or request
            itinerary_id: ID of the relevant itinerary
            message_history: Recent message history for context
            sender_email: Email of the person asking the question
            
        Returns:
            AI-generated response
        """
        try:
            # Get itinerary context
            itinerary_context = self.get_itinerary_context(itinerary_id)
            
            # Get message history context
            msg_context = ""
            if collection: 
                query_results = collection.query(
                    query_texts=[query],
                    n_results=10
                )
                logger.info(f"RAG query documents: \n{query_results['distances']}\n-----\nRAG query distances: \n{query_results['distances']}\n")
                # Extract the documents from the query results
                if query_results and 'documents' in query_results and query_results['documents']:
                    msg_context += "\n".join(query_results['documents'][0])
            
            # Extract intent and relevant data
            intent, extracted_data = self.extract_query_intent(query)
            
            # Build system prompt
            system_prompt = f"""You are an intelligent AI trip coordinator with full authority to manage itineraries. You can add, remove, modify, and reschedule events based on user requests and smart reasoning.

            ## Your Capabilities:
            1. **Answer questions** about the trip
            2. **Analyze messages** to extract information for storage
            3. **Manage the itinerary** - add/remove/modify events intelligently
            4. **Make scheduling decisions** - choose optimal times, resolve conflicts, suggest alternatives
            5. **Understand context** - consider trip theme, existing events, preferences, logistics

            ## Itinerary Management Powers:
            - **Smart Scheduling**: Choose logical times based on context (meals around meal times, activities during day, etc.)
            - **Conflict Resolution**: Move or suggest alternatives when events conflict
            - **Intelligent Categorization**: Determine event types (restaurant, activity, hotel, flight, etc.)
            - **Location Awareness**: Use trip destination and context for realistic locations
            - **Budget Consideration**: Factor in trip budget when suggesting events
            - **Group Preferences**: Consider any stated preferences or past conversation

            ## Event Types:
            - `restaurant` - dining, meals, food venues
            - `activity` - tours, attractions, experiences, sports
            - `hotel` - accommodation, lodging
            - `flight` - air travel
            - `transport` - cars, buses, trains, local transport
            - `meeting` - group meetings, check-ins
            - `free_time` - unstructured time, breaks
            - `other` - anything else

            ## Smart Scheduling Examples:
            - "Add Owens Fish Camp" → Schedule for appropriate meal time, detect as restaurant
            - "We need dinner reservations" → Choose evening time, restaurant type
            - "Book a morning tour" → Schedule for morning, activity type  
            - "Cancel the 2pm meeting" → Remove specific event
            - "Move dinner earlier" → Modify existing dinner event time

            ## Response Format:
            You MUST respond with valid JSON in this exact format:
            {{
                "is_pure_question": true/false,
                "facts_summary": "Summary of factual information to store (empty string if pure question)",
                "query_response": "Your helpful response to the user",
                "itinerary_actions": [
                    {{
                        "action_type": "add_event|remove_event|modify_event|none",
                        "event_data": {{
                            "title": "Event Name",
                            "event_type": "restaurant|activity|hotel|flight|transport|meeting|free_time|other",
                            "start_datetime": "YYYY-MM-DD HH:MM:SS",
                            "end_datetime": "YYYY-MM-DD HH:MM:SS", 
                            "location": {{"name": "Location Name", "city": "City"}},
                            "description": "Event description",
                            "cost": 0.0,
                            "priority": "high|medium|low"
                        }},
                        "removal_criteria": "text to match for removal (only for remove_event)",
                        "reasoning": "Why you chose this time/action"
                    }}
                ]
            }}
\
            ## Guidelines:
            - Use the trip's actual date range ({itinerary_context.split("**Dates**: ")[1].split("\\n")[0] if "**Dates**: " in itinerary_context else "dates not found"}) 
            - Consider existing events to avoid conflicts
            - Choose realistic times (breakfast 7-9am, lunch 12-2pm, dinner 6-9pm, activities 10am-6pm)
            - Be specific with event details - real locations, accurate durations
            - If unsure about timing, suggest options in your response
            - All group members are also confirmed particpipants in all events unless specified otherwise.

            ## Earlier Chat History(from least to most recent):
            {history if history else "None"}
            
            ## Current Context:
            Trip Information: {itinerary_context} \n {msg_context if msg_context else "None"}
            Sender: {sender_email if sender_email else "Unknown"}
            Detected Intent: {intent}
            Extracted Data: {extracted_data if extracted_data else "None"}
            """
            
            # Generate response using the configured AI provider
            if self.ai_provider == "google":
                # Use Google AI (Gemini)
                prompt = f"{system_prompt}\n\nUser {sender_email}: {query}\nAssistant:"
                
                # Log what we're sending to Gemini
                logger.info(f"=== SENDING TO GEMINI ===")
                logger.info(f"Model: {self.model}")
                logger.info(f"Prompt length: {len(prompt)} characters")
                logger.info(f"Full prompt:\n{prompt}")
                logger.info(f"Generation config: temperature={self.temperature}, max_output_tokens={self.max_tokens}")
                logger.info(f"=== END GEMINI REQUEST ===")
                
                try:
                    response = self.google_client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=self.genai_types.GenerateContentConfig(
                            temperature=self.temperature,
                            max_output_tokens=self.max_tokens,
                            response_mime_type="application/json",
                            response_schema=EmailAnalysis
                        )
                    )
                    parsed_response = response.parsed

                    # Log the response we got back
                    logger.info(f"=== GEMINI RESPONSE ===")
                    logger.info(f"Response: {parsed_response}")
                    logger.info(f"=== END GEMINI RESPONSE ===")
                    
                    return parsed_response
                    
                except Exception as schema_error:
                    logger.warning(f"Schema response failed: {schema_error}, falling back to text parsing")
                    
                    # Fallback: Get text response and try to parse manually
                    response = self.google_client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=self.genai_types.GenerateContentConfig(
                            temperature=self.temperature,
                            max_output_tokens=self.max_tokens
                        )
                    )
                    
                    response_text = response.text.strip()
                    logger.info(f"=== GEMINI FALLBACK RESPONSE ===")
                    logger.info(f"Raw text: {response_text}")
                    logger.info(f"=== END GEMINI FALLBACK ===")
                    
                    try:
                        # Try to parse JSON from the text response
                        import json
                        if response_text.startswith('```json'):
                            response_text = response_text.split('```json')[1].split('```')[0].strip()
                        elif response_text.startswith('```'):
                            response_text = response_text.split('```')[1].split('```')[0].strip()
                        
                        response_json = json.loads(response_text)
                        parsed_response = EmailAnalysis(**response_json)
                        return parsed_response
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.error(f"Failed to parse Gemini JSON response: {e}")
                        # Return a basic EmailAnalysis object
                        return EmailAnalysis(
                            is_pure_question=True,
                            facts_summary="",
                            query_response=response_text,
                            itinerary_actions=[]
                        )
            
            else:
                # Use OpenAI (default)
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_api_key)
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ]
                
                # Log what we're sending to OpenAI
                logger.info(f"=== SENDING TO OPENAI ===")
                logger.info(f"Model: {self.model}")
                logger.info(f"Messages: {json.dumps(messages, indent=2)}")
                logger.info(f"Config: max_tokens={self.max_tokens}, temperature={self.temperature}")
                logger.info(f"=== END OPENAI REQUEST ===")
                
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    top_p=1.0,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                    response_format={"type": "json_object"}
                )
                
                # Log the response we got back
                response_text = response.choices[0].message.content.strip()
                logger.info(f"=== OPENAI RESPONSE ===")
                logger.info(f"Response text: {response_text}")
                logger.info(f"=== END OPENAI RESPONSE ===")
                
                # Parse JSON response into EmailAnalysis object
                try:
                    response_json = json.loads(response_text)
                    parsed_response = EmailAnalysis(**response_json)
                    return parsed_response
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"Failed to parse OpenAI JSON response: {e}")
                    # Fallback: create a basic EmailAnalysis object
                    return EmailAnalysis(
                        is_pure_question=True,
                        facts_summary="",
                        query_response=response_text
                    )
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return f"I'm sorry, I encountered an error processing your request. Please try again or contact the trip organizer for assistance."
    
    def should_store_in_rag(self, analysis: EmailAnalysis) -> bool:
        """
        Determine if content should be stored in RAG based on analysis.
        
        Args:
            analysis: EmailAnalysis result from generate_response
            
        Returns:
            bool: True if content should be stored in RAG
        """
        # Only store if it's not a pure question and has facts
        return not analysis.is_pure_question and bool(analysis.facts_summary.strip())
    
    def get_storage_content(self, analysis: EmailAnalysis) -> str:
        """  
        Get the content that should be stored in RAG.
        
        Args:
            analysis: EmailAnalysis result from generate_response
            
        Returns:
            str: Content to store, or empty string if nothing to store
        """
        if not self.should_store_in_rag(analysis):
            return ""
            
        return analysis.facts_summary.strip()
    
    def get_rag_metadata(self, analysis: EmailAnalysis, sender_email: str = None) -> Dict[str, Any]:
        """
        Generate metadata for RAG storage.
        
        Args:
            analysis: EmailAnalysis result
            sender_email: Email of the sender
            
        Returns:
            Dict: Metadata for the RAG entry
        """
        metadata = {
            "is_pure_question": analysis.is_pure_question,
            "timestamp": datetime.now().isoformat(),
            "has_facts": bool(analysis.facts_summary.strip())
        }
        
        if sender_email:
            metadata["sender"] = sender_email
            
        return metadata

    def create_event_in_trip_ai(self, trip_id: str, event_data: Dict[str, Any]) -> bool:
        """
        Create an event in the trip JSON file using AI-generated data.
        
        Args:
            trip_id: ID of the trip
            event_data: Complete event data from AI
            
        Returns:
            bool: True if event was created successfully
        """
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            itinerary_file = os.path.join(project_root, 'data', f'itinerary_{trip_id}.json')
            
            if not os.path.exists(itinerary_file):
                logger.error(f"Itinerary file not found: {itinerary_file}")
                return False
            
            # Load current itinerary
            with open(itinerary_file, 'r') as f:
                itinerary_data = json.load(f)
            
            # Generate new event using AI data
            # Handle location data - ensure all required fields are present
            location_data = event_data.get("location", {})
            full_location = {
                "name": location_data.get("name", "TBD"),
                "address": location_data.get("address", "TBD"),
                "city": location_data.get("city", "TBD"),
                "country": location_data.get("country", "USA"),
                "latitude": location_data.get("latitude"),
                "longitude": location_data.get("longitude"),
                "timezone": location_data.get("timezone"),
                "notes": location_data.get("notes")
            }
            
            new_event = {
                "id": str(uuid.uuid4())[:8],
                "title": event_data.get("title", "New Event"),
                "event_type": event_data.get("event_type", "other"),
                "start_datetime": event_data.get("start_datetime"),
                "end_datetime": event_data.get("end_datetime"),
                "location": full_location,
                "description": event_data.get("description", ""),
                "contacts": [],
                "cost": event_data.get("cost", 0.0),
                "currency": "USD",
                "priority": event_data.get("priority", "medium"),
                "attendees": [],
                "confirmation_number": event_data.get("confirmation_number"),
                "notes": None,
                "metadata": {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Add event to itinerary
            itinerary_data["events"].append(new_event)
            itinerary_data["updated_at"] = datetime.now().isoformat()
            
            # Save back to file
            with open(itinerary_file, 'w') as f:
                json.dump(itinerary_data, f, indent=2)
            
            logger.info(f"AI successfully created event '{new_event['title']}' in trip {trip_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create AI event in trip {trip_id}: {e}")
            return False
