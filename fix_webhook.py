#!/usr/bin/env python3
"""
Fix webhook URL for existing trip
"""
import json
from src.config import get_settings
from src.agentmail_client import AgentMailClient

def main():
    # Load settings
    settings = get_settings()
    
    # Create AgentMail client
    client = AgentMailClient(settings.agentmail.api_token)
    
    # Load trip data
    with open('data/trips.json', 'r') as f:
        trips = json.load(f)
    
    trip_id = "8b2fbe83"
    trip = trips[trip_id]
    
    # Delete old webhook
    old_webhook_id = trip['webhook_id']
    print(f"Deleting old webhook: {old_webhook_id}")
    client.delete_webhook(old_webhook_id)
    
    # Create new webhook with correct URL
    correct_webhook_url = f"https://sclerosed-wilhemina-heapy.ngrok-free.dev/webhook/{trip_id}"
    print(f"Creating new webhook: {correct_webhook_url}")
    new_webhook = client.create_webhook("message.received", correct_webhook_url)
    
    # Update trip data
    trip['webhook_id'] = new_webhook.id
    trip['webhook_url'] = correct_webhook_url
    
    # Save updated trip data
    with open('data/trips.json', 'w') as f:
        json.dump(trips, f, indent=2)
    
    print(f"Updated webhook ID: {new_webhook.id}")
    print("Webhook fixed successfully!")

if __name__ == "__main__":
    main()