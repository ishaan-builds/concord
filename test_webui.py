#!/usr/bin/env python3
"""
Simple test script to verify web UI is working
"""
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    print("Testing web UI imports...")
    import web_ui
    print("✓ Web UI imports successfully")
    
    print(f"✓ Found {len(web_ui.TRIPS_STORE)} trips in store")
    
    # Test creating the Flask app
    app = web_ui.app
    print("✓ Flask app created successfully")
    
    # Test if templates exist
    template_files = ['base.html', 'index.html', 'create_trip.html', 'trip_detail.html']
    for template in template_files:
        template_path = os.path.join(project_root, 'templates', template)
        if os.path.exists(template_path):
            print(f"✓ Template {template} exists")
        else:
            print(f"✗ Template {template} missing")
    
    print("\nStarting web UI on http://localhost:5001")
    print("Press Ctrl+C to stop")
    
    app.run(host='0.0.0.0', port=5001, debug=True)
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()