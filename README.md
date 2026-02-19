# AI Murder Mystery Game

An AI-powered murder mystery game inspired by Among Us, where you play as either a **Detective** investigating a murder or the **Killer** trying to evade detection. All NPC characters are driven by AI (via OpenRouter), creating unique scenarios every playthrough.

## Features

- 🔍 **Two Roles**: Play as Detective or Killer
- 🤖 **AI-Driven NPCs**: 12 unique characters with distinct personalities
- 🎲 **Procedural Mysteries**: AI generates unique scenarios, clues, and motives each game
- 🗺️ **Dynamic World**: NPCs move between locations, interact with each other, and react to events
- 🧠 **Isolated NPC Memory**: Each character only knows what they should (ChromaDB vector DB)
- 🎨 **Premium UI**: Atmospheric dark noir theme with cinematic typography

## Prerequisites

- Python 3.11+
- Node.js 18+
- OpenRouter API key (free tier: [openrouter.ai](https://openrouter.ai))

## First-Time Setup

```bash
# 1. Install Python dependencies
cd backend
python -m venv venv
venv\Scripts\activate   # On Mac/Linux: source venv/bin/activate
pip install -r requirements.txt

# 2. Configure your API key
cp .env.example .env
# Edit .env and add your OpenRouter API key

# 3. Install Electron dependencies
cd ../frontend
npm install
```

## Running the Game

Open two terminals:

```bash
# Terminal 1 — Backend
cd backend
venv\Scripts\activate
python -m uvicorn main:app --host 127.0.0.1 --port 8765
```

```bash
# Terminal 2 — Frontend
cd frontend
npm start
```

## License

MIT
