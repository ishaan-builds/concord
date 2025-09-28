#!/usr/bin/env python3
"""
Web UI for creating and managing AgentMail trip coordination inboxes.
This version is refactored to use the central message_processor.
"""
import os
import sys
import json
import uuid
import logging
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import chromadb

# Add project root to path to import our modules
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.config import get_settings
# --- THIS IS THE FIX: Removed the failing import of IsTakenError ---
from src.agentmail_client import AgentMailClient
from src.itinerary_models import TripItinerary, Location, GroupMember
from src.message_processor import process_message_and_get_reply
from src.markdown_converter import format_ai_response

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize clients and storage
chroma_client = chromadb.HttpClient(host='localhost', port=8001)
TRIPS_STORE = {}
TRIPS_FILE = os.path.join(project_root, 'data', 'trips.json')


def _create_unique_inbox(agentmail_client: AgentMailClient, base_name: str, display_name: str):
    """
    Creates an AgentMail inbox with a unique, human-readable username.
    It correctly handles the API's response by inspecting the error message.
    """
    slug = re.sub(r'[^a-z0-9]+', '-', base_name.lower()).strip('-')
    if not slug:
        slug = "trip"

    # First attempt with the ideal username.
    try:
        logger.info(f"Attempting to create inbox with preferred username: {slug}")
        inbox = agentmail_client.inboxes.create(
            display_name=display_name,
            username=slug
        )
        return inbox
    except Exception as e:
        # Check if it's an AlreadyExistsError or similar inbox taken error
        error_str = str(e).lower()
        if ('alreadyexistserror' in error_str or 'inbox already exists' in error_str or 
            'istakenerror' in error_str or 'inbox is taken' in error_str):
            logger.warning(f"Inbox username '{slug}' is taken. Trying numbered alternatives.")
        else:
            # It's a different, unexpected error, so we should stop.
            logger.error(f"An unexpected error occurred while creating inbox '{slug}': {e}")
            raise e

    # If the first attempt failed because the name was taken, loop and add numbers.
    for i in range(1, 101):
        numbered_slug = f"{slug}{i}"
        try:
            logger.info(f"Attempting to create inbox with username: {numbered_slug}")
            inbox = agentmail_client.inboxes.create(
                display_name=display_name,
                username=numbered_slug
            )
            return inbox
        except Exception as e:
            # Check if it's an AlreadyExistsError or similar inbox taken error
            error_str = str(e).lower()
            if ('alreadyexistserror' in error_str or 'inbox already exists' in error_str or 
                'istakenerror' in error_str or 'inbox is taken' in error_str):
                continue  # This numbered username is also taken, try the next number.
            else:
                logger.error(f"An unexpected error occurred while creating inbox '{numbered_slug}': {e}")
                raise e

    raise Exception(f"Could not find a unique inbox name for '{slug}' after 100 attempts.")


# Removed old _convert_text_to_html function - now using comprehensive markdown_converter

