#!/bin/bash

# Stop all Concord services

echo "🛑 Stopping Concord services..."

# Kill all related processes
pkill -f "python.*web_ui.py" 2>/dev/null && echo "✅ Stopped Web UI" || echo "ℹ️  Web UI not running"
pkill -f "python.*main.py" 2>/dev/null && echo "✅ Stopped Webhook Server" || echo "ℹ️  Webhook Server not running"
pkill -f "ngrok.*http.*8000" 2>/dev/null && echo "✅ Stopped ngrok" || echo "ℹ️  ngrok not running"

# Also try to kill by port (backup method)
lsof -ti:5001 | xargs -r kill 2>/dev/null || true
lsof -ti:8000 | xargs -r kill 2>/dev/null || true

echo "🎉 All services stopped!"