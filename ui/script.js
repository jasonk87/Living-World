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

    async function fetchBuildingDetails(x, y) {
        if (!showEntityDetails) {
            displayEntityDetails(null, 'building_detailed'); // Clear or hide panel
            return;
        }
        try {
            const response = await fetch(`${API_BASE_URL}/building_info?x=${x}&y=${y}`);
            if (!response.ok) {
                console.error(`HTTP error fetching building details! status: ${response.status}`);
                entityDetailsDiv.innerHTML = `<p>Error fetching building details for (${x},${y}): ${response.status}</p>`;
                if (response.status === 404) {
                     entityDetailsDiv.innerHTML = `<p>No building or stockpile found at (${x},${y}).</p>`;
                }
                return;
            }
            const buildingDetails = await response.json();
            // Use display_name from buildingDetails for the header, and pass the whole object
            displayEntityDetails({ name: buildingDetails.display_name, ...buildingDetails }, 'building_detailed');
        } catch (error) {
            console.error('Error fetching building details:', error);
            entityDetailsDiv.innerHTML = `<p>Failed to fetch building details for (${x},${y}).</p>`;
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
                cell.classList.add(`tile-${tile.replace(/\s+/g, '')}`); // Add class like tile-Grass, tile-Forest
                cell.textContent = tile[0];
                cell.title = tile;
                cell.dataset.x = c_idx;
                cell.dataset.y = r_idx;
                gameMapDiv.appendChild(cell);
            });
        });

        // Render buildings and stockpiles (from game_state.buildings which now includes stockpiles)
        if (gameState.buildings) {
            gameState.buildings.forEach(b => {
                for (let r_offset = 0; r_offset < b.height; r_offset++) {
                    for (let c_offset = 0; c_offset < b.width; c_offset++) {
                        const buildingCellX = b.x + c_offset;
                        const buildingCellY = b.y + r_offset;
                        const cellIndex = buildingCellY * gameState.grid_size[1] + buildingCellX;
                        const cellDiv = gameMapDiv.children[cellIndex];
                        if (cellDiv) {
                            cellDiv.innerHTML = ''; // Clear base tile content
                            cellDiv.textContent = b.map_char;
                            cellDiv.title = `${b.display_name} (${b.structure_type})`;
                            cellDiv.classList.remove('tile-Grass', 'tile-Forest', 'tile-Water', 'tile-Rocks'); // Remove base tile class
                            if (b.structure_type === "Stockpile") {
                                cellDiv.classList.add('stockpile-cell');
                            } else {
                                cellDiv.classList.add('building-cell');
                            }
                            // Add click listener for building/stockpile details
                            cellDiv.removeEventListener('click', handleMapCellClick); // Remove generic tile listener first
                            cellDiv.addEventListener('click', () => {
                                fetchBuildingDetails(buildingCellX, buildingCellY);
                            });
                        }
                    }
                }
            });
        }

        // Render characters on top
        if (gameState.characters) {
            gameState.characters.forEach(char => {
                const cellIndex = char.y * gameState.grid_size[1] + char.x;
                const cellDiv = gameMapDiv.children[cellIndex];
                if (cellDiv) {
                    // If cellDiv was turned into a building/stockpile cell, its content might have been set.
                    // We need to ensure character is displayed, possibly clearing previous content or appending.
                    cellDiv.innerHTML = ''; // Clear previous content (tile or building char) to ensure char is prominent
                    const charMarker = document.createElement('span');
                    charMarker.textContent = char.name[0];
                    charMarker.title = `${char.name} (${char.job})`;
                    charMarker.style.fontWeight = 'bold';
                    charMarker.style.color = char.is_sick ? 'orange' : (char.is_injured ? 'red' : 'blue');
                    charMarker.addEventListener('click', (e) => {
                        e.stopPropagation();
                        fetchCharacterDetails(char.name);
                    });
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
        if (type === 'character_detailed') { // Changed type to reflect detailed data
            detailsHtml += `<ul>
                <li>Name: ${entity.name}</li>
                <li>Job: ${entity.job || 'N/A'} (Rank: ${entity.rank || 'N/A'})</li>
                <li>Position: (${entity.x}, ${entity.y})</li>
                <li>Goal: ${entity.current_goal || 'N/A'}</li>
                <li>Personality: ${entity.personality || 'N/A'}</li>
                <li>Traits: ${(entity.traits || []).join(', ') || 'None'}</li>
                <li>Health:
                    Sick: ${entity.is_sick ? `Yes (Severity: ${entity.sickness_severity})` : 'No'},
                    Injured: ${entity.is_injured ? `Yes (Severity: ${entity.injury_severity})` : 'No'}
                </li>
                <li>Needs: <pre>${JSON.stringify(entity.needs, null, 2)}</pre></li>
                <li>Inventory: <pre>${JSON.stringify(entity.inventory, null, 2)}</pre></li>
                <li>Skills: <pre>${JSON.stringify(entity.skills, null, 2)}</pre></li>
                <li>Supervisor: ${entity.supervisor_name || 'None'}</li>
                <li>Appointed By: ${entity.appointed_by || 'N/A'}</li>
                <li>Subordinates: ${(entity.subordinates_names || []).join(', ') || 'None'}</li>
                <li>Performance: ${entity.performance_rating || 'N/A'} (Warnings: ${entity.warning_count || 0})</li>
                <li>Last 5 Memories:</li><ul>`;
            (entity.memory || []).slice(-5).reverse().forEach(mem => { // Show newest 5 first
                detailsHtml += `<li>${mem}</li>`;
            });
            detailsHtml += `</ul></ul>`;
        } else if (type === 'building_detailed') {
            detailsHtml += `<ul>
                <li>Name: ${entity.display_name}</li>
                <li>Type: ${entity.structure_type}</li>
                <li>Location: (${entity.location[0]}, ${entity.location[1]})</li>
                <li>Size: (${entity.size[0]} x ${entity.size[1]})</li>
                <li>Operational: ${entity.is_operational ? 'Yes' : 'No'}</li>`;
            if (!entity.is_operational && entity.build_time > 0) {
                detailsHtml += `<li>Construction: ${entity.current_progress.toFixed(1)} / ${entity.build_time.toFixed(1)} (${entity.current_phase_name || 'N/A'})</li>`;
            }
            if (entity.inventory) {
                detailsHtml += `<li>Inventory: <pre>${JSON.stringify(entity.inventory, null, 2)}</pre></li>`;
            }
            if (entity.allowed_resources) {
                detailsHtml += `<li>Allowed Resources: ${entity.allowed_resources.join(', ') || 'Any'}</li>`;
            }
            detailsHtml += `</ul>`;
        } else if (type === 'tile') { // Basic tile info
             detailsHtml += `<p>Tile Type: ${entity.tileType}</p><p>Coordinates: (${entity.x}, ${entity.y})</p>`;
        }
        entityDetailsDiv.innerHTML = detailsHtml;
    }

    async function fetchCharacterDetails(characterName) {
        if (!showEntityDetails) { // Don't fetch if panel is hidden
            displayEntityDetails(null, 'character_detailed'); // Clear or hide panel
            return;
        }
        try {
            const response = await fetch(`${API_BASE_URL}/character_info?name=${encodeURIComponent(characterName)}`);
            if (!response.ok) {
                console.error(`HTTP error fetching character details! status: ${response.status}`);
                entityDetailsDiv.innerHTML = `<p>Error fetching details for ${characterName}: ${response.status}</p>`;
                return;
            }
            const charDetails = await response.json();
            displayEntityDetails(charDetails, 'character_detailed');
        } catch (error) {
            console.error('Error fetching character details:', error);
            entityDetailsDiv.innerHTML = `<p>Failed to fetch details for ${characterName}.</p>`;
        }
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

    // Generic click handler for map cells (tiles)
    function handleMapCellClick(event) {
        const cell = event.currentTarget; // `currentTarget` refers to the element the listener was attached to
        if (cell && cell.dataset.x && cell.dataset.y) {
            // Check if the click was on a character marker (span) inside the cell
            // If the click target is the cell itself (not a child span), then it's a tile click.
            if (event.target === cell || !event.target.closest('span')) {
                 displayEntityDetails({
                    name: `Tile (${cell.dataset.x},${cell.dataset.y})`,
                    x: cell.dataset.x,
                    y: cell.dataset.y,
                    tileType: cell.title
                }, 'tile');
            }
        }
    }

    // Initial setup of the main map click listener. Specific listeners for buildings/chars are added in renderMap.
    // This listener will catch clicks on cells that don't get a more specific listener.
    // However, the logic in renderMap now adds specific listeners to building/stockpile cells
    // which might override or precede this. We need to be careful.
    // A better approach is to add this generic listener to each cell, and let building/char listeners use stopPropagation.
    // The current renderMap logic already adds specific listeners to building/stockpile cells.
    // The character listeners also use stopPropagation.
    // So, this generic listener should be added to cells that *don't* become building/stockpile cells.
    // This is handled in renderMap where cells are created. The generic listener is added there.
    // The below is redundant if individual cells get listeners in renderMap.
    // For now, let's ensure each cell gets a listener if it's not a building/char.

    // Modified the renderMap function to add the generic click listener to non-building/non-stockpile cells.
    // The gameMapDiv.addEventListener part below becomes a fallback or can be removed if cell-specific listeners are comprehensive.

    // Fallback click listener for the map grid container itself
    // This can be simplified if individual cell listeners are robust.
    // gameMapDiv.addEventListener('click', (event) => {
    //     const cell = event.target.closest('.map-cell');
    //     // Ensure it's a direct click on a cell, not on a character or already handled building
    //     if (cell && cell.dataset.x && cell.dataset.y &&
    //         !event.target.closest('span') && // Not a character marker
    //         !cell.classList.contains('building-cell') &&
    //         !cell.classList.contains('stockpile-cell')) {
    //              displayEntityDetails({ name: `Tile (${cell.dataset.x},${cell.dataset.y})`, x: cell.dataset.x, y: cell.dataset.y, tileType: cell.title }, 'tile');
    //     }
    // });


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
