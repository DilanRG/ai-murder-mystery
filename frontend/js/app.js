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

$('#btn-settings').addEventListener('click', () => {
    $('#modal-settings').classList.remove('hidden');
});

// ── Settings Modal ──────────────────────────────────────
$('#btn-close-settings').addEventListener('click', () => {
    $('#modal-settings').classList.add('hidden');
});
$('#modal-settings .modal-backdrop').addEventListener('click', () => {
    $('#modal-settings').classList.add('hidden');
});

$('#input-temperature').addEventListener('input', (e) => {
    $('#temp-value').textContent = e.target.value;
});

$('#btn-save-settings').addEventListener('click', async () => {
    const apiKey = $('#input-api-key').value.trim();
    const model = $('#input-model').value;
    const temperature = parseFloat($('#input-temperature').value);

    try {
        await api('/api/settings', 'POST', {
            api_key: apiKey || undefined,
            model: model || undefined,
            temperature,
        });
        $('#modal-settings').classList.add('hidden');
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
