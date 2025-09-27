#!/usr/bin/env python3
"""
Custom itinerary example showing how to create and load your own trip data.
"""
import sys
import os
from datetime import datetime, date, timedelta
import json

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.itinerary_models import (
    TripItinerary, ItineraryEvent, GroupMember, Location, Contact,
    EventType, Priority
)
from src.chatbot_engine import ChatbotEngine
from src.config import get_settings

def create_custom_itinerary():
    """Create a custom itinerary - modify this function for your trip."""
    
    # Customize these details for your trip
    trip_title = "Tokyo Adventure 2024"
    trip_description = "Exploring the vibrant culture and cuisine of Tokyo"
    
    # Trip dates
    start_date = date(2024, 10, 15)  # Modify these dates
    end_date = date(2024, 10, 22)
    
    # Destination
    destination = Location(
        name="Tokyo",
        address="Tokyo, Japan",
        city="Tokyo",
        country="Japan",
        timezone="Asia/Tokyo"
    )
    
    # Group organizer
    organizer = GroupMember(
        name="Your Name",  # Change this
        email="your.email@example.com",  # Change this
        role="organizer"
    )
    
    # Group members - add your actual group members
    members = [
        GroupMember(name="Member 1", email="member1@example.com"),
        GroupMember(name="Member 2", email="member2@example.com"),
        # Add more members as needed
    ]
    
    # Create the itinerary
    itinerary = TripItinerary(
        id="tokyo_adventure_2024",  # Make this unique
        title=trip_title,
        description=trip_description,
        start_date=start_date,
        end_date=end_date,
        destination=destination,
        organizer=organizer,
        members=members,
        budget_total=5000.0,  # Adjust budget
        budget_per_person=1000.0,
        currency="USD"
    )
    
    # Add important information
    itinerary.important_info.update({
        "Language": "Japanese - download Google Translate app",
        "Currency": "Japanese Yen (JPY)",
        "Time Zone": "JST (UTC+9)",
        "Emergency Number": "110 (Police), 119 (Fire/Medical)",
        "Pocket WiFi": "Device pickup at airport counter"
    })
    
    # Create events - customize these for your actual plans
    base_datetime = datetime.combine(start_date, datetime.min.time())
    
    events = [
        # Arrival
        ItineraryEvent(
            id="arrival",
            title="Arrive at Narita Airport",
            event_type=EventType.FLIGHT,
            start_datetime=base_datetime.replace(hour=14, minute=30),
            location=Location(
                name="Narita International Airport",
                address="1-1 Furugome, Narita, Chiba 282-0004, Japan",
                city="Narita",
                country="Japan"
            ),
            priority=Priority.HIGH,
            notes="Immigration, collect pocket WiFi, take Skyliner to Tokyo"
        ),
        
        # Hotel
        ItineraryEvent(
            id="hotel_checkin",
            title="Hotel Check-in",
            event_type=EventType.HOTEL,
            start_datetime=base_datetime.replace(hour=16, minute=0),
            location=Location(
                name="Hotel Name",  # Add your actual hotel
                address="Hotel Address, Tokyo, Japan",
                city="Tokyo",
                country="Japan"
            ),
            contacts=[
                Contact(
                    name="Hotel Front Desk",
                    phone="+81-3-XXXX-XXXX"  # Add actual phone
                )
            ],
            priority=Priority.HIGH
        ),
        
        # Activities - add your planned activities
        ItineraryEvent(
            id="shibuya_crossing",
            title="Visit Shibuya Crossing",
            event_type=EventType.ACTIVITY,
            start_datetime=base_datetime.replace(hour=18, minute=0),
            end_datetime=base_datetime.replace(hour=20, minute=0),
            location=Location(
                name="Shibuya Crossing",
                address="Shibuya, Tokyo, Japan",
                city="Tokyo",
                country="Japan"
            ),
            description="Experience the famous scramble crossing and explore Shibuya",
            cost=0.0
        ),
        
        # Dining
        ItineraryEvent(
            id="sushi_dinner",
            title="Sushi Dinner",
            event_type=EventType.RESTAURANT,
            start_datetime=base_datetime.replace(hour=20, minute=30),
            end_datetime=base_datetime.replace(hour=22, minute=0),
            location=Location(
                name="Sushi Restaurant Name",  # Add actual restaurant
                address="Restaurant Address, Tokyo, Japan",
                city="Tokyo",
                country="Japan"
            ),
            cost=300.0,
            description="Traditional sushi experience",
            notes="Reservation required"
        )
        
        # Add more events for other days...
    ]
    
    # Add all events to itinerary
    for event in events:
        itinerary.add_event(event)
    
    return itinerary

def save_itinerary(itinerary: TripItinerary, filename: str = "custom_itinerary.json"):
    """Save itinerary to JSON file."""
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, "w") as f:
        f.write(itinerary.to_json())
    print(f"💾 Saved itinerary to: {filepath}")

def load_itinerary(filename: str = "custom_itinerary.json") -> TripItinerary:
    """Load itinerary from JSON file."""
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, "r") as f:
        return TripItinerary.from_json(f.read())

def test_custom_itinerary():
    """Test the custom itinerary with sample queries."""
    print("🧪 Testing custom itinerary...")
    
    try:
        # Load the itinerary
        itinerary = load_itinerary()
        
        # Initialize chatbot
        settings = get_settings()
        chatbot = ChatbotEngine(
            openai_api_key=settings.openai.api_key,
            model=settings.openai.model
        )
        chatbot.set_itinerary(itinerary)
        
        # Test queries specific to your itinerary
        test_queries = [
            "What's our itinerary for the first day?",
            "Where are we staying?",
            "What activities do we have planned?",
            "What's the total budget?",
            "What should I know about the destination?",
            # Add more queries specific to your trip
        ]
        
        for query in test_queries:
            print(f"\\n❓ {query}")
            response = chatbot.generate_response(
                query=query,
                itinerary_id=itinerary.id,
                sender_email="test@example.com"
            )
            print(f"🤖 {response[:200]}{'...' if len(response) > 200 else ''}")
            
    except FileNotFoundError:
        print("❌ Custom itinerary file not found. Run with --create first.")
    except Exception as e:
        print(f"❌ Error testing itinerary: {e}")

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Custom Itinerary Manager")
    parser.add_argument("--create", action="store_true", help="Create a new custom itinerary")
    parser.add_argument("--test", action="store_true", help="Test the custom itinerary")
    parser.add_argument("--file", default="custom_itinerary.json", help="Itinerary filename")
    
    args = parser.parse_args()
    
    print("📝 Custom Itinerary Manager")
    print("=" * 30)
    
    if args.create:
        print("🏗️  Creating custom itinerary...")
        itinerary = create_custom_itinerary()
        save_itinerary(itinerary, args.file)
        
        print(f"✅ Created itinerary: {itinerary.title}")
        print(f"📅 Dates: {itinerary.start_date} to {itinerary.end_date}")
        print(f"👥 Group size: {len(itinerary.members) + 1}")
        print(f"🎯 Events: {len(itinerary.events)}")
        
        print("\\n📋 Next steps:")
        print(f"1. Edit {args.file} to customize your trip details")
        print(f"2. Test with: python {__file__} --test")
        print("3. Use this itinerary ID in your webhook server:", itinerary.id)
    
    elif args.test:
        test_custom_itinerary()
    
    else:
        print("Use --create to create a new itinerary or --test to test existing one")
        print(f"Example: python {__file__} --create")

if __name__ == "__main__":
    main()