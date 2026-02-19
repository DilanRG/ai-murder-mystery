/**
 * AI Murder Mystery Game — Electron Main Process
 * Manages the application window and spawns the Python backend.
 */
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

let mainWindow;
let backendProcess;
const BACKEND_PORT = 8765;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1024,
        minHeight: 768,
        backgroundColor: '#0a0a0f',
        titleBarStyle: 'hidden',
        titleBarOverlay: {
            color: '#0a0a0f',
            symbolColor: '#c9a55a',
            height: 36,
        },
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
        },
        icon: null,
        show: false,
    });

    mainWindow.loadFile('index.html');

    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
        stopBackend();
    });
}

function startBackend() {
    // app.isPackaged is false during `npm start` / `electron .`, true after packaging
    if (!app.isPackaged) {
        console.log('[Backend] Dev mode — expecting backend at', BACKEND_URL);
        console.log('[Backend] Start it manually: cd backend && python -m uvicorn main:app --port 8765');
        return;
    }

    // In production, spawn the bundled backend
    const backendPath = path.join(process.resourcesPath, 'backend', 'main');

    if (!fs.existsSync(backendPath) && !fs.existsSync(backendPath + '.exe')) {
        console.error('[Backend] Bundled backend not found at:', backendPath);
        return;
    }

    console.log('[Backend] Starting:', backendPath);

    backendProcess = spawn(backendPath, [], {
        stdio: ['ignore', 'pipe', 'pipe'],
        env: { ...process.env },
    });

    backendProcess.stdout.on('data', (data) => {
        console.log(`[Backend] ${data}`);
    });

    backendProcess.stderr.on('data', (data) => {
        console.error(`[Backend ERR] ${data}`);
    });

    backendProcess.on('close', (code) => {
        console.log(`[Backend] Exited with code ${code}`);
    });
}

function stopBackend() {
    if (backendProcess) {
        backendProcess.kill();
        backendProcess = null;
    }
}

// IPC handlers for frontend communication
ipcMain.handle('get-backend-url', () => BACKEND_URL);

app.whenReady().then(() => {
    startBackend();
    createWindow();
});

app.on('window-all-closed', () => {
    stopBackend();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});
