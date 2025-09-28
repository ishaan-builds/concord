import logging
import json
from datetime import datetime
import chromadb

from .config import get_settings
from .chatbot_engine import ChatbotEngine
from .itinerary_models import TripItinerary

logger = logging.getLogger(__name__)

# Initialize clients once when the module is imported for better performance
settings = get_settings()
chroma_client = chromadb.HttpClient(host='localhost', port=8001)
chatbot_engine = ChatbotEngine(
    ai_provider=settings.ai.provider,
    openai_api_key=settings.ai.openai_api_key,
    google_api_key=settings.ai.google_api_key,
    model=settings.ai.google_model if settings.ai.provider == 'google' else settings.ai.openai_model,
    max_tokens=settings.ai.max_tokens,
    temperature=settings.ai.temperature
)


def process_message_and_get_reply(trip_id: str, query: str, sender: str, message_id: str) -> str:
    """
    The central logic for processing any message, from email or UI.
    
    This function handles loading data, calling the AI, and storing facts.
    
    Args:
        trip_id: The ID of the trip.
        query: The user's message/question.
        sender: The email or identifier of the sender.
        message_id: A unique ID for the message.

    Returns:
        The text of the AI's reply.
    """
    try:
        # 1. Load trip and itinerary data
        with open("data/trips.json", 'r') as f:
            trip_data = json.load(f).get(trip_id)
        if not trip_data:
            raise ValueError(f"Trip {trip_id} not found.")

        with open(trip_data['itinerary_file'], 'r') as f:
            itinerary = TripItinerary.from_json(f.read())
        
        chatbot_engine.set_itinerary(itinerary)
        
        # 2. Get RAG context from ChromaDB
        collection = chroma_client.get_or_create_collection(trip_id)
        
        # 3. Generate AI response
        response = chatbot_engine.generate_response(
            query=query,
            itinerary_id=trip_id,
            collection=collection,
            sender_email=sender
        )
        
        # 4. Handle potential empty AI response (Graceful fallback)
        if not response:
            logger.error(f"Chatbot engine returned None for message_id: {message_id}")
            return "I'm sorry, I was unable to generate a response. Please try rephrasing your message."

        # 5. Store facts in ChromaDB if necessary
        if not response.is_pure_question and response.facts_summary:
            collection.add(
                ids=[message_id],
                documents=[response.facts_summary],
                metadatas=[{'sender': sender, 'timestamp': datetime.now().isoformat()}]
            )
            logger.info(f"Stored facts from message {message_id} in ChromaDB.")
            
        return response.query_response

    except Exception as e:
        logger.error(f"Error in message processor for trip {trip_id}: {e}", exc_info=True)
        return "I'm sorry, I encountered an internal error. Please contact the trip organizer."