---
description: How to build and run the AI Murder Mystery game locally during development
---

# Build & Run — AI Murder Mystery Game

## Prerequisites

1. **Python 3.11+** installed and on PATH
2. **Node.js 18+** and **npm** installed and on PATH
3. An **OpenRouter API key** (get one free at https://openrouter.ai)

---

## First-Time Setup

### 1. Install Python dependencies
// turbo
```
cd c:\random scripting\game\backend
pip install -r requirements.txt
```

### 2. Install Electron dependencies
// turbo
```
cd c:\random scripting\game\frontend
npm install
```

### 3. Configure environment
Create a `.env` file in the `backend/` directory:
```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
LLM_MODEL=openai/gpt-4o-mini
```

---

## Development Run

### 4. Start the Python backend
```
cd c:\random scripting\game\backend
python -m uvicorn main:app --host 127.0.0.1 --port 8765 --reload
```
Wait until you see `INFO: Uvicorn running on http://127.0.0.1:8765`.

### 5. Start the Electron frontend (in a new terminal)
```
cd c:\random scripting\game\frontend
npm start
```
The Electron window should open and connect to the backend.

---

## Running Tests

### 6. Backend tests
// turbo
```
cd c:\random scripting\game\backend
python -m pytest tests/ -v
```

### 7. Frontend tests
// turbo
```
cd c:\random scripting\game\frontend
npm test
```

---

## Production Build (Single Executable)

### 8. Build the Python backend binary
```
cd c:\random scripting\game
python build/build_backend.py
```
This uses PyInstaller to create a standalone backend executable in `dist/`.

### 9. Build the cross-platform Electron app
```
cd c:\random scripting\game\frontend
npm run build
```
This uses electron-builder to create:
- **Windows**: `dist/MurderMystery-Setup.exe` (NSIS installer) or portable
- **macOS**: `dist/MurderMystery.dmg`
- **Linux**: `dist/MurderMystery.AppImage`

The Electron app bundles the PyInstaller backend binary inside, so users get a single file.
