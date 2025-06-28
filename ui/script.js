document.addEventListener('DOMContentLoaded', () => {
    const gameMapDiv = document.getElementById('game-map');
    const entityDetailsDiv = document.getElementById('entity-details');
    const eventLogDiv = document.getElementById('event-log');
    const gameStatusDiv = document.getElementById('game-status');
    const pauseButton = document.getElementById('pause-button');
    const toggleDetailsButton = document.getElementById('toggle-details-button');
    const speedButtons = document.querySelectorAll('.speed-button');

    let API_BASE_URL = 'http://localhost:8000';
    let showEntityDetails = false; // Controlled by toggle button
    let currentSpeedMultiplier = 1.0; // To keep track locally for UI updates
    let isFetchingGameState = false; // Prevent multiple simultaneous fetches

    async function fetchGameState() {
        if (isFetchingGameState) return null; // Don't fetch if already fetching
        isFetchingGameState = true;
        // Simple loading indicator for game status
        // gameStatusDiv.innerHTML = 'Loading game state...';
        try {
            const response = await fetch(`${API_BASE_URL}/game_state`);
            if (!response.ok) {
                console.error(`HTTP error! status: ${response.status}`);
                if (gameStatusDiv) gameStatusDiv.innerHTML = `<p class="error">Error fetching game state: ${response.status}</p>`;
                return null;
            }
            const data = await response.json();
            // Clear loading message from gameStatusDiv if it was set there, by updateGameInfo
            return data;
        } catch (error) {
            console.error('Error fetching game state:', error);
            if (gameStatusDiv) gameStatusDiv.innerHTML = '<p class="error">Failed to connect to game server. Is it running?</p>';
            return null;
        } finally {
            isFetchingGameState = false;
        }
    }

    async function setSimulationSpeed(multiplier) {
        try {
            const response = await fetch(`${API_BASE_URL}/set_speed?multiplier=${multiplier}`, { method: 'POST' });
            if (!response.ok) {
                console.error(`HTTP error setting speed! status: ${response.status}`);
                return;
            }
            const data = await response.json();
            currentSpeedMultiplier = data.new_speed_multiplier; // Update local state
            updateUI(); // Refresh UI to show new speed and button state
        } catch (error) {
            console.error('Error setting simulation speed:', error);
        }
    }

    async function fetchBuildingDetails(x, y) {
        if (!showEntityDetails) {
            displayEntityDetails(null, 'building_detailed'); // Clear or hide panel
            return;
        }
        entityDetailsDiv.innerHTML = `<p>Loading details for (${x},${y})...</p>`;
        try {
            const response = await fetch(`${API_BASE_URL}/building_info?x=${x}&y=${y}`);
            if (!response.ok) {
                console.error(`HTTP error fetching building details! status: ${response.status}`);
                let errorMsg = `Error fetching building details for (${x},${y}): ${response.status}`;
                if (response.status === 404) {
                     errorMsg = `<p>No building or stockpile found at (${x},${y}).</p>`;
                }
                entityDetailsDiv.innerHTML = `<p class="error">${errorMsg}</p>`;
                return;
            }
            const buildingDetails = await response.json();
            // Use display_name from buildingDetails for the header, and pass the whole object
            displayEntityDetails({ name: buildingDetails.display_name, ...buildingDetails }, 'building_detailed');
        } catch (error) {
            console.error('Error fetching building details:', error);
            entityDetailsDiv.innerHTML = `<p class="error">Failed to fetch building details for (${x},${y}). Check connection.</p>`;
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
                const tileClassName = `tile-${tile.replace(/\s+/g, '-') || 'Unknown'}`;
                cell.classList.add(tileClassName);

                // Set textContent based on proposed symbols
                let tileSymbol = '';
                switch (tile) {
                    case 'Grass': tileSymbol = '.'; break;
                    case 'Forest': tileSymbol = '♣'; break;
                    case 'Water': tileSymbol = '≈'; break;
                    case 'Rocks': tileSymbol = '▲'; break;
                    case 'OutOfBounds': tileSymbol = 'X'; break;
                    default: tileSymbol = '?'; // For unknown tiles
                }
                cell.textContent = tileSymbol;
                cell.title = tile; // Tooltip shows full tile name
                cell.dataset.x = c_idx;
                cell.dataset.y = r_idx;
                cell.addEventListener('click', handleMapCellClick);
                gameMapDiv.appendChild(cell);
            });
        });

        // Render buildings and stockpiles
        if (gameState.buildings) {
            gameState.buildings.forEach(b => {
                for (let r_offset = 0; r_offset < b.height; r_offset++) {
                    for (let c_offset = 0; c_offset < b.width; c_offset++) {
                        const buildingCellX = b.x + c_offset;
                        const buildingCellY = b.y + r_offset;

                        if (buildingCellY >= gameState.grid_size[0] || buildingCellX >= gameState.grid_size[1]) continue;

                        const cellIndex = buildingCellY * gameState.grid_size[1] + buildingCellX;
                        const cellDiv = gameMapDiv.children[cellIndex];

                        if (cellDiv) {
                            cellDiv.innerHTML = ''; // Clear base tile symbol
                            // Use map_char from backend for building/stockpile symbol
                            cellDiv.textContent = b.map_char;
                            cellDiv.title = `${b.display_name} (${b.structure_type} at ${buildingCellX},${buildingCellY})`;

                            cellDiv.className = 'map-cell'; // Reset to base
                            if (b.structure_type === "Stockpile") {
                                cellDiv.classList.add('stockpile-cell');
                            } else {
                                cellDiv.classList.add('building-cell');
                                if (b.structure_type) { // e.g., building-wooden_hut
                                     cellDiv.classList.add(`building-${b.structure_type.replace(/\s+/g, '_')}`);
                                }
                            }
                            cellDiv.removeEventListener('click', handleMapCellClick);
                            cellDiv.addEventListener('click', (e) => {
                                e.stopPropagation();
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
                    // If the cell is a base tile (not a building/stockpile), clear its text content (e.g., 'G' for Grass)
                    // to make way for the character marker.
                    // If it's a building/stockpile cell, its textContent (e.g. 'H') should remain,
                    // and the absolutely positioned charMarker will appear on top.
                    if (!cellDiv.classList.contains('building-cell') && !cellDiv.classList.contains('stockpile-cell')) {
                        cellDiv.innerHTML = ''; // Clear only base tile character's text content
                    } else {
                        // For building/stockpile cells, we might have set textContent.
                        // To ensure the charMarker span can be appended and positioned correctly,
                        // we ensure any existing text content is wrapped or cleared if charMarker is sole content.
                        // However, since charMarker is absolute, appending it should just work.
                        // If there's an issue, we might need to wrap existing building char in a span too.
                        // For now, let's assume direct append + absolute positioning is enough.
                    }

                    const charMarker = document.createElement('span');
                    charMarker.classList.add('char-marker');
                    charMarker.textContent = char.name[0];
                    charMarker.title = `${char.name} (${char.job}) at (${char.x},${char.y})`;
                    charMarker.style.color = char.is_sick ? 'orange' : (char.is_injured ? 'red' : 'blue'); // Dynamic color based on health

                    charMarker.addEventListener('click', (e) => {
                        e.stopPropagation();
                        fetchCharacterDetails(char.name);
                    });
                    cellDiv.appendChild(charMarker); // Append, CSS will handle overlay
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
        currentSpeedMultiplier = gameState.current_speed_multiplier || 1.0; // Update local speed
        gameStatusDiv.innerHTML = `
            Day: ${gameState.day}, Tick: ${gameState.tick}/${gameState.ticks_per_day}<br>
            Season: ${gameState.season}, Weather: ${gameState.weather}<br>
            Status: ${gameState.is_paused ? "Paused" : "Running"} | Speed: ${currentSpeedMultiplier}x <br>
            ${electionText}
        `;
        pauseButton.textContent = gameState.is_paused ? "Resume" : "Pause";

        speedButtons.forEach(button => {
            if (parseFloat(button.dataset.speed) === currentSpeedMultiplier) {
                button.style.fontWeight = 'bold';
                button.style.backgroundColor = '#0056b3'; // Highlight active speed
            } else {
                button.style.fontWeight = 'normal';
                button.style.backgroundColor = '#007bff';
            }
        });
    }

    function displayEntityDetails(entity, type) {
        if (!showEntityDetails) {
            entityDetailsDiv.innerHTML = '<p><em>Entity details are currently hidden. Click "Toggle Entity Details" to show.</em></p>';
            return;
        }
        if (!entityDetailsDiv) return;
        if (!entity && type !== 'clear') { // If entity is null but not a clear instruction, show placeholder
             entityDetailsDiv.innerHTML = '<p>Select an entity to see details, or enable details view.</p>';
             return;
        }
         if (type === 'clear' || !showEntityDetails) {
            entityDetailsDiv.innerHTML = '<p><em>Entity details are currently hidden. Click "Toggle Entity Details" to show.</em></p>';
            return;
        }

        if (!entityDetailsDiv) return;
        if (!entity && type !== 'clear') {
             entityDetailsDiv.innerHTML = '<p>Select an entity to see details, or enable details view.</p>';
             return;
        }
         if (type === 'clear' || !showEntityDetails) {
            entityDetailsDiv.innerHTML = '<p><em>Entity details are currently hidden. Click "Toggle Entity Details" to show.</em></p>';
            return;
        }

        let detailsHtml = `<h4>Details: ${entity.name || entity.display_name || 'N/A'}</h4><dl class="details-list">`;

        function formatObject(obj) {
            if (typeof obj !== 'object' || obj === null) return obj;
            return Object.entries(obj).map(([key, value]) => `${key}: ${value}`).join('<br>');
        }

        if (type === 'character_detailed') {
            detailsHtml += `<dt>Name</dt><dd>${entity.name}</dd>`;
            detailsHtml += `<dt>Job</dt><dd>${entity.job || 'N/A'} (Rank: ${entity.rank || 'N/A'})</dd>`;
            detailsHtml += `<dt>Position</dt><dd>(${entity.x}, ${entity.y})</dd>`;
            detailsHtml += `<dt>Goal</dt><dd>${entity.current_goal || 'N/A'}</dd>`;
            detailsHtml += `<dt>Personality</dt><dd>${entity.personality || 'N/A'}</dd>`;
            detailsHtml += `<dt>Traits</dt><dd>${(entity.traits || []).join(', ') || 'None'}</dd>`;
            detailsHtml += `<dt>Health</dt><dd>Sick: ${entity.is_sick ? `Yes (Sev: ${entity.sickness_severity})` : 'No'}, Injured: ${entity.is_injured ? `Yes (Sev: ${entity.injury_severity})` : 'No'}</dd>`;

            detailsHtml += `<dt>Needs</dt><dd>${formatObject(entity.needs)}</dd>`;
            detailsHtml += `<dt>Inventory</dt><dd>${formatObject(entity.inventory)}</dd>`;
            detailsHtml += `<dt>Skills</dt><dd>${formatObject(entity.skills)}</dd>`;

            detailsHtml += `<dt>Supervisor</dt><dd>${entity.supervisor_name || 'None'}</dd>`;
            detailsHtml += `<dt>Appointed By</dt><dd>${entity.appointed_by || 'N/A'}</dd>`;
            detailsHtml += `<dt>Subordinates</dt><dd>${(entity.subordinates_names || []).join(', ') || 'None'}</dd>`;
            detailsHtml += `<dt>Performance</dt><dd>${entity.performance_rating || 'N/A'} (Warnings: ${entity.warning_count || 0})</dd>`;
            detailsHtml += `<dt>Last 5 Memories:</dt><dd><ul>`;
            (entity.memory || []).slice(-5).reverse().forEach(mem => {
                detailsHtml += `<li>${mem}</li>`;
            });
            detailsHtml += `</ul></dd>`;
        } else if (type === 'building_detailed') {
            detailsHtml += `<dt>Name</dt><dd>${entity.display_name}</dd>`;
            detailsHtml += `<dt>Type</dt><dd>${entity.structure_type}</dd>`;
            detailsHtml += `<dt>Location</dt><dd>(${entity.location[0]}, ${entity.location[1]})</dd>`;
            detailsHtml += `<dt>Size</dt><dd>(${entity.size[0]} x ${entity.size[1]})</dd>`;
            detailsHtml += `<dt>Operational</dt><dd>${entity.is_operational ? 'Yes' : 'No'}</dd>`;
            if (!entity.is_operational && entity.build_time > 0) {
                detailsHtml += `<dt>Construction</dt><dd>${entity.current_progress.toFixed(1)} / ${entity.build_time.toFixed(1)} (${entity.current_phase_name || 'N/A'})</dd>`;
            }
            if (entity.inventory && Object.keys(entity.inventory).length > 0) {
                detailsHtml += `<dt>Inventory</dt><dd>${formatObject(entity.inventory)}</dd>`;
            } else if (entity.inventory) {
                 detailsHtml += `<dt>Inventory</dt><dd>Empty</dd>`;
            }
            if (entity.allowed_resources) {
                detailsHtml += `<dt>Allowed Resources</dt><dd>${entity.allowed_resources.join(', ') || 'Any'}</dd>`;
            }
        } else if (type === 'tile') {
             detailsHtml += `<dt>Tile Type</dt><dd>${entity.tileType}</dd>`;
             detailsHtml += `<dt>Coordinates</dt><dd>(${entity.x}, ${entity.y})</dd>`;
        }
        detailsHtml += `</dl>`;
        entityDetailsDiv.innerHTML = detailsHtml;
    }

    async function fetchCharacterDetails(characterName) {
        if (!showEntityDetails) { // Don't fetch if panel is hidden
            displayEntityDetails(null, 'character_detailed'); // Clear or hide panel
            return;
        }
        entityDetailsDiv.innerHTML = `<p>Loading details for ${characterName}...</p>`;
        try {
            const response = await fetch(`${API_BASE_URL}/character_info?name=${encodeURIComponent(characterName)}`);
            if (!response.ok) {
                console.error(`HTTP error fetching character details! status: ${response.status}`);
                let errorMsg = `Error fetching details for ${characterName}: ${response.status}`;
                 if (response.status === 404) {
                    errorMsg = `Character ${characterName} not found.`;
                }
                entityDetailsDiv.innerHTML = `<p class="error">${errorMsg}</p>`;
                return;
            }
            const charDetails = await response.json();
            displayEntityDetails(charDetails, 'character_detailed');
        } catch (error) {
            console.error('Error fetching character details:', error);
            entityDetailsDiv.innerHTML = `<p class="error">Failed to fetch details for ${characterName}. Check connection.</p>`;
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

    speedButtons.forEach(button => {
        button.addEventListener('click', () => {
            const speed = parseFloat(button.dataset.speed);
            setSimulationSpeed(speed);
        });
    });

    // Initial UI update and start interval
    updateUI();
    setInterval(updateUI, 2000); // Refresh every 2 seconds

    // Hide entity details by default
    entityDetailsDiv.innerHTML = '<p><em>Entity details are hidden. Click "Toggle Entity Details" to show.</em></p>';
});
