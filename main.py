# main.py

#!/usr/bin/env python3
"""
Main entry point for the AgentMail AI Chatbot Webhook Server.
"""
import os
import sys
import logging
import uvicorn

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.config import get_settings, check_required_env_vars, setup_config_file
from src.agentmail_client import AgentMailClient
from src.chatbot_engine import ChatbotEngine
from src.webhook_server import create_webhook_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Initialize and run the webhook server."""
    print("🤖 Starting AgentMail AI Chatbot Webhook Server...")
    
    # Set up and validate configuration
    setup_config_file()
    all_vars_present, missing_vars = check_required_env_vars()
    if not all_vars_present:
        logger.error(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please create and configure 'config/.env' before running.")
        sys.exit(1)
    
    settings = get_settings()
    
    print(f"🧠 AI Model: {settings.ai.google_model if settings.ai.provider == 'google' else settings.ai.openai_model}")
    print(f"🔗 Webhook URL: {settings.webhook.url}")
    print(f"🚀 Server will run on {settings.webhook.host}:{settings.webhook.port}")

    try:
        # Initialize the AgentMail client with the CORRECTED attribute name
        agentmail_client = AgentMailClient(
            api_key=settings.agentmail.api_key  # <--- THIS IS THE FIX
        )

        # Initialize the chatbot engine
        chatbot_engine = ChatbotEngine(
            ai_provider=settings.ai.provider,
            openai_api_key=settings.ai.openai_api_key,
            google_api_key=settings.ai.google_api_key,
            model=settings.ai.google_model if settings.ai.provider == 'google' else settings.ai.openai_model,
            max_tokens=settings.ai.max_tokens,
            temperature=settings.ai.temperature
        )

        # Create the FastAPI app instance
        webhook_server = create_webhook_server(
            agentmail_client=agentmail_client,
            chatbot_engine=chatbot_engine,
            default_itinerary_id=settings.app.default_itinerary_id
        )
        app = webhook_server.app;       
        # Start the Uvicorn server
        uvicorn.run(
            app,
            host=settings.webhook.host,
            port=settings.webhook.port
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}", exc_info=True)
        print(f"❌ Failed to start server: {e}")

if __name__ == "__main__":
    main()