/**
 * AI Murder Mystery Game — Main Application Controller
 * Handles all screens, API communication, and game interactions.
 */

const API_BASE = 'http://127.0.0.1:8765';

// ── State ───────────────────────────────────────────────
let gameState = {
    selectedRole: null,
    currentScreen: 'title',
    talkingTo: null,
    isLoading: false,
};

// ── DOM References ──────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// Screens
const screens = {
    title: $('#screen-title'),
    setup: $('#screen-setup'),
    loading: $('#screen-loading'),
    game: $('#screen-game'),
    results: $('#screen-results'),
};

// ── API Helper ──────────────────────────────────────────
async function api(endpoint, method = 'GET', body = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);

    try {
        const res = await fetch(`${API_BASE}${endpoint}`, opts);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `API Error: ${res.status}`);
        }
        return await res.json();
    } catch (e) {
        console.error(`API ${method} ${endpoint} failed:`, e);
        throw e;
    }
}

// ── Screen Navigation ───────────────────────────────────
function showScreen(name) {
    Object.entries(screens).forEach(([key, el]) => {
        el.classList.remove('active');
        el.classList.add('hidden');
    });
    if (screens[name]) {
        screens[name].classList.remove('hidden');
        // Trigger reflow for animation
        void screens[name].offsetWidth;
        screens[name].classList.add('active');
    }
    gameState.currentScreen = name;
}

// ── Title Screen ────────────────────────────────────────
$('#btn-new-game').addEventListener('click', () => {
    showScreen('setup');
});

$('#btn-settings').addEventListener('click', async () => {
    $('#modal-settings').classList.remove('hidden');
    await loadSettingsIntoForm();
});

// ── Settings Modal ──────────────────────────────────────
let _modelSearchTimeout = null;
let _selectedModelId = '';
let _selectedProviders = [];
let _allKnownProviders = [];

function closeSettings() {
    $('#modal-settings').classList.add('hidden');
    $('#model-results').classList.add('hidden');
    $('#provider-results').classList.add('hidden');
}

$('#btn-close-settings').addEventListener('click', closeSettings);
$('#btn-close-settings-2').addEventListener('click', closeSettings);
$('#modal-settings .modal-backdrop').addEventListener('click', closeSettings);

// Range sliders — live value display
$('#input-temperature').addEventListener('input', (e) => {
    $('#temp-value').textContent = e.target.value;
});
$('#input-top-p').addEventListener('input', (e) => {
    $('#top-p-value').textContent = e.target.value;
});
$('#input-rep-penalty').addEventListener('input', (e) => {
    $('#rep-value').textContent = e.target.value;
});

// API key reveal toggle
$('#btn-reveal-key').addEventListener('click', () => {
    const input = $('#input-api-key');
    input.type = input.type === 'password' ? 'text' : 'password';
});

// Connection test
$('#btn-connect').addEventListener('click', async () => {
    const keyInput = $('#input-api-key');
    const key = keyInput.value.trim();
    if (!key) { alert('Enter an API key first.'); return; }

    $('#connection-text').textContent = 'Connecting...';
    try {
        const result = await api('/api/settings', 'POST', { api_key: key });
        updateConnectionStatus(result.connected);
    } catch (e) {
        updateConnectionStatus(false);
    }
});

function updateConnectionStatus(connected) {
    const dot = $('#connection-dot');
    const text = $('#connection-text');
    dot.classList.toggle('connected', connected);
    dot.classList.toggle('disconnected', !connected);
    text.textContent = connected ? 'Connected' : 'Not connected';
}

