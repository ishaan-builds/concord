"""
AI-powered chatbot engine for processing group itinerary queries.
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date
import re
import json

from .itinerary_models import TripItinerary, ItineraryEvent, EventType, ItineraryManager
from .agentmail_client import AgentMailClient, Message

logger = logging.getLogger(__name__)

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
            import google.generativeai as genai
            genai.configure(api_key=google_api_key)
            self.google_model = genai.GenerativeModel(model)
        
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
        context_parts.append("\\n## Itinerary Events")
        
        # Group events by date
        events_by_date = {}
        for event in sorted(itinerary.events, key=lambda e: e.start_datetime):
            event_date = event.start_datetime.date()
            if event_date not in events_by_date:
                events_by_date[event_date] = []
            events_by_date[event_date].append(event)
        
        for event_date, events in events_by_date.items():
            context_parts.append(f"\\n### {event_date.strftime('%A, %B %d, %Y')}")
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
            context_parts.append("\\n## Emergency Contacts")
            for contact in itinerary.emergency_contacts:
                contact_info = f"- **{contact.name}**"
                if contact.phone:
                    contact_info += f" - Phone: {contact.phone}"
                if contact.email:
                    contact_info += f" - Email: {contact.email}"
                context_parts.append(contact_info)
        
        # Important information
        if itinerary.important_info:
            context_parts.append("\\n## Important Information")
            for key, value in itinerary.important_info.items():
                context_parts.append(f"- **{key}**: {value}")
        
        return "\\n".join(context_parts)
    
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
        
        return "\\n".join(context_parts)
    
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
    
    def generate_response(self, query: str, itinerary_id: str, 
                         message_history: List[Message] = None,
                         sender_email: str = None) -> str:
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
            history_context = ""
            if message_history:
                history_context = self.get_message_history_context(message_history)
            
            # Extract intent and relevant data
            intent, extracted_data = self.extract_query_intent(query)
            
            # Build system prompt
            system_prompt = f"""You are a helpful AI assistant for a group trip coordination chatbot. 
            You have access to the complete trip itinerary and can answer questions about:
            - Schedule and timing of events
            - Locations and directions
            - Contact information
            - Costs and budget information
            - Transportation details
            - Accommodation information
            - Restaurant and dining plans
            - Activities and attractions
            - Emergency information
            
            Always be friendly, helpful, and concise. If you don't have specific information, 
            suggest how the person might find it or who to contact.
            
            Current trip information:
            {itinerary_context}
            
            {history_context if history_context else ""}
            
            The person asking is: {sender_email if sender_email else "Unknown"}
            Detected query intent: {intent}
            Extracted information: {extracted_data if extracted_data else "None"}
            """
            
            # Generate response using the configured AI provider
            if self.ai_provider == "google":
                # Use Google AI (Gemini)
                prompt = f"{system_prompt}\n\nUser: {query}\nAssistant:"
                response = self.google_model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": self.temperature,
                        "max_output_tokens": self.max_tokens,
                    }
                )
                return response.text.strip()
            
            else:
                # Use OpenAI (default)
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_api_key)
                
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    top_p=1.0,
                    frequency_penalty=0.0,
                    presence_penalty=0.0
                )
                
                return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return f"I'm sorry, I encountered an error processing your request. Please try again or contact the trip organizer for assistance."
    
    def suggest_follow_up_questions(self, query: str, response: str) -> List[str]:
        """
        Suggest relevant follow-up questions based on the query and response.
        
        Args:
            query: Original user query
            response: AI response
            
        Returns:
            List of suggested follow-up questions
        """
        intent, _ = self.extract_query_intent(query)
        
        follow_ups = {
            "schedule": [
                "What time should I leave to get there?",
                "Is there anything I need to bring?",
                "Who else will be there?"
            ],
            "location": [
                "How long does it take to get there?",
                "What's the best way to travel there?",
                "Are there nearby parking options?"
            ],
            "contact": [
                "What are their business hours?",
                "Should I mention I'm with the group?",
                "Is there a backup contact?"
            ],
            "cost": [
                "Is this already paid for?",
                "Do I need to bring cash?",
                "Are tips included?"
            ],
            "transport": [
                "What time should I arrive at pickup?",
                "Do I need to print tickets?",
                "What if I'm running late?"
            ],
            "accommodation": [
                "What time is check-in/check-out?",
                "What amenities are included?",
                "How do I get room keys?"
            ],
            "food": [
                "Do they accommodate dietary restrictions?",
                "Is it family-style or individual orders?",
                "What's the dress code?"
            ]
        }
        
        return follow_ups.get(intent, [
            "What should I know about this?",
            "Is there anything else planned?",
            "Who should I contact if I have questions?"
        ])
    
    def format_response_with_suggestions(self, response: str, query: str) -> str:
        """
        Format the response with follow-up suggestions.
        
        Args:
            response: AI-generated response
            query: Original query
            
        Returns:
            Formatted response with suggestions
        """
        suggestions = self.suggest_follow_up_questions(query, response)
        
        formatted_response = response
        
        if suggestions:
            formatted_response += "\\n\\n**You might also want to ask:**\\n"
            for i, suggestion in enumerate(suggestions[:3], 1):  # Limit to 3 suggestions
                formatted_response += f"{i}. {suggestion}\\n"
        
        return formatted_response