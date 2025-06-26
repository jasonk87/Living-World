document.addEventListener('DOMContentLoaded', () => {
    const gameMapDiv = document.getElementById('game-map');
    const entityDetailsDiv = document.getElementById('entity-details');
    const eventLogDiv = document.getElementById('event-log');
    const gameStatusDiv = document.getElementById('game-status');
    const pauseButton = document.getElementById('pause-button');
    const toggleDetailsButton = document.getElementById('toggle-details-button');

    let API_BASE_URL = 'http://localhost:8000';
    let showEntityDetails = false; // Controlled by toggle button

    async function fetchGameState() {
        try {
            const response = await fetch(`${API_BASE_URL}/game_state`);
            if (!response.ok) {
                console.error(`HTTP error! status: ${response.status}`);
                gameStatusDiv.textContent = `Error fetching game state: ${response.status}`;
                return null;
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching game state:', error);
            gameStatusDiv.textContent = 'Failed to connect to game server.';
            return null;
        }
    }

    function renderMap(gameState) {
        if (!gameMapDiv || !gameState || !gameState.grid) {
            console.error("Map div or game state for map rendering not found/valid.");
            return;
        }
        gameMapDiv.innerHTML = ''; // Clear previous map
        gameMapDiv.style.gridTemplateColumns = `repeat(${gameState.grid_size[1]}, 1fr)`;

        gameState.grid.forEach((row, r_idx) => {
            row.forEach((tile, c_idx) => {
                const cell = document.createElement('div');
                cell.classList.add('map-cell');
                cell.textContent = tile[0]; // Display first letter of tile type
                cell.title = tile; // Show full tile type on hover
                cell.dataset.x = c_idx;
                cell.dataset.y = r_idx;
                gameMapDiv.appendChild(cell);
            });
        });

        if (gameState.characters) {
            gameState.characters.forEach(char => {
                const cellIndex = char.y * gameState.grid_size[1] + char.x;
                const cellDiv = gameMapDiv.children[cellIndex];
                if (cellDiv) {
                    const charMarker = document.createElement('span');
                    charMarker.textContent = char.name[0];
                    charMarker.title = `${char.name} (${char.job})`;
                    charMarker.style.fontWeight = 'bold';
                    charMarker.style.color = char.is_sick ? 'orange' : (char.is_injured ? 'red' : 'blue');
                     // Make character marker clickable for details
                    charMarker.addEventListener('click', (e) => {
                        e.stopPropagation(); // Prevent map cell click if any
                        displayEntityDetails(char, 'character');
                    });
                    cellDiv.innerHTML = ''; // Clear tile text
                    cellDiv.appendChild(charMarker);
                }
            });
        }
    }

    function updateEventLog(gameState) {
        if (!eventLogDiv || !gameState || !gameState.event_log) return;
        eventLogDiv.innerHTML = '';
        // Display latest events first
        gameState.event_log.slice().reverse().forEach(logEntry => {
            const p = document.createElement('p');
            p.textContent = logEntry;
            eventLogDiv.appendChild(p);
        });
    }

    function updateGameInfo(gameState) {
        if (!gameStatusDiv || !gameState) return;
        let electionText = gameState.days_until_election >= 0 ? `Election in: ${gameState.days_until_election} days` : "Election TBD";
        gameStatusDiv.innerHTML = `
            Day: ${gameState.day}, Tick: ${gameState.tick}/${gameState.ticks_per_day}<br>
            Season: ${gameState.season}, Weather: ${gameState.weather}<br>
            Status: ${gameState.is_paused ? "Paused" : "Running"}<br>
            ${electionText}
        `;
        pauseButton.textContent = gameState.is_paused ? "Resume" : "Pause";
    }

    function displayEntityDetails(entity, type) {
        if (!showEntityDetails) {
            entityDetailsDiv.innerHTML = '<p><em>Entity details are currently hidden. Click "Toggle Entity Details" to show.</em></p>';
            return;
        }
        if (!entityDetailsDiv) return;
        let detailsHtml = `<h4>Details: ${entity.name} (${type})</h4>`;
        if (type === 'character') {
            detailsHtml += `<ul>
                <li>Position: (${entity.x}, ${entity.y})</li>
                <li>Job: ${entity.job || 'N/A'}</li>
                <li>Goal: ${entity.goal || 'N/A'}</li>
                <li>Inventory Load: ${entity.inventory_load !== undefined ? entity.inventory_load : 'N/A'}</li>
                <li>Sick: ${entity.is_sick ? 'Yes' : 'No'}</li>
                <li>Injured: ${entity.is_injured ? 'Yes' : 'No'}</li>
            </ul>`;
            // In future, could fetch full details: /character_details?name=${entity.name}
        } else if (type === 'tile') { // Basic tile info
             detailsHtml += `<p>Tile Type: ${entity.tileType}</p><p>Coordinates: (${entity.x}, ${entity.y})</p>`;
        }
        // Add more types like 'building' later
        entityDetailsDiv.innerHTML = detailsHtml;
    }


    async function togglePause() {
        try {
            const response = await fetch(`${API_BASE_URL}/toggle_pause`, { method: 'POST' }); // POST is often better for actions
            if (!response.ok) {
                console.error(`HTTP error! status: ${response.status}`);
                return;
            }
            const data = await response.json();
            game_paused = data.paused; // Update local state if needed, though /game_state will also update it
            pauseButton.textContent = game_paused ? "Resume" : "Pause";
            updateUI(); // Refresh UI immediately to show change
        } catch (error) {
            console.error('Error toggling pause:', error);
        }
    }

    toggleDetailsButton.addEventListener('click', () => {
        showEntityDetails = !showEntityDetails;
        toggleDetailsButton.textContent = `Toggle Entity Details (${showEntityDetails ? 'On' : 'Off'})`;
        if (!showEntityDetails) {
            entityDetailsDiv.innerHTML = '<p><em>Entity details are hidden. Click button above to show.</em></p>';
        } else {
            entityDetailsDiv.innerHTML = '<p>Click on a character/building on the map for details.</p>';
        }
    });

    gameMapDiv.addEventListener('click', (event) => {
        const cell = event.target.closest('.map-cell');
        if (cell && cell.dataset.x && cell.dataset.y) {
            // If cell contains a character marker, that click is handled by charMarker's listener
            // This handles clicks on empty cells or cells with just tile info
            if (!event.target.closest('span')) { // Check if the click was not on a character span
                 displayEntityDetails({ name: `Tile (${cell.dataset.x},${cell.dataset.y})`, x: cell.dataset.x, y: cell.dataset.y, tileType: cell.title }, 'tile');
            }
        }
    });


    async function updateUI() {
        const gameState = await fetchGameState();
        if (gameState) {
            renderMap(gameState);
            updateEventLog(gameState);
            updateGameInfo(gameState);
        }
    }

    if (pauseButton) {
        pauseButton.addEventListener('click', togglePause);
    }

    // Initial UI update and start interval
    updateUI();
    setInterval(updateUI, 2000); // Refresh every 2 seconds

    // Hide entity details by default
    entityDetailsDiv.innerHTML = '<p><em>Entity details are hidden. Click "Toggle Entity Details" to show.</em></p>';
});