// Load current settings into the form
async function loadSettingsIntoForm() {
    try {
        const s = await api('/api/settings');
        // Connection
        if (s.api_key_set && !$('#input-api-key').value) {
            $('#input-api-key').value = '';
            $('#input-api-key').placeholder = s.api_key || 'sk-or-v1-...';
        }
        updateConnectionStatus(s.connected);

        // Model
        _selectedModelId = s.model || '';
        if (_selectedModelId) {
            $('#model-selected').classList.remove('hidden');
            $('#model-selected-name').textContent = _selectedModelId;
        } else {
            $('#model-selected').classList.add('hidden');
        }

        // Providers
        _selectedProviders = s.providers || [];
        renderProviderTags();

        // Generation
        $('#input-context-length').value = s.context_length || 8192;
        $('#input-response-length').value = s.response_length || 1024;

        // Load instruct presets
        const presets = await api('/api/instruct-presets');
        const select = $('#select-instruct');
        select.innerHTML = '';
        presets.presets.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            if (p.id === s.instruct_template) opt.selected = true;
            select.appendChild(opt);
        });

        // Samplers
        $('#input-temperature').value = s.temperature ?? 0.9;
        $('#temp-value').textContent = s.temperature ?? 0.9;
        $('#input-top-p').value = s.top_p ?? 0.95;
        $('#top-p-value').textContent = s.top_p ?? 0.95;
        $('#input-top-k').value = s.top_k ?? 40;
        $('#input-min-p').value = s.min_p ?? 0.05;
        $('#input-rep-penalty').value = s.repetition_penalty ?? 1.1;
        $('#rep-value').textContent = s.repetition_penalty ?? 1.1;
    } catch (e) {
        console.warn('Failed to load settings:', e);
    }
}

// ── Model Search ────────────────────────────────────────
$('#input-model-search').addEventListener('input', (e) => {
    const query = e.target.value.trim();
    clearTimeout(_modelSearchTimeout);
    if (query.length < 2) {
        $('#model-results').classList.add('hidden');
        return;
    }
    // Show loading
    const results = $('#model-results');
    results.innerHTML = '<div class="model-result-loading">Searching...</div>';
    results.classList.remove('hidden');

    _modelSearchTimeout = setTimeout(() => searchModels(query), 350);
});

$('#input-model-search').addEventListener('focus', (e) => {
    if (e.target.value.trim().length >= 2) {
        searchModels(e.target.value.trim());
    }
});

// Close model results on click outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.model-search-container')) {
        $('#model-results').classList.add('hidden');
    }
    if (!e.target.closest('.provider-container')) {
        $('#provider-results').classList.add('hidden');
    }
});

async function searchModels(query) {
    try {
        const data = await api(`/api/models/search?q=${encodeURIComponent(query)}`);
        const results = $('#model-results');

        if (data.models.length === 0) {
            results.innerHTML = '<div class="model-result-empty">No models found</div>';
            results.classList.remove('hidden');
            return;
        }

        // Collect providers for the provider search
        const providerSet = new Set(_allKnownProviders);
        data.models.forEach(m => { if (m.provider) providerSet.add(m.provider); });
        _allKnownProviders = [...providerSet].sort();

        results.innerHTML = data.models.map(m => {
            const isSelected = m.id === _selectedModelId;
            const ctxK = m.context_length >= 1000 ? `${Math.round(m.context_length / 1024)}k` : m.context_length;
            const price = m.prompt_price === 0 ? 'Free' : `$${m.prompt_price}/M tok`;
            return `
                <div class="model-result-item${isSelected ? ' selected' : ''}"
                     data-model-id="${m.id}" data-model-name="${m.name}" data-ctx="${m.context_length}">
                    <div class="model-result-name">${m.name}</div>
                    <div class="model-result-meta">${ctxK} ctx | ${price}</div>
                </div>
            `;
        }).join('');
        results.classList.remove('hidden');

        // Click handlers for model results
        results.querySelectorAll('.model-result-item').forEach(item => {
            item.addEventListener('click', () => {
                _selectedModelId = item.dataset.modelId;
                $('#model-selected').classList.remove('hidden');
                $('#model-selected-name').textContent = `${item.dataset.modelName}`;
                $('#input-model-search').value = '';
                results.classList.add('hidden');

                // Auto-set context length from model
                const ctx = parseInt(item.dataset.ctx);
                if (ctx > 0) {
                    $('#input-context-length').value = ctx;
                }
            });
        });
    } catch (e) {
        $('#model-results').innerHTML = '<div class="model-result-empty">Search failed</div>';
    }
}

