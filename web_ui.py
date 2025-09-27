#!/usr/bin/env python3
"""
Web UI for creating and managing AgentMail trip coordination inboxes.
"""
import os
import sys
import json
import uuid
import logging
from datetime import datetime, date
from typing import Dict, List, Optional
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.config import get_settings
from src.agentmail_client import AgentMailClient
from src.chatbot_engine import ChatbotEngine
from src.itinerary_models import TripItinerary, ItineraryEvent, EventType, Priority, Location, Contact, GroupMember
from src.webhook_server import create_webhook_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Store created trips in memory (in production, use a database)
TRIPS_STORE = {}
TRIPS_FILE = os.path.join(project_root, 'data', 'trips.json')

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
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            if end_dt < start_dt:
                flash('End date must be after start date.', 'error')
                return redirect(url_for('create_form'))
        except ValueError:
            flash('Invalid date format.', 'error')
            return redirect(url_for('create_form'))
        
        # Parse budget
        try:
            budget_total = float(budget_total) if budget_total else 0
        except ValueError:
            budget_total = 0
        
        # Parse participants
        participant_list = [p.strip() for p in participants.split(',') if p.strip()] if participants else []
        participant_count = len(participant_list) + 1  # +1 for organizer
        budget_per_person = budget_total / participant_count if participant_count > 0 and budget_total > 0 else 0
        
        # Generate unique trip ID
        trip_id = str(uuid.uuid4())[:8]
        
        # Initialize AgentMail client
        settings = get_settings()
        agentmail_client = AgentMailClient(settings.agentmail.api_token)
        
        # Create inbox for the trip
        inbox_display_name = f"{trip_name} Coordinator"
        inbox = agentmail_client.create_inbox(inbox_display_name)
        
        # Create destination location object if provided
        destination_location = None
        if destination:
            destination_location = Location(
                name=destination,
                address="",
                city=destination,
                country=""
            )
        
        # Create organizer as GroupMember
        organizer_member = GroupMember(
            name=organizer_name,
            email=organizer_email,
            role="organizer"
        )
        
        # Create members list from participants
        members_list = [organizer_member]  # Start with organizer
        for participant_name in participant_list:
            member = GroupMember(
                name=participant_name,
                email="",  # Email not provided in form
                role="member"
            )
            members_list.append(member)
        
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
            budget_per_person=budget_per_person,
            currency="USD",
            events=[],
            emergency_contacts=[],
            important_info={}
        )
        
        # Save itinerary to file
        itinerary_file = os.path.join(project_root, 'data', f'itinerary_{trip_id}.json')
        os.makedirs(os.path.dirname(itinerary_file), exist_ok=True)
        with open(itinerary_file, 'w') as f:
            f.write(itinerary.to_json())
        
        # Create webhook URL for trip-specific routing on main server
        base_webhook_url = settings.webhook.url
        
        # Remove existing /webhook path if present
        if base_webhook_url.endswith('/webhook'):
            base_webhook_url = base_webhook_url[:-8]  # Remove '/webhook'
        
        # Use trip-specific webhook path on main server (port 8000)
        webhook_url = f"{base_webhook_url}/webhook/{trip_id}"
        
        # Create webhook
        webhook = agentmail_client.create_webhook("message.received", webhook_url)
        
        # Store trip information
        trip_data = {
            'id': trip_id,
            'name': trip_name,
            'description': trip_description,
            'destination': destination,
            'start_date': start_date,
            'end_date': end_date,
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
        logger.error(f"Error creating trip: {e}")
        flash(f'Error creating trip: {str(e)}', 'error')
        return redirect(url_for('create_form'))

@app.route('/trip/<trip_id>')
def trip_detail(trip_id):
    """Show details for a specific trip."""
    if trip_id not in TRIPS_STORE:
        flash('Trip not found.', 'error')
        return redirect(url_for('index'))
    
    trip = TRIPS_STORE[trip_id]
    return render_template('trip_detail.html', trip=trip)

@app.route('/trip/<trip_id>/test', methods=['POST'])
def test_chatbot(trip_id):
    """Test the chatbot for a specific trip."""
    if trip_id not in TRIPS_STORE:
        return jsonify({'error': 'Trip not found'}), 404
    
    query = request.json.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    try:
        # Load itinerary
        trip = TRIPS_STORE[trip_id]
        itinerary_file = trip['itinerary_file']
        
        with open(itinerary_file, 'r') as f:
            itinerary_data = f.read()
        
        itinerary = TripItinerary.from_json(itinerary_data)
        
        # Initialize chatbot engine
        settings = get_settings()
        chatbot_engine = ChatbotEngine(
            ai_provider=settings.ai.provider,
            openai_api_key=settings.ai.openai_api_key,
            google_api_key=settings.ai.google_api_key,
            model=settings.ai.google_model if settings.ai.provider == 'google' else settings.ai.openai_model,
            max_tokens=settings.ai.max_tokens,
            temperature=settings.ai.temperature
        )
        chatbot_engine.set_itinerary(itinerary)
        
        # Generate response
        response = chatbot_engine.generate_response(
            query=query,
            itinerary_id=trip_id,
            sender_email="test@example.com"
        )
        
        formatted_response = chatbot_engine.format_response_with_suggestions(response, query)
        
        return jsonify({
            'response': formatted_response,
            'query': query
        })
        
    except Exception as e:
        logger.error(f"Error testing chatbot: {e}")
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/trip/<trip_id>/delete', methods=['POST'])
def delete_trip(trip_id):
    """Delete a trip and its associated resources."""
    if trip_id not in TRIPS_STORE:
        flash('Trip not found.', 'error')
        return redirect(url_for('index'))
    
    try:
        trip = TRIPS_STORE[trip_id]
        
        # Initialize AgentMail client
        settings = get_settings()
        agentmail_client = AgentMailClient(settings.agentmail.api_token)
        
        # Clean up webhook (if possible - AgentMail API might not support deletion)
        try:
            # Note: AgentMail API doesn't seem to have delete webhook endpoint
            # So we'll just remove it from our records
            pass
        except Exception as e:
            logger.warning(f"Could not delete webhook: {e}")
        
        # Delete itinerary file
        try:
            if os.path.exists(trip['itinerary_file']):
                os.remove(trip['itinerary_file'])
        except Exception as e:
            logger.warning(f"Could not delete itinerary file: {e}")
        
        # Remove from store
        del TRIPS_STORE[trip_id]
        save_trips_to_file()
        
        flash(f'Trip "{trip["name"]}" deleted successfully.', 'success')
        
    except Exception as e:
        logger.error(f"Error deleting trip: {e}")
        flash(f'Error deleting trip: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/api/trips')
def api_trips():
    """API endpoint to get all trips."""
    return jsonify(list(TRIPS_STORE.values()))

@app.route('/api/trip/<trip_id>')
def api_trip_detail(trip_id):
    """API endpoint to get trip details."""
    if trip_id not in TRIPS_STORE:
        return jsonify({'error': 'Trip not found'}), 404
    
    return jsonify(TRIPS_STORE[trip_id])

if __name__ == '__main__':
    # Create data directory
    os.makedirs(os.path.join(project_root, 'data'), exist_ok=True)
    
    # Run the Flask app on port 5001 to avoid conflicts with AirPlay
    port = int(os.environ.get('WEB_UI_PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"🌐 Starting Trip Creator Web UI on http://localhost:{port}")
    print("📧 Create new AgentMail inboxes for trip coordination!")
    
    app.run(host='0.0.0.0', port=port, debug=debug)