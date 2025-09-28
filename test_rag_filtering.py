#!/usr/bin/env python3
"""
Test script to demonstrate the simplified RAG filtering system.
"""
import sys
import os
import json
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from src.chatbot_engine import ChatbotEngine, EmailAnalysis

def create_sample_analysis_results():
    """Create sample analysis results to demonstrate simplified RAG filtering."""
    
    # Sample 1: Pure question - should NOT be stored
    # User asked: "What time is dinner?" - no new facts from user
    pure_question = EmailAnalysis(
        is_pure_question=True,
        facts_summary="",  # No new facts from user input
        query_response="Dinner is scheduled for 7:30 PM at Luigi's Restaurant."  # Response from existing itinerary
    )
    
    # Sample 2: Preference statement - should be stored
    preference_statement = EmailAnalysis(
        is_pure_question=False,
        facts_summary="John Smith is vegetarian",
        query_response="Got it! I've noted that you're vegetarian. I'll make sure the restaurant is aware of your dietary preference."
    )
    
    # Sample 3: Mixed content - extract only the facts
    mixed_content = EmailAnalysis(
        is_pure_question=False,
        facts_summary="Sarah Johnson is allergic to shellfish",
        query_response="We're meeting at the hotel lobby at 6 PM. I've also noted your shellfish allergy - I'll make sure all restaurants are informed."
    )
    
    # Sample 4: Logistics update - should be stored
    logistics_update = EmailAnalysis(
        is_pure_question=False,
        facts_summary="Uber booked for 7am pickup at hotel lobby",
        query_response="Perfect! I've noted the 7am Uber pickup from the hotel lobby. Thanks for taking care of that!"
    )
    
    # Sample 5: Social chatter - pure question, don't store
    social_chatter = EmailAnalysis(
        is_pure_question=True,
        facts_summary="",
        query_response="I'm excited too! This is going to be an amazing trip!"
    )
    
    return [pure_question, preference_statement, mixed_content, logistics_update, social_chatter]

def test_rag_filtering():
    """Test the simplified RAG filtering system with sample data."""
    
    print("🧪 Testing Simplified RAG Filtering System")
    print("=" * 50)
    
    # Initialize chatbot engine (we don't need real API keys for this test)
    chatbot = ChatbotEngine()
    
    # Get sample analysis results
    sample_analyses = create_sample_analysis_results()
    sample_names = ["Pure Question", "Vegetarian Preference", "Mixed Content", "Logistics Update", "Social Chatter"]
    
    for i, (analysis, name) in enumerate(zip(sample_analyses, sample_names), 1):
        print(f"\n📧 Sample Email #{i}: {name}")
        print(f"   Is Pure Question: {analysis.is_pure_question}")
        print(f"   Response: {analysis.query_response[:60]}...")
        
        # Test if should store
        should_store = chatbot.should_store_in_rag(analysis)
        print(f"   Store in RAG: {'✅ YES' if should_store else '❌ NO'}")
        
        if should_store:
            # Get storage content
            storage_content = chatbot.get_storage_content(analysis)
            print(f"   Storage Content: '{storage_content}'")
            
            # Get metadata
            metadata = chatbot.get_rag_metadata(analysis, "test@example.com")
            print(f"   Metadata: {json.dumps(metadata, indent=6)}")
    
    print("\n" + "=" * 50)
    print("✅ Simplified RAG Filtering Test Complete!")
    
    # Summary
    stored_count = sum(1 for analysis in sample_analyses if chatbot.should_store_in_rag(analysis))
    total_count = len(sample_analyses)
    
    print(f"📊 Results: {stored_count}/{total_count} emails would be stored in RAG")
    print(f"🎯 This represents a {((total_count - stored_count) / total_count) * 100:.1f}% reduction in storage")
    print("🎯 Much simpler: just 'pure questions' vs 'contains facts'!")

if __name__ == "__main__":
    test_rag_filtering()