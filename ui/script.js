document.addEventListener('DOMContentLoaded', () => {
    // --- Element Selectors ---
    const gameStatusHeader = document.getElementById('game-status-header');
    const gameMapDiv = document.getElementById('game-map');
    const entityDetailsDiv = document.getElementById('entity-details');
    const eventLogDiv = document.getElementById('event-log');
    const pauseButton = document.getElementById('pause-button');
    const speedButtons = document.querySelectorAll('.speed-button');
    const tabs = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    // --- API & State ---
    const API_BASE_URL = 'http://localhost:8000';
    let isFetchingGameState = false;

    // --- Tab Switching Logic ---
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Deactivate all tabs and content
            tabs.forEach(item => item.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Activate the clicked tab and its content
            tab.classList.add('active');
            const targetContent = document.getElementById(tab.dataset.tab);
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });

    // --- API Calls ---
    async function fetchGameState() {
        if (isFetchingGameState) return null;
        isFetchingGameState = true;
        try {
            const response = await fetch(`${API_BASE_URL}/game_state`);
            if (!response.ok) {
                console.error(`HTTP error! status: ${response.status}`);
                if (gameStatusHeader) gameStatusHeader.innerHTML = `<span class="error">Error: ${response.status}</span>`;
                return null;
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching game state:', error);
            if (gameStatusHeader) gameStatusHeader.innerHTML = `<span class="error">Connection Failed</span>`;
            return null;
        } finally {
            isFetchingGameState = false;
        }
    }


    async function performControlAction(url) {
        try {
            await fetch(url, { method: 'POST' });
            updateUI(); // Refresh UI immediately after action
        } catch (error) {
            console.error('Error performing control action:', error);
        }
    }

    // --- Rendering Functions ---
    function renderMap(gameState) {
        if (!gameMapDiv || !gameState || !gameState.grid) return;

        gameMapDiv.innerHTML = '';
        gameMapDiv.style.gridTemplateColumns = `repeat(${gameState.grid_size[1]}, 1fr)`;
        gameMapDiv.style.gridTemplateRows = `repeat(${gameState.grid_size[0]}, 1fr)`;

        // Render base tiles
        for (let r = 0; r < gameState.grid_size[0]; r++) {
            for (let c = 0; c < gameState.grid_size[1]; c++) {
                const cell = document.createElement('div');
                cell.classList.add('map-cell');
                const tileType = gameState.grid[r][c];
                cell.classList.add(`tile-${tileType.replace(/\s+/g, '-') || 'Unknown'}`);
                cell.title = `${tileType} (${c}, ${r})`;
                gameMapDiv.appendChild(cell);
            }
        }

        // Render buildings on top of tiles
        (gameState.buildings || []).forEach(b => {
            for (let r_offset = 0; r_offset < b.height; r_offset++) {
                for (let c_offset = 0; c_offset < b.width; c_offset++) {
                    const cellX = b.x + c_offset;
                    const cellY = b.y + r_offset;
                    const cellIndex = cellY * gameState.grid_size[1] + cellX;
                    const cellDiv = gameMapDiv.children[cellIndex];
                    if (cellDiv) {
                        cellDiv.className = 'map-cell'; // Reset classes
                        const typeClass = b.structure_type === "Stockpile" ? 'stockpile-cell' : 'building-cell';
                        cellDiv.classList.add(typeClass);
                        cellDiv.title = `${b.display_name} (${b.structure_type})`;
                        cellDiv.addEventListener('click', () => fetchEntityDetails('building', {x: cellX, y: cellY}));
                    }
                }
            }
        });

        // Render characters as circles on top of everything
        (gameState.characters || []).forEach(char => {
            const cellIndex = char.y * gameState.grid_size[1] + char.x;
            const cellDiv = gameMapDiv.children[cellIndex];
            if (cellDiv) {
                const charMarker = document.createElement('div');
                charMarker.classList.add('char-marker');
                charMarker.title = `${char.name} (${char.job})`;
                if (char.is_sick) charMarker.style.backgroundColor = 'orange';
                if (char.is_injured) charMarker.style.borderColor = 'red';

                charMarker.addEventListener('click', (e) => {
                    e.stopPropagation(); // Prevent tile click
                    fetchEntityDetails('character', char.name, 'entity-details');
                });
                cellDiv.appendChild(charMarker);
            }
        });
    }


    function updateEventLog(log) {
        if (!eventLogDiv || !log) return;
        eventLogDiv.innerHTML = log.slice().reverse().map(entry => `<p>${entry}</p>`).join('');
    }

    function updateGameInfo(gameState) {
        if (!gameStatusHeader || !gameState) return;
        gameStatusHeader.innerHTML = `
            <span>Day: ${gameState.day}, ${gameState.season}</span> |
            <span>Status: ${gameState.is_paused ? "Paused" : "Running"}</span> |
            <span>Speed: ${gameState.current_speed_multiplier}x</span>
        `;
        pauseButton.textContent = gameState.is_paused ? "Resume" : "Pause";
    }

    function renderCharacterList(characters) {
        const characterListDiv = document.getElementById('character-list');
        const characterDetailsPanel = document.getElementById('character-details-panel');
        if (!characterListDiv || !characters) return;

        // Sort characters alphabetically
        const sortedCharacters = [...characters].sort((a, b) => a.name.localeCompare(b.name));

        characterListDiv.innerHTML = '<ul>' + sortedCharacters.map(char => `
            <li data-char-name="${char.name}">
                <strong>${char.name}</strong><br>
                <small>${char.job} | Goal: ${char.current_goal ? char.current_goal.type : 'None'}</small>
            </li>
        `).join('') + '</ul>';

        // Add event listeners
        characterListDiv.querySelectorAll('li').forEach(li => {
            li.addEventListener('click', () => {
                // Remove active class from any previously selected character
                characterListDiv.querySelectorAll('li').forEach(item => item.classList.remove('active'));
                // Add active class to the clicked character
                li.classList.add('active');
                fetchEntityDetails('character', li.dataset.charName, 'character-details-panel');
            });
        });
    }

    async function fetchEntityDetails(type, identifier, targetPanelId) {
        const targetPanel = document.getElementById(targetPanelId || 'entity-details');
        if (!targetPanel) return;

        targetPanel.innerHTML = `<p>Loading details...</p>`;
        let url = '';
        if (type === 'character') {
            url = `${API_BASE_URL}/character_info?name=${encodeURIComponent(identifier)}`;
        } else if (type === 'building') {
            url = `${API_BASE_URL}/building_info?x=${identifier.x}&y=${identifier.y}`;
        } else {
            targetPanel.innerHTML = `<p>Unknown entity type.</p>`;
            return;
        }

        try {
            const response = await fetch(url);
            if (!response.ok) {
                targetPanel.innerHTML = `<p class="error">Error fetching details: ${response.status}</p>`;
                return;
            }
            const details = await response.json();
            console.log("Received entity details:", details);
            displayEntityDetails(details, type, targetPanelId);
        } catch (error) {
            console.error(`Error fetching ${type} details:`, error);
            targetPanel.innerHTML = `<p class="error">Failed to fetch details.</p>`;
        }
    }

    function displayEntityDetails(entity, type, targetPanelId) {
        const targetPanel = document.getElementById(targetPanelId || 'entity-details');
        if (!targetPanel) return;

        targetPanel.innerHTML = '';
        const dl = document.createElement('dl');

        if (type === 'character') {
            let skillsHtml = '<ul>';
            for (const [skill, data] of Object.entries(entity.skills)) {
                skillsHtml += `<li>${skill}: ${data.level}</li>`;
            }
            skillsHtml += '</ul>';

            let needsHtml = '<ul>';
            for (const [need, value] of Object.entries(entity.needs)) {
                needsHtml += `<li>${need}: ${value}</li>`;
            }
            needsHtml += '</ul>';

            dl.innerHTML = `
                <h3>${entity.name}</h3>
                <dt>Job</dt><dd>${entity.job} (${entity.rank})</dd>
                <dt>Money</dt><dd>${entity.money} coins</dd>
                <dt>Goal</dt><dd>${entity.current_goal.type} (Prio: ${entity.current_goal.priority})</dd>
                <dt>Goal Status</dt><dd>${entity.current_goal.status}</dd>
                <dt>Health</dt><dd>Sick: ${entity.is_sick ? `Yes (Sev: ${entity.sickness_severity})` : 'No'}, Injured: ${entity.is_injured ? `Yes (Sev: ${entity.injury_severity})` : 'No'}</dd>
                <hr>
                <dt>Needs</dt><dd>${needsHtml}</dd>
                <hr>
                <dt>Skills</dt><dd>${skillsHtml}</dd>
                <hr>
                <dt>Inventory</dt><dd>${Object.keys(entity.inventory).length > 0 ? JSON.stringify(entity.inventory) : 'Empty'}</dd>
            `;
        } else if (type === 'building') {
            dl.innerHTML = `
                <h3>${entity.display_name}</h3>
                <dt>Type</dt><dd>${entity.structure_type}</dd>
                <dt>Operational</dt><dd>${entity.is_operational}</dd>
                ${entity.inventory ? `<dt>Inventory</dt><dd>${JSON.stringify(entity.inventory)}</dd>` : ''}
            `;
        }
        targetPanel.appendChild(dl);
    }

    async function updateUI() {
        const gameState = await fetchGameState();
        if (gameState) {
            renderMap(gameState);
            updateEventLog(gameState.event_log);
            updateGameInfo(gameState);
            renderCharacterList(gameState.characters);
        }
    }

    // --- Event Listeners ---
    pauseButton.addEventListener('click', () => performControlAction(`${API_BASE_URL}/toggle_pause`));
    speedButtons.forEach(button => {
        button.addEventListener('click', () => {
            performControlAction(`${API_BASE_URL}/set_speed?multiplier=${button.dataset.speed}`);
        });
    });

    // --- Initial Load & Interval ---
    updateUI();
    setInterval(updateUI, 2000);
});
