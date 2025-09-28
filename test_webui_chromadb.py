#!/usr/bin/env python3
"""
Test script to debug ChromaDB integration in web UI
"""
import os
import sys
import json
import chromadb
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.config import get_settings
from src.chatbot_engine import ChatbotEngine
from src.itinerary_models import TripItinerary

def test_chromadb_integration():
    """Test ChromaDB integration like web UI does it"""
    print("🧪 Testing ChromaDB Integration...")
    
    # Initialize ChromaDB client (same as web UI)
    chroma_client = chromadb.PersistentClient(path='./db/')
    
    # Test trip ID
    trip_id = "8b2fbe83"  # Use your actual trip ID
    
    # Get or create collection
    try:
        collection = chroma_client.get_or_create_collection(trip_id)
        print(f"✅ Successfully created/accessed collection: {trip_id}")
        
        # Check what's in the collection
        existing_data = collection.get()
        print(f"📊 Collection contains {len(existing_data['ids'])} items")
        if existing_data['ids']:
            print("Sample IDs:", existing_data['ids'][:3])
            
    except Exception as e:
        print(f"❌ ChromaDB collection error: {e}")
        return
    
    # Test chatbot engine initialization
    try:
        settings = get_settings()
        chatbot_engine = ChatbotEngine(
            ai_provider=settings.ai.provider,
            openai_api_key=settings.ai.openai_api_key,
            google_api_key=settings.ai.google_api_key,
            model=settings.ai.google_model if settings.ai.provider == 'google' else settings.ai.openai_model,
            max_tokens=settings.ai.max_tokens,
            temperature=settings.ai.temperature
        )
        print(f"✅ ChatbotEngine initialized with provider: {settings.ai.provider}")
        
    except Exception as e:
        print(f"❌ ChatbotEngine initialization error: {e}")
        return
    
    # Load test itinerary
    try:
        itinerary_file = f'./data/itinerary_{trip_id}.json'
        if os.path.exists(itinerary_file):
            with open(itinerary_file, 'r') as f:
                itinerary_data = f.read()
            itinerary = TripItinerary.from_json(itinerary_data)
            chatbot_engine.set_itinerary(itinerary)
            print(f"✅ Loaded itinerary: {itinerary.title}")
        else:
            print(f"❌ Itinerary file not found: {itinerary_file}")
            return
            
    except Exception as e:
        print(f"❌ Itinerary loading error: {e}")
        return
    
    # Test AI response generation
    try:
        query = "Hello, how are you?"
        print(f"🤖 Testing query: {query}")
        
        message_id = f"test_{int(datetime.now().timestamp() * 1000)}"
        
        response = chatbot_engine.generate_response(
            query=query,
            itinerary_id=trip_id,
            collection=collection,
            message_history=[],
            sender_email="test@example.com"
        )
        
        print(f"✅ AI Response generated successfully")
        print(f"Response type: {type(response)}")
        print(f"Is pure question: {response.is_pure_question}")
        print(f"Facts summary: {response.facts_summary}")
        print(f"Query response: {response.query_response[:100]}...")
        
        # Test storage logic
        if not response.is_pure_question:
            collection.add(
                ids=[message_id],
                documents=[response.facts_summary],
                metadatas={
                    'sender': 'test@example.com',
                    'recipient': 'webui',
                    'subject': 'Test Chat',
                    'labels': ['webui', 'test']
                }
            )
            print(f"✅ Stored facts in ChromaDB with ID: {message_id}")
        else:
            print("ℹ️  Pure question - not storing facts")
            
    except Exception as e:
        print(f"❌ AI response generation error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("🎉 All tests passed!")

if __name__ == "__main__":
    test_chromadb_integration()