def load_trips_from_file():
    """Load trip data from persistent JSON file."""
    try:
        os.makedirs(os.path.dirname(TRIPS_FILE), exist_ok=True)
        if os.path.exists(TRIPS_FILE):
            with open(TRIPS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading trips: {e}")
    return {}

def save_trips_to_file():
    """Save trip data to persistent JSON file."""
    try:
        os.makedirs(os.path.dirname(TRIPS_FILE), exist_ok=True)
        with open(TRIPS_FILE, 'w') as f:
            json.dump(TRIPS_STORE, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving trips: {e}")

# Load existing trips on application startup
TRIPS_STORE.update(load_trips_from_file())

@app.route('/')
def index():
    """Home page showing overview and existing trips."""
    return render_template('index.html', trips=TRIPS_STORE)

@app.route('/create')
def create_form():
    """Show the trip creation form."""
    return render_template('create_trip.html')

@app.route('/create', methods=['POST'])
def create_trip():
    """Handle trip creation form submission."""
    try:
        settings = get_settings()
        agentmail_client = AgentMailClient(api_key=settings.agentmail.api_key)

        trip_name = request.form.get('trip_name', '').strip()
        if not trip_name:
            flash('Trip Name is a required field.', 'error')
            return redirect(url_for('create_form'))

        trip_id = str(uuid.uuid4())[:8]
        
        inbox_display_name = f"{trip_name} Coordinator"
        
        inbox = _create_unique_inbox(
            agentmail_client=agentmail_client,
            base_name=trip_name,
            display_name=inbox_display_name
        )
        
        # Get the email address from the inbox object
        # Check if inbox_id already contains the full email or just the username part
        if '@' in inbox.inbox_id:
            inbox_email = inbox.inbox_id  # It's already a full email address
        else:
            inbox_email = f"{inbox.inbox_id}@agentmail.to"  # Add domain if needed
        logger.info(f"Constructed inbox email: {inbox_email}")
        
        base_webhook_url = settings.webhook.url.rstrip('/')
        webhook_url = f"{base_webhook_url}/{trip_id}"
        # Corrected line for webhook creation
        webhook = agentmail_client.webhooks.create(event_types=["message.received"], url=webhook_url)

        itinerary = TripItinerary(
            id=trip_id,
            title=trip_name,
            description=request.form.get('trip_description', '').strip(),
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date(),
            end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date(),
            organizer=GroupMember(name=request.form.get('organizer_name'), email=request.form.get('organizer_email'), role="organizer"),
        )
        itinerary_file = os.path.join(project_root, 'data', f'itinerary_{trip_id}.json')
        os.makedirs(os.path.dirname(itinerary_file), exist_ok=True)
        with open(itinerary_file, 'w') as f:
            f.write(itinerary.to_json())
        
        # Corrected block for trip data
        trip_data = {
            'id': trip_id,
            'name': trip_name,
            'inbox_id': inbox.inbox_id,
            'inbox_email': inbox_email,
            'webhook_id': webhook.webhook_id,
            'itinerary_file': itinerary_file,
            'created_at': datetime.now().isoformat()
        }
        
        TRIPS_STORE[trip_id] = trip_data
        save_trips_to_file()
        
        # Check if this is an AJAX request expecting JSON (check for XMLHttpRequest header or Accept header)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
            return jsonify({
                'success': True,
                'message': f'Trip "{trip_name}" created successfully!',
                'redirect_url': url_for('trip_detail', trip_id=trip_id)
            })
        else:
            flash(f'Trip "{trip_name}" created successfully!', 'success')
            return redirect(url_for('trip_detail', trip_id=trip_id))
        
    except Exception as e:
        logger.error(f"Error creating trip: {e}", exc_info=True)
        
        # Provide more user-friendly error messages
        error_message = ""
        if 'api_key' in str(e).lower():
            error_message = 'API configuration error. Please check your AgentMail settings.'
        elif 'connection' in str(e).lower() or 'network' in str(e).lower():
            error_message = 'Network connection error. Please check your internet connection and try again.'
        elif 'webhook' in str(e).lower():
            error_message = 'Webhook configuration error. Please check your webhook settings.'
        else:
            error_message = f'An unexpected error occurred while creating the trip. Please try again.'
        
        # Check if this is an AJAX request expecting JSON (check for XMLHttpRequest header or Accept header)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
            return jsonify({
                'success': False,
                'error': error_message
            }), 400
        else:
            flash(error_message, 'error')
            return redirect(url_for('create_form'))

@app.route('/trip/<trip_id>')
def trip_detail(trip_id):
    """Show details for a specific trip."""
    trip = TRIPS_STORE.get(trip_id)
    if not trip:
        flash('Trip not found.', 'error')
        return redirect(url_for('index'))
    
    return render_template('trip_detail.html', trip=trip)

@app.route('/trip/<trip_id>/chatbot', methods=['POST'])
def chatbot(trip_id):
    """Handles a chat query from the web UI by delegating to the central processor."""
    if trip_id not in TRIPS_STORE:
        return jsonify({'error': 'Trip not found'}), 404
    
    query = request.json.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    # Get chat history from request body (optional)
    chat_history = request.json.get('history', [])
    logger.info(f"{chat_history}")
    if not isinstance(chat_history, list):
        chat_history = []

    logger.info(f"Received request body: {request.json}")
    logger.info(f"Earlier chat history (length: {len(chat_history)}):\n{chat_history}")
    
    if len(chat_history) == 0:
        logger.info("Chat history is empty - this is a new conversation")
    else:
        logger.info(f"Chat history has {len(chat_history)} items - continuing conversation")
    
    try:
        sender = "webui_chatbot"
        message_id = f"webui_{int(datetime.now().timestamp() * 1000)}"

        ai_reply_text = process_message_and_get_reply(trip_id, query, sender, message_id, chat_history)
        
        html_formatted_response = format_ai_response(ai_reply_text)
        
        # Build updated history for the frontend to maintain conversation state
        updated_history = chat_history + [f"User: {query}", f"Assistant: {ai_reply_text}"]
        
        return jsonify({
            'response': html_formatted_response,
            'query': query,
            'history': updated_history
        })
        
    except Exception as e:
        logger.error(f"Error in web UI chatbot: {e}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred.'}), 500

@app.route('/trip/<trip_id>/conversations', methods=['GET'])
def get_conversations(trip_id):
    """Get conversation history for a trip from ChromaDB."""
    if trip_id not in TRIPS_STORE:
        return jsonify({'error': 'Trip not found'}), 404
    
    try:
        collection = chroma_client.get_collection(name=trip_id)
        results = collection.get(include=['documents', 'metadatas'])
        
        conversations = [
            {
                'id': doc_id,
                'content': doc,
                'sender': meta.get('sender', 'unknown'),
                'timestamp': meta.get('timestamp', 'unknown')
            }
            for doc_id, doc, meta in zip(results.get('ids', []), results.get('documents', []), results.get('metadatas', []))
        ]
        
        conversations.sort(key=lambda x: x.get('timestamp', x['id']))
        
        return jsonify({'conversations': conversations, 'total': len(conversations)})
        
    except Exception as e:
        if "does not exist" in str(e).lower():
            return jsonify({'conversations': [], 'total': 0})
        logger.error(f"Error getting conversations: {e}", exc_info=True)
        return jsonify({'error': 'Could not retrieve conversations.'}), 500

@app.route('/trip/<trip_id>/delete', methods=['POST'])
def delete_trip(trip_id):
    """Delete a trip and its associated resources."""
    trip = TRIPS_STORE.get(trip_id)
    if not trip:
        flash('Trip not found.', 'error')
        return redirect(url_for('index'))
    
    try:
        settings = get_settings()
        agentmail_client = AgentMailClient(api_key=settings.agentmail.api_key)
        
        try:
            agentmail_client.webhooks.delete(trip['webhook_id'])
            logger.info(f"Deleted webhook {trip['webhook_id']}")
        except Exception as e:
            logger.warning(f"Could not delete webhook {trip['webhook_id']}: {e}")
        
        try:
            agentmail_client.inboxes.delete(trip['inbox_id'])
            logger.info(f"Deleted inbox {trip['inbox_id']}")
        except Exception as e:
            logger.warning(f"Could not delete inbox {trip['inbox_id']}: {e}")
        
        if os.path.exists(trip['itinerary_file']):
            os.remove(trip['itinerary_file'])
        
        del TRIPS_STORE[trip_id]
        save_trips_to_file()
        
        flash(f'Trip "{trip["name"]}" deleted successfully.', 'success')
        
    except Exception as e:
        logger.error(f"Error deleting trip {trip_id}: {e}", exc_info=True)
        flash('An unexpected error occurred while deleting the trip.', 'error')
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    os.makedirs(os.path.join(project_root, 'data'), exist_ok=True)
    port = int(os.environ.get('WEB_UI_PORT', 5002))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)