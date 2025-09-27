# AgentMail Trip Creator Web UI

A user-friendly web interface for creating AI-powered trip coordination assistants using AgentMail.

## Features

✨ **Easy Trip Creation** - Simple web form to set up new trips
📧 **Automatic Inbox Generation** - Creates unique AgentMail inboxes for each trip
🤖 **AI Assistant Configuration** - Sets up chatbots with trip-specific knowledge
💬 **Live Chat Testing** - Test your AI assistant before sharing with your group
📊 **Trip Management Dashboard** - View and manage all your created trips
🔗 **Shareable Email Addresses** - Get unique email addresses to share with participants

## Quick Start

### 1. Set up your environment

Make sure you have your environment configured in `config/.env`:

```bash
# Required
AGENTMAIL_API_TOKEN=your_agentmail_token
OPENAI_API_KEY=your_openai_key  # or GOOGLE_API_KEY
WEBHOOK_URL=https://your-ngrok-url.ngrok.io  # Your public webhook URL

# Optional
WEB_UI_PORT=5000
FLASK_DEBUG=true
FLASK_SECRET_KEY=your-secret-key
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the webhook server

The webhook server handles incoming emails for all trips:

```bash
python multi_webhook_server.py
```

### 4. Start the web UI

In a separate terminal:

```bash
python web_ui.py
```

### 5. Set up ngrok (if needed)

If you're running locally, use ngrok to expose your webhook server:

```bash
./ngrok http 8000
```

Update your `WEBHOOK_URL` in `.env` with the ngrok URL.

## Usage

### Creating a New Trip

1. Visit http://localhost:5000
2. Click "Create New Trip"
3. Fill out the trip details:
   - **Trip Name**: e.g., "San Francisco Weekend Getaway"
   - **Destination**: Where you're going
   - **Dates**: Start and end dates
   - **Organizer Info**: Your name and email
   - **Participants**: Names of other travelers (optional)
   - **Budget**: Total budget (optional)

4. Click "Create Trip Assistant"

### Using Your Trip Assistant

After creating a trip, you'll get:

- **Unique Email Address**: Share this with your group
- **Trip Dashboard**: View details and test the AI
- **Live Chat**: Test questions before sharing

Example questions your AI can answer:
- "What's our budget per person?"
- "When does our trip start?"
- "Who's organizing this trip?"
- "What are the trip dates?"

### Managing Trips

- **View All Trips**: Homepage shows all your created trips
- **Trip Details**: Click "View" to see full trip information
- **Test AI**: Use the built-in chat to test responses
- **Copy Email**: Easily copy the inbox email to share
- **Delete Trip**: Remove trips you no longer need

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web UI        │    │  Multi-Webhook   │    │   AgentMail     │
│  (Flask App)    │    │     Server       │    │     API         │
│  Port 5000      │    │   Port 8000      │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         │ Creates trips          │ Handles emails         │ Sends/receives
         │ Manages inboxes        │ Processes AI           │ email messages
         └────────────────────────┼────────────────────────┘
                                  │
                          ┌───────▼────────┐
                          │  Trip Data     │
                          │  Storage       │
                          │ (JSON files)   │
                          └────────────────┘
```

## File Structure

```
├── web_ui.py                 # Flask web application
├── multi_webhook_server.py   # Multi-trip webhook handler
├── templates/                # HTML templates
│   ├── base.html            # Base template with Bootstrap
│   ├── index.html           # Homepage with trip list
│   ├── create_trip.html     # Trip creation form
│   └── trip_detail.html     # Trip details and testing
├── data/                    # Data storage
│   ├── trips.json          # Trip metadata
│   └── itinerary_*.json    # Individual trip itineraries
└── src/                     # Core functionality
    ├── agentmail_client.py  # AgentMail API wrapper
    ├── chatbot_engine.py    # AI response generation
    └── itinerary_models.py  # Data models
```

## API Endpoints

### Web UI Endpoints

- `GET /` - Homepage with trip list
- `GET /create` - Trip creation form  
- `POST /create` - Handle trip creation
- `GET /trip/<id>` - Trip details page
- `POST /trip/<id>/test` - Test AI chat (AJAX)
- `POST /trip/<id>/delete` - Delete trip

### Webhook Endpoints

- `POST /webhook/<trip_id>` - Handle AgentMail webhooks for specific trips
- `GET /health` - Health check
- `GET /` - Server status

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AGENTMAIL_API_TOKEN` | Yes | Your AgentMail API token |
| `OPENAI_API_KEY` | Yes* | OpenAI API key for GPT models |
| `GOOGLE_API_KEY` | Yes* | Google API key for Gemini models |
| `WEBHOOK_URL` | Yes | Public URL for webhook server |
| `WEB_UI_PORT` | No | Web UI port (default: 5000) |
| `WEBHOOK_PORT` | No | Webhook server port (default: 8000) |
| `FLASK_DEBUG` | No | Enable Flask debug mode |
| `FLASK_SECRET_KEY` | No | Secret key for sessions |

*Either OpenAI or Google API key required

### AI Model Configuration

Set in `config/.env`:

```bash
# Use OpenAI (default)
AI_PROVIDER=openai
OPENAI_MODEL=gpt-4
OPENAI_API_KEY=your_key

# Or use Google Gemini
AI_PROVIDER=google
GOOGLE_MODEL=gemini-1.5-flash
GOOGLE_API_KEY=your_key
```

## Production Deployment

For production use:

1. **Use a real database** instead of JSON files
2. **Set up proper authentication** for the web UI
3. **Use a reverse proxy** (nginx) for the web UI
4. **Set secure environment variables**
5. **Use a process manager** (systemd, supervisor)
6. **Set up SSL certificates** for HTTPS

## Troubleshooting

### Common Issues

**"Trip not found" errors**
- Check that `data/trips.json` exists and contains your trip
- Verify the trip ID in the URL matches the stored data

**Webhook not receiving messages**
- Confirm your `WEBHOOK_URL` is publicly accessible
- Check that ngrok is running and forwarding correctly
- Verify the webhook was created in AgentMail

**AI not responding**
- Check your OpenAI/Google API key is valid
- Verify the model name is correct
- Check the webhook server logs for errors

**Web UI not starting**
- Ensure Flask is installed: `pip install flask`
- Check for port conflicts (default port 5000)
- Verify all required environment variables are set

### Logs

Check logs in these locations:
- Web UI: Console output where you ran `python web_ui.py`
- Webhook Server: Console output where you ran `python multi_webhook_server.py`
- Trip Data: Stored in `data/trips.json`

## Contributing

To add new features:

1. **Web UI**: Modify `web_ui.py` and add templates in `templates/`
2. **Webhook Handling**: Update `multi_webhook_server.py`
3. **AI Features**: Enhance `src/chatbot_engine.py`
4. **Data Models**: Extend `src/itinerary_models.py`

## License

Same license as the main AgentMail project.