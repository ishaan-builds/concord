#!/bin/bash

# Cloudflare Tunnel startup script for Concord
# This script starts both your local services and the Cloudflare tunnel

set -e

echo "🚀 Starting Concord with Cloudflare Tunnel..."

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Activate virtual environment
if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
    echo "✅ Activated virtual environment"
else
    echo "⚠️  No virtual environment found at $PROJECT_DIR/venv"
fi

# Check if local cloudflared exists
if [ ! -f "./cloudflared" ]; then
    echo "❌ cloudflared not found. Please run setup first."
    exit 1
fi

# Check if tunnel is configured
TUNNEL_CONFIG="$HOME/.cloudflared/config.yml"
if [ ! -f "$TUNNEL_CONFIG" ]; then
    echo "❌ Cloudflare tunnel not configured. Please run setup first:"
    echo "   See DNS_UPDATE_INSTRUCTIONS.md for instructions"
    exit 1
fi

# Start local services in background
echo "🌐 Starting Web UI on port 5002..."
WEB_UI_PORT=5002 python "$PROJECT_DIR/web_ui.py" > "$PROJECT_DIR/logs/web_ui.log" 2>&1 &
WEB_UI_PID=$!

echo "🎣 Starting Webhook Server on port 8000..."
python "$PROJECT_DIR/main.py" > "$PROJECT_DIR/logs/webhook.log" 2>&1 &
WEBHOOK_PID=$!

# Wait a moment for services to start
sleep 3

# Start Cloudflare tunnel
echo "☁️  Starting Cloudflare tunnel..."
echo "   Your site will be available at: https://sample-website.xyz"
echo "   Webhook endpoint: https://webhook.sample-website.xyz/webhook"
echo ""
echo "Press Ctrl+C to stop all services"

# Function to clean up background processes
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $WEB_UI_PID 2>/dev/null || true
    kill $WEBHOOK_PID 2>/dev/null || true
    exit 0
}

# Set up trap to clean up on Ctrl+C
trap cleanup SIGINT SIGTERM

# Run cloudflared tunnel (this blocks)
./cloudflared tunnel run concord

# This line should not be reached, but just in case
cleanup