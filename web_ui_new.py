#!/usr/bin/env python3
"""
Web UI for creating and managing AgentMail trip coordination inboxes.
Refactored to use ChatbotEngine methods instead of duplicating logic.
"""
import os
import sys
import json
import uuid
import logging
import chromadb
from datetime import datetime
from typing import Dict, List, Optional
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.config import get_settings
from src.agentmail_client import AgentMailClient
from src.chatbot_engine import ChatbotEngine
from src.itinerary_models import TripItinerary, Location, GroupMember

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize ChromaDB client
chroma_client = chromadb.HttpClient(host='localhost', port=8001)

# Store created trips in memory
TRIPS_STORE = {}
TRIPS_FILE = os.path.join(project_root, 'data', 'trips.json')

# Global chatbot engine instance (will be initialized once)
_chatbot_engine = None

def get_chatbot_engine():
    """Get or create the global chatbot engine instance."""
    global _chatbot_engine
    if _chatbot_engine is None:
        settings = get_settings()
        _chatbot_engine = ChatbotEngine(
            ai_provider=settings.ai.provider,
            openai_api_key=settings.ai.openai_api_key,
            google_api_key=settings.ai.google_api_key,
            model=settings.ai.google_model if settings.ai.provider == 'google' else settings.ai.openai_model
        )
    return _chatbot_engine

def _convert_text_to_html(text: str) -> str:
    """
    Convert plain text to HTML with proper formatting.
    This replaces the private method from the old client.
    """
    import re
    html = text.replace('\\n', '\n').replace('\r\n', '\n')
    paragraphs = html.split('\n\n')
    formatted_paragraphs = []
    for paragraph in paragraphs:
        if paragraph.strip():
            paragraph_html = paragraph.replace('\n', '<br>')
            paragraph_html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', paragraph_html)
            formatted_paragraphs.append(f'<p>{paragraph_html}</p>')
    return ''.join(formatted_paragraphs)

