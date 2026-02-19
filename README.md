# AI Murder Mystery Game

An AI-powered murder mystery game inspired by Among Us, where you play as either a **Detective** investigating a murder or the **Killer** trying to evade detection. All NPC characters are driven by AI (via OpenRouter), creating unique scenarios every playthrough.

## Features

- 🔍 **Two Roles**: Play as Detective or Killer
- 🤖 **AI-Driven NPCs**: 12 unique characters with distinct personalities
- 🎲 **Procedural Mysteries**: AI generates unique scenarios, clues, and motives each game
- 🗺️ **Dynamic World**: NPCs move between locations, interact with each other, and react to events
- 🧠 **Isolated NPC Memory**: Each character only knows what they should (ChromaDB vector DB)
- 🎨 **Premium UI**: Atmospheric dark noir theme with cinematic typography

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- OpenRouter API key (free tier: [openrouter.ai](https://openrouter.ai))

### Setup

1. **Install Python dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Configure API key:**
   ```bash
   cp backend/.env.example backend/.env
   # Edit .env and add your OpenRouter API key
   ```

3. **Install Electron dependencies:**
   ```bash
   cd frontend
   npm install
   ```

### Run (Development)

1. **Start backend:**
   ```bash
   cd backend
   python -m uvicorn main:app --host 127.0.0.1 --port 8765 --reload
   ```

2. **Start frontend (new terminal):**
   ```bash
   cd frontend
   npm start
   ```

### Build (Production)

```bash
# Build Python backend executable
python build/build_backend.py

# Build Electron app (Windows/Mac/Linux)
cd frontend
npm run build
```

## Project Structure

```
game/
├── backend/           # Python FastAPI server
│   ├── config/        # Settings, sampler presets, instruct templates
│   ├── llm/           # LLM API client & prompt builder
│   ├── game/          # Core game engine
│   ├── memory/        # ChromaDB vector database
│   └── characters/    # Character Card V2 JSON pool
├── frontend/          # Electron app
│   ├── css/           # Premium dark theme
│   └── js/            # App controller
└── build/             # Build scripts
```

## License

MIT