// Clear selected model
$('#btn-clear-model').addEventListener('click', () => {
    _selectedModelId = '';
    $('#model-selected').classList.add('hidden');
    $('#model-selected-name').textContent = '';
});

// ── Provider Tags ───────────────────────────────────────
function renderProviderTags() {
    const container = $('#provider-tags');
    container.innerHTML = _selectedProviders.map(p => `
        <span class="provider-tag">
            <button class="provider-tag-remove" data-provider="${p}">✕</button>
            ${p}
        </span>
    `).join('');

    container.querySelectorAll('.provider-tag-remove').forEach(btn => {
        btn.addEventListener('click', () => {
            _selectedProviders = _selectedProviders.filter(x => x !== btn.dataset.provider);
            renderProviderTags();
        });
    });
}

$('#input-provider-search').addEventListener('input', (e) => {
    const query = e.target.value.trim().toLowerCase();
    const results = $('#provider-results');

    if (!query) {
        results.classList.add('hidden');
        return;
    }

    // Filter known providers
    const filtered = _allKnownProviders
        .filter(p => p.toLowerCase().includes(query) && !_selectedProviders.includes(p));

    if (filtered.length === 0) {
        results.classList.add('hidden');
        return;
    }

    results.innerHTML = filtered.slice(0, 15).map(p => `
        <div class="provider-result-item" data-provider="${p}">${p}</div>
    `).join('');
    results.classList.remove('hidden');

    results.querySelectorAll('.provider-result-item').forEach(item => {
        item.addEventListener('click', () => {
            _selectedProviders.push(item.dataset.provider);
            renderProviderTags();
            $('#input-provider-search').value = '';
            results.classList.add('hidden');
        });
    });
});

// ── Save Settings ───────────────────────────────────────
$('#btn-save-settings').addEventListener('click', async () => {
    const payload = {};

    // API key — only send if user typed a new one
    const keyInput = $('#input-api-key');
    if (keyInput.value.trim()) {
        payload.api_key = keyInput.value.trim();
    }

    // Model
    if (_selectedModelId) {
        payload.model = _selectedModelId;
    }

    // Providers
    payload.providers = _selectedProviders;

    // Generation
    payload.instruct_template = $('#select-instruct').value;
    payload.context_length = parseInt($('#input-context-length').value) || 8192;
    payload.response_length = parseInt($('#input-response-length').value) || 1024;

    // Samplers
    payload.temperature = parseFloat($('#input-temperature').value);
    payload.top_p = parseFloat($('#input-top-p').value);
    payload.top_k = parseInt($('#input-top-k').value) || 0;
    payload.min_p = parseFloat($('#input-min-p').value) || 0;
    payload.repetition_penalty = parseFloat($('#input-rep-penalty').value);

    try {
        const result = await api('/api/settings', 'POST', payload);
        updateConnectionStatus(result.connected);
        closeSettings();
    } catch (e) {
        alert('Failed to save settings: ' + e.message);
    }
});


// ── Setup Screen ────────────────────────────────────────
$$('.role-card').forEach((card) => {
    card.addEventListener('click', () => {
        $$('.role-card').forEach((c) => c.classList.remove('selected'));
        card.classList.add('selected');
        gameState.selectedRole = card.dataset.role;

        // Update default name based on role
        const nameInput = $('#input-player-name');
        if (gameState.selectedRole === 'detective') {
            nameInput.value = 'Detective Gray';
        } else {
            nameInput.value = 'The Stranger';
        }

        // Show player setup
        $('#player-setup').classList.remove('hidden');
    });
});

