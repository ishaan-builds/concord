#!/bin/bash

# Simple startup script for development
# Just starts the services without all the bells and whistles

echo "🚀 Starting Concord services..."

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtual environment
source "$PROJECT_DIR/venv/bin/activate"

# Start services in background
echo "Starting Web UI..."
WEB_UI_PORT=5001 python web_ui.py &

echo "Starting Webhook Server..."  
python main.py &

echo "Starting ngrok..."

echo "✅ All services started!"
echo "📱 Web UI: http://localhost:5001"
echo "🎣 Webhook: http://localhost:8000" 
echo "🌍 ngrok Dashboard: http://localhost:4040"
echo ""
echo "Press any key to stop all services..."
read

# Kill all background jobs
echo "Stopping services..."
pkill -f "python.*web_ui.py" 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true  
pkill -f "ngrok.*http.*8000" 2>/dev/null || true

echo "✅ All services stopped!"