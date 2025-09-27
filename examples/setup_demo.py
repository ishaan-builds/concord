#!/usr/bin/env python3
"""
Demo setup script for AgentMail chatbot.
This script demonstrates how to:
1. Create an AgentMail inbox
2. Set up a webhook
3. Create a sample itinerary
4. Test the chatbot functionality
"""
import sys
import os
from datetime import datetime, date, timedelta
import json

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.config import get_settings, check_required_env_vars
from src.agentmail_client import AgentMailClient
from src.chatbot_engine import ChatbotEngine
from src.itinerary_models import (
    TripItinerary, ItineraryEvent, GroupMember, Location, Contact,
    EventType, Priority
)

def create_sample_itinerary() -> TripItinerary:
    """Create a sample trip itinerary for demonstration."""
    
    # Create trip location
    destination = Location(
        name="San Francisco Bay Area",
        address="San Francisco, CA, USA",
        city="San Francisco",
        country="USA",
        latitude=37.7749,
        longitude=-122.4194,
        timezone="America/Los_Angeles"
    )
    
    # Create group members
    organizer = GroupMember(
        name="Alice Johnson",
        email="alice@example.com",
        phone="+1-555-0101",
        role="organizer"
    )
    
    members = [
        GroupMember(name="Bob Smith", email="bob@example.com", phone="+1-555-0102"),
        GroupMember(name="Carol Davis", email="carol@example.com", phone="+1-555-0103"),
        GroupMember(name="David Wilson", email="david@example.com", phone="+1-555-0104")
    ]
    
    # Create itinerary
    trip_start = date.today() + timedelta(days=30)
    trip_end = trip_start + timedelta(days=3)
    
    itinerary = TripItinerary(
        id="sf_weekend_2024",
        title="San Francisco Weekend Getaway",
        description="A fun weekend exploring San Francisco with friends",
        start_date=trip_start,
        end_date=trip_end,
        destination=destination,
        organizer=organizer,
        members=members,
        budget_total=2000.0,
        budget_per_person=500.0,
        currency="USD"
    )
    
    # Add emergency contacts
    itinerary.emergency_contacts.append(
        Contact(
            name="Trip Emergency Hotline",
            phone="+1-800-555-HELP",
            email="emergency@travelcompany.com"
        )
    )
    
    # Add important info
    itinerary.important_info.update({
        "Weather": "Expect cool temperatures, bring layers",
        "Transportation": "We have a rental car for the group",
        "Hotel WiFi": "Password is 'SFWeekend2024'",
        "Group Chat": "WhatsApp group 'SF Adventure'"
    })
    
    # Create events
    base_datetime = datetime.combine(trip_start, datetime.min.time().replace(hour=9))
    
    # Day 1 events
    events = [
        ItineraryEvent(
            id="arrival_flight",
            title="Flight Arrival - United 1234",
            event_type=EventType.FLIGHT,
            start_datetime=base_datetime.replace(hour=10, minute=30),
            end_datetime=base_datetime.replace(hour=11, minute=0),
            location=Location(
                name="San Francisco International Airport",
                address="San Francisco, CA 94128",
                city="San Francisco",
                country="USA"
            ),
            confirmation_number="ABC123",
            priority=Priority.HIGH,
            attendees=["alice@example.com", "bob@example.com", "carol@example.com", "david@example.com"],
            notes="Terminal 3, Gate G91. Alice will coordinate pickup."
        ),
        
        ItineraryEvent(
            id="hotel_checkin",
            title="Hotel Check-in",
            event_type=EventType.HOTEL,
            start_datetime=base_datetime.replace(hour=15, minute=0),
            end_datetime=base_datetime.replace(hour=16, minute=0),
            location=Location(
                name="The Phoenix Hotel",
                address="601 Eddy St, San Francisco, CA 94109",
                city="San Francisco",
                country="USA"
            ),
            contacts=[
                Contact(
                    name="Hotel Front Desk",
                    phone="+1-415-776-1380",
                    email="reservations@phoenixsf.com"
                )
            ],
            confirmation_number="HTL789456",
            priority=Priority.HIGH,
            notes="Early check-in requested. Rooms: 2 doubles"
        ),
        
        ItineraryEvent(
            id="fishermans_wharf",
            title="Explore Fisherman's Wharf",
            event_type=EventType.ACTIVITY,
            start_datetime=base_datetime.replace(hour=17, minute=0),
            end_datetime=base_datetime.replace(hour=19, minute=0),
            location=Location(
                name="Fisherman's Wharf",
                address="Fisherman's Wharf, San Francisco, CA",
                city="San Francisco",
                country="USA"
            ),
            description="Walk around, see sea lions, street performers",
            cost=0.0,
            priority=Priority.MEDIUM
        ),
        
        ItineraryEvent(
            id="dinner_crab_house",
            title="Dinner at Swan Oyster Depot",
            event_type=EventType.RESTAURANT,
            start_datetime=base_datetime.replace(hour=19, minute=30),
            end_datetime=base_datetime.replace(hour=21, minute=0),
            location=Location(
                name="Swan Oyster Depot",
                address="1517 Polk St, San Francisco, CA 94109",
                city="San Francisco",
                country="USA"
            ),
            contacts=[
                Contact(
                    name="Swan Oyster Depot",
                    phone="+1-415-673-1101"
                )
            ],
            cost=200.0,
            description="Famous seafood counter, no reservations",
            notes="Arrive early, expect a wait. Cash only!"
        )
    ]
    
    # Day 2 events
    day2_base = base_datetime + timedelta(days=1)
    
    events.extend([
        ItineraryEvent(
            id="golden_gate_bridge",
            title="Golden Gate Bridge Visit",
            event_type=EventType.ACTIVITY,
            start_datetime=day2_base.replace(hour=9, minute=0),
            end_datetime=day2_base.replace(hour=11, minute=0),
            location=Location(
                name="Golden Gate Bridge",
                address="Golden Gate Bridge, San Francisco, CA",
                city="San Francisco",
                country="USA"
            ),
            description="Walk or bike across the bridge, take photos",
            cost=0.0,
            priority=Priority.HIGH,
            notes="Bring warm clothes, it's windy!"
        ),
        
        ItineraryEvent(
            id="alcatraz_tour",
            title="Alcatraz Island Tour",
            event_type=EventType.ACTIVITY,
            start_datetime=day2_base.replace(hour=13, minute=30),
            end_datetime=day2_base.replace(hour=16, minute=30),
            location=Location(
                name="Alcatraz Island",
                address="Alcatraz Island, San Francisco, CA",
                city="San Francisco",
                country="USA"
            ),
            contacts=[
                Contact(
                    name="Alcatraz Cruises",
                    phone="+1-415-981-7625"
                )
            ],
            confirmation_number="ALC456789",
            cost=160.0,
            priority=Priority.HIGH,
            description="Audio tour of the famous prison",
            notes="Depart from Pier 33, arrive 30 minutes early"
        ),
        
        ItineraryEvent(
            id="chinatown_dinner",
            title="Dinner in Chinatown",
            event_type=EventType.RESTAURANT,
            start_datetime=day2_base.replace(hour=18, minute=30),
            end_datetime=day2_base.replace(hour=20, minute=0),
            location=Location(
                name="R&G Lounge",
                address="631 Kearny St, San Francisco, CA 94108",
                city="San Francisco",
                country="USA"
            ),
            contacts=[
                Contact(
                    name="R&G Lounge",
                    phone="+1-415-982-7877"
                )
            ],
            cost=180.0,
            description="Famous for salt and pepper crab",
            notes="Reservation under Alice Johnson"
        )
    ])
    
    # Day 3 events
    day3_base = base_datetime + timedelta(days=2)
    
    events.extend([
        ItineraryEvent(
            id="hotel_checkout",
            title="Hotel Check-out",
            event_type=EventType.HOTEL,
            start_datetime=day3_base.replace(hour=11, minute=0),
            end_datetime=day3_base.replace(hour=11, minute=30),
            location=Location(
                name="The Phoenix Hotel",
                address="601 Eddy St, San Francisco, CA 94109",
                city="San Francisco",
                country="USA"
            ),
            priority=Priority.HIGH,
            notes="Late checkout arranged until 11 AM"
        ),
        
        ItineraryEvent(
            id="brunch_mission",
            title="Brunch in Mission District",
            event_type=EventType.RESTAURANT,
            start_datetime=day3_base.replace(hour=12, minute=0),
            end_datetime=day3_base.replace(hour=13, minute=30),
            location=Location(
                name="Tartine Bakery",
                address="600 Guerrero St, San Francisco, CA 94110",
                city="San Francisco",
                country="USA"
            ),
            cost=80.0,
            description="Famous bakery and cafe",
            notes="Expect a wait on weekends"
        ),
        
        ItineraryEvent(
            id="departure_flight",
            title="Departure Flight - United 5678",
            event_type=EventType.FLIGHT,
            start_datetime=day3_base.replace(hour=16, minute=45),
            end_datetime=day3_base.replace(hour=17, minute=15),
            location=Location(
                name="San Francisco International Airport",
                address="San Francisco, CA 94128",
                city="San Francisco",
                country="USA"
            ),
            confirmation_number="DEF789",
            priority=Priority.CRITICAL,
            attendees=["alice@example.com", "bob@example.com", "carol@example.com", "david@example.com"],
            notes="Terminal 3, arrive 2 hours early. Check-in online."
        )
    ])
    
    # Add all events to itinerary
    for event in events:
        itinerary.add_event(event)
    
    return itinerary