def load_trips_from_file():
    """Load trips from persistent storage."""
    try:
        os.makedirs(os.path.dirname(TRIPS_FILE), exist_ok=True)
        if os.path.exists(TRIPS_FILE):
            with open(TRIPS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading trips: {e}")
    return {}

def save_trips_to_file():
    """Save trips to persistent storage."""
    try:
        os.makedirs(os.path.dirname(TRIPS_FILE), exist_ok=True)
        with open(TRIPS_FILE, 'w') as f:
            json.dump(TRIPS_STORE, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving trips: {e}")

# Load existing trips on startup
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
        # Get form data
        trip_name = request.form.get('trip_name', '').strip()
        trip_description = request.form.get('trip_description', '').strip()
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        destination = request.form.get('destination', '').strip()
        organizer_name = request.form.get('organizer_name', '').strip()
        organizer_email = request.form.get('organizer_email', '').strip()
        participants = request.form.get('participants', '').strip()
        budget_total = request.form.get('budget_total', '0')
        
        # Validation
        if not all([trip_name, start_date, end_date, organizer_name, organizer_email]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('create_form'))
        
        # Parse dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        if end_dt < start_dt:
            flash('End date must be after start date.', 'error')
            return redirect(url_for('create_form'))
        
        # Parse budget and participants
        budget_total = float(budget_total) if budget_total else 0
        participant_list = [p.strip() for p in participants.split(',') if p.strip()]
        participant_count = len(participant_list) + 1
        budget_per_person = budget_total / participant_count if participant_count > 0 and budget_total > 0 else 0
        
        # Generate unique trip ID
        trip_id = str(uuid.uuid4())[:8]
        
        # Initialize AgentMail client
        settings = get_settings()
        agentmail_client = AgentMailClient(api_key=settings.agentmail.api_key)
        
        # Create inbox for the trip using the new SDK method
        inbox_display_name = f"{trip_name} Coordinator"
        inbox = agentmail_client.inboxes.create(display_name=inbox_display_name)
        
        # Prepare itinerary objects
        destination_location = Location(name=destination, address="", city=destination, country="") if destination else None
        organizer_member = GroupMember(name=organizer_name, email=organizer_email, role="organizer")
        members_list = [organizer_member] + [GroupMember(name=p, email="", role="member") for p in participant_list]
        
        # Create itinerary
        itinerary = TripItinerary(
            id=trip_id,
            title=trip_name,
            description=trip_description,
            destination=destination_location,
            start_date=start_dt,
            end_date=end_dt,
            organizer=organizer_member,
            members=members_list,
            budget_total=budget_total,
            budget_per_person=budget_per_person
        )
        
        # Save itinerary to file
        itinerary_file = os.path.join(project_root, 'data', f'itinerary_{trip_id}.json')
        os.makedirs(os.path.dirname(itinerary_file), exist_ok=True)
        with open(itinerary_file, 'w') as f:
            f.write(itinerary.to_json())
        
        # Construct webhook URL for the trip
        base_webhook_url = settings.webhook.url.rstrip('/')
        webhook_url = f"{base_webhook_url}/webhook/{trip_id}"
        
        # Create webhook using the new SDK method
        webhook = agentmail_client.webhooks.create(event_type="message.received", url=webhook_url)
        
        # Store trip information
        trip_data = {
            'id': trip_id,
            'name': trip_name,
            'description': trip_description,
            'destination': destination,
            'start_date': str(start_dt),
            'end_date': str(end_dt),
            'organizer_name': organizer_name,
            'organizer_email': organizer_email,
            'participants': participant_list,
            'members_count': len(members_list),
            'budget_total': budget_total,
            'budget_per_person': budget_per_person,
            'inbox_id': inbox.id,
            'inbox_email': inbox.email_address,
            'webhook_id': webhook.id,
            'webhook_url': webhook_url,
            'created_at': datetime.now().isoformat(),
            'itinerary_file': itinerary_file
        }
        
        TRIPS_STORE[trip_id] = trip_data
        save_trips_to_file()
        
        flash(f'Trip "{trip_name}" created successfully!', 'success')
        return redirect(url_for('trip_detail', trip_id=trip_id))
        
    except Exception as e:
        logger.error(f"Error creating trip: {e}", exc_info=True)
        flash(f'Error creating trip: {str(e)}', 'error')
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
    """Chat with the AI assistant for a specific trip - refactored to use ChatbotEngine methods."""
    trip = TRIPS_STORE.get(trip_id)
    if not trip:
        return jsonify({'error': 'Trip not found'}), 404
    
    query = request.json.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    try:
        # Load itinerary from file
        with open(trip['itinerary_file'], 'r') as f:
            itinerary = TripItinerary.from_json(f.read())
        
        # Get the chatbot engine and set the itinerary
        chatbot_engine = get_chatbot_engine()
        chatbot_engine.set_itinerary(itinerary)
        
        # Get ChromaDB collection for this trip
        collection = chroma_client.get_or_create_collection(trip_id)
        
        # Generate response using ChatbotEngine (this handles all the AI logic)
        analysis = chatbot_engine.generate_response(
            query=query,
            itinerary_id=trip_id,
            collection=collection,
            message_history=[],  # Empty for web UI - could be enhanced later
            sender_email="webui_chatbot"
        )
        
        # Store facts in ChromaDB if the ChatbotEngine determined we should
        if chatbot_engine.should_store_in_rag(analysis):
            storage_content = chatbot_engine.get_storage_content(analysis)
            if storage_content:
                message_id = f"webui_{int(datetime.now().timestamp() * 1000)}"
                
                # Get metadata from ChatbotEngine
                metadata = chatbot_engine.get_rag_metadata(analysis, sender_email="webui_chatbot")
                metadata.update({
                    'subject': 'Web UI Chat',
                    'sender': 'webui_chatbot'
                })
                
                collection.add(
                    ids=[message_id],
                    documents=[storage_content],
                    metadatas=[metadata]
                )
                logger.info(f"Stored factual information from message {message_id} in database")
        
        # Convert response to HTML using the existing helper function
        html_formatted_response = _convert_text_to_html(analysis.query_response)
        
        return jsonify({
            'response': html_formatted_response,
            'query': query,
            'stored_facts': not analysis.is_pure_question  # Debug info
        })
        
    except Exception as e:
        logger.error(f"Error in chatbot endpoint: {e}", exc_info=True)
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/trip/<trip_id>/conversations', methods=['GET'])
def get_conversations(trip_id):
    """Get conversation history for a trip from ChromaDB."""
    if trip_id not in TRIPS_STORE:
        return jsonify({'error': 'Trip not found'}), 404
    
    try:
        collection = chroma_client.get_or_create_collection(trip_id)
        results = collection.get(include=['documents', 'metadatas'])
        
        conversations = [
            {
                'id': doc_id,
                'content': doc,
                'sender': meta.get('sender', 'unknown'),
                'timestamp': meta.get('timestamp', 'unknown')
            }
            for doc_id, doc, meta in zip(results['ids'], results['documents'], results['metadatas'])
        ]
        
        conversations.sort(key=lambda x: x.get('timestamp', x['id']))
        
        return jsonify({
            'conversations': conversations,
            'total': len(conversations)
        })
        
    except Exception as e:
        logger.error(f"Error getting conversations: {e}", exc_info=True)
        return jsonify({'error': f'Error: {str(e)}'}), 500

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
        
        # Delete the AgentMail webhook using the SDK
        try:
            agentmail_client.webhooks.delete(trip['webhook_id'])
            logger.info(f"Deleted webhook {trip['webhook_id']} for trip {trip_id}")
        except Exception as e:
            logger.warning(f"Could not delete webhook {trip['webhook_id']}: {e}")
        
        # Delete the AgentMail inbox using the SDK
        try:
            agentmail_client.inboxes.delete(trip['inbox_id'])
            logger.info(f"Deleted inbox {trip['inbox_id']} for trip {trip_id}")
        except Exception as e:
            logger.warning(f"Could not delete inbox {trip['inbox_id']}: {e}")
        
        # Delete itinerary file
        if os.path.exists(trip['itinerary_file']):
            os.remove(trip['itinerary_file'])
        
        # Remove from store and save
        del TRIPS_STORE[trip_id]
        save_trips_to_file()
        
        flash(f'Trip "{trip["name"]}" and all associated resources deleted successfully.', 'success')
        
    except Exception as e:
        logger.error(f"Error deleting trip {trip_id}: {e}", exc_info=True)
        flash(f'Error deleting trip: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/api/trips')
def api_trips():
    """API endpoint to get all trips."""
    return jsonify(list(TRIPS_STORE.values()))

@app.route('/api/trip/<trip_id>')
def api_trip_detail(trip_id):
    """API endpoint to get trip details."""
    trip = TRIPS_STORE.get(trip_id)
    if not trip:
        return jsonify({'error': 'Trip not found'}), 404
    return jsonify(trip)

if __name__ == '__main__':
    os.makedirs(os.path.join(project_root, 'data'), exist_ok=True)
    
    port = int(os.environ.get('WEB_UI_PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"🌐 Starting Trip Creator Web UI on http://localhost:{port}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)