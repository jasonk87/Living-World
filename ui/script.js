document.addEventListener('DOMContentLoaded', () => {
    // --- Element Selectors ---
    const gameStatusHeader = document.getElementById('game-status-header');
    const mapStage = document.getElementById('map-stage');
    const mapViewport = document.getElementById('map-viewport');
    const mapGridDiv = document.getElementById('game-map');
    const mapCharactersLayer = document.getElementById('map-characters');
    const eventLogDiv = document.getElementById('event-log');
    const pauseButton = document.getElementById('pause-button');
    const speedButtons = document.querySelectorAll('.speed-button');
    const overlayButtons = document.querySelectorAll('.overlay-toggle');
    const overlayPanels = document.querySelectorAll('.overlay-panel');
    const panelCloseButtons = document.querySelectorAll('.panel-close');
    const characterListDiv = document.getElementById('character-list');
    const followOverlay = document.getElementById('followed-character-overlay');
    const followOverlayBody = document.getElementById('followed-character-body');
    const eventFeedDiv = document.getElementById('event-feed');
    const mapMeta = document.getElementById('map-meta');
    const hudPopulationValue = document.getElementById('hud-population-value');
    const hudSeasonValue = document.getElementById('hud-season-value');
    const hudWeatherValue = document.getElementById('hud-weather-value');
    const hudTravelValue = document.getElementById('hud-travel-value');
    const hudElectionValue = document.getElementById('hud-election-value');
    const hudTreasuryValue = document.getElementById('hud-treasury-value');
    const hudRationsValue = document.getElementById('hud-rations-value');
    const hudHydrationValue = document.getElementById('hud-hydration-value');
    const hudHousingValue = document.getElementById('hud-housing-value');
    const economyMarketList = document.getElementById('economy-market-list');
    const economyPressureList = document.getElementById('economy-pressure-list');
    const economyWageList = document.getElementById('economy-wage-list');
    const economyCrimeNote = document.getElementById('economy-crime-note');
    const economyCampaignList = document.getElementById('economy-campaign-list');
    const environmentModifierList = document.getElementById('environment-modifier-list');
    const rumorFeedList = document.getElementById('rumor-feed-list');
    const housingStatusList = document.getElementById('housing-status-list');
    const characterSearchInput = document.getElementById('character-search');
    const infoPanel = document.getElementById('info-panel');

    // --- API & State ---
    const DEFAULT_API_BASE_URL = 'http://localhost:5000';
    const API_BASE_URL = (() => {
        const { origin, protocol } = window.location;
        const isHttpProtocol = protocol === 'http:' || protocol === 'https:';
        if (origin && origin !== 'null' && isHttpProtocol) {
            return origin;
        }
        return DEFAULT_API_BASE_URL;
    })();
    let isFetchingGameState = false;
    let latestGameState = null;
    let selectedCharacterName = null;
    let followedCharacterName = null;
    let characterSearchTerm = '';
    let pendingAutoCenter = false;
    let autoFollowCamera = true;

    const characterMarkers = new Map();
    let mapDimensions = { rows: 0, cols: 0 };
    let viewportPan = { x: 0, y: 0 };
    let viewportZoom = 1;
    let activePointerId = null;
    let lastPointerPosition = { x: 0, y: 0 };

    // --- Utility Helpers ---
    const getTileSize = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--tile-size')) || 48;

    function openPanel(panelId) {
        const panel = document.getElementById(panelId);
        if (!panel) return;
        panel.classList.add('open');
        panel.setAttribute('aria-hidden', 'false');
    }

    function closePanel(panelId) {
        const panel = document.getElementById(panelId);
        if (!panel) return;
        panel.classList.remove('open');
        panel.setAttribute('aria-hidden', 'true');
        if (panelId === 'info-panel') {
            const entityDetails = document.getElementById('entity-details');
            if (entityDetails && !entityDetails.innerHTML.trim()) {
                entityDetails.innerHTML = '<p>Click on the map to inspect citizens or structures.</p>';
            }
        }
    }

    function updateEconomyIntel(gameState) {
        if (!gameState) return;
        const report = gameState.daily_economy_report || {};
        const environment = gameState.environment_effects || report.environment || {};
        const housingSnapshot = gameState.housing || report.housing || {};

        if (hudTreasuryValue) {
            const treasury = typeof gameState.treasury === 'number' ? gameState.treasury : null;
            hudTreasuryValue.textContent = treasury !== null ? `${treasury}c` : '—';
        }

        if (hudRationsValue) {
            const consumed = typeof report.food_consumed === 'number' ? report.food_consumed : '—';
            const deficit = typeof report.food_deficit === 'number' ? report.food_deficit : 0;
            const deficitText = deficit > 0 ? ` • Short ${deficit}` : '';
            hudRationsValue.textContent = `${consumed}${deficitText}`;
        }

        if (hudHydrationValue) {
            const waterConsumed = typeof report.water_consumed === 'number' ? report.water_consumed : '—';
            const waterDeficit = typeof report.water_deficit === 'number' ? report.water_deficit : 0;
            const deficitText = waterDeficit > 0 ? ` • Short ${waterDeficit}` : '';
            hudHydrationValue.textContent = `${waterConsumed}${deficitText}`;
        }

        if (hudHousingValue) {
            const claimed = typeof housingSnapshot.claimed_beds === 'number' ? housingSnapshot.claimed_beds : null;
            const totalBeds = typeof housingSnapshot.total_beds === 'number' ? housingSnapshot.total_beds : null;
            const availableBeds = typeof housingSnapshot.available_beds === 'number' ? housingSnapshot.available_beds : null;
            const homelessCount = Array.isArray(housingSnapshot.homeless_characters)
                ? housingSnapshot.homeless_characters.length
                : 0;
            if (claimed === null || totalBeds === null || availableBeds === null) {
                hudHousingValue.textContent = '—';
            } else {
                const homelessText = homelessCount ? ` • Outside ${homelessCount}` : '';
                hudHousingValue.textContent = `${claimed}/${totalBeds} occupied • ${availableBeds} open${homelessText}`;
            }
        }

        if (hudTravelValue) {
            const travelSpeed = typeof environment.travel_speed === 'number'
                ? environment.travel_speed
                : typeof gameState.travel_speed_modifier === 'number'
                    ? gameState.travel_speed_modifier
                    : null;
            hudTravelValue.textContent = travelSpeed !== null ? `${travelSpeed.toFixed(2)}×` : '—';
        }

        if (economyMarketList) {
            const prices = Object.entries(gameState.market_prices || {});
            if (!prices.length) {
                economyMarketList.innerHTML = '<li class="empty">No market data.</li>';
            } else {
                prices.sort((a, b) => b[1] - a[1]);
                const topEntries = prices.slice(0, 5);
                economyMarketList.innerHTML = topEntries
                    .map(([item, price]) => `<li><strong>${item}</strong>: ${price}c</li>`)
                    .join('');
            }
        }

        if (economyPressureList) {
            const pressures = Array.isArray(gameState.resource_pressures) ? gameState.resource_pressures : [];
            if (!pressures.length) {
                economyPressureList.innerHTML = '<li class="empty">No active pressures.</li>';
            } else {
                economyPressureList.innerHTML = pressures
                    .slice(0, 5)
                    .map(pressure => {
                        const status = pressure.status === 'shortage' ? 'Shortage' : 'Surplus';
                        return `<li><strong>${pressure.resource}</strong>: ${status} (Δ ${pressure.severity})</li>`;
                    })
                    .join('');
            }
        }

        if (economyWageList) {
            const arrears = Array.isArray(gameState.pending_wages) ? gameState.pending_wages : [];
            if (!arrears.length) {
                economyWageList.innerHTML = '<li class="empty">No outstanding wages.</li>';
            } else {
                economyWageList.innerHTML = arrears
                    .slice(0, 5)
                    .map(entry => {
                        const amount = typeof entry.amount_due === 'number' ? entry.amount_due : 0;
                        const reason = entry.reason || 'duties';
                        const day = typeof entry.day_incurred === 'number' && entry.day_incurred >= 0
                            ? ` (Day ${entry.day_incurred})`
                            : '';
                        return `<li><strong>${entry.character}</strong>: ${amount}c for ${reason}${day}</li>`;
                    })
                    .join('');
            }
        }

        if (environmentModifierList) {
            const lines = [];
            const resourceMultipliers = environment.resource_multipliers || {};
            Object.entries(resourceMultipliers).forEach(([resource, entries]) => {
                let total = 1.0;
                (entries || []).forEach(entry => {
                    const multiplier = typeof entry.multiplier === 'number' ? entry.multiplier : 1.0;
                    total *= multiplier;
                });
                if (Math.abs(total - 1.0) > 0.01) {
                    const sources = (entries || []).map(entry => entry.source || 'Effect').join(', ');
                    lines.push(`<li><strong>${resource}</strong>: x${total.toFixed(2)} <span class="meta">${sources}</span></li>`);
                }
            });

            const travelSources = Array.isArray(environment.travel_sources) ? environment.travel_sources : [];
            if (travelSources.length) {
                const travelDetails = travelSources.map(entry => `${entry.source || 'Effect'} x${(entry.multiplier || 1).toFixed(2)}`);
                lines.unshift(`<li><strong>Travel</strong>: ${environment.travel_speed ? environment.travel_speed.toFixed(2) + '×' : 'Stable'} <span class="meta">${travelDetails.join(', ')}</span></li>`);
            }

            const marketMultipliers = environment.market_multipliers || {};
            Object.entries(marketMultipliers).forEach(([item, entries]) => {
                let total = 1.0;
                (entries || []).forEach(entry => {
                    const multiplier = typeof entry.multiplier === 'number' ? entry.multiplier : 1.0;
                    total *= multiplier;
                });
                if (Math.abs(total - 1.0) > 0.01) {
                    const sources = (entries || []).map(entry => entry.source || 'Effect').join(', ');
                    lines.push(`<li><strong>${item}</strong>: x${total.toFixed(2)} <span class="meta">${sources}</span></li>`);
                }
            });

            environmentModifierList.innerHTML = lines.length
                ? lines.slice(0, 6).join('')
                : '<li class="empty">No modifiers active.</li>';
        }

        if (housingStatusList) {
            const lines = [];
            const totalBeds = typeof housingSnapshot.total_beds === 'number' ? housingSnapshot.total_beds : null;
            const claimedBeds = typeof housingSnapshot.claimed_beds === 'number' ? housingSnapshot.claimed_beds : null;
            const availableBeds = typeof housingSnapshot.available_beds === 'number' ? housingSnapshot.available_beds : null;
            const restingNames = Array.isArray(housingSnapshot.resting_characters)
                ? housingSnapshot.resting_characters
                : [];
            const homelessNames = Array.isArray(housingSnapshot.homeless_characters)
                ? housingSnapshot.homeless_characters
                : [];

            if (totalBeds !== null && claimedBeds !== null && availableBeds !== null) {
                const summaryBits = [`${claimedBeds}/${totalBeds} occupied`, `${availableBeds} open`];
                if (restingNames.length) {
                    summaryBits.push(`${restingNames.length} resting`);
                }
                lines.push(`<li><strong>Capacity</strong>: ${summaryBits.join(' • ')}</li>`);
            }

            const structures = Array.isArray(housingSnapshot.structures) ? housingSnapshot.structures : [];
            structures.slice(0, 5).forEach(structure => {
                const capacity = typeof structure.capacity === 'number' ? structure.capacity : 0;
                const occupants = Array.isArray(structure.occupants) ? structure.occupants : [];
                const used = Math.min(occupants.length, capacity);
                const available = Math.max(0, capacity - used);
                const className = available === 0 ? 'housing-full' : 'housing-available';
                const occupantPreview = occupants.length
                    ? `${occupants.slice(0, 3).join(', ')}${occupants.length > 3 ? '…' : ''}`
                    : 'Vacant';
                lines.push(`
                    <li class="${className}">
                        <strong>${structure.name}</strong>: ${used}/${capacity} beds
                        <span class="meta">${available} open • ${occupantPreview}</span>
                    </li>
                `.trim());
            });

            if (homelessNames.length) {
                const preview = homelessNames.slice(0, 4).join(', ');
                const more = homelessNames.length > 4 ? '…' : '';
                const meta = preview ? `<span class="meta">${preview}${more}</span>` : '';
                lines.push(`<li class="alert"><strong>Homeless</strong>: ${homelessNames.length} ${meta}</li>`);
            }

            housingStatusList.innerHTML = lines.length
                ? lines.join('')
                : '<li class="empty">No housing data.</li>';
        }

        if (economyCrimeNote) {
            const reportCrimes = Array.isArray(report.crime_events) ? report.crime_events : [];
            const historyCrimes = Array.isArray(gameState.crime_reports) ? gameState.crime_reports : [];
            const pendingCrimes = Array.isArray(gameState.pending_crimes) ? gameState.pending_crimes : [];
            let latestCrime = null;
            if (reportCrimes.length) {
                latestCrime = reportCrimes[reportCrimes.length - 1];
            } else if (historyCrimes.length) {
                latestCrime = historyCrimes[historyCrimes.length - 1];
            }

            const messageParts = [];
            if (pendingCrimes.length) {
                const activeAssignments = pendingCrimes.filter(crime => crime.status === 'assigned').length;
                const openCases = pendingCrimes.length;
                const activeText = activeAssignments ? `, ${activeAssignments} active` : '';
                messageParts.push(`${openCases} case${openCases === 1 ? '' : 's'} open${activeText}`);
            }

            if (latestCrime && latestCrime.description) {
                const crimeDay = typeof latestCrime.day === 'number' && latestCrime.day >= 0
                    ? latestCrime.day
                    : typeof latestCrime.reported_day === 'number' && latestCrime.reported_day >= 0
                        ? latestCrime.reported_day
                        : null;
                const dayLabel = crimeDay !== null ? `Day ${crimeDay}: ` : '';
                const statusLabel = latestCrime.status
                    ? ` (${latestCrime.status.charAt(0).toUpperCase()}${latestCrime.status.slice(1)})`
                    : '';
                messageParts.push(`${dayLabel}${latestCrime.description}${statusLabel}`);
            }

            economyCrimeNote.textContent = messageParts.length
                ? messageParts.join(' • ')
                : 'No incidents reported.';
        }

        if (economyCampaignList) {
            const promisesByCandidate = gameState.campaign_promises || {};
            const allPromises = Object.entries(promisesByCandidate)
                .flatMap(([candidate, entries]) => (Array.isArray(entries) ? entries : [])
                    .map(promise => ({ ...promise, candidate })));

            if (!allPromises.length) {
                economyCampaignList.innerHTML = '<li class="empty">No promises active.</li>';
            } else {
                const statusOrder = { failed: 0, pledged: 1, enacted: 2 };
                const statusLabels = { pledged: 'Pledged', enacted: 'Fulfilled', failed: 'Failed' };
                const formatDay = day => (typeof day === 'number' && day >= 0 ? `Day ${day}` : null);

                allPromises.sort((a, b) => {
                    const orderDiff = (statusOrder[a.status] ?? 1) - (statusOrder[b.status] ?? 1);
                    if (orderDiff !== 0) return orderDiff;
                    return (b.created_day ?? 0) - (a.created_day ?? 0);
                });

                economyCampaignList.innerHTML = allPromises.slice(0, 5).map(promise => {
                    const status = (promise.status || 'pledged').toLowerCase();
                    const statusLabel = statusLabels[status] || status.charAt(0).toUpperCase() + status.slice(1);
                    const deadlineText = status === 'pledged'
                        ? formatDay(promise.deadline_day)
                        : status === 'enacted'
                            ? formatDay(promise.fulfilled_day)
                            : status === 'failed'
                                ? formatDay(promise.failed_day || promise.deadline_day)
                                : null;
                    const timeline = deadlineText
                        ? (status === 'pledged'
                            ? `Due ${deadlineText}`
                            : status === 'enacted'
                                ? `Fulfilled ${deadlineText}`
                                : `Failed ${deadlineText}`)
                        : '';

                    const summaryText = promise.summary || 'Promise logged.';
                    const timelineHtml = timeline ? `<div class="meta">${timeline}</div>` : '';
                    return `
                        <li class="status-${status}">
                            <div><strong>${promise.candidate}</strong> • ${statusLabel}</div>
                            <div>${summaryText}</div>
                            ${timelineHtml}
                        </li>
                    `;
                }).join('');
            }
        }

        if (rumorFeedList) {
            const rumors = Array.isArray(gameState.rumors) ? gameState.rumors : [];
            if (!rumors.length) {
                rumorFeedList.innerHTML = '<li class="empty">No rumors circulating.</li>';
            } else {
                rumorFeedList.innerHTML = rumors.slice(0, 6).map(rumor => {
                    const tone = rumor.is_positive ? 'Positive' : 'Negative';
                    const strength = typeof rumor.strength === 'number' ? rumor.strength : '?';
                    const reach = typeof rumor.known_count === 'number' ? rumor.known_count : 0;
                    return `
                        <li class="rumor-${tone.toLowerCase()}">
                            <div><strong>${rumor.subject}</strong> • ${tone}</div>
                            <div>${rumor.content}</div>
                            <div class="meta">Strength ${strength} • Heard by ${reach}</div>
                        </li>
                    `;
                }).join('');
            }
        }
    }

    function togglePanel(panelId) {
        const panel = document.getElementById(panelId);
        if (!panel) return;
        const isOpen = panel.classList.contains('open');
        if (isOpen) {
            closePanel(panelId);
        } else {
            if (!panel.classList.contains('dock-right')) {
                overlayPanels.forEach(other => {
                    if (other.id !== panelId && !other.classList.contains('dock-right')) {
                        closePanel(other.id);
                    }
                });
            }
            openPanel(panelId);
        }
    }

    function setPanelLoading(panelId, message = 'Loading details...') {
        const panel = document.getElementById(panelId);
        if (!panel) return;
        panel.innerHTML = `<p>${message}</p>`;
        if (panelId === 'entity-details') {
            openPanel('info-panel');
        }
        if (panelId === 'character-details-panel') {
            openPanel('characters-panel');
        }
    }

    function handleCharacterSelection(name) {
        selectedCharacterName = name;
        setFollowedCharacter(name, { autoCenter: true });
        openPanel('info-panel');
        openPanel('characters-panel');
        loadCharacterDetails(name, { worldPanel: true, characterPanel: true });
    }

    function updateFollowedCharacterOverlay(character) {
        if (!followOverlay || !followOverlayBody) return;

        if (!character || character.name !== followedCharacterName) {
            followOverlay.classList.add('hidden');
            followOverlayBody.innerHTML = '<p>Select a character to follow.</p>';
            return;
        }

        followOverlay.classList.remove('hidden');
        const sicknessText = character.is_sick ? `Sick${character.sickness_severity !== undefined ? ` (sev ${character.sickness_severity})` : ''}` : 'Well';
        const injuryText = character.is_injured ? `Injured${character.injury_severity !== undefined ? ` (sev ${character.injury_severity})` : ''}` : 'Unhurt';
        const healthSummary = `Health: ${sicknessText}, ${injuryText}`;
        const goalDetails = extractGoal(character.current_goal);
        const goalSummary = `${goalDetails.type}${goalDetails.priority !== '—' ? ` (prio ${goalDetails.priority})` : ''}`;
        const energyText = typeof character.energy === 'number' ? character.energy : '—';
        const thirstText = typeof character.thirst === 'number' ? character.thirst : '—';
        const housingSummary = character.resting_at_home
            ? 'Resting at assigned housing'
            : Array.isArray(character.home_location)
                ? `Sheltered at (${character.home_location[0]}, ${character.home_location[1]})`
                : 'No assigned housing';
        const lastDialogue = (character.dialogue_history || []).slice(-1)[0];
        let dialogueSummary = 'No recent conversations logged.';
        if (lastDialogue) {
            const exchanges = Array.isArray(lastDialogue.dialogue_exchanges) ? lastDialogue.dialogue_exchanges : [];
            if (exchanges.length) {
                dialogueSummary = exchanges.map(line => `${line.speaker}: “${line.line}”`).join('<br>');
            } else {
                dialogueSummary = 'Conversation noted, but no transcript available.';
            }
        }

        const jobTitle = character.job || 'Unassigned';

        followOverlayBody.innerHTML = `
            <p><strong>${character.name}</strong> — ${jobTitle}</p>
            <p>Location: (${character.x}, ${character.y})</p>
            <p>Goal: ${goalSummary}</p>
            <p>${healthSummary}</p>
            <p>Needs: Energy ${energyText} • Thirst ${thirstText}</p>
            <p>Housing: ${housingSummary}</p>
            <hr>
            <p><strong>Latest Social Exchange</strong></p>
            <p class="dialogue-snippet">${dialogueSummary}</p>
        `;
    }

    function updateWorldSummary(gameState) {
        if (!gameState) return;
        const population = Array.isArray(gameState.characters) ? gameState.characters.length : 0;
        const environment = gameState.environment_effects || {};
        if (hudPopulationValue) {
            hudPopulationValue.textContent = population;
        }
        if (hudSeasonValue) {
            const seasonName = environment.season || gameState.season || 'Unknown';
            const seasonDay = environment.season_day;
            hudSeasonValue.textContent = typeof seasonDay === 'number'
                ? `${seasonName} · Day ${seasonDay}`
                : seasonName;
        }
        if (hudWeatherValue) {
            const weatherLabel = environment.weather || gameState.weather;
            const weatherText = [weatherLabel, gameState.temperature_label].filter(Boolean).join(' • ');
            hudWeatherValue.textContent = weatherText || weatherLabel || 'Calm';
        }
        if (hudTravelValue) {
            const travelSpeed = typeof environment.travel_speed === 'number'
                ? environment.travel_speed
                : typeof gameState.travel_speed_modifier === 'number'
                    ? gameState.travel_speed_modifier
                    : null;
            hudTravelValue.textContent = travelSpeed !== null ? `${travelSpeed.toFixed(2)}×` : '—';
        }
        if (hudElectionValue) {
            const days = gameState.days_until_election;
            if (typeof days === 'number' && days >= 0) {
                hudElectionValue.textContent = days === 0 ? 'Today' : `${days} day${days === 1 ? '' : 's'}`;
            } else {
                hudElectionValue.textContent = 'Unknown';
            }
        }
    }

    function updateMapMetaInfo(gameState) {
        if (!mapMeta) return;
        if (!gameState) {
            mapMeta.textContent = '';
            return;
        }
        const gridSize = Array.isArray(gameState.grid_size) ? gameState.grid_size : [];
        const buildingsCount = Array.isArray(gameState.buildings) ? gameState.buildings.length : 0;
        const population = Array.isArray(gameState.characters) ? gameState.characters.length : 0;
        const metaParts = [];
        if (gridSize.length === 2) {
            metaParts.push(`${gridSize[0]}×${gridSize[1]} grid`);
        }
        metaParts.push(`${population} citizen${population === 1 ? '' : 's'}`);
        if (buildingsCount) {
            metaParts.push(`${buildingsCount} structure${buildingsCount === 1 ? '' : 's'}`);
        }
        mapMeta.textContent = metaParts.join(' • ');
    }

    function updateEventFeed(log) {
        if (!eventFeedDiv) return;
        if (!log || !log.length) {
            eventFeedDiv.innerHTML = '<p class="empty">No events logged yet.</p>';
            return;
        }
        const latestEntries = log.slice(-6).reverse();
        eventFeedDiv.innerHTML = latestEntries.map(entry => `<p>${entry}</p>`).join('');
    }

    function setFollowedCharacter(name, { autoCenter = false } = {}) {
        if (followedCharacterName !== name) {
            followedCharacterName = name;
        }
        if (!name) {
            pendingAutoCenter = false;
            autoFollowCamera = false;
            updateFollowedCharacterOverlay(null);
        } else {
            if (autoCenter) {
                pendingAutoCenter = true;
                autoFollowCamera = true;
            }
            if (latestGameState) {
                const match = (latestGameState.characters || []).find(char => char.name === name);
                updateFollowedCharacterOverlay(match || null);
            }
        }
        if (latestGameState) {
            renderCharacterList(latestGameState.characters || []);
        }
    }

    function extractGoal(goal) {
        if (!goal) return { type: 'Idle', status: 'Idle', priority: '—' };
        if (typeof goal === 'string') return { type: goal, status: 'Active', priority: '—' };
        return {
            type: goal.type || 'Unknown',
            status: goal.status || 'Active',
            priority: goal.priority !== undefined ? goal.priority : '—',
        };
    }

    function formatKeyValueList(data) {
        const list = document.createElement('ul');
        Object.entries(data || {}).forEach(([key, value]) => {
            const item = document.createElement('li');
            item.innerHTML = `<strong>${key}:</strong> ${value}`;
            list.appendChild(item);
        });
        if (!list.children.length) {
            const empty = document.createElement('p');
            empty.textContent = 'None recorded.';
            return empty;
        }
        return list;
    }

    function formatNestedOpinions(opinions) {
        const container = document.createElement('div');
        const entries = Object.entries(opinions || {});
        if (!entries.length) {
            container.innerHTML = '<p>No opinions recorded.</p>';
            return container;
        }
        entries.sort((a, b) => a[0].localeCompare(b[0]));
        entries.forEach(([target, feelings]) => {
            const block = document.createElement('div');
            block.classList.add('opinion-block');
            block.innerHTML = `<strong>${target}</strong>`;
            const list = document.createElement('ul');
            Object.entries(feelings || {}).forEach(([topic, score]) => {
                const li = document.createElement('li');
                li.innerHTML = `${topic}: ${score}`;
                list.appendChild(li);
            });
            if (!list.children.length) {
                const empty = document.createElement('p');
                empty.textContent = 'No specific impressions.';
                block.appendChild(empty);
            } else {
                block.appendChild(list);
            }
            container.appendChild(block);
        });
        return container;
    }

    function formatDialogueHistory(history) {
        const container = document.createElement('div');
        if (!history || !history.length) {
            container.innerHTML = '<p>No dialogue history recorded.</p>';
            return container;
        }
        const list = document.createElement('ul');
        [...history].reverse().forEach(entry => {
            const li = document.createElement('li');
            const lines = (entry.dialogue_exchanges || []).map(line => `${line.speaker}: “${line.line}”`).join('<br>');
            li.innerHTML = `
                <strong>Day ${entry.day} – ${entry.type}</strong><br>
                ${lines || 'No transcript available.'}
            `;
            list.appendChild(li);
        });
        container.appendChild(list);
        return container;
    }

    function buildOverviewContent(character) {
        const wrapper = document.createElement('div');
        const needsSection = document.createElement('section');
        needsSection.innerHTML = '<h4>Needs</h4>';
        needsSection.appendChild(formatKeyValueList(character.needs));

        const housingSection = document.createElement('section');
        housingSection.innerHTML = '<h4>Housing & Rest</h4>';
        const home = Array.isArray(character.home_location)
            ? `(${character.home_location[0]}, ${character.home_location[1]})`
            : 'Unassigned';
        const restStatus = character.resting_at_home ? 'Resting' : 'Active';
        housingSection.innerHTML += `<p><strong>Status:</strong> ${restStatus}</p>`;
        housingSection.innerHTML += `<p><strong>Home:</strong> ${home}</p>`;

        const skillsSection = document.createElement('section');
        skillsSection.innerHTML = '<h4>Skills</h4>';
        const skillLevels = Object.fromEntries(Object.entries(character.skills || {}).map(([skill, level]) => [skill, level]));
        skillsSection.appendChild(formatKeyValueList(skillLevels));

        const inventorySection = document.createElement('section');
        inventorySection.innerHTML = '<h4>Inventory</h4>';
        if (character.inventory && Object.keys(character.inventory).length) {
            inventorySection.appendChild(formatKeyValueList(character.inventory));
        } else {
            const empty = document.createElement('p');
            empty.textContent = 'Inventory is empty.';
            inventorySection.appendChild(empty);
        }

        wrapper.append(needsSection, housingSection, skillsSection, inventorySection);
        return wrapper;
    }

    function buildSocialContent(character) {
        const wrapper = document.createElement('div');

        const knownSection = document.createElement('section');
        knownSection.innerHTML = '<h4>Known Characters</h4>';
        if (character.known_characters && character.known_characters.length) {
            const list = document.createElement('ul');
            character.known_characters.sort().forEach(name => {
                const li = document.createElement('li');
                li.textContent = name;
                list.appendChild(li);
            });
            knownSection.appendChild(list);
        } else {
            knownSection.innerHTML += '<p>No acquaintances yet.</p>';
        }

        const relationshipsSection = document.createElement('section');
        relationshipsSection.innerHTML = '<h4>Relationships</h4>';
        const relationshipEntries = Object.entries(character.relationships || {});
        if (relationshipEntries.length) {
            relationshipEntries.sort((a, b) => b[1] - a[1]);
            const list = document.createElement('ul');
            relationshipEntries.forEach(([name, score]) => {
                const li = document.createElement('li');
                li.innerHTML = `<strong>${name}</strong>: ${score}`;
                list.appendChild(li);
            });
            relationshipsSection.appendChild(list);
        } else {
            relationshipsSection.innerHTML += '<p>No formed relationships.</p>';
        }

        const opinionsSection = document.createElement('section');
        opinionsSection.innerHTML = '<h4>Opinions</h4>';
        opinionsSection.appendChild(formatNestedOpinions(character.opinions));

        const dialogueSection = document.createElement('section');
        dialogueSection.innerHTML = '<h4>Recent Conversations</h4>';
        dialogueSection.appendChild(formatDialogueHistory(character.dialogue_history));

        wrapper.append(knownSection, relationshipsSection, opinionsSection, dialogueSection);
        return wrapper;
    }

    function buildActivityContent(character) {
        const wrapper = document.createElement('div');

        const goalSection = document.createElement('section');
        goalSection.innerHTML = '<h4>Current Focus</h4>';
        const activityGoal = extractGoal(character.current_goal);
        goalSection.innerHTML += `
            <p><strong>Goal:</strong> ${activityGoal.type}</p>
            <p><strong>Status:</strong> ${activityGoal.status}</p>
            <p><strong>Priority:</strong> ${activityGoal.priority}</p>
        `;

        const placementSection = document.createElement('section');
        placementSection.innerHTML = '<h4>Placement</h4>';
        placementSection.innerHTML += `
            <p><strong>Coordinates:</strong> (${character.x}, ${character.y})</p>
            <p><strong>Region:</strong> ${character.region || 'Unknown'}</p>
        `;

        const historySection = document.createElement('section');
        historySection.innerHTML = '<h4>Activity History</h4>';
        if (character.activity_log && character.activity_log.length) {
            const list = document.createElement('ul');
            character.activity_log.slice(-8).reverse().forEach(entry => {
                const li = document.createElement('li');
                li.innerHTML = `<strong>Day ${entry.day}</strong>: ${entry.description}`;
                list.appendChild(li);
            });
            historySection.appendChild(list);
        } else {
            historySection.innerHTML += '<p>No recent activity recorded.</p>';
        }

        wrapper.append(goalSection, placementSection, historySection);
        return wrapper;
    }

    function buildCharacterDetails(character) {
        const wrapper = document.createElement('section');
        wrapper.classList.add('detail-tabs');

        const header = document.createElement('header');
        header.innerHTML = `
            <h3>${character.name}</h3>
            <p>${character.job || 'Unassigned'} • Reputation ${character.reputation ?? '—'}</p>
        `;

        const followButton = document.createElement('button');
        followButton.type = 'button';
        followButton.classList.add('primary-control');
        if (character.name === followedCharacterName) {
            followButton.textContent = 'Following';
            followButton.setAttribute('aria-pressed', 'true');
        } else {
            followButton.textContent = 'Follow';
            followButton.setAttribute('aria-pressed', 'false');
        }

        followButton.addEventListener('click', () => {
            if (followedCharacterName === character.name) {
                setFollowedCharacter(null);
                followButton.textContent = 'Follow';
                followButton.setAttribute('aria-pressed', 'false');
            } else {
                setFollowedCharacter(character.name, { autoCenter: true });
                followButton.textContent = 'Following';
                followButton.setAttribute('aria-pressed', 'true');
            }
        });

        header.appendChild(followButton);

        const tabButtonsContainer = document.createElement('div');
        tabButtonsContainer.classList.add('detail-tab-buttons');
        const tabContentsContainer = document.createElement('div');
        tabContentsContainer.classList.add('detail-tab-contents');

        const tabs = [
            { label: 'Overview', builder: buildOverviewContent },
            { label: 'Social', builder: buildSocialContent },
            { label: 'Activity', builder: buildActivityContent },
        ];

        tabs.forEach((tabConfig, index) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.classList.add('detail-tab-button');
            if (index === 0) button.classList.add('active');
            button.textContent = tabConfig.label;

            const content = document.createElement('div');
            content.classList.add('detail-tab-content');
            if (index === 0) content.classList.add('active');
            content.appendChild(tabConfig.builder(character));

            button.addEventListener('click', () => {
                tabButtonsContainer.querySelectorAll('.detail-tab-button').forEach(btn => btn.classList.remove('active'));
                tabContentsContainer.querySelectorAll('.detail-tab-content').forEach(panel => panel.classList.remove('active'));
                button.classList.add('active');
                content.classList.add('active');
            });

            tabButtonsContainer.appendChild(button);
            tabContentsContainer.appendChild(content);
        });

        wrapper.append(header, tabButtonsContainer, tabContentsContainer);
        return wrapper;
    }

    function displayEntityDetails(entity, type, targetPanelId) {
        const targetPanel = document.getElementById(targetPanelId || 'entity-details');
        if (!targetPanel) return;

        targetPanel.innerHTML = '';
        const dl = document.createElement('dl');

        if (type === 'character') {
            targetPanel.appendChild(buildCharacterDetails(entity));
            updateFollowedCharacterOverlay(entity);
            openPanel('info-panel');
            return;
        }

        if (type === 'error') {
            targetPanel.innerHTML = `<p class="error">${entity.message || 'Failed to load details.'}</p>`;
            return;
        }

        if (type === 'building') {
            dl.innerHTML = `
                <h3>${entity.display_name}</h3>
                <dt>Type</dt><dd>${entity.structure_type}</dd>
                <dt>Operational</dt><dd>${entity.is_operational}</dd>
                ${entity.provides_shelter ? `<dt>Shelter Capacity</dt><dd>${entity.provides_shelter}</dd>` : ''}
                ${Array.isArray(entity.occupants) ? `<dt>Occupants</dt><dd>${entity.occupants.length ? entity.occupants.join(', ') : 'None'}</dd>` : ''}
                ${entity.inventory ? `<dt>Inventory</dt><dd>${JSON.stringify(entity.inventory)}</dd>` : ''}
            `;
        }
        targetPanel.appendChild(dl);
        openPanel('info-panel');
    }

    function updateViewportTransform() {
        if (!mapViewport) return;
        mapViewport.style.transform = `translate(${viewportPan.x}px, ${viewportPan.y}px) scale(${viewportZoom})`;
    }

    function centerViewportOn(x, y) {
        if (!mapStage || !mapViewport) return;
        const tileSize = getTileSize();
        const stageRect = mapStage.getBoundingClientRect();
        const targetX = (x + 0.5) * tileSize;
        const targetY = (y + 0.5) * tileSize;
        viewportPan.x = stageRect.width / 2 - targetX * viewportZoom;
        viewportPan.y = stageRect.height / 2 - targetY * viewportZoom;
        updateViewportTransform();
    }

    function ensureMapBase(gameState) {
        if (!mapGridDiv || !mapCharactersLayer || !gameState || !Array.isArray(gameState.grid)) return;
        const gridSize = Array.isArray(gameState.grid_size) ? gameState.grid_size : [0, 0];
        const [rows, cols] = gridSize;
        if (!rows || !cols) return;

        const needsRebuild = rows !== mapDimensions.rows || cols !== mapDimensions.cols || mapGridDiv.childElementCount === 0;
        if (needsRebuild) {
            mapDimensions = { rows, cols };
            mapGridDiv.innerHTML = '';
            const fragment = document.createDocumentFragment();
            for (let r = 0; r < rows; r++) {
                for (let c = 0; c < cols; c++) {
                    const cell = document.createElement('div');
                    cell.classList.add('map-cell');
                    cell.dataset.x = c;
                    cell.dataset.y = r;
                    cell.addEventListener('click', onMapCellClick);
                    fragment.appendChild(cell);
                }
            }
            mapGridDiv.appendChild(fragment);
        }

        const tileSize = getTileSize();
        const width = cols * tileSize;
        const height = rows * tileSize;
        mapViewport.style.width = `${width}px`;
        mapViewport.style.height = `${height}px`;
        mapCharactersLayer.style.width = `${width}px`;
        mapCharactersLayer.style.height = `${height}px`;

        const cells = mapGridDiv.children;
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const index = r * cols + c;
                const cell = cells[index];
                if (!cell) continue;
                const tileRow = gameState.grid[r] || [];
                const tileType = tileRow[c] || 'Unknown';
                const tileClass = `tile-${tileType.replace(/\s+/g, '-')}`;
                cell.className = `map-cell ${tileClass}`;
                cell.title = `${tileType} (${c}, ${r})`;
                delete cell.dataset.building;
                delete cell.dataset.buildingOriginX;
                delete cell.dataset.buildingOriginY;
                delete cell.dataset.buildingName;
            }
        }

        (gameState.buildings || []).forEach(building => {
            for (let r = 0; r < building.height; r++) {
                for (let c = 0; c < building.width; c++) {
                    const x = building.x + c;
                    const y = building.y + r;
                    if (x < 0 || y < 0 || x >= cols || y >= rows) continue;
                    const index = y * cols + x;
                    const cell = mapGridDiv.children[index];
                    if (!cell) continue;
                    cell.classList.add(building.structure_type === 'Stockpile' ? 'stockpile-cell' : 'building-cell');
                    cell.dataset.building = 'true';
                    cell.dataset.buildingOriginX = building.x;
                    cell.dataset.buildingOriginY = building.y;
                    cell.dataset.buildingName = building.display_name || building.structure_type;
                    cell.title = `${building.display_name || building.structure_type} (${x}, ${y})`;
                }
            }
        });
    }

    function onMapCellClick(event) {
        const cell = event.currentTarget;
        if (cell.dataset.building === 'true') {
            event.stopPropagation();
            const coords = {
                x: Number(cell.dataset.buildingOriginX),
                y: Number(cell.dataset.buildingOriginY),
            };
            openPanel('info-panel');
            loadBuildingDetails(coords);
        }
    }

    function updateCharacterMarkers(characters) {
        if (!mapCharactersLayer) return;
        const tileSize = getTileSize();
        const seen = new Set();

        (characters || []).forEach(character => {
            let marker = characterMarkers.get(character.name);
            if (!marker) {
                marker = document.createElement('button');
                marker.type = 'button';
                marker.classList.add('char-marker');
                marker.addEventListener('click', (e) => {
                    e.stopPropagation();
                    handleCharacterSelection(character.name);
                });
                marker.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleCharacterSelection(character.name);
                    }
                });
                marker.addEventListener('pointerdown', (e) => {
                    e.stopPropagation();
                });
                mapCharactersLayer.appendChild(marker);
                characterMarkers.set(character.name, marker);
            }

            marker.dataset.job = character.job || 'Unassigned';
            marker.dataset.name = character.name;
            marker.textContent = character.name.charAt(0).toUpperCase();
            marker.title = `${character.name} (${character.job || 'Unassigned'})`;
            marker.classList.toggle('following', character.name === followedCharacterName);
            marker.classList.toggle('sick', Boolean(character.is_sick));
            marker.classList.toggle('injured', Boolean(character.is_injured));
            marker.style.transform = `translate3d(${character.x * tileSize}px, ${character.y * tileSize}px, 0)`;

            if (character.name === selectedCharacterName) {
                marker.classList.add('active');
            } else {
                marker.classList.remove('active');
            }

            seen.add(character.name);
        });

        Array.from(characterMarkers.keys()).forEach(name => {
            if (!seen.has(name)) {
                const marker = characterMarkers.get(name);
                if (marker && marker.parentElement) {
                    marker.parentElement.removeChild(marker);
                }
                characterMarkers.delete(name);
            }
        });

        if (followedCharacterName) {
            const followed = (characters || []).find(char => char.name === followedCharacterName);
            updateFollowedCharacterOverlay(followed || null);
            if (followed && (pendingAutoCenter || autoFollowCamera)) {
                centerViewportOn(followed.x, followed.y);
                pendingAutoCenter = false;
            }
        } else {
            updateFollowedCharacterOverlay(null);
        }
    }

    function updateGameInfo(gameState) {
        if (!gameStatusHeader || !gameState) return;
        const statusClass = gameState.is_paused ? 'status-pill muted' : 'status-pill';
        gameStatusHeader.innerHTML = `
            <span class="status-pill">Day ${gameState.day}</span>
            <span class="status-pill">Tick ${gameState.tick}/${gameState.ticks_per_day}</span>
            <span class="status-pill">Speed ${gameState.current_speed_multiplier}x</span>
            <span class="${statusClass}">${gameState.is_paused ? 'Paused' : 'Running'}</span>
        `;
        if (pauseButton) {
            pauseButton.textContent = gameState.is_paused ? 'Resume' : 'Pause';
        }
    }

    function updateEventLog(log) {
        if (!eventLogDiv) return;
        if (!log || !log.length) {
            eventLogDiv.innerHTML = '<p class="empty">No events logged yet.</p>';
            return;
        }
        eventLogDiv.innerHTML = log.slice().reverse().map(entry => `<p>${entry}</p>`).join('');
    }

    function renderCharacterList(characters) {
        if (!characterListDiv || !Array.isArray(characters)) return;

        const sortedCharacters = [...characters].sort((a, b) => a.name.localeCompare(b.name));
        const searchTerm = characterSearchTerm.trim();
        const filteredCharacters = sortedCharacters.filter(char => {
            if (!searchTerm) return true;
            const haystack = `${char.name} ${char.job} ${extractGoal(char.current_goal).type}`.toLowerCase();
            return haystack.includes(searchTerm);
        });

        if (!filteredCharacters.length) {
            characterListDiv.innerHTML = '<div class="empty-state">No citizens match your search.</div>';
            return;
        }

        characterListDiv.innerHTML = filteredCharacters.map(char => {
            const isActive = char.name === selectedCharacterName;
            const isFollowing = char.name === followedCharacterName;
            const goal = extractGoal(char.current_goal).type;
            const loadText = typeof char.inventory_load === 'number' ? ` • Load: ${char.inventory_load}` : '';
            const statusFlags = [];
            if (char.resting_at_home) statusFlags.push('Resting');
            if (typeof char.energy === 'number' && char.energy < 40) statusFlags.push('Fatigued');
            if (typeof char.thirst === 'number' && char.thirst < 40) statusFlags.push('Thirsty');
            const statusLine = statusFlags.length ? `<small class="status-flags">${statusFlags.join(' • ')}</small>` : '';
            return `
                <article class="character-card ${isActive ? 'active' : ''} ${isFollowing ? 'following' : ''}" data-char-name="${char.name}">
                    <strong>${char.name}</strong>
                    <small>${char.job || 'Unassigned'} • Goal: ${goal}</small>
                    <small>Pos: (${char.x}, ${char.y})${loadText}</small>
                    ${statusLine}
                </article>
            `;
        }).join('');

        characterListDiv.querySelectorAll('.character-card').forEach(card => {
            card.addEventListener('click', () => {
                const name = card.dataset.charName;
                handleCharacterSelection(name);
            });
        });
    }

    function renderMap(gameState) {
        if (!gameState) return;
        ensureMapBase(gameState);
        updateCharacterMarkers(gameState.characters || []);
        latestGameState = gameState;
        updateMapMetaInfo(gameState);
    }

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

    async function loadCharacterDetails(name, { worldPanel = true, characterPanel = true, showLoading = true } = {}) {
        if (showLoading) {
            if (worldPanel) setPanelLoading('entity-details');
            if (characterPanel) setPanelLoading('character-details-panel');
        }
        try {
            const response = await fetch(`${API_BASE_URL}/character_info?name=${encodeURIComponent(name)}`);
            if (!response.ok) {
                const errorMessage = `Error fetching details: ${response.status}`;
                if (worldPanel) displayEntityDetails({ message: errorMessage }, 'error', 'entity-details');
                if (characterPanel) displayEntityDetails({ message: errorMessage }, 'error', 'character-details-panel');
                return;
            }
            const details = await response.json();
            if (worldPanel) displayEntityDetails(details, 'character', 'entity-details');
            if (characterPanel) displayEntityDetails(details, 'character', 'character-details-panel');
        } catch (error) {
            console.error('Error fetching character details:', error);
            const errorHtml = '<p class="error">Failed to fetch character details.</p>';
            if (worldPanel) {
                const panel = document.getElementById('entity-details');
                if (panel) panel.innerHTML = errorHtml;
            }
            if (characterPanel) {
                const panel = document.getElementById('character-details-panel');
                if (panel) panel.innerHTML = errorHtml;
            }
        }
    }

    async function loadBuildingDetails(coords, targetPanelId = 'entity-details') {
        setPanelLoading(targetPanelId);
        try {
            const response = await fetch(`${API_BASE_URL}/building_info?x=${coords.x}&y=${coords.y}`);
            if (!response.ok) {
                const panel = document.getElementById(targetPanelId);
                if (panel) panel.innerHTML = `<p class="error">Error fetching details: ${response.status}</p>`;
                return;
            }
            const details = await response.json();
            displayEntityDetails(details, 'building', targetPanelId);
        } catch (error) {
            console.error('Error fetching building details:', error);
            const panel = document.getElementById(targetPanelId);
            if (panel) panel.innerHTML = '<p class="error">Failed to fetch details.</p>';
        }
    }

    async function performControlAction(url) {
        try {
            await fetch(url, { method: 'POST' });
            updateUI();
        } catch (error) {
            console.error('Error performing control action:', error);
        }
    }

    async function updateUI() {
        const gameState = await fetchGameState();
        if (gameState) {
            renderMap(gameState);
            updateEventLog(gameState.event_log);
            updateGameInfo(gameState);
            updateEventFeed(gameState.event_log);
            updateWorldSummary(gameState);
            updateEconomyIntel(gameState);
            renderCharacterList(gameState.characters);
            if (followedCharacterName) {
                loadCharacterDetails(followedCharacterName, { worldPanel: false, characterPanel: true, showLoading: false });
            }
        }
    }

    function handleWheelZoom(event) {
        if (!mapStage) return;
        event.preventDefault();
        const zoomFactor = event.deltaY < 0 ? 1.1 : 0.9;
        const newZoom = Math.min(3, Math.max(0.5, viewportZoom * zoomFactor));
        const rect = mapStage.getBoundingClientRect();
        const cursorX = event.clientX - rect.left;
        const cursorY = event.clientY - rect.top;
        const offsetX = (cursorX - viewportPan.x) / viewportZoom;
        const offsetY = (cursorY - viewportPan.y) / viewportZoom;
        viewportZoom = newZoom;
        viewportPan.x = cursorX - offsetX * viewportZoom;
        viewportPan.y = cursorY - offsetY * viewportZoom;
        updateViewportTransform();
    }

    function beginMapDrag(event) {
        if (event.pointerType === 'mouse' && event.button !== 0) return;
        if (activePointerId !== null) return;
        activePointerId = event.pointerId;
        lastPointerPosition = { x: event.clientX, y: event.clientY };
        mapStage.setPointerCapture(activePointerId);
        autoFollowCamera = false;
    }

    function moveMapDrag(event) {
        if (activePointerId !== event.pointerId) return;
        const deltaX = event.clientX - lastPointerPosition.x;
        const deltaY = event.clientY - lastPointerPosition.y;
        lastPointerPosition = { x: event.clientX, y: event.clientY };
        viewportPan.x += deltaX;
        viewportPan.y += deltaY;
        updateViewportTransform();
    }

    function endMapDrag(event) {
        if (activePointerId !== event.pointerId) return;
        mapStage.releasePointerCapture(activePointerId);
        activePointerId = null;
    }

    function refreshMapLayout() {
        if (!latestGameState) return;
        ensureMapBase(latestGameState);
        updateCharacterMarkers(latestGameState.characters || []);
        updateViewportTransform();
        if (followedCharacterName && autoFollowCamera) {
            const followed = (latestGameState.characters || []).find(char => char.name === followedCharacterName);
            if (followed) {
                centerViewportOn(followed.x, followed.y);
            }
        }
    }

    // --- Event Listeners ---
    overlayButtons.forEach(button => {
        button.addEventListener('click', () => togglePanel(button.dataset.panel));
    });

    panelCloseButtons.forEach(button => {
        button.addEventListener('click', () => closePanel(button.dataset.panel));
    });

    if (characterSearchInput) {
        characterSearchInput.addEventListener('input', () => {
            characterSearchTerm = characterSearchInput.value.trim().toLowerCase();
            if (latestGameState) {
                renderCharacterList(latestGameState.characters || []);
            }
        });
    }

    if (pauseButton) {
        pauseButton.addEventListener('click', () => performControlAction(`${API_BASE_URL}/toggle_pause`));
    }

    speedButtons.forEach(button => {
        button.addEventListener('click', () => {
            performControlAction(`${API_BASE_URL}/set_speed?multiplier=${button.dataset.speed}`);
        });
    });

    if (mapStage) {
        mapStage.addEventListener('pointerdown', beginMapDrag);
        mapStage.addEventListener('pointermove', moveMapDrag);
        mapStage.addEventListener('pointerup', endMapDrag);
        mapStage.addEventListener('pointerleave', endMapDrag);
        mapStage.addEventListener('wheel', handleWheelZoom, { passive: false });
    }

    if (followOverlay) {
        followOverlay.addEventListener('click', () => {
            if (followedCharacterName) {
                autoFollowCamera = true;
                pendingAutoCenter = true;
                if (latestGameState) {
                    const followed = (latestGameState.characters || []).find(char => char.name === followedCharacterName);
                    if (followed) {
                        centerViewportOn(followed.x, followed.y);
                    }
                }
            }
        });
    }

    window.addEventListener('resize', () => {
        refreshMapLayout();
    });

    // --- Initial State ---
    openPanel('hud-panel');
    updateViewportTransform();

    // --- Initial Load & Interval ---
    updateUI();
    setInterval(updateUI, 2000);
});
