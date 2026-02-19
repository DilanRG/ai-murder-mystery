/**
 * AI Murder Mystery Game — Electron Main Process
 * Manages the application window and spawns the Python backend.
 */
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const http = require('http');

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
        icon: null,
        show: true, // Show immediately for debugging
    });

    mainWindow.loadFile('index.html');

    // Debugging events
    mainWindow.webContents.on('did-finish-load', () => {
        console.log('[Window] Content loaded');
    });

    mainWindow.once('ready-to-show', () => {
        console.log('[Window] Ready to show');
        mainWindow.show();
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
        stopBackend();
    });
}

/**
 * Find the backend executable path.
 * In production: extraResources/backend/murder-mystery-backend[.exe]
 * In dev: not bundled — user runs manually.
 */
function getBackendPath() {
    if (!app.isPackaged) return null;

    const baseName = process.platform === 'win32'
        ? 'murder-mystery-backend.exe'
        : 'murder-mystery-backend';

    const backendPath = path.join(process.resourcesPath, 'backend', baseName);

    if (fs.existsSync(backendPath)) return backendPath;

    console.error('[Backend] Executable not found at:', backendPath);
    return null;
}

function startBackend() {
    if (!app.isPackaged) {
        console.log('[Backend] Dev mode - expecting backend at', BACKEND_URL);
        console.log('[Backend] Start it manually: cd backend && python -m uvicorn main:app --port 8765');
        return;
    }

    const backendPath = getBackendPath();
    if (!backendPath) return;

    console.log('[Backend] Starting:', backendPath);

    // Set up environment — tell the backend where to find its data
    const backendDir = path.dirname(backendPath);
    const env = { ...process.env };

    backendProcess = spawn(backendPath, [], {
        stdio: ['ignore', 'pipe', 'pipe'],
        cwd: backendDir,
        env,
    });

    backendProcess.stdout.on('data', (data) => {
        console.log(`[Backend] ${data}`);
    });

    backendProcess.stderr.on('data', (data) => {
        console.error(`[Backend ERR] ${data}`);
    });

    backendProcess.on('close', (code) => {
        console.log(`[Backend] Exited with code ${code}`);
        backendProcess = null;
    });

    backendProcess.on('error', (err) => {
        console.error('[Backend] Failed to start:', err);
    });
}

/**
 * Poll the backend health endpoint until it responds.
 * Returns a promise that resolves when backend is ready.
 */
function waitForBackend(maxRetries = 60, intervalMs = 500) {
    return new Promise((resolve, reject) => {
        let attempts = 0;

        const check = () => {
            attempts++;
            const req = http.get(`${BACKEND_URL}/api/health`, (res) => {
                if (res.statusCode === 200) {
                    console.log(`[Backend] Ready after ${attempts} checks`);
                    resolve();
                } else {
                    retry();
                }
            });
            req.on('error', retry);
            req.setTimeout(2000, () => { req.destroy(); retry(); });
        };

        const retry = () => {
            if (attempts >= maxRetries) {
                reject(new Error('Backend failed to start after ' + maxRetries + ' attempts'));
            } else {
                setTimeout(check, intervalMs);
            }
        };

        check();
    });
}

function stopBackend() {
    if (backendProcess) {
        console.log('[Backend] Stopping...');
        backendProcess.kill();
        backendProcess = null;
    }
}

// IPC handlers for frontend communication
ipcMain.handle('get-backend-url', () => BACKEND_URL);

app.whenReady().then(async () => {
    startBackend();

    if (app.isPackaged) {
        // Wait for backend to become healthy before showing the window
        try {
            await waitForBackend();
        } catch (e) {
            console.error('[Backend]', e.message);
            // Show the window anyway — the frontend will show an error
        }
    }

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