def main():
    """Main demo setup function."""
    print("🚀 AgentMail Chatbot Demo Setup")
    print("=" * 50)
    
    # Check environment variables
    all_present, missing_vars = check_required_env_vars()
    if not all_present:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please copy config/.env.example to config/.env and fill in your API keys")
        return
    
    try:
        # Load configuration
        settings = get_settings()
        
        # Initialize clients
        print("🔧 Initializing AgentMail client...")
        agentmail_client = AgentMailClient(settings.agentmail.api_token)
        
        print("🧠 Initializing AI chatbot engine...")
        chatbot_engine = ChatbotEngine(
            ai_provider=settings.ai.provider,
            openai_api_key=settings.ai.openai_api_key,
            google_api_key=settings.ai.google_api_key,
            model=settings.ai.google_model if settings.ai.provider == "google" else settings.ai.openai_model,
            max_tokens=settings.ai.max_tokens,
            temperature=settings.ai.temperature
        )
        
        # Step 1: Create or get inbox
        print("\\n📧 Setting up AgentMail inbox...")
        inboxes = agentmail_client.list_inboxes()
        
        target_inbox = None
        for inbox in inboxes:
            if inbox.display_name == settings.agentmail.inbox_display_name:
                target_inbox = inbox
                break
        
        if not target_inbox:
            print(f"Creating new inbox: {settings.agentmail.inbox_display_name}")
            target_inbox = agentmail_client.create_inbox(settings.agentmail.inbox_display_name)
        else:
            print(f"Using existing inbox: {target_inbox.display_name}")
        
        print(f"📮 Inbox email: {target_inbox.email_address}")
        
        # Step 2: Set up webhook
        print("\\n🔗 Setting up webhook...")
        webhooks = agentmail_client.list_webhooks()
        
        target_webhook = None
        for webhook in webhooks:
            if webhook.target_url == settings.webhook.url and webhook.event_type == "message.received":
                target_webhook = webhook
                break
        
        if not target_webhook:
            print(f"Creating webhook for: {settings.webhook.url}")
            target_webhook = agentmail_client.create_webhook(
                event_type="message.received",
                target_url=settings.webhook.url
            )
        else:
            print(f"Using existing webhook: {target_webhook.id}")
        
        print(f"🎣 Webhook status: {'Active' if target_webhook.is_active else 'Inactive'}")
        
        # Step 3: Create sample itinerary
        print("\\n🗓️  Creating sample itinerary...")
        sample_itinerary = create_sample_itinerary()
        chatbot_engine.set_itinerary(sample_itinerary)
        
        print(f"📋 Created itinerary: {sample_itinerary.title}")
        print(f"📅 Dates: {sample_itinerary.start_date} to {sample_itinerary.end_date}")
        print(f"👥 Group size: {len(sample_itinerary.members) + 1} people")
        print(f"🎯 Events: {len(sample_itinerary.events)} scheduled")
        
        # Save itinerary to file for reference
        itinerary_file = os.path.join(os.path.dirname(__file__), "sample_itinerary.json")
        with open(itinerary_file, "w") as f:
            f.write(sample_itinerary.to_json())
        print(f"💾 Saved itinerary to: {itinerary_file}")
        
        # Step 4: Test chatbot responses
        print("\\n🤖 Testing chatbot responses...")
        
        test_queries = [
            "What's our schedule for tomorrow?",
            "Where are we staying?",
            "What time is the Alcatraz tour?",
            "Do we have dinner reservations?",
            "What's the hotel phone number?",
            "How much is the total budget?"
        ]
        
        for query in test_queries:
            print(f"\\n❓ Q: {query}")
            response = chatbot_engine.generate_response(
                query=query,
                itinerary_id=sample_itinerary.id,
                sender_email="test@example.com"
            )
            print(f"🤖 A: {response[:200]}{'...' if len(response) > 200 else ''}")
        
        # Step 5: Summary and next steps
        print("\\n" + "=" * 50)
        print("✅ Setup Complete!")
        print("\\n📋 Summary:")
        print(f"   📧 Inbox: {target_inbox.email_address}")
        print(f"   🔗 Webhook: {target_webhook.target_url}")
        print(f"   🗓️  Itinerary: {sample_itinerary.id}")
        print(f"   🤖 AI Model: {settings.ai.google_model if settings.ai.provider == 'google' else settings.ai.openai_model}")
        
        print("\\n🚀 Next Steps:")
        print("1. Run the webhook server:")
        print("   python main.py")
        print("\\n2. Test the chatbot by sending emails to:")
        print(f"   {target_inbox.email_address}")
        print("\\n3. Ask questions like:")
        print("   - 'What's our schedule today?'")
        print("   - 'Where is the hotel located?'")
        print("   - 'What time is our flight?'")
        print("   - 'What's the budget for this trip?'")
        
        print("\\n🎉 Happy chatting!")
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()