$('#btn-start-game').addEventListener('click', async () => {
    if (!gameState.selectedRole) return;

    const name = $('#input-player-name').value.trim() || 'The Player';
    const desc = $('#input-player-desc').value.trim();

    // Show loading
    $('.btn-text').classList.add('hidden');
    $('.btn-loading').classList.remove('hidden');
    $('#btn-start-game').disabled = true;

    try {
        // Step 1: Create game
        showScreen('loading');
        updateLoading('Assembling the cast...', 'Selecting characters for your mystery...');

        await api('/api/game/new', 'POST', {
            player_role: gameState.selectedRole,
            player_name: name,
            player_description: desc,
        });

        // Step 2: Generate scenario
        updateLoading('Crafting the Mystery', 'The AI is weaving a web of intrigue and deception...');

        const scenario = await api('/api/game/generate-scenario', 'POST');

        // Step 3: Transition to game
        updateLoading('Setting the Stage', 'Placing characters and hiding clues...');
        await sleep(800);

        // Initialize game screen
        initGameScreen(scenario);

        // Show opening narration
        showScreen('game');
        addMessage('system', scenario.opening_narration || `Welcome to "${scenario.title}". The investigation begins.`);

    } catch (e) {
        alert('Failed to start game: ' + e.message);
        showScreen('setup');
    } finally {
        $('.btn-text').classList.remove('hidden');
        $('.btn-loading').classList.add('hidden');
        $('#btn-start-game').disabled = false;
    }
});

// ── Loading Screen ──────────────────────────────────────
function updateLoading(title, text) {
    $('#loading-title').textContent = title;
    $('#loading-text').textContent = text;
}

// ── Game Screen ─────────────────────────────────────────
function initGameScreen(scenario) {
    $('#scenario-title').textContent = scenario.title || 'Murder Mystery';
    refreshGameState();
}

async function refreshGameState() {
    try {
        const state = await api('/api/state');
        updateSidebars(state);
    } catch (e) {
        console.error('Failed to refresh state:', e);
    }
}

function updateSidebars(state) {
    if (!state || state.state === 'no_session') return;

    // Current location
    if (state.current_location) {
        $('#location-name').textContent = state.current_location.name;
        $('#location-desc').textContent = state.current_location.description || '';
    }

    // Adjacent locations
    const locList = $('#location-list');
    locList.innerHTML = '';
    if (state.adjacent_locations) {
        state.adjacent_locations.forEach((loc) => {
            const btn = document.createElement('button');
            btn.className = 'location-btn';
            // Count characters at this location
            const locData = state.all_locations?.find(l => l.id === loc.id);
            const charCount = locData?.characters?.length || 0;
            btn.innerHTML = `
                <span>${loc.name}</span>
                ${charCount > 0 ? `<span class="char-count">${charCount} 👤</span>` : ''}
            `;
            btn.addEventListener('click', () => handleMove(loc.id));
            locList.appendChild(btn);
        });
    }

    // Characters here
    const charList = $('#characters-here');
    charList.innerHTML = '';
    if (state.characters_here) {
        state.characters_here.forEach((char) => {
            const chip = document.createElement('div');
            chip.className = `character-chip${char.is_player ? ' is-player' : ''}`;
            const initial = char.name.charAt(0).toUpperCase();
            chip.innerHTML = `
                <span class="char-avatar">${initial}</span>
                <span>${char.name}${char.is_player ? ' (You)' : ''}</span>
            `;
            if (!char.is_player) {
                chip.addEventListener('click', () => {
                    gameState.talkingTo = char.name;
                    $('#input-message').placeholder = `Say something to ${char.name}...`;
                    $('#input-message').focus();
                    $('#btn-send').disabled = false;
                    addMessage('event', `You approach ${char.name}.`);
                });
            }
            charList.appendChild(chip);
        });
    }

    // Turn counter
    $('#turn-counter').textContent = `${state.turn || 0} / ${state.max_turns || 30}`;

    // Clues
    if (state.clues) {
        $('#clue-counter').textContent = `${state.clues.discovered} / ${state.clues.total}`;
        updateClueJournal(state.clues.list || []);
    }

    // Populate accusation suspect list
    if (state.npcs) {
        const select = $('#select-suspect');
        select.innerHTML = '';
        state.npcs.forEach((npc) => {
            const option = document.createElement('option');
            option.value = npc.name;
            option.textContent = npc.name;
            select.appendChild(option);
        });
    }
}

