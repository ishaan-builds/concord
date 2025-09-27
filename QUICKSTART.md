# Quick Start Guide

## 🚀 Getting Started

### 1. Install Dependencies
```bash
cd agentmail-chatbot
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy the example configuration
cp config/.env.example config/.env

# Edit config/.env with your actual API keys:
# - AGENTMAIL_API_TOKEN: Your AgentMail API token
# - OPENAI_API_KEY: Your OpenAI API key  
# - WEBHOOK_URL: Your public webhook URL (use ngrok for local testing)
```

### 3. Test Connectivity
```bash
python examples/test_connection.py
```

### 4. Set Up Demo
```bash
python examples/setup_demo.py
```

### 5. Run the Server
```bash
# FastAPI (recommended)
python main.py

# Or Flask alternative
python examples/flask_server.py
```

## 📧 Testing the Chatbot

After setup, send emails to your AgentMail inbox address and ask questions like:

- "What's our schedule for tomorrow?"
- "Where is the hotel located?"
- "What time is our flight?"
- "What's the budget for this trip?"
- "Do we have dinner reservations?"

## 🔧 Using Your Own Itinerary

```bash
# Create custom itinerary template
python examples/custom_itinerary.py --create

# Edit the generated JSON file with your trip details
# Test your custom itinerary
python examples/custom_itinerary.py --test
```

## 🌐 Local Development with ngrok

If testing locally, use ngrok to expose your webhook:

```bash
# Install ngrok, then:
ngrok http 8000

# Use the https URL in your WEBHOOK_URL setting
```

## ❓ Common Issues

- **Missing API keys**: Make sure `.env` file has valid tokens
- **Webhook not receiving**: Check that your WEBHOOK_URL is publicly accessible
- **OpenAI errors**: Verify your OpenAI API key has sufficient credits
- **AgentMail connection**: Confirm your AgentMail API token is correct