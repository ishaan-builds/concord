"""
AI-powered chatbot engine for processing group itinerary queries.
"""
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, date
from chromadb import Collection  
from pydantic import BaseModel, Field
from enum import Enum
import re
import json

from .itinerary_models import TripItinerary, ItineraryEvent, EventType, ItineraryManager
from .agentmail_client import AgentMailClient, Message

logger = logging.getLogger(__name__)

class EmailAnalysis(BaseModel):
    """Simplified email analysis: pure questions vs facts."""
    is_pure_question: bool = Field(description="True if this is only a question with no facts to store")
    facts_summary: str = Field(description="Summary of factual information to store. Empty if pure question.")
    query_response: str = Field(description="Response to send back to the user")

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
    
    def generate_response(self, query: str, itinerary_id: str,
                            collection: Collection, message_history: List[Message] = None,
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
            if message_history:
                msg_context += self.get_message_history_context(message_history)
            elif collection: 
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
            system_prompt = f"""You are a helpful AI assistant for a group trip coordination chatbot with advanced content analysis capabilities.

            ## Your Responsibilities:
            1. Answer questions about the trip itinerary and logistics
            2. Analyze incoming messages to extract valuable information for future reference
            3. Classify content to optimize our knowledge storage system (RAG)

            ## Simple Classification System:
            
            You need to determine if an email is:
            1. **PURE QUESTION** - Only asking for information, no facts to store
            2. **CONTAINS FACTS** - Has factual information that should be remembered
            
            ## Pure Questions (Don't Store):
            - "What time is dinner?"
            - "Where are we staying?" 
            - "How much did we budget?"
            - "What's the weather like?"
            - "When do we leave?"
            
            ## Contains Facts (Store the Facts):
            - "I'm vegetarian" → Store: "User is vegetarian" 
            - "The hotel changed check-in to 4pm" → Store: "Hotel check-in changed to 4pm"
            - "Where's dinner? Also I'm allergic to shellfish" → Store: "User is allergic to shellfish" (ignore the question)
            - "My flight is delayed to 8pm" → Store: "User's flight delayed to 8pm"
            - "I booked an Uber for 7am" → Store: "Uber booked for 7am pickup"
            
            ## What Facts to Store:
            - Dietary restrictions/preferences/allergies
            - Schedule/booking/timing changes
            - Transportation arrangements  
            - Budget updates
            - Contact information updates
            - Personal constraints or availability
            - Any concrete trip information that others should know
            
            ## Important:
            - If a message has BOTH questions and facts, classify as "contains facts" and extract only the factual parts
            - Focus on information that would be useful for trip coordination
            - Keep fact summaries concise and clear
            
            ## Response Guidelines:
            - Always provide a helpful response to any questions
            - Acknowledge when you've received and understood new information
            - Be friendly and concise
            - If unsure about classification, err on the side of storing useful information
            
            ## JSON Response Format:
            You MUST respond with valid JSON in this exact format:
            {{
                "is_pure_question": true/false,
                "facts_summary": "Summary of factual information to store (empty string if pure question)",
                "query_response": "Your helpful response to the user"
            }}
            
            ## Current Context:
            Trip Information: {itinerary_context}
            Message History: {msg_context if msg_context else "None"}
            Sender: {sender_email if sender_email else "Unknown"}
            Detected Intent: {intent}
            Extracted Data: {extracted_data if extracted_data else "None"}
            """
            
            # Generate response using the configured AI provider
            if self.ai_provider == "google":
                # Use Google AI (Gemini)
                prompt = f"{system_prompt}\n\nUser: {query}\nAssistant:"
                
                # Log what we're sending to Gemini
                logger.info(f"=== SENDING TO GEMINI ===")
                logger.info(f"Model: {self.model}")
                logger.info(f"Prompt length: {len(prompt)} characters")
                logger.info(f"Full prompt:\n{prompt}")
                logger.info(f"Generation config: temperature={self.temperature}, max_output_tokens={self.max_tokens}")
                logger.info(f"=== END GEMINI REQUEST ===")
                
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

    