function updateClueJournal(clues) {
    const journal = $('#clue-journal');
    if (clues.length === 0) {
        journal.innerHTML = '<p class="journal-empty">No clues discovered yet. Start investigating!</p>';
        return;
    }

    journal.innerHTML = '';
    clues.forEach((clue) => {
        const entry = document.createElement('div');
        entry.className = 'clue-entry';
        entry.dataset.difficulty = clue.difficulty;
        entry.innerHTML = `
            <div>${clue.description}</div>
            <div class="clue-turn">Turn ${clue.discovered_at_turn}</div>
        `;
        journal.appendChild(entry);
    });
}

// ── Messages ────────────────────────────────────────────
function addMessage(type, content, sender = '') {
    const panel = $('#dialogue-messages');
    const msg = document.createElement('div');
    msg.className = `message message-${type}`;

    if (sender) {
        msg.innerHTML = `<div class="message-sender">${sender}</div><div>${formatContent(content)}</div>`;
    } else {
        msg.innerHTML = formatContent(content);
    }

    panel.appendChild(msg);
    panel.scrollTop = panel.scrollHeight;
}

function formatContent(text) {
    if (!text) return '';
    // Basic markdown-like formatting
    return text
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/🔍/g, '🔍')
        .replace(/\n/g, '<br>');
}

function addEventToLog(event) {
    const log = $('#event-log');
    const empty = log.querySelector('.log-empty');
    if (empty) empty.remove();

    const entry = document.createElement('div');
    entry.className = `event-entry${event.visible ? ' visible' : ''}`;
    entry.textContent = event.description;
    log.prepend(entry);

    // Keep max 50 entries
    while (log.children.length > 50) {
        log.removeChild(log.lastChild);
    }
}

// ── Player Actions ──────────────────────────────────────
async function handleMove(locationId) {
    if (gameState.isLoading) return;
    gameState.isLoading = true;
    gameState.talkingTo = null;
    $('#btn-send').disabled = true;
    $('#input-message').placeholder = 'Say something to the NPC...';

    try {
        addMessage('event', 'Moving...');
        const result = await api('/api/game/move', 'POST', { location_id: locationId });
        addMessage('system', result.response);

        // Add events
        if (result.events) {
            result.events.forEach((e) => {
                if (e.visible) addMessage('event', e.description);
                addEventToLog(e);
            });
        }

        updateSidebars(result.state);
    } catch (e) {
        addMessage('event', 'Failed to move: ' + e.message);
    }
    gameState.isLoading = false;
}

$('#btn-send').addEventListener('click', handleSendMessage);
$('#input-message').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
    }
});

async function handleSendMessage() {
    if (gameState.isLoading || !gameState.talkingTo) return;
    const input = $('#input-message');
    const message = input.value.trim();
    if (!message) return;

    gameState.isLoading = true;
    input.value = '';

    addMessage('player', message, 'You');

    try {
        const result = await api('/api/game/talk', 'POST', {
            npc_name: gameState.talkingTo,
            message,
        });

        addMessage('npc', result.response, gameState.talkingTo);

        // Process events
        if (result.events) {
            result.events.forEach((e) => {
                if (e.visible) addMessage('event', e.description);
                addEventToLog(e);
            });
        }

        updateSidebars(result.state);

        // Check for game over
        if (result.state?.state === 'results') {
            showResults(result.state);
        }
    } catch (e) {
        addMessage('event', 'Communication error: ' + e.message);
    }
    gameState.isLoading = false;
}

