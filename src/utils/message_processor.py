import logging
import json
import os
from datetime import datetime
import chromadb

from ..config.settings import get_settings
from ..core.chatbot_engine import ChatbotEngine
from ..core.itinerary_models import TripItinerary
from agentmail import Thread
from quotequail import quote

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

def get_thread_history(thread: Thread) -> str:
    """
    Extracts and concatenates the text from all messages in a thread.
    
    Args:
        thread: The Thread object containing messages.
        
    Returns:
        A single string with all message texts concatenated.
    """
    messages_text = []
    for msg in thread.messages[:-1]:
        text = msg.text
        quote_result = quote(text)
        reply_lines = [reply_line for is_quote, reply_line in quote_result if is_quote]
        messages_text.append('\n'.join(reply_lines).strip())
    
    history = ""
    for i, msg in enumerate(messages_text):
        history += f"{messages_text[i]}\n"

    return history

def process_message_and_get_reply(trip_id: str, query: str, sender: str, message_id: str, session_history: Thread | list[str]) -> str:
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

        # Check if itinerary file exists
        itinerary_file = trip_data.get('itinerary_file')
        if itinerary_file and os.path.exists(itinerary_file):
            with open(itinerary_file, 'r') as f:
                itinerary = TripItinerary.from_json(f.read())
            chatbot_engine.set_itinerary(itinerary)
        else:
            # Create a minimal itinerary if file doesn't exist
            logger.warning(f"Itinerary file not found for trip {trip_id}. Creating minimal itinerary.")
            itinerary = TripItinerary(
                id=trip_id,
                name=trip_data.get('name', f'Trip {trip_id}'),
                destination=trip_data.get('destination', 'Unknown'),
                start_date="TBD",
                end_date="TBD",
                participants=[],
                days=[]
            )
            chatbot_engine.set_itinerary(itinerary)
        
        # 2. Get RAG context from ChromaDB
        collection = chroma_client.get_or_create_collection(trip_id)
        
        # 3. Generate AI response
        if(isinstance(session_history, Thread)):
            response = chatbot_engine.generate_response(
                query=query,
                history=get_thread_history(session_history),
                itinerary_id=trip_id,
                collection=collection,
                sender_email=sender
            )
        else:
            response = chatbot_engine.generate_response(
                query=query,
                history="\n".join(session_history),
                itinerary_id=trip_id,
                collection=collection,
                sender_email=sender
            )
            
        # 4. Handle potential empty AI response (Graceful fallback)
        if not response:
            logger.error(f"Chatbot engine returned None for message_id: {message_id}")
            return "I'm sorry, I was unable to generate a response. Please try rephrasing your message."

        # 5. Execute AI-determined itinerary actions
        if hasattr(response, 'itinerary_actions') and response.itinerary_actions:
            for action in response.itinerary_actions:
                if action.action_type == "add_event" and action.event_data:
                    # Convert Pydantic model to dict for the create function
                    event_dict = action.event_data.dict() if hasattr(action.event_data, 'dict') else action.event_data
                    if hasattr(event_dict.get('location'), 'dict'):
                        event_dict['location'] = event_dict['location'].dict()
                    
                    success = chatbot_engine.create_event_in_trip_ai(trip_id, event_dict)
                    if success:
                        logger.info(f"AI successfully added event '{event_dict.get('title', 'Unknown')}' - Reasoning: {action.reasoning}")
                    else:
                        logger.warning(f"AI failed to add event: {action.reasoning}")
                        
                elif action.action_type == "remove_event" and action.removal_criteria:
                    success = chatbot_engine.remove_event_from_trip(trip_id, action.removal_criteria)
                    if success:
                        logger.info(f"AI successfully removed event matching '{action.removal_criteria}' - Reasoning: {action.reasoning}")
                    else:
                        logger.warning(f"AI failed to remove event: {action.reasoning}")
                        
                elif action.action_type == "modify_event":
                    logger.info(f"AI requested event modification - Reasoning: {action.reasoning}")
                    # TODO: Implement event modification logic
        
        # 6. Store facts in ChromaDB if necessary  
        if hasattr(response, 'is_pure_question') and hasattr(response, 'facts_summary'):
            if not response.is_pure_question and response.facts_summary:
                collection.add(
                    ids=[message_id],
                    documents=[response.facts_summary],
                    metadatas=[{'sender': sender, 'timestamp': datetime.now().isoformat()}]
                )
                logger.info(f"Stored facts from message {message_id} in ChromaDB.")
            
        # Return the appropriate response
        if hasattr(response, 'query_response'):
            return response.query_response
        else:
            # Fallback for string responses
            return str(response)

    except Exception as e:
        logger.error(f"Error in message processor for trip {trip_id}: {e}", exc_info=True)
        return "I'm sorry, I encountered an internal error. Please contact the trip organizer."