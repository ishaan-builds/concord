# Concord - AI-Powered Trip Coordination Platform

An intelligent trip planning and coordination platform that combines AgentMail's infrastructure with advanced AI capabilities for seamless group travel management.

## 🚀 Features

- **AI-Powered Itinerary Management**: Uses Google Gemini 2.0 to intelligently schedule and organize trip events
- **Interactive Web Interface**: Modern React-like UI with real-time calendar integration using FullCalendar
- **Email-Based Coordination**: Group members can interact via email through dedicated AgentMail inboxes
- **Smart Event Creation**: AI automatically determines optimal scheduling, locations, and event details
- **Vector Database Storage**: ChromaDB integration for persistent trip context and intelligent RAG queries  
- **Multi-Domain Support**: Custom domain setup with Cloudflare tunnels for professional deployment
- **Real-time Chat Interface**: Built-in AI assistant for instant trip planning and coordination

## 🏗️ Architecture

### Core Components
1. **Web UI** (`web_ui.py`) - Flask-based web interface with calendar visualization
2. **AI Engine** (`src/chatbot_engine.py`) - Gemini-powered intelligent trip planning
3. **AgentMail Integration** (`src/agentmail_client.py`) - Email coordination and inbox management
4. **Vector Database** (`db/`) - ChromaDB for context storage and retrieval
5. **Webhook Server** (`src/webhook_server.py`) - Real-time email processing

### AI-Powered Scheduling
- **Intelligent Event Placement**: AI decides optimal timing based on trip context
- **Dynamic Rescheduling**: Automatically adjusts itineraries when conflicts arise
- **Smart Location Matching**: Resolves addresses and coordinates for mapping
- **Cost Optimization**: Considers budget constraints in planning decisions

## 🛠️ Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp config/.env.example config/.env
# Edit config/.env with your API keys:
# - AGENTMAIL_API_KEY (get from AgentMail dashboard)
# - GOOGLE_API_KEY (for Gemini AI)
# - OPENAI_API_KEY (optional, for OpenAI fallback)
```

### 3. Start the Application
```bash
# Start the web UI
python web_ui.py

# Or start the webhook server for email integration
python main.py
```

### 4. Create Your First Trip
1. Visit `http://localhost:5002`
2. Click "Create New Trip"
3. Configure your trip details
4. Share the generated email address with your group

## 📱 Usage

### Web Interface
- **Trip Creation**: Set up new trips with destinations and group details
- **AI Chat**: Ask the AI assistant to plan activities, book restaurants, or adjust schedules
- **Calendar View**: Visual timeline of all trip events with interactive details
- **Group Coordination**: Share trip email for seamless group communication

### Email Integration
Group members can email the trip address to:
- Ask questions about the itinerary
- Request changes to plans
- Get recommendations for activities
- Receive automated confirmations and updates

### AI Commands
The AI understands natural language requests like:
- "Add a flight from NYC to Paris on December 15th at 6 PM"
- "Find a good restaurant near the hotel for dinner tomorrow"
- "Move the museum visit to earlier in the day"
- "What's the total cost of our trip so far?"

## 🌐 Custom Domain Setup

For professional deployment with custom domains:

```bash
# Configure Cloudflare tunnel
./start-cloudflare.sh

# Your app will be available at your custom domain
# Webhook endpoint: https://webhook.your-domain.com/webhook
```

## 🔧 Configuration

Key settings in `config/.env`:
- **AI_PROVIDER**: Choose between 'google' (Gemini) or 'openai' (GPT)
- **AI_MODEL**: Specific model version (gemini-2.0-flash-exp recommended)
- **WEBHOOK_URL**: Public URL for email webhook processing
- **DEBUG**: Enable detailed logging for development

## 🎯 Perfect for Hackathons

- **Quick Setup**: Get running in under 5 minutes
- **Modern Tech Stack**: AI, Vector DB, Real-time UI
- **Scalable Architecture**: Ready for production deployment
- **Demo-Friendly**: Interactive calendar and chat interface
- **Practical Use Case**: Solves real coordination problems