$('#btn-investigate').addEventListener('click', async () => {
    if (gameState.isLoading) return;
    gameState.isLoading = true;

    try {
        addMessage('event', 'You search the area carefully...');
        const result = await api('/api/game/investigate', 'POST');
        addMessage('system', result.response);

        if (result.events) {
            result.events.forEach((e) => {
                if (e.visible) addMessage('event', e.description);
                addEventToLog(e);
            });
        }

        updateSidebars(result.state);
    } catch (e) {
        addMessage('event', 'Investigation failed: ' + e.message);
    }
    gameState.isLoading = false;
});

$('#btn-wait').addEventListener('click', async () => {
    if (gameState.isLoading) return;
    gameState.isLoading = true;

    try {
        const result = await api('/api/game/wait', 'POST');
        addMessage('system', result.response);

        if (result.events) {
            result.events.forEach((e) => {
                if (e.visible) addMessage('event', e.description);
                addEventToLog(e);
            });
        }

        updateSidebars(result.state);
    } catch (e) {
        addMessage('event', 'Error: ' + e.message);
    }
    gameState.isLoading = false;
});

// ── Accusation ──────────────────────────────────────────
$('#btn-accuse').addEventListener('click', () => {
    $('#modal-accuse').classList.remove('hidden');
});
$('#btn-cancel-accuse').addEventListener('click', () => {
    $('#modal-accuse').classList.add('hidden');
});
$('#modal-accuse .modal-backdrop').addEventListener('click', () => {
    $('#modal-accuse').classList.add('hidden');
});

$('#btn-confirm-accuse').addEventListener('click', async () => {
    const suspect = $('#select-suspect').value;
    const reasoning = $('#input-reasoning').value.trim();

    if (!suspect) return;

    $('#modal-accuse').classList.add('hidden');
    gameState.isLoading = true;

    showScreen('loading');
    updateLoading('The Moment of Truth', 'Revealing the outcome...');

    try {
        const result = await api('/api/game/accuse', 'POST', {
            suspect_name: suspect,
            reasoning,
        });

        showResults(result);
    } catch (e) {
        alert('Accusation error: ' + e.message);
        showScreen('game');
    }
    gameState.isLoading = false;
});

// ── Results Screen ──────────────────────────────────────
function showResults(result) {
    showScreen('results');

    const isWin = result.result === 'detective_wins' || result.outcome === 'correct';

    $('#results-icon').textContent = isWin ? '🏆' : '💀';
    $('#results-title').textContent = isWin ? 'Case Solved!' : 'Case Unsolved';

    if (result.narrative_ending) {
        $('#results-narrative').textContent = result.narrative_ending;
    } else {
        $('#results-narrative').textContent = `You accused ${result.accused}. The real killer was ${result.actual_killer}.`;
    }

    const statsHtml = `
        <div class="stat-item">
            <div class="stat-value">${result.turns_taken || '?'}</div>
            <div class="stat-label">Turns</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${result.clues_found || 0}/${result.total_clues || '?'}</div>
            <div class="stat-label">Clues Found</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${isWin ? '✓' : '✗'}</div>
            <div class="stat-label">Verdict</div>
        </div>
    `;
    $('#results-stats').innerHTML = statsHtml;
}

$('#btn-play-again').addEventListener('click', () => {
    // Reset everything
    gameState = { selectedRole: null, currentScreen: 'title', talkingTo: null, isLoading: false };
    $('#dialogue-messages').innerHTML = '';
    $('#event-log').innerHTML = '<p class="log-empty">The investigation begins...</p>';
    $$('.role-card').forEach((c) => c.classList.remove('selected'));
    $('#player-setup').classList.add('hidden');
    showScreen('title');
});

// ── Utilities ───────────────────────────────────────────
function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Initialize ──────────────────────────────────────────
async function init() {
    // Check backend health
    try {
        const health = await api('/api/health');
        console.log('Backend connected:', health);
    } catch (e) {
        console.warn('Backend not available yet. Start the backend server first.');
    }
}

init();
