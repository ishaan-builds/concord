#!/usr/bin/env python3
"""
Main server script to run the AgentMail chatbot webhook server.
"""
import uvicorn
import logging
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.config import get_settings, check_required_env_vars
from src.agentmail_client import AgentMailClient
from src.chatbot_engine import ChatbotEngine
from src.webhook_server import create_webhook_server

logger = logging.getLogger(__name__)

def main():
    """Main entry point for the webhook server."""
    print("🤖 Starting AgentMail AI Chatbot Webhook Server...")
    
    # Check environment variables
    all_present, missing_vars = check_required_env_vars()
    if not all_present:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please copy config/.env.example to config/.env and fill in your API keys")
        sys.exit(1)
    
    try:
        # Load configuration
        settings = get_settings()
        
        print(f"📧 AgentMail API: {settings.agentmail.base_url}")
        print(f"🧠 AI Model: {settings.ai.google_model if settings.ai.provider == 'google' else settings.ai.openai_model}")
        print(f"🔗 Webhook URL: {settings.webhook.url}")
        print(f"🚀 Server will run on {settings.webhook.host}:{settings.webhook.port}")
        
        # Initialize clients
        agentmail_client = AgentMailClient(settings.agentmail.api_token)
        chatbot_engine = ChatbotEngine(
            ai_provider=settings.ai.provider,
            openai_api_key=settings.ai.openai_api_key,
            google_api_key=settings.ai.google_api_key,
            model=settings.ai.google_model if settings.ai.provider == 'google' else settings.ai.openai_model,
            max_tokens=settings.ai.max_tokens,
            temperature=settings.ai.temperature
        )
        
        # Load sample itinerary if available
        sample_itinerary_file = os.path.join(project_root, "examples", "sample_itinerary.json")
        if os.path.exists(sample_itinerary_file):
            try:
                from src.itinerary_models import TripItinerary
                import json
                with open(sample_itinerary_file, 'r') as f:
                    itinerary_data = f.read()
                
                # Fix enum serialization issues
                itinerary_data = itinerary_data.replace('"EventType.FLIGHT"', '"flight"')
                itinerary_data = itinerary_data.replace('"EventType.HOTEL"', '"hotel"')
                itinerary_data = itinerary_data.replace('"EventType.RESTAURANT"', '"restaurant"')
                itinerary_data = itinerary_data.replace('"EventType.ACTIVITY"', '"activity"')
                itinerary_data = itinerary_data.replace('"Priority.HIGH"', '"high"')
                itinerary_data = itinerary_data.replace('"Priority.MEDIUM"', '"medium"')
                itinerary_data = itinerary_data.replace('"Priority.LOW"', '"low"')
                itinerary_data = itinerary_data.replace('"Priority.CRITICAL"', '"critical"')
                
                sample_itinerary = TripItinerary.from_json(itinerary_data)
                chatbot_engine.set_itinerary(sample_itinerary)
                default_itinerary_id = sample_itinerary.id
                print(f"✅ Loaded itinerary: {sample_itinerary.title}")
                print(f"📅 Trip dates: {sample_itinerary.start_date} to {sample_itinerary.end_date}")
            except Exception as e:
                print(f"⚠️  Could not load sample itinerary: {e}")
                default_itinerary_id = "demo"
        elif not settings.app.default_itinerary_id:
            print("⚠️  No default itinerary ID set. Use examples/setup_demo.py to create one.")
            default_itinerary_id = "demo"
        else:
            default_itinerary_id = settings.app.default_itinerary_id
        
        # Create webhook server
        webhook_server = create_webhook_server(
            agentmail_client=agentmail_client,
            chatbot_engine=chatbot_engine,
            default_itinerary_id=default_itinerary_id
        )
        
        print("✅ Server initialized successfully!")
        print("📱 Send messages to your AgentMail inbox to test the chatbot")
        print("🔄 Use Ctrl+C to stop the server")
        print("-" * 50)
        
        # Run server
        uvicorn.run(
            webhook_server.get_app(),
            host=settings.webhook.host,
            port=settings.webhook.port,
            log_level=settings.app.log_level.lower()
        )
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()