#!/bin/bash

# Concord Trip Coordination System - Startup Script
# This script starts all required services for the system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$PROJECT_DIR/venv"
NGROK_PORT=8000
WEB_UI_PORT=5001

echo -e "${BLUE}🚀 Starting Concord Trip Coordination System...${NC}"
echo -e "${BLUE}📁 Project Directory: $PROJECT_DIR${NC}"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if port is available
port_available() {
    ! lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null
}

# Function to wait for service to be ready
wait_for_service() {
    local port=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}⏳ Waiting for $service_name to be ready on port $port...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null; then
            echo -e "${GREEN}✅ $service_name is ready!${NC}"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}❌ $service_name failed to start within 30 seconds${NC}"
    return 1
}

# Check prerequisites
echo -e "${PURPLE}🔍 Checking prerequisites...${NC}"

if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}❌ Virtual environment not found at $VENV_PATH${NC}"
    echo -e "${YELLOW}💡 Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt${NC}"
    exit 1
fi

if ! command_exists ngrok && [ ! -f "$PROJECT_DIR/ngrok" ]; then
    echo -e "${RED}❌ ngrok not found in PATH or project directory${NC}"
    echo -e "${YELLOW}💡 Install ngrok from https://ngrok.com/download${NC}"
    exit 1
fi

# Check if ports are available
if ! port_available $NGROK_PORT; then
    echo -e "${RED}❌ Port $NGROK_PORT is already in use (needed for webhook server)${NC}"
    exit 1
fi

if ! port_available $WEB_UI_PORT; then
    echo -e "${RED}❌ Port $WEB_UI_PORT is already in use (needed for web UI)${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites met${NC}"

# Activate virtual environment
echo -e "${PURPLE}🐍 Activating virtual environment...${NC}"
source "$VENV_PATH/bin/activate"

# Check if ChromaDB is running (optional but recommended)
if ! lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null; then
    echo -e "${YELLOW}⚠️  ChromaDB not detected on port 8001${NC}"
    echo -e "${YELLOW}   You may want to start it separately: chroma run --path ./db/ --host localhost --port 8001${NC}"
    echo -e "${YELLOW}   Continuing anyway...${NC}"
else
    echo -e "${GREEN}✅ ChromaDB detected on port 8001${NC}"
fi

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down services...${NC}"
    
    # Kill all background jobs
    jobs -p | xargs -r kill 2>/dev/null || true
    
    # Wait a moment for graceful shutdown
    sleep 2
    
    # Force kill any remaining processes
    pkill -f "python.*web_ui.py" 2>/dev/null || true
    pkill -f "python.*main.py" 2>/dev/null || true
    pkill -f "ngrok.*http.*$NGROK_PORT" 2>/dev/null || true
    
    echo -e "${GREEN}✅ Cleanup complete${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start services
echo -e "${BLUE}🌐 Starting Web UI on port $WEB_UI_PORT...${NC}"
WEB_UI_PORT=$WEB_UI_PORT python web_ui.py > "$PROJECT_DIR/logs/web_ui.log" 2>&1 &
WEB_UI_PID=$!

# Wait for Web UI to be ready
wait_for_service $WEB_UI_PORT "Web UI"

echo -e "${BLUE}🎣 Starting Webhook Server on port $NGROK_PORT...${NC}"
python main.py > "$PROJECT_DIR/logs/webhook_server.log" 2>&1 &
WEBHOOK_PID=$!

# Wait for Webhook Server to be ready
wait_for_service $NGROK_PORT "Webhook Server"

echo -e "${BLUE}🌍 Starting ngrok tunnel...${NC}"
if command_exists ngrok; then
    ngrok http $NGROK_PORT --log=stdout > "$PROJECT_DIR/logs/ngrok.log" 2>&1 &
else
    "$PROJECT_DIR/ngrok" http $NGROK_PORT --log=stdout > "$PROJECT_DIR/logs/ngrok.log" 2>&1 &
fi
NGROK_PID=$!

# Wait a moment for ngrok to establish tunnel
sleep 3

# Try to get ngrok URL
NGROK_URL=""
if command_exists curl; then
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for tunnel in data.get('tunnels', []):
        if tunnel.get('proto') == 'https':
            print(tunnel.get('public_url', ''))
            break
except:
    pass
" 2>/dev/null)
fi

# Display status
echo -e "\n${GREEN}🎉 All services started successfully!${NC}"
echo -e "${GREEN}=================================${NC}"
echo -e "${GREEN}📱 Web UI:           ${BLUE}http://localhost:$WEB_UI_PORT${NC}"
echo -e "${GREEN}🎣 Webhook Server:   ${BLUE}http://localhost:$NGROK_PORT${NC}"
if [ -n "$NGROK_URL" ]; then
    echo -e "${GREEN}🌍 Public URL:       ${BLUE}$NGROK_URL${NC}"
    echo -e "${YELLOW}💡 Update your WEBHOOK_URL in config/.env to: $NGROK_URL/webhook${NC}"
else
    echo -e "${YELLOW}🌍 Public URL:       ${YELLOW}Check ngrok dashboard at http://localhost:4040${NC}"
fi
echo -e "${GREEN}📊 ngrok Dashboard:  ${BLUE}http://localhost:4040${NC}"
echo -e "${GREEN}=================================${NC}"

echo -e "${PURPLE}📋 Service Status:${NC}"
echo -e "   Web UI PID: $WEB_UI_PID"
echo -e "   Webhook Server PID: $WEBHOOK_PID"
echo -e "   ngrok PID: $NGROK_PID"

echo -e "\n${YELLOW}📝 Logs are available at:${NC}"
echo -e "   Web UI: $PROJECT_DIR/logs/web_ui.log"
echo -e "   Webhook Server: $PROJECT_DIR/logs/webhook_server.log"
echo -e "   ngrok: $PROJECT_DIR/logs/ngrok.log"

echo -e "\n${BLUE}🔄 All services are running. Press Ctrl+C to stop all services.${NC}"

# Wait for user interrupt
while true; do
    sleep 1
    
    # Check if any service died
    if ! kill -0 $WEB_UI_PID 2>/dev/null; then
        echo -e "${RED}❌ Web UI service died${NC}"
        cleanup
    fi
    
    if ! kill -0 $WEBHOOK_PID 2>/dev/null; then
        echo -e "${RED}❌ Webhook Server service died${NC}"
        cleanup
    fi
    
    if ! kill -0 $NGROK_PID 2>/dev/null; then
        echo -e "${RED}❌ ngrok service died${NC}"
        cleanup
    fi
done