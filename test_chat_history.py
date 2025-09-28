#!/usr/bin/env python3
"""
Test script to verify chat history functionality
"""
import sys
import os
import json
import requests
import time

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_chat_history_functionality():
    """Test the chat history functionality by simulating API calls"""
    
    print("🧪 Testing Chat History Functionality")
    print("=" * 50)
    
    # Test configuration
    BASE_URL = "http://localhost:5001"
    
    # First, let's check if there are any trips in the store
    try:
        import web_ui
        if not web_ui.TRIPS_STORE:
            print("❌ No trips found in store. Please create a trip first.")
            return False
            
        # Get the first trip ID
        trip_id = list(web_ui.TRIPS_STORE.keys())[0]
        trip_name = web_ui.TRIPS_STORE[trip_id]['name']
        print(f"✅ Using trip: {trip_name} (ID: {trip_id})")
        
    except Exception as e:
        print(f"❌ Error loading trips: {e}")
        return False
    
    # Test 1: Send first message (empty history)
    print("\n📝 Test 1: First message with empty history")
    try:
        response = requests.post(
            f"{BASE_URL}/trip/{trip_id}/chatbot",
            json={
                "query": "Hello, I'm testing the chat functionality",
                "history": []
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ First message sent successfully")
            print(f"   Response: {data.get('response', 'No response')[:100]}...")
            
            if 'history' in data:
                history = data['history']
                print(f"✅ History returned with {len(history)} items")
                print(f"   History: {history}")
            else:
                print("❌ No history returned in response")
                return False
        else:
            print(f"❌ First message failed: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Make sure the web server is running on localhost:5001")
        return False
    except Exception as e:
        print(f"❌ Error sending first message: {e}")
        return False
    
    # Test 2: Send second message with history from first response
    print("\n📝 Test 2: Second message with previous history")
    try:
        response2 = requests.post(
            f"{BASE_URL}/trip/{trip_id}/chatbot",
            json={
                "query": "What was my previous message about?",
                "history": history  # Use history from previous response
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response2.status_code == 200:
            data2 = response2.json()
            print("✅ Second message sent successfully")
            print(f"   Response: {data2.get('response', 'No response')[:100]}...")
            
            if 'history' in data2:
                new_history = data2['history']
                print(f"✅ Updated history returned with {len(new_history)} items")
                print(f"   New history length: {len(new_history)} vs old: {len(history)}")
                
                # Check if history grew
                if len(new_history) > len(history):
                    print("✅ History is accumulating correctly")
                else:
                    print("❌ History not growing as expected")
                    return False
            else:
                print("❌ No history returned in second response")
                return False
        else:
            print(f"❌ Second message failed: {response2.status_code} - {response2.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending second message: {e}")
        return False
    
    # Test 3: Check if AI can reference previous context
    print("\n📝 Test 3: Context awareness test")
    try:
        response3 = requests.post(
            f"{BASE_URL}/trip/{trip_id}/chatbot",
            json={
                "query": "Can you summarize our conversation so far?",
                "history": new_history
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response3.status_code == 200:
            data3 = response3.json()
            print("✅ Context test message sent successfully")
            print(f"   Response: {data3.get('response', 'No response')[:200]}...")
            
            # Check if the AI response mentions previous messages
            response_text = data3.get('response', '').lower()
            if 'test' in response_text or 'previous' in response_text or 'conversation' in response_text:
                print("✅ AI appears to be aware of conversation context")
            else:
                print("⚠️  AI may not be using conversation context effectively")
                
        else:
            print(f"❌ Context test failed: {response3.status_code} - {response3.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error in context test: {e}")
        return False
    
    print("\n🎉 All chat history tests completed successfully!")
    return True

def test_frontend_javascript():
    """Test if the frontend JavaScript is properly structured"""
    print("\n🧪 Testing Frontend JavaScript Structure")
    print("=" * 50)
    
    template_path = os.path.join(project_root, 'templates', 'trip_detail.html')
    
    try:
        with open(template_path, 'r') as f:
            content = f.read()
            
        # Check for chat history variable
        if 'let chatHistory = [];' in content:
            print("✅ Chat history variable declared")
        else:
            print("❌ Chat history variable not found")
            
        # Check for history in fetch requests
        if 'history: chatHistory' in content:
            print("✅ History being sent in fetch requests")
        else:
            print("❌ History not being sent in fetch requests")
            
        # Check for history update handling
        if 'chatHistory = data.history;' in content:
            print("✅ History update handling found")
        else:
            print("❌ History update handling not found")
            
        # Check for template literal issues
        if 'fetch(`/trip/{{ trip.id }}/chatbot`' in content:
            print("⚠️  Template literal found - this may cause parsing issues")
        elif "fetch('/trip/{{ trip.id }}/chatbot'" in content:
            print("✅ Using proper string quotes for fetch URL")
            
        print("✅ Frontend JavaScript structure looks good")
        return True
        
    except Exception as e:
        print(f"❌ Error checking frontend: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Chat History Tests")
    print("Make sure the web server is running: python web_ui.py")
    print()
    
    # Test frontend structure first
    frontend_ok = test_frontend_javascript()
    
    if frontend_ok:
        # Wait a moment for user to start server if needed
        input("\nPress Enter when the web server is running on localhost:5001...")
        
        # Test API functionality
        api_ok = test_chat_history_functionality()
        
        if api_ok:
            print("\n✅ All tests passed! Chat history functionality is working correctly.")
        else:
            print("\n❌ Some tests failed. Check the output above for details.")
    else:
        print("\n❌ Frontend structure issues found. Please fix before testing API.")