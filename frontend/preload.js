/**
 * Preload script — secure bridge between Electron main process and renderer.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
});
