# AgentMail AI Chatbot for Group Coordination

A personalized AI-powered chatbot using AgentMail's infrastructure for group information sharing, specifically designed for managing trip itineraries and group coordination.

## Features

- **Centralized Information Storage**: Store group itinerary and trip details in AgentMail inbox as the authoritative source
- **Multi-Channel Access**: Enable group members to query via email or other messaging channels
- **Context-Aware Responses**: AI chatbot uses persistent message history and threads for intelligent answers
- **Automated Coordination**: No manual email management - fully automated responses
- **Persistent History**: All interactions saved and searchable via AgentMail's API
- **Real-time Updates**: Webhook-based system for instant responses to new messages

## Architecture

The system consists of:

1. **AgentMail Inbox**: Central storage for itinerary data and message history
2. **AI Engine**: OpenAI GPT-powered responses with contextual awareness
3. **Webhook Handler**: Automated message processing and response generation
4. **API Client**: AgentMail integration for inbox, thread, and webhook management

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
```bash
cp config/.env.example config/.env
# Edit config/.env with your API keys
```

3. Run the webhook server:
```bash
python src/webhook_server.py
```

4. Set up your AgentMail inbox and webhook:
```bash
python examples/setup_demo.py
```

## Usage

The chatbot automatically responds to messages sent to your AgentMail inbox. Group members can:

- Ask about trip itinerary details
- Get location information
- Query schedules and timing
- Request contact information
- Update trip details (if authorized)

## API Integration

Uses AgentMail's API endpoints:
- `/v0/inboxes` - Inbox management
- `/v0/threads` - Message history access
- `/v0/webhooks` - Event-driven automation

## Configuration

See `config/settings.py` for customization options including:
- AI model selection
- Response templates
- Authorization rules
- Webhook endpoints