document.addEventListener('DOMContentLoaded', () => {
    // --- Element Selectors ---
    const gameStatusHeader = document.getElementById('game-status-header');
    const mapStage = document.getElementById('map-stage');
    const mapCanvas = document.getElementById('map-canvas');
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
    const hudPhaseValue = document.getElementById('hud-phase-value');
    const hudTravelValue = document.getElementById('hud-travel-value');
    const hudElectionValue = document.getElementById('hud-election-value');
    const hudTreasuryValue = document.getElementById('hud-treasury-value');
    const hudRationsValue = document.getElementById('hud-rations-value');
    const hudHydrationValue = document.getElementById('hud-hydration-value');
    const hudHousingValue = document.getElementById('hud-housing-value');
    const hudBadgeWorld = document.getElementById('hud-badge-world');
    const hudBadgeEconomy = document.getElementById('hud-badge-economy');
    const hudBadgeCivic = document.getElementById('hud-badge-civic');
    const hudBadgeFamilies = document.getElementById('hud-badge-families');
    const economyMarketList = document.getElementById('economy-market-list');
    const economyPressureList = document.getElementById('economy-pressure-list');
    const economyWageList = document.getElementById('economy-wage-list');
    const economyCrimeNote = document.getElementById('economy-crime-note');
    const economyCampaignList = document.getElementById('economy-campaign-list');
    const environmentModifierList = document.getElementById('environment-modifier-list');
    const rumorFeedList = document.getElementById('rumor-feed-list');
    const housingStatusList = document.getElementById('housing-status-list');
    const housingStoryList = document.getElementById('housing-story-list');
    const neighborhoodGatheringList = document.getElementById('neighborhood-gathering-list');
    const resourceNodeList = document.getElementById('resource-node-list');
    const populationEventList = document.getElementById('population-event-list');
    const weatherEventNote = document.getElementById('environment-weather-event');
    const workCrewNote = document.getElementById('work-crew-note');
    const workCrewList = document.getElementById('work-crew-list');
    const workShipmentList = document.getElementById('work-shipment-list');
    const trainingNeedsNote = document.getElementById('training-needs-note');
    const trainingSessionList = document.getElementById('training-session-list');
    const trainingWaitlistList = document.getElementById('training-waitlist-list');
    const familySpotlight = document.getElementById('family-spotlight');
    const familyStoriesList = document.getElementById('family-stories-list');
    const familyHouseholdList = document.getElementById('family-household-list');
    const lawCodeList = document.getElementById('law-code-list');
    const lawPetitionList = document.getElementById('law-petition-list');
    const lawInvestigationList = document.getElementById('law-investigation-list');
    const characterSearchInput = document.getElementById('character-search');
    const infoPanel = document.getElementById('info-panel');
    const hudPopoverButtons = document.querySelectorAll('[data-popover-target]');
    const hudPopovers = document.querySelectorAll('.hud-popover');
    const hudPopoverContainer = document.getElementById('hud-popover-container');

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
    let worldBadgeBase = 0;
    let worldBadgeSupplement = 0;

    const characterMarkers = new Map();
    let mapDimensions = { rows: 0, cols: 0 };
    let viewportPan = { x: 0, y: 0 };
    let viewportZoom = 1;
    let activePointerId = null;
    let lastPointerPosition = { x: 0, y: 0 };
    let mapTerrainCache = [];
    let mapOverlayCache = [];
    let mapRevisionStamp = null;

    const rosterCardCache = new Map();
    const rosterState = {
        filtered: [],
        cardHeight: 0,
        renderedStart: -1,
        renderedEnd: -1,
    };
    let rosterWindowEl = null;
    let rosterSpacerTop = null;
    let rosterSpacerBottom = null;

    // --- Utility Helpers ---
    const getTileSize = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--tile-size')) || 48;

    function formatCoins(value) {
        if (typeof value !== 'number' || Number.isNaN(value)) return null;
        return `${Math.round(value).toLocaleString()}c`;
    }

    function formatSatisfaction(value) {
        if (typeof value !== 'number' || Number.isNaN(value)) return '—';
        const percent = Math.max(0, Math.min(100, Math.round(value * 100)));
        return `${percent}%`;
    }

    function updateHudBadge(element, count) {
        if (!element) return;
        const safeCount = Number.isFinite(count) ? Math.max(0, Math.floor(count)) : 0;
        if (safeCount > 0) {
            element.textContent = safeCount > 99 ? '99+' : String(safeCount);
            element.classList.add('active');
        } else {
            element.textContent = '';
            element.classList.remove('active');
        }
    }

    function refreshWorldBadge() {
        updateHudBadge(hudBadgeWorld, worldBadgeBase + worldBadgeSupplement);
    }

    function closeHudPopovers(exceptId = null) {
        hudPopovers.forEach(popover => {
            const shouldOpen = exceptId && popover.id === exceptId;
            popover.classList.toggle('open', shouldOpen);
            popover.setAttribute('aria-hidden', shouldOpen ? 'false' : 'true');
        });
        hudPopoverButtons.forEach(button => {
            const targetId = button.dataset.popoverTarget;
            const expanded = exceptId && targetId === exceptId;
            button.classList.toggle('active', Boolean(expanded));
            button.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        });
    }

    function setupHudPopovers() {
        if (!hudPopoverButtons.length) return;
        hudPopoverButtons.forEach(button => {
            button.setAttribute('aria-expanded', 'false');
            button.addEventListener('click', event => {
                event.stopPropagation();
                const targetId = button.dataset.popoverTarget;
                if (!targetId) return;
                const target = document.getElementById(targetId);
                if (!target) return;
                const isOpen = target.classList.contains('open');
                if (isOpen) {
                    closeHudPopovers(null);
                } else {
                    closeHudPopovers(targetId);
                }
            });
        });

        document.addEventListener('click', event => {
            if (event.target.closest('[data-popover-target]')) return;
            if (event.target.closest('.hud-popover')) return;
            closeHudPopovers(null);
        });

        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                closeHudPopovers(null);
            }
        });

        closeHudPopovers(null);
    }

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

    function initCharacterRosterContainer() {
        if (!characterListDiv || rosterWindowEl) return;
        characterListDiv.classList.add('virtualized-roster');
        characterListDiv.classList.remove('character-grid');
        characterListDiv.innerHTML = '';

        rosterSpacerTop = document.createElement('div');
        rosterSpacerTop.className = 'roster-spacer roster-spacer-top';

        rosterWindowEl = document.createElement('div');
        rosterWindowEl.className = 'roster-window character-grid';

        rosterSpacerBottom = document.createElement('div');
        rosterSpacerBottom.className = 'roster-spacer roster-spacer-bottom';

        characterListDiv.append(rosterSpacerTop, rosterWindowEl, rosterSpacerBottom);
        characterListDiv.addEventListener('scroll', onRosterScroll);
        characterListDiv.addEventListener('click', onRosterClick);
    }

    function onRosterScroll() {
        updateVirtualizedRoster();
    }

    function onRosterClick(event) {
        const card = event.target.closest('.character-card');
        if (!card) return;
        const { charName } = card.dataset;
        if (charName) {
            handleCharacterSelection(charName);
        }
    }

    function getCharacterCard(character) {
        let card = rosterCardCache.get(character.name);
        if (!card) {
            card = document.createElement('article');
            card.classList.add('character-card');
            rosterCardCache.set(character.name, card);
        }
        return card;
    }

    function updateCharacterCardElement(card, character) {
        card.dataset.charName = character.name;
        const goal = extractGoal(character.current_goal).type;
        const loadText = typeof character.inventory_load === 'number' ? ` • Load: ${character.inventory_load}` : '';
        const statusFlags = [];
        if (character.resting_at_home) statusFlags.push('Resting');
        if (typeof character.energy === 'number' && character.energy < 40) statusFlags.push('Fatigued');
        if (typeof character.thirst === 'number' && character.thirst < 40) statusFlags.push('Thirsty');
        const statusSignature = statusFlags.join(',');
        const signature = [
            character.job || 'Unassigned',
            goal,
            character.x,
            character.y,
            loadText,
            statusSignature,
        ].join('|');

        if (card.dataset.signature !== signature) {
            const statusLine = statusFlags.length
                ? `<small class="status-flags">${statusFlags.join(' • ')}</small>`
                : '';
            card.dataset.signature = signature;
            card.innerHTML = `
                <strong>${character.name}</strong>
                <small>${character.job || 'Unassigned'} • Goal: ${goal}</small>
                <small>Pos: (${character.x}, ${character.y})${loadText}</small>
                ${statusLine}
            `;
        }
    }

    function updateVirtualizedRoster(forceMeasure = false) {
        if (!rosterWindowEl) return;
        const filtered = rosterState.filtered;
        if (!filtered.length) return;

        if (forceMeasure) {
            rosterState.cardHeight = 0;
        }

        if (!rosterState.cardHeight) {
            const sampleCharacter = filtered[0];
            const sampleCard = getCharacterCard(sampleCharacter);
            updateCharacterCardElement(sampleCard, sampleCharacter);
            sampleCard.style.position = 'absolute';
            sampleCard.style.visibility = 'hidden';
            sampleCard.style.pointerEvents = 'none';
            sampleCard.style.left = '-9999px';
            rosterWindowEl.appendChild(sampleCard);
            rosterState.cardHeight = Math.max(sampleCard.getBoundingClientRect().height, 72);
            rosterWindowEl.removeChild(sampleCard);
        }

        const cardHeight = rosterState.cardHeight || 1;
        const scrollTop = characterListDiv.scrollTop;
        const viewportHeight = characterListDiv.clientHeight || cardHeight;
        const buffer = 4;
        const startIndex = Math.max(0, Math.floor(scrollTop / cardHeight) - buffer);
        const endIndex = Math.min(
            filtered.length,
            startIndex + Math.ceil(viewportHeight / cardHeight) + buffer * 2,
        );

        rosterState.renderedStart = startIndex;
        rosterState.renderedEnd = endIndex;

        rosterSpacerTop.style.height = `${startIndex * cardHeight}px`;
        rosterSpacerBottom.style.height = `${Math.max(0, (filtered.length - endIndex) * cardHeight)}px`;

        const fragment = document.createDocumentFragment();
        for (let i = startIndex; i < endIndex; i++) {
            const character = filtered[i];
            const card = getCharacterCard(character);
            updateCharacterCardElement(card, character);
            card.classList.toggle('active', character.name === selectedCharacterName);
            card.classList.toggle('following', character.name === followedCharacterName);
            fragment.appendChild(card);
        }

        rosterWindowEl.replaceChildren(fragment);
    }

    function updateEconomyIntel(gameState) {
        if (!gameState) return;
        const report = gameState.daily_economy_report || {};
        const environment = gameState.environment_effects || report.environment || {};
        const housingSnapshot = gameState.housing || report.housing || {};
        const populationSnapshot = gameState.population || report.population_snapshot || {};
        const trainingReport = gameState.training || report.training || {};
        const workforceReport = gameState.workforce || report.workforce || {};
        const governance = gameState.governance || {};
        const neighborhoodGatherings = Array.isArray(housingSnapshot.neighborhood_gatherings)
            ? housingSnapshot.neighborhood_gatherings
            : [];
        let economyBadgeCount = 0;
        let civicBadgeCount = 0;
        let worldBadgeExtras = 0;

        const normalizeCount = (value) => {
            if (Array.isArray(value)) return value.length;
            if (typeof value === 'number' && Number.isFinite(value)) return value;
            return 0;
        };

        const addEconomyCount = (value) => {
            const amount = normalizeCount(value);
            if (amount > 0) {
                economyBadgeCount += amount;
            }
        };

        const addCivicCount = (value) => {
            const amount = normalizeCount(value);
            if (amount > 0) {
                civicBadgeCount += amount;
            }
        };

        const addWorldExtra = (value) => {
            const amount = normalizeCount(value);
            if (amount > 0) {
                worldBadgeExtras += amount;
            }
        };

        addEconomyCount(neighborhoodGatherings.length);

        if (hudPopulationValue) {
            const totalPopulation = typeof populationSnapshot.population === 'number'
                ? populationSnapshot.population
                : Array.isArray(gameState.characters)
                    ? gameState.characters.length
                    : null;
            if (totalPopulation !== null) {
                const births = populationSnapshot.births_today ?? populationSnapshot.births ?? 0;
                const migrants = populationSnapshot.migrants_today ?? populationSnapshot.migrants ?? 0;
                const departures = populationSnapshot.departures_today ?? populationSnapshot.departures ?? 0;
                const deltas = [];
                if (births) deltas.push(`+${births} birth${births === 1 ? '' : 's'}`);
                if (migrants) deltas.push(`+${migrants} arrival${migrants === 1 ? '' : 's'}`);
                if (departures) deltas.push(`-${departures} departure${departures === 1 ? '' : 's'}`);
                hudPopulationValue.textContent = deltas.length
                    ? `${totalPopulation} (${deltas.join(' · ')})`
                    : `${totalPopulation}`;
            } else {
                hudPopulationValue.textContent = '—';
            }
        }

        if (hudTreasuryValue) {
            const treasury = typeof gameState.treasury === 'number' ? gameState.treasury : null;
            hudTreasuryValue.textContent = treasury !== null ? `${treasury}c` : '—';
        }

        if (hudRationsValue) {
            const consumed = typeof report.food_consumed === 'number' ? report.food_consumed : null;
            const required = typeof report.food_required === 'number' ? report.food_required : null;
            const deficit = typeof report.food_deficit === 'number' ? report.food_deficit : 0;
            const yieldModifier = typeof report.food_consumption_modifier === 'number'
                ? report.food_consumption_modifier
                : null;

            let summaryText = '—';
            if (consumed !== null && required !== null) {
                summaryText = `${consumed}/${required}`;
            } else if (consumed !== null) {
                summaryText = `${consumed}`;
            }

            const deficitText = deficit > 0 ? ` • Short ${deficit}` : '';
            const yieldText = yieldModifier ? ` • Yield ×${yieldModifier.toFixed(2)}` : '';
            hudRationsValue.textContent = `${summaryText}${deficitText}${yieldText}`;
        }

        if (hudHydrationValue) {
            const waterConsumed = typeof report.water_consumed === 'number' ? report.water_consumed : null;
            const waterRequired = typeof report.water_required === 'number' ? report.water_required : null;
            const waterDeficit = typeof report.water_deficit === 'number' ? report.water_deficit : 0;
            const waterYield = typeof report.water_consumption_modifier === 'number'
                ? report.water_consumption_modifier
                : null;

            let summaryText = '—';
            if (waterConsumed !== null && waterRequired !== null) {
                summaryText = `${waterConsumed}/${waterRequired}`;
            } else if (waterConsumed !== null) {
                summaryText = `${waterConsumed}`;
            }

            const deficitText = waterDeficit > 0 ? ` • Short ${waterDeficit}` : '';
            const yieldText = waterYield ? ` • Flow ×${waterYield.toFixed(2)}` : '';
            hudHydrationValue.textContent = `${summaryText}${deficitText}${yieldText}`;
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

        if (lawCodeList) {
            const laws = Array.isArray(governance.laws) ? governance.laws : [];
            if (!laws.length) {
                lawCodeList.innerHTML = '<li class="empty">No civic laws enacted.</li>';
            } else {
                lawCodeList.innerHTML = laws
                    .map(law => {
                        const penalty = law.penalty && typeof law.penalty.amount === 'number'
                            ? `${law.penalty.amount}c`
                            : (law.penalty && law.penalty.type) || '—';
                        const status = law.status === 'draft' ? 'Draft' : 'Active';
                        return `<li><strong>${law.title}</strong><small>${status} • ${law.offense || 'General'} • Penalty ${penalty}</small></li>`;
                    })
                    .join('');
            }
        }

        if (lawPetitionList) {
            const petitions = Array.isArray(governance.petitions) ? governance.petitions : [];
            const activePetitions = petitions.filter(petition => petition.status !== 'enacted');
            addCivicCount(activePetitions);
            if (!petitions.length) {
                lawPetitionList.innerHTML = '<li class="empty">No petitions awaiting review.</li>';
            } else {
                lawPetitionList.innerHTML = petitions
                    .map(petition => {
                        const support = typeof petition.support === 'number'
                            ? `${Math.round(petition.support * 100)}%`
                            : '—';
                        const badge = petition.status === 'enacted'
                            ? 'Enacted'
                            : petition.status === 'drafting'
                                ? 'Drafting'
                                : 'Pending';
                        return `<li><strong>${petition.title}</strong><small>${badge} • Support ${support} • Incidents ${petition.incident_count ?? 0}</small></li>`;
                    })
                    .join('');
            }
        }

        if (lawInvestigationList) {
            const interviews = Array.isArray(governance.interviews) ? governance.interviews : [];
            addCivicCount(interviews);
            if (!interviews.length) {
                lawInvestigationList.innerHTML = '<li class="empty">No interviews assigned.</li>';
            } else {
                lawInvestigationList.innerHTML = interviews
                    .map(interview => {
                        const status = interview.status ? interview.status.replace(/_/g, ' ') : 'Pending';
                        const assigned = interview.assigned_to ? ` • ${interview.assigned_to}` : '';
                        return `<li><strong>${interview.witness || 'Witness'}</strong><small>Case ${interview.case_id} • ${status}${assigned}</small></li>`;
                    })
                    .join('');
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
            addEconomyCount(pressures);
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
            addEconomyCount(arrears);
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

        if (weatherEventNote) {
            const weatherEvent = environment.weather_event || gameState.active_weather_event;
            if (weatherEvent && weatherEvent.name) {
                const severity = typeof weatherEvent.severity === 'number' ? `Severity ${weatherEvent.severity}` : null;
                const endDay = typeof weatherEvent.end_day === 'number' ? `Ends Day ${weatherEvent.end_day}` : null;
                const details = [severity, endDay].filter(Boolean).join(' · ');
                weatherEventNote.textContent = details ? `${weatherEvent.name} (${details})` : weatherEvent.name;
                weatherEventNote.classList.remove('muted');
            } else {
                weatherEventNote.textContent = 'Calm skies.';
                weatherEventNote.classList.add('muted');
            }
        }

        if (resourceNodeList) {
            const nodes = Array.isArray(gameState.resource_nodes) ? gameState.resource_nodes : [];
            if (!nodes.length) {
                resourceNodeList.innerHTML = '<li class="empty">No tracked nodes.</li>';
            } else {
                const sortedNodes = nodes
                    .slice()
                    .sort((a, b) => {
                        if (a.depleted === b.depleted) {
                            return (b.durability || 0) - (a.durability || 0);
                        }
                        return a.depleted ? 1 : -1;
                    })
                    .slice(0, 6);
                resourceNodeList.innerHTML = sortedNodes
                    .map(node => {
                        const loc = Array.isArray(node.location) ? node.location.join(',') : '—';
                        const status = node.depleted
                            ? `Regrowth ${(node.regrowth_progress * 100 || 0).toFixed(0)}%`
                            : `${node.durability}/${node.max_durability}`;
                        return `<li><strong>${node.resource}</strong> @ (${loc}) • ${status}</li>`;
                    })
                    .join('');
            }
        }

        if (workCrewNote) {
            const gatheredTotal = typeof workforceReport.gathered_total === 'number' ? workforceReport.gathered_total : 0;
            const deliveredTotal = typeof workforceReport.delivered_total === 'number' ? workforceReport.delivered_total : 0;
            const backlogTotal = typeof workforceReport.backlog_total === 'number' ? workforceReport.backlog_total : 0;
            const alerts = Array.isArray(workforceReport.alerts) ? workforceReport.alerts : [];
            addEconomyCount(alerts);

            if (!gatheredTotal && !deliveredTotal && !backlogTotal && !alerts.length) {
                workCrewNote.textContent = 'Crews waiting on orders.';
                workCrewNote.classList.add('muted');
            } else {
                const fragments = [`Gathered ${gatheredTotal}`, `Delivered ${deliveredTotal}`];
                if (backlogTotal) fragments.push(`Backlog ${backlogTotal}`);
                if (alerts.length) fragments.push(`Alerts: ${alerts.join('; ')}`);
                workCrewNote.textContent = fragments.join(' • ');
                workCrewNote.classList.toggle('muted', false);
            }
        }

        const workCrews = Array.isArray(workforceReport.crews) ? workforceReport.crews : [];

        if (workCrewList) {
            if (!workCrews.length) {
                workCrewList.innerHTML = '<li class="empty">No crews reported.</li>';
            } else {
                const crewItems = workCrews.map((crew) => {
                    const workerCount = Array.isArray(crew.workers) ? crew.workers.length : 0;
                    const haulerCount = Array.isArray(crew.haulers) ? crew.haulers.length : 0;
                    const resourceLabel = crew.resource ? ` ${crew.resource}` : '';
                    const parts = [
                        `${workerCount} worker${workerCount === 1 ? '' : 's'}`,
                    ];
                    if (haulerCount) {
                        parts.push(`${haulerCount} hauler${haulerCount === 1 ? '' : 's'}`);
                    }
                    parts.push(`gathered ${crew.gathered}${resourceLabel}`);
                    parts.push(`delivered ${crew.delivered}`);
                    if (crew.backlog) {
                        parts.push(`backlog ${crew.backlog}`);
                    }
                    const inputsConsumed = crew.inputs_consumed && typeof crew.inputs_consumed === 'object'
                        ? Object.entries(crew.inputs_consumed).filter(([, qty]) => typeof qty === 'number' && qty > 0)
                        : [];
                    if (inputsConsumed.length) {
                        const usedSummary = inputsConsumed
                            .map(([inputName, qty]) => `${qty} ${inputName}`)
                            .join(', ');
                        parts.push(`used ${usedSummary}`);
                    }
                    const details = parts.join(' • ');
                    const notes = Array.isArray(crew.notes) ? crew.notes.join(' • ') : '';
                    const noteHtml = notes ? `<small class="muted">${notes}</small>` : '';
                    return `<li><strong>${crew.title}</strong> — ${details}${noteHtml ? `<br>${noteHtml}` : ''}</li>`;
                });
                workCrewList.innerHTML = crewItems.join('');
            }
        }

        if (workShipmentList) {
            const shipments = Array.isArray(workforceReport.shipments) ? workforceReport.shipments : [];
            const alerts = Array.isArray(workforceReport.alerts) ? workforceReport.alerts : [];
            const entries = [];
            if (shipments.length) {
                shipments.forEach((shipment) => {
                    const crew = workCrews.find((entry) => entry.key === shipment.sector);
                    const label = crew ? crew.title : (shipment.sector || 'Crew');
                    const resource = shipment.resource || 'goods';
                    const delivered = typeof shipment.delivered === 'number' ? shipment.delivered : 0;
                    const routes = Array.isArray(shipment.routes) ? shipment.routes : [];
                    const routeSummary = routes.length
                        ? routes.map((route) => `${route.quantity} → ${route.stockpile}`).join(', ')
                        : 'No storage available';
                    entries.push(`<li>${label}: ${delivered} ${resource} (${routeSummary})</li>`);
                });
            }
            if (alerts.length) {
                alerts.forEach((alert) => {
                    entries.push(`<li class="alert">${alert}</li>`);
                });
            }
            if (!entries.length) {
                workShipmentList.innerHTML = '<li class="empty">No deliveries dispatched.</li>';
            } else {
                workShipmentList.innerHTML = entries.join('');
            }
        }

        if (trainingSessionList) {
            const activeSessions = Array.isArray(trainingReport.active_sessions)
                ? trainingReport.active_sessions
                : [];
            if (!activeSessions.length) {
                trainingSessionList.innerHTML = '<li class="empty">No active sessions.</li>';
            } else {
                trainingSessionList.innerHTML = activeSessions
                    .slice(0, 4)
                    .map(session => {
                        const progressText = typeof session.progress === 'number' && typeof session.duration === 'number'
                            ? `Day ${session.progress}/${session.duration}`
                            : `Day ${session.progress ?? 0}`;
                        const instructor = session.instructor ? `Led by ${session.instructor}` : 'No instructor';
                        const trainees = Array.isArray(session.trainees) && session.trainees.length
                            ? session.trainees.join(', ')
                            : 'No trainees';
                        return `
                            <li>
                                <strong>${session.program}</strong>
                                <div class="meta">${progressText} • ${instructor} • ${trainees}</div>
                            </li>
                        `;
                    })
                    .join('');
            }
        }

        if (trainingWaitlistList) {
            const waitlists = Array.isArray(trainingReport.waitlists) ? trainingReport.waitlists : [];
            const queued = waitlists.filter(entry => Array.isArray(entry.queued) && entry.queued.length);
            const queuedCount = queued.reduce((sum, entry) => sum + (Array.isArray(entry.queued) ? entry.queued.length : 0), 0);
            addEconomyCount(queuedCount);
            if (!queued.length) {
                trainingWaitlistList.innerHTML = '<li class="empty">No one queued.</li>';
            } else {
                trainingWaitlistList.innerHTML = queued
                    .slice(0, 4)
                    .map(entry => {
                        const names = entry.queued.slice(0, 4).join(', ');
                        const count = typeof entry.count === 'number' ? entry.count : entry.queued.length;
                        return `
                            <li>
                                <strong>${entry.program}</strong>: ${count} waiting
                                <div class="meta">${names}</div>
                            </li>
                        `;
                    })
                    .join('');
            }
        }

        if (trainingNeedsNote) {
            const needs = Array.isArray(trainingReport.assessed_needs) ? trainingReport.assessed_needs : [];
            const flagged = needs
                .filter(entry => (entry.under_target || 0) > 0)
                .sort((a, b) => (b.under_target || 0) - (a.under_target || 0));
            addEconomyCount(flagged);
            if (!flagged.length) {
                trainingNeedsNote.textContent = 'No programs flagged.';
                trainingNeedsNote.classList.add('muted');
            } else {
                const summary = flagged
                    .slice(0, 3)
                    .map(entry => {
                        const avg = typeof entry.avg_level === 'number'
                            ? entry.avg_level.toFixed(1)
                            : '—';
                        const waiting = entry.under_target || 0;
                        return `${entry.program}: avg ${avg} • ${waiting} behind`;
                    })
                    .join(' | ');
                trainingNeedsNote.textContent = summary;
                trainingNeedsNote.classList.remove('muted');
            }
        }

        if (populationEventList) {
            const popEvents = Array.isArray(report.population_events) ? report.population_events : [];
            addWorldExtra(popEvents);
            if (!popEvents.length) {
                populationEventList.innerHTML = '<li class="empty">No changes today.</li>';
            } else {
                const recentEvents = popEvents.slice(-5).reverse();
                populationEventList.innerHTML = recentEvents
                    .map(event => {
                        if (event.type === 'birth') {
                            return `<li>Birth: <strong>${event.name}</strong> (parent ${event.parent || 'unknown'})</li>`;
                        }
                        if (event.type === 'arrival') {
                            return `<li>Arrival: <strong>${event.name}</strong> joins as ${event.job || 'laborer'}.</li>`;
                        }
                        if (event.type === 'departure') {
                            return `<li>Departure: <strong>${event.name}</strong> left (${event.reason || 'unknown'}).</li>`;
                        }
                        return `<li>${event.summary || 'Population change recorded.'}</li>`;
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
            addEconomyCount(homelessNames.length);

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
                const tierLabel = structure.tier ? String(structure.tier) : '';
                const amenities = Array.isArray(structure.amenities) ? structure.amenities : [];
                const amenityPreview = amenities.length
                    ? `${amenities.slice(0, 2).join(', ')}${amenities.length > 2 ? '…' : ''}`
                    : '';
                const metaParts = [`${available} open`];
                if (occupantPreview && occupantPreview !== 'Vacant') {
                    metaParts.push(occupantPreview);
                }
                const statusLine = metaParts.join(' • ');
                const amenityLine = amenityPreview ? `<span class="meta subtle">${amenityPreview}</span>` : '';
                const tierBadge = tierLabel ? `<span class="tier-label tier-${tierLabel}">${tierLabel}</span>` : '';
                lines.push(`
                    <li class="${className}">
                        <strong>${structure.name}</strong>${tierBadge ? ` ${tierBadge}` : ''}: ${used}/${capacity} beds
                        <span class="meta">${statusLine}</span>
                        ${amenityLine}
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

        if (housingStoryList) {
            const stories = Array.isArray(housingSnapshot.household_vignettes)
                ? housingSnapshot.household_vignettes
                : [];
            if (stories.length) {
                const recent = stories.slice(-4).reverse();
                housingStoryList.innerHTML = recent
                    .map(story => {
                        const summary = story.summary || 'Evening passed quietly.';
                        const buildingName = story.building || 'Household';
                        const dayLabel = typeof story.day === 'number' ? `Day ${story.day}` : 'Today';
                        return `
                            <li>
                                <strong>${buildingName}</strong>: ${summary}
                                <span class="meta subtle">${dayLabel}</span>
                            </li>
                        `.trim();
                    })
                    .join('');
            } else {
                housingStoryList.innerHTML = '<li class="empty">No household stories recorded today.</li>';
            }
        }

        if (neighborhoodGatheringList) {
            if (neighborhoodGatherings.length) {
                const recentGatherings = neighborhoodGatherings.slice(-4).reverse();
                neighborhoodGatheringList.innerHTML = recentGatherings
                    .map(gathering => {
                        const summary = gathering.summary || 'Neighbors spent time together.';
                        const hostLabel = gathering.host || 'Neighbor';
                        const dayLabel = typeof gathering.day === 'number' ? `Day ${gathering.day}` : 'Recent';
                        return `
                            <li>
                                <strong>${hostLabel}</strong>: ${summary}
                                <span class="meta subtle">${dayLabel}</span>
                            </li>
                        `.trim();
                    })
                    .join('');
            } else {
                neighborhoodGatheringList.innerHTML = '<li class="empty">No neighborhood gatherings yet.</li>';
            }
        }

        if (economyCrimeNote) {
            const reportCrimes = Array.isArray(report.crime_events) ? report.crime_events : [];
            const historyCrimes = Array.isArray(gameState.crime_reports) ? gameState.crime_reports : [];
            const pendingCrimes = Array.isArray(gameState.pending_crimes) ? gameState.pending_crimes : [];
            addCivicCount(pendingCrimes);
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
            const outstandingPromises = allPromises.filter(promise => promise.status !== 'enacted');
            addCivicCount(outstandingPromises);

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
            addWorldExtra(rumors);
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

        worldBadgeSupplement = worldBadgeExtras;
        refreshWorldBadge();
        updateHudBadge(hudBadgeEconomy, economyBadgeCount);
        updateHudBadge(hudBadgeCivic, civicBadgeCount);
    }

    function updateFamilyIntel(gameState) {
        if (!familySpotlight && !familyStoriesList && !familyHouseholdList) return;
        const snapshot = (gameState && gameState.families) || {};
        const families = Array.isArray(snapshot.families) ? snapshot.families : [];
        const recentHistory = Array.isArray(snapshot.recent_history) ? snapshot.recent_history : [];
        const familyById = new Map(families.map(family => [family.family_id, family]));

        if (familyHouseholdList) {
            if (!families.length) {
                familyHouseholdList.innerHTML = '<li class="empty">No families registered.</li>';
            } else {
                familyHouseholdList.innerHTML = families.slice(0, 5).map(family => {
                    const members = Array.isArray(family.members) && family.members.length
                        ? family.members.join(', ')
                        : 'No members listed.';
                    const tagline = family.tagline || 'Household';
                    const memberCount = Array.isArray(family.members) ? family.members.length : 0;
                    const lineagePreview = Array.isArray(family.lineage_preview) && family.lineage_preview.length
                        ? family.lineage_preview.join(' • ')
                        : null;
                    const metaParts = [`${memberCount} member${memberCount === 1 ? '' : 's'}`];
                    if (lineagePreview) {
                        metaParts.push(lineagePreview);
                    }
                    const meta = `<div class="meta">${metaParts.join(' • ')}</div>`;
                    return `
                        <li>
                            <strong>${tagline}</strong>
                            <div>${members}</div>
                            ${meta}
                        </li>
                    `;
                }).join('');
            }
        }

        if (familyStoriesList) {
            if (!recentHistory.length) {
                familyStoriesList.innerHTML = '<li class="empty">No family events recorded.</li>';
            } else {
                familyStoriesList.innerHTML = recentHistory.slice(-6).reverse().map(event => {
                    const dayLabel = typeof event.day === 'number' ? `Day ${event.day}` : 'Day —';
                    const family = familyById.get(event.family_id);
                    const familyLabel = family ? (family.tagline || (family.members || []).join(', ')) : (event.family_id || 'Household');
                    const summary = event.summary || 'No details recorded.';
                    const typeLabel = event.type ? event.type.replace(/_/g, ' ') : 'Event';
                    const source = event.source ? `<div class="meta">${typeLabel} • ${event.source}</div>` : `<div class="meta">${typeLabel}</div>`;
                    return `
                        <li>
                            <strong>${dayLabel}</strong> • ${familyLabel}
                            <div>${summary}</div>
                            ${source}
                        </li>
                    `;
                }).join('');
            }
        }

        if (familySpotlight) {
            if (!recentHistory.length) {
                familySpotlight.textContent = 'No family stories logged.';
            } else {
                const latest = recentHistory[recentHistory.length - 1];
                const dayLabel = typeof latest.day === 'number' ? `Day ${latest.day}` : 'Day —';
                const family = familyById.get(latest.family_id);
                const familyLabel = family ? (family.tagline || (family.members || []).join(', ')) : (latest.family_id || 'Household');
                const summary = latest.summary || 'No details recorded.';
                familySpotlight.textContent = `${dayLabel}: ${summary} (${familyLabel})`;
            }
        }

        updateHudBadge(hudBadgeFamilies, recentHistory.length);
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
        updateVirtualizedRoster();
    }

    function positionFollowOverlay(character) {
        if (!followOverlay || !mapStage || !character) return;
        const marker = characterMarkers.get(character.name);
        if (!marker) return;

        requestAnimationFrame(() => {
            const markerRect = marker.getBoundingClientRect();
            const stageRect = mapStage.getBoundingClientRect();
            const overlayRect = followOverlay.getBoundingClientRect();
            const offset = 16;

            let top = markerRect.top - stageRect.top - overlayRect.height / 2 + markerRect.height / 2;
            top = Math.max(16, Math.min(top, stageRect.height - overlayRect.height - 16));

            let left = markerRect.right - stageRect.left + offset;
            if (left + overlayRect.width + 16 > stageRect.width) {
                left = markerRect.left - stageRect.left - overlayRect.width - offset;
            }
            left = Math.max(16, Math.min(left, stageRect.width - overlayRect.width - 16));

            followOverlay.style.top = `${top}px`;
            followOverlay.style.left = `${left}px`;
            followOverlay.style.right = 'auto';
        });
    }

    function updateFollowedCharacterOverlay(character) {
        if (!followOverlay || !followOverlayBody) return;

        if (!character || character.name !== followedCharacterName) {
            followOverlay.classList.add('hidden');
            followOverlayBody.innerHTML = '<p>Select a character to follow.</p>';
            followOverlay.style.top = '';
            followOverlay.style.left = '';
            followOverlay.style.right = '';
            return;
        }

        followOverlay.classList.remove('hidden');
        const sicknessText = character.is_sick ? `Sick${character.sickness_severity !== undefined ? ` (sev ${character.sickness_severity})` : ''}` : 'Well';
        const injuryText = character.is_injured ? `Injured${character.injury_severity !== undefined ? ` (sev ${character.injury_severity})` : ''}` : 'Unhurt';
        const goalDetails = extractGoal(character.current_goal);
        const goalSummary = `${goalDetails.type}${goalDetails.priority !== '—' ? ` (prio ${goalDetails.priority})` : ''}`;
        const energyText = typeof character.energy === 'number' ? character.energy : '—';
        const thirstText = typeof character.thirst === 'number' ? character.thirst : '—';
        const housingSummary = character.resting_at_home
            ? 'Resting at assigned housing'
            : Array.isArray(character.home_location)
                ? `Sheltered at (${character.home_location[0]}, ${character.home_location[1]})`
                : 'No assigned housing';
        const ageText = typeof character.age === 'number' ? `${character.age}` : '—';
        const originText = character.origin || 'Unknown origin';
        const citizenshipText = character.citizenship || 'Resident';
        const rankTitle = character.rank ? character.rank : null;
        const netWorthValue = formatCoins(character.net_worth);
        const netWorthText = netWorthValue
            ? `${netWorthValue}${character.wealth_status ? ` (${character.wealth_status})` : ''}`
            : 'Unknown';
        const purseText = formatCoins(character.money) || '—';
        const careerStage = character.career_stage || 'Apprentice';
        const tenureValue = typeof character.profession_tenure === 'number' ? character.profession_tenure : null;
        const tenureText = tenureValue !== null ? `${tenureValue} day${tenureValue === 1 ? '' : 's'}` : '—';
        const satisfactionText = formatSatisfaction(character.job_satisfaction);
        const focusSuffix = character.profession_focus ? ` • Focus ${character.profession_focus}` : '';

        const ownedVentures = Array.isArray(character.businesses_owned) ? character.businesses_owned : [];
        const businessRoles = Object.entries(character.business_roles || {});
        const businessLines = [];
        if (ownedVentures.length) {
            businessLines.push(`Owns ${ownedVentures.length} venture${ownedVentures.length === 1 ? '' : 's'}`);
        }
        businessRoles.forEach(([businessId, role]) => {
            const label = role.replace(/_/g, ' ');
            businessLines.push(`${label} @ ${businessId}`);
        });
        const businessSummary = businessLines.length
            ? `<ul class="mini-list">${businessLines.slice(0, 4).map(line => `<li>${line}</li>`).join('')}</ul>`
            : '<p class="muted">No active business roles.</p>';

        const familyMembers = Array.isArray(character.family_members)
            ? character.family_members.filter(name => name && name !== character.name)
            : [];
        let familySummary = '<p class="muted">No immediate kin registered.</p>';
        if (familyMembers.length) {
            const preview = familyMembers.slice(0, 5);
            const remainder = familyMembers.length - preview.length;
            const namesText = preview.join(', ');
            familySummary = `<p>${namesText}${remainder > 0 ? `, +${remainder} more` : ''}</p>`;
        }

        const romanticPartners = Array.isArray(character.romantic_partners)
            ? character.romantic_partners.filter(name => name && name !== character.name)
            : [];
        const courtingEntries = character.active_romances && typeof character.active_romances === 'object'
            ? Object.entries(character.active_romances)
            : [];
        const courtingPreview = courtingEntries.slice(0, 3).map(([name, details]) => {
            const compat = details && typeof details.compatibility === 'number'
                ? `${Math.round(details.compatibility * 100)}%`
                : '—';
            return `${name} (${compat})`;
        });
        const partnerSummary = romanticPartners.length ? romanticPartners.join(', ') : 'None';
        const courtingSummary = courtingPreview.length ? courtingPreview.join(', ') : 'None';

        const highlights = Array.isArray(character.life_highlights) ? character.life_highlights : [];
        const highlightSummary = highlights.length
            ? `<ul class="mini-list compact">${highlights.slice(-3).reverse().map(evt => {
                const when = evt.day !== undefined ? `Day ${evt.day}` : (evt.type || 'Milestone');
                const summary = evt.summary || evt.type || 'Notable moment recorded.';
                return `<li><strong>${when}</strong>: ${summary}</li>`;
            }).join('')}</ul>`
            : '<p class="muted">No highlights logged.</p>';

        followOverlayBody.innerHTML = `
            <p><strong>${character.name}</strong>${rankTitle ? ` • ${rankTitle}` : ''}</p>
            <p>${character.job || 'Unassigned'} • Goal: ${goalSummary}</p>
            <p>Stage: ${careerStage} • Tenure ${tenureText} • Satisfaction ${satisfactionText}${focusSuffix}</p>
            <p>Coords: (${character.x}, ${character.y}) • Age ${ageText} • ${originText} • ${citizenshipText}</p>
            <p>Health: ${sicknessText}, ${injuryText}</p>
            <p>Needs: Energy ${energyText} • Thirst ${thirstText}</p>
            <p>Housing: ${housingSummary}</p>
            <hr>
            <p><strong>Wealth</strong></p>
            <p>Net Worth ${netWorthText} • Purse ${purseText}</p>
            ${businessSummary}
            <hr>
            <p><strong>Family</strong></p>
            ${familySummary}
            <p><strong>Relationships</strong></p>
            <p>Partners: ${partnerSummary}</p>
            <p>Courtships: ${courtingSummary}</p>
            <hr>
            <p><strong>Highlights</strong></p>
            ${highlightSummary}
        `;

        positionFollowOverlay(character);
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
        if (hudPhaseValue) {
            const phase = environment.phase || gameState.current_phase || {};
            if (phase && (phase.name || phase.key)) {
                const phaseName = phase.name || String(phase.key).replace(/_/g, ' ');
                const tickLabel = typeof phase.tick === 'number' ? `Tick ${phase.tick}` : '';
                hudPhaseValue.textContent = tickLabel ? `${phaseName} (${tickLabel})` : phaseName;
            } else {
                hudPhaseValue.textContent = '—';
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
        const phase = (gameState.environment_effects && gameState.environment_effects.phase)
            || gameState.current_phase
            || {};
        if (phase && (phase.name || phase.key)) {
            metaParts.push(phase.name || String(phase.key).replace(/_/g, ' '));
        }
        if (gridSize.length === 2) {
            metaParts.push(`${gridSize[0]}×${gridSize[1]} grid`);
        }
        metaParts.push(`${population} citizen${population === 1 ? '' : 's'}`);
        if (buildingsCount) {
            metaParts.push(`${buildingsCount} structure${buildingsCount === 1 ? '' : 's'}`);
        }
        const weatherEvent = (gameState.environment_effects && gameState.environment_effects.weather_event)
            || gameState.active_weather_event;
        if (weatherEvent && weatherEvent.name) {
            metaParts.push(`${weatherEvent.name}`);
        }
        mapMeta.textContent = metaParts.join(' • ');
    }

    function updateEventFeed(log) {
        if (!eventFeedDiv) return;
        const count = Array.isArray(log) ? log.length : 0;
        worldBadgeBase = count;
        refreshWorldBadge();
        if (!count) {
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
        updateVirtualizedRoster();
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

    function renderLifeEventList(events, limit = 10, emptyMessage = 'No events recorded.') {
        const list = document.createElement('ul');
        list.classList.add('mini-list');

        if (!events || !events.length) {
            const empty = document.createElement('li');
            empty.classList.add('empty');
            empty.textContent = emptyMessage;
            list.appendChild(empty);
            return list;
        }

        const slice = events.slice(-limit).reverse();
        slice.forEach(event => {
            const li = document.createElement('li');
            const dayLabel = typeof event.day === 'number' ? `Day ${event.day}` : 'Day —';
            const typeLabel = event.type ? event.type.replace(/_/g, ' ') : 'Event';
            const summary = event.summary || 'No details recorded.';

            const metaParts = [];
            if (event.source) {
                metaParts.push(`Source: ${event.source}`);
            }
            const related = Array.isArray(event.related) ? event.related.filter(name => name && name !== event.source) : [];
            if (related.length) {
                metaParts.push(`With ${related.join(', ')}`);
            }
            const metaHtml = metaParts.length ? `<div class="meta">${metaParts.join(' • ')}</div>` : '';

            const tags = Array.isArray(event.tags) ? event.tags : [];
            const tagHtml = tags.length
                ? `<div class="event-tags">${tags.slice(0, 5).map(tag => `<span>${tag}</span>`).join('')}</div>`
                : '';

            li.innerHTML = `
                <strong>${dayLabel}</strong> • ${typeLabel}
                <div>${summary}</div>
                ${metaHtml}
                ${tagHtml}
            `;
            list.appendChild(li);
        });

        return list;
    }

    function renderLineageDetails(lineage) {
        const panel = document.createElement('div');
        panel.classList.add('lineage-panel');

        const heading = document.createElement('h5');
        heading.textContent = 'Lineage web';
        panel.appendChild(heading);

        const list = document.createElement('dl');
        list.classList.add('lineage-grid');

        Object.entries(lineage)
            .sort(([a], [b]) => a.localeCompare(b))
            .forEach(([member, ties]) => {
                const term = document.createElement('dt');
                term.textContent = member;
                list.appendChild(term);

                const desc = document.createElement('dd');
                if (ties && Object.keys(ties).length) {
                    const fragments = Object.entries(ties).map(([role, names]) => {
                        const label = role.replace(/_/g, ' ');
                        const formatted = Array.isArray(names) ? names.join(', ') : String(names);
                        return `<span><strong>${label}:</strong> ${formatted}</span>`;
                    });
                    desc.innerHTML = fragments.join(' • ');
                } else {
                    desc.textContent = 'No documented ties yet.';
                }
                list.appendChild(desc);
            });

        panel.appendChild(list);
        return panel;
    }

    function buildOverviewContent(character) {
        const wrapper = document.createElement('div');

        const profileSection = document.createElement('section');
        profileSection.innerHTML = '<h4>Profile</h4>';
        const ageLabel = typeof character.age === 'number' ? character.age : '—';
        const originLabel = character.origin || 'Unknown';
        const citizenshipLabel = character.citizenship || 'Resident';
        const rankLabel = character.rank ? ` • ${character.rank}` : '';
        const netWorthLabel = formatCoins(character.net_worth);
        const purseLabel = formatCoins(character.money);
        profileSection.innerHTML += `
            <p><strong>Role:</strong> ${character.job || 'Unassigned'}${rankLabel}</p>
            <p><strong>Age:</strong> ${ageLabel} • <strong>Origin:</strong> ${originLabel} • <strong>Citizenship:</strong> ${citizenshipLabel}</p>
            <p><strong>Wealth:</strong> ${netWorthLabel ? netWorthLabel : 'Unknown'}${character.wealth_status ? ` (${character.wealth_status})` : ''} • <strong>Purse:</strong> ${purseLabel || '—'}</p>
        `;

        const careerSection = document.createElement('section');
        careerSection.innerHTML = '<h4>Career</h4>';
        const stageLabel = character.career_stage || 'Apprentice';
        const tenureDisplay = typeof character.profession_tenure === 'number'
            ? `${character.profession_tenure} day${character.profession_tenure === 1 ? '' : 's'}`
            : '—';
        const satisfactionDisplay = formatSatisfaction(character.job_satisfaction);
        const focusDisplay = character.profession_focus || 'Generalist';
        careerSection.innerHTML += `
            <p><strong>Stage:</strong> ${stageLabel} • <strong>Tenure:</strong> ${tenureDisplay}</p>
            <p><strong>Satisfaction:</strong> ${satisfactionDisplay} • <strong>Focus:</strong> ${focusDisplay}</p>
        `;
        const careerHistory = Array.isArray(character.profession_history) ? character.profession_history : [];
        if (careerHistory.length) {
            const list = document.createElement('ul');
            list.classList.add('mini-list', 'compact', 'subtle');
            careerHistory.slice(-5).reverse().forEach(entry => {
                const li = document.createElement('li');
                const jobLabel = entry.job || 'Unassigned';
                const stage = entry.stage || '—';
                const tenure = typeof entry.tenure === 'number' ? `${entry.tenure}d` : '—';
                const startDay = typeof entry.start_day === 'number' ? `Day ${entry.start_day}` : null;
                const endDay = typeof entry.end_day === 'number' ? `Day ${entry.end_day}` : null;
                const period = entry.status === 'current'
                    ? (startDay ? `${startDay} → present` : 'current post')
                    : (startDay && endDay ? `${startDay} → ${endDay}` : endDay ? `ended ${endDay}` : 'concluded');
                const statusTag = entry.status === 'current' ? ' • current' : '';
                li.innerHTML = `<strong>${jobLabel}</strong> • ${stage} • ${tenure}${period ? ` • ${period}` : ''}${statusTag}`;
                list.appendChild(li);
            });
            careerSection.appendChild(list);
        } else {
            const empty = document.createElement('p');
            empty.classList.add('muted');
            empty.textContent = 'No recorded career history yet.';
            careerSection.appendChild(empty);
        }

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

        const venturesSection = document.createElement('section');
        venturesSection.innerHTML = '<h4>Ventures</h4>';
        const ventureLines = [];
        (character.businesses_owned || []).forEach(name => {
            ventureLines.push(`Owner • ${name}`);
        });
        Object.entries(character.business_roles || {}).forEach(([businessId, role]) => {
            ventureLines.push(`${role.replace(/_/g, ' ')} • ${businessId}`);
        });
        if (ventureLines.length) {
            const list = document.createElement('ul');
            list.classList.add('mini-list');
            ventureLines.forEach(line => {
                const li = document.createElement('li');
                li.textContent = line;
                list.appendChild(li);
            });
            venturesSection.appendChild(list);
        } else {
            const empty = document.createElement('p');
            empty.textContent = 'No current business roles.';
            venturesSection.appendChild(empty);
        }

        const wealthHistorySection = document.createElement('section');
        wealthHistorySection.innerHTML = '<h4>Wealth Trend</h4>';
        const history = Array.isArray(character.wealth_history) ? character.wealth_history : [];
        if (history.length) {
            const list = document.createElement('ul');
            list.classList.add('mini-list', 'compact', 'subtle');
            history.slice(-6).reverse().forEach(entry => {
                const li = document.createElement('li');
                const day = typeof entry.day === 'number' ? entry.day : '—';
                const worth = formatCoins(entry.net_worth);
                li.innerHTML = `<strong>Day ${day}</strong>: ${worth || '—'}`;
                list.appendChild(li);
            });
            wealthHistorySection.appendChild(list);
        } else {
            const empty = document.createElement('p');
            empty.textContent = 'No wealth records logged yet.';
            wealthHistorySection.appendChild(empty);
        }

        wrapper.append(profileSection, careerSection, needsSection, housingSection, skillsSection, inventorySection, venturesSection, wealthHistorySection);
        return wrapper;
    }

    function buildSocialContent(character) {
        const wrapper = document.createElement('div');

        const familySection = document.createElement('section');
        familySection.innerHTML = '<h4>Family</h4>';
        const familyProfile = character.family_profile;
        if (familyProfile && Array.isArray(familyProfile.members) && familyProfile.members.length) {
            if (familyProfile.tagline) {
                const tagline = document.createElement('p');
                tagline.classList.add('mini-note');
                tagline.textContent = familyProfile.tagline;
                familySection.appendChild(tagline);
            }
            const membersPara = document.createElement('p');
            membersPara.innerHTML = `<strong>Members:</strong> ${familyProfile.members.join(', ')}`;
            familySection.appendChild(membersPara);
            if (familyProfile.role_snapshot && Object.keys(familyProfile.role_snapshot).length) {
                const rolesBlock = document.createElement('div');
                rolesBlock.classList.add('mini-note');
                const roleParts = Object.entries(familyProfile.role_snapshot).map(([role, names]) => `${role}: ${names.join(', ')}`);
                rolesBlock.innerHTML = `<strong>Roles:</strong> ${roleParts.join(' • ')}`;
                familySection.appendChild(rolesBlock);
            }
            if (familyProfile.lineage && Object.keys(familyProfile.lineage).length) {
                familySection.appendChild(renderLineageDetails(familyProfile.lineage));
            }
            const sharedMoments = renderLifeEventList(familyProfile.latest_events || [], 4, 'No shared moments logged.');
            familySection.appendChild(sharedMoments);
        } else {
            familySection.innerHTML += '<p>No registered family ties.</p>';
        }

        const romanceSection = document.createElement('section');
        romanceSection.innerHTML = '<h4>Romance & Partnerships</h4>';
        const partners = Array.isArray(character.romantic_partners)
            ? character.romantic_partners.filter(name => name && name !== character.name)
            : [];
        const courtships = character.active_romances && typeof character.active_romances === 'object'
            ? Object.entries(character.active_romances)
            : [];
        const exPartners = Array.isArray(character.ex_partners)
            ? character.ex_partners.filter(name => name && name !== character.name)
            : [];
        const children = Array.isArray(character.children)
            ? character.children
            : (Array.isArray(character.children_names) ? character.children_names : []);
        const parents = Array.isArray(character.parents)
            ? character.parents
            : (Array.isArray(character.parent_names) ? character.parent_names : []);

        const partnerPara = document.createElement('p');
        partnerPara.innerHTML = `<strong>Partners:</strong> ${partners.length ? partners.join(', ') : 'None'}`;
        romanceSection.appendChild(partnerPara);

        const courtingList = document.createElement('div');
        courtingList.classList.add('mini-note');
        if (courtships.length) {
            const list = document.createElement('ul');
            list.classList.add('mini-list', 'compact');
            courtships.forEach(([name, details]) => {
                const li = document.createElement('li');
                const compat = details && typeof details.compatibility === 'number'
                    ? `${Math.round(details.compatibility * 100)}%`
                    : '—';
                const since = details && typeof details.since_day === 'number'
                    ? ` • since Day ${details.since_day}`
                    : '';
                li.textContent = `${name} (${compat})${since}`;
                list.appendChild(li);
            });
            courtingList.appendChild(list);
        } else {
            courtingList.textContent = 'No active courtships.';
        }
        romanceSection.appendChild(courtingList);

        if (exPartners.length) {
            const exPara = document.createElement('p');
            exPara.innerHTML = `<strong>Former partners:</strong> ${exPartners.join(', ')}`;
            romanceSection.appendChild(exPara);
        }

        if (character.marriage_history && character.marriage_history.length) {
            const historyList = document.createElement('ul');
            historyList.classList.add('mini-list', 'compact');
            character.marriage_history.slice(-5).reverse().forEach(entry => {
                const li = document.createElement('li');
                const partnerName = entry.partner || 'Unknown';
                const status = entry.status || 'history';
                const dayText = typeof entry.day === 'number' ? `Day ${entry.day}` : 'Unknown day';
                const endText = entry.ended_day !== undefined ? ` • ended Day ${entry.ended_day}` : '';
                li.textContent = `${dayText}: ${partnerName} (${status})${endText}`;
                historyList.appendChild(li);
            });
            romanceSection.appendChild(historyList);
        }

        if (children.length) {
            const childrenPara = document.createElement('p');
            childrenPara.innerHTML = `<strong>Children:</strong> ${children.join(', ')}`;
            romanceSection.appendChild(childrenPara);
        }
        if (parents.length) {
            const parentsPara = document.createElement('p');
            parentsPara.innerHTML = `<strong>Parents:</strong> ${parents.join(', ')}`;
            romanceSection.appendChild(parentsPara);
        }

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

        wrapper.append(familySection, romanceSection, knownSection, relationshipsSection, opinionsSection, dialogueSection);
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

        const highlightsSection = document.createElement('section');
        highlightsSection.innerHTML = '<h4>Life Highlights</h4>';
        highlightsSection.appendChild(renderLifeEventList(character.life_highlights || [], 6, 'No highlights logged.'));

        const chronicleSection = document.createElement('section');
        chronicleSection.innerHTML = '<h4>Life Chronicle</h4>';
        chronicleSection.appendChild(renderLifeEventList(character.life_history || [], 12, 'No life events recorded.'));

        wrapper.append(goalSection, placementSection, historySection, highlightsSection, chronicleSection);
        return wrapper;
    }

    function buildCharacterDetails(character) {
        const wrapper = document.createElement('section');
        wrapper.classList.add('detail-tabs');

        const header = document.createElement('header');
        const stageLabel = character.career_stage ? ` • ${character.career_stage}` : '';
        const satisfactionLabel = formatSatisfaction(character.job_satisfaction);
        const reputationLabel = character.reputation ?? '—';
        header.innerHTML = `
            <h3>${character.name}</h3>
            <p>${character.job || 'Unassigned'}${stageLabel} • Reputation ${reputationLabel} • Satisfaction ${satisfactionLabel}</p>
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

    function abbreviateTileName(name) {
        if (typeof name !== 'string' || !name.length) return '';
        const spaced = name.replace(/([a-z])([A-Z])/g, '$1 $2');
        const parts = spaced.split(/\s+/).filter(Boolean);
        if (!parts.length) return name.slice(0, 2).toUpperCase();
        return parts
            .map(part => part.charAt(0))
            .join('')
            .slice(0, 3)
            .toUpperCase();
    }

    function buildBuildingPlan(tileLayout) {
        if (!Array.isArray(tileLayout) || !tileLayout.length) return null;
        const plan = document.createElement('div');
        plan.classList.add('building-plan');
        tileLayout.forEach(row => {
            const rowEl = document.createElement('div');
            rowEl.classList.add('building-plan-row');
            const cells = Array.isArray(row) ? row : [];
            cells.forEach(tileName => {
                const cellEl = document.createElement('div');
                cellEl.classList.add('building-plan-cell');
                if (tileName) {
                    const safeName = String(tileName);
                    cellEl.classList.add('tile-chip');
                    cellEl.classList.add(`tile-${safeName}`);
                    cellEl.textContent = abbreviateTileName(safeName);
                    cellEl.title = safeName.replace(/([a-z])([A-Z])/g, '$1 $2');
                } else {
                    cellEl.classList.add('empty');
                }
                rowEl.appendChild(cellEl);
            });
            plan.appendChild(rowEl);
        });
        return plan;
    }

    function buildBuildingDetails(building) {
        const wrapper = document.createElement('div');
        wrapper.classList.add('building-details');

        const heading = document.createElement('h3');
        heading.textContent = building.display_name || building.structure_type || 'Structure';
        wrapper.appendChild(heading);

        const dl = document.createElement('dl');
        dl.innerHTML = `
            <dt>Type</dt><dd>${building.structure_type || 'Unknown'}</dd>
            <dt>Operational</dt><dd>${building.is_operational ? 'Yes' : 'No'}</dd>
        `;
        if (typeof building.provides_shelter === 'number') {
            dl.innerHTML += `<dt>Shelter Capacity</dt><dd>${building.provides_shelter}</dd>`;
        }
        if (building.wealth_tier) {
            dl.innerHTML += `<dt>Wealth Tier</dt><dd class="tier-text tier-${building.wealth_tier}">${building.wealth_tier}</dd>`;
        }
        if (building.household_style) {
            dl.innerHTML += `<dt>Household Style</dt><dd>${building.household_style}</dd>`;
        }
        if (Array.isArray(building.amenities) && building.amenities.length) {
            dl.innerHTML += `<dt>Amenities</dt><dd>${building.amenities.join(', ')}</dd>`;
        }
        if (Array.isArray(building.occupants)) {
            const occupants = building.occupants.length
                ? building.occupants.join(', ')
                : 'None';
            dl.innerHTML += `<dt>Occupants</dt><dd>${occupants}</dd>`;
        }
        wrapper.appendChild(dl);

        if (Array.isArray(building.occupant_profiles) && building.occupant_profiles.length) {
            const occupantSection = document.createElement('section');
            occupantSection.classList.add('building-occupants');
            occupantSection.innerHTML = '<h4>Residents</h4>';
            const list = document.createElement('ul');
            list.classList.add('mini-list', 'compact');
            building.occupant_profiles.forEach(profile => {
                const job = profile.job || 'Unassigned';
                const wealth = profile.wealth_status ? ` • ${profile.wealth_status}` : '';
                const mood = profile.mood ? ` • Mood: ${profile.mood}` : '';
                list.innerHTML += `
                    <li>
                        <strong>${profile.name}</strong> — ${job}${wealth}${mood}
                    </li>
                `;
            });
            occupantSection.appendChild(list);
            wrapper.appendChild(occupantSection);
        }

        if (Array.isArray(building.tile_layout) && building.tile_layout.length) {
            const plan = buildBuildingPlan(building.tile_layout);
            if (plan) {
                const planSection = document.createElement('section');
                planSection.classList.add('building-plan-section');
                planSection.innerHTML = '<h4>Floor Plan</h4>';
                planSection.appendChild(plan);
                wrapper.appendChild(planSection);
            }
        }

        if (building.latest_household_story) {
            const story = building.latest_household_story;
            const storySection = document.createElement('section');
            storySection.classList.add('building-story');
            const dayLabel = typeof story.day === 'number' ? `Day ${story.day}` : 'Recent';
            storySection.innerHTML = `
                <h4>Recent Evening</h4>
                <p>${story.summary || 'A quiet night passed.'}</p>
                <p class="meta subtle">${dayLabel}</p>
            `;
            wrapper.appendChild(storySection);
        }

        if (building.latest_neighborhood_story) {
            const story = building.latest_neighborhood_story;
            const section = document.createElement('section');
            section.classList.add('building-story');
            const dayLabel = typeof story.day === 'number' ? `Day ${story.day}` : 'Recent';
            const neighborhood = story.neighborhood || 'Neighborhood';
            section.innerHTML = `
                <h4>Neighborhood Highlight</h4>
                <p>${story.summary || 'Neighbors gathered nearby.'}</p>
                <p class="meta subtle">${neighborhood} • ${dayLabel}</p>
            `;
            wrapper.appendChild(section);
        }

        return wrapper;
    }

    function displayEntityDetails(entity, type, targetPanelId) {
        const targetPanel = document.getElementById(targetPanelId || 'entity-details');
        if (!targetPanel) return;

        targetPanel.innerHTML = '';

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
            const details = buildBuildingDetails(entity);
            if (entity.inventory) {
                const inventorySection = document.createElement('section');
                inventorySection.classList.add('building-inventory');
                inventorySection.innerHTML = `<h4>Inventory</h4><pre>${JSON.stringify(entity.inventory, null, 2)}</pre>`;
                details.appendChild(inventorySection);
            }
            targetPanel.appendChild(details);
            openPanel('info-panel');
            return;
        }
        openPanel('info-panel');
    }

    function updateViewportTransform() {
        if (!mapViewport) return;
        mapViewport.style.transform = `translate(${viewportPan.x}px, ${viewportPan.y}px) scale(${viewportZoom})`;
        if (followedCharacterName) {
            positionFollowOverlay({ name: followedCharacterName });
        }
    }

    function centerViewportOn(x, y) {
        const surface = mapCanvas || mapStage;
        if (!surface || !mapViewport) return;
        const tileSize = getTileSize();
        const surfaceRect = surface.getBoundingClientRect();
        const targetX = (x + 0.5) * tileSize;
        const targetY = (y + 0.5) * tileSize;
        viewportPan.x = surfaceRect.width / 2 - targetX * viewportZoom;
        viewportPan.y = surfaceRect.height / 2 - targetY * viewportZoom;
        updateViewportTransform();
    }

    function ensureMapBase(gameState) {
        if (!mapGridDiv || !mapCharactersLayer || !gameState || !Array.isArray(gameState.grid)) return;
        const gridSize = Array.isArray(gameState.grid_size) ? gameState.grid_size : [0, 0];
        const [rows, cols] = gridSize;
        if (!rows || !cols) return;

        const needsRebuild = rows !== mapDimensions.rows || cols !== mapDimensions.cols || mapGridDiv.childElementCount === 0;
        const totalCells = rows * cols;

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

        const incomingRevision = typeof gameState.map_revision === 'number' ? gameState.map_revision : null;
        const revisionChanged = incomingRevision !== null && incomingRevision !== mapRevisionStamp;
        if (needsRebuild || revisionChanged || mapTerrainCache.length !== totalCells || mapOverlayCache.length !== totalCells) {
            mapTerrainCache = new Array(totalCells).fill(null);
            mapOverlayCache = new Array(totalCells).fill(null);
        }
        mapRevisionStamp = incomingRevision;

        const tileSize = getTileSize();
        const width = cols * tileSize;
        const height = rows * tileSize;
        mapViewport.style.width = `${width}px`;
        mapViewport.style.height = `${height}px`;
        mapCharactersLayer.style.width = `${width}px`;
        mapCharactersLayer.style.height = `${height}px`;

        const cells = mapGridDiv.children;
        for (let r = 0; r < rows; r++) {
            const tileRow = gameState.grid[r] || [];
            for (let c = 0; c < cols; c++) {
                const index = r * cols + c;
                const cell = cells[index];
                if (!cell) continue;
                const tileType = tileRow[c] || 'Unknown';
                if (mapTerrainCache[index] !== tileType) {
                    const previousClass = cell.dataset.terrainClass;
                    if (previousClass) {
                        cell.classList.remove(previousClass);
                    }
                    const tileClass = `tile-${tileType.replace(/\s+/g, '-')}`;
                    cell.classList.add(tileClass);
                    cell.dataset.terrainClass = tileClass;
                    mapTerrainCache[index] = tileType;
                }
                cell.dataset.baseTitle = tileType;
                if (!cell.dataset.buildingName) {
                    cell.title = `${tileType} (${c}, ${r})`;
                }
            }
        }

        const nextOverlayCache = new Array(totalCells).fill(null);
        (gameState.buildings || []).forEach(building => {
            const originX = building.x ?? 0;
            const originY = building.y ?? 0;
            const widthCells = building.width ?? 1;
            const heightCells = building.height ?? 1;
            const overlayType = building.structure_type === 'Stockpile' ? 'stockpile' : 'building';
            const label = building.display_name || building.structure_type || 'Structure';
            const rawType = building.structure_type || label;
            const slug = rawType
                ? String(rawType).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
                : '';
            const tier = building.wealth_tier || '';
            const style = building.household_style || '';
            const signature = JSON.stringify({ overlayType, label, originX, originY, slug, tier, style });
            for (let r = 0; r < heightCells; r++) {
                for (let c = 0; c < widthCells; c++) {
                    const x = originX + c;
                    const y = originY + r;
                    if (x < 0 || y < 0 || x >= cols || y >= rows) continue;
                    const index = y * cols + x;
                    nextOverlayCache[index] = signature;
                }
            }
        });

        for (let index = 0; index < totalCells; index++) {
            const cell = cells[index];
            if (!cell) continue;
            const prevSignature = mapOverlayCache[index];
            const nextSignature = nextOverlayCache[index];
            if (prevSignature === nextSignature && !needsRebuild) {
                continue;
            }

            if (prevSignature && prevSignature !== nextSignature) {
                cell.classList.remove('building-cell', 'stockpile-cell', 'building-origin');
                delete cell.dataset.building;
                delete cell.dataset.buildingOriginX;
                delete cell.dataset.buildingOriginY;
                delete cell.dataset.buildingName;
                delete cell.dataset.buildingType;
                if (cell.dataset.buildingTierClass) {
                    cell.classList.remove(cell.dataset.buildingTierClass);
                    delete cell.dataset.buildingTierClass;
                }
                delete cell.dataset.householdStyle;
                const baseTitle = cell.dataset.baseTitle || mapTerrainCache[index] || 'Unknown';
                const x = index % cols;
                const y = Math.floor(index / cols);
                cell.title = `${baseTitle} (${x}, ${y})`;
            }

            if (!nextSignature) {
                if (!prevSignature && needsRebuild) {
                    const x = index % cols;
                    const y = Math.floor(index / cols);
                    const baseTitle = cell.dataset.baseTitle || mapTerrainCache[index] || 'Unknown';
                    cell.title = `${baseTitle} (${x}, ${y})`;
                }
                continue;
            }

            let overlayDescriptor;
            try {
                overlayDescriptor = JSON.parse(nextSignature);
            } catch (error) {
                overlayDescriptor = null;
            }
            if (!overlayDescriptor) {
                continue;
            }
            const { overlayType, label, originX, originY, slug, tier, style } = overlayDescriptor;
            const isStockpile = overlayType === 'stockpile';
            cell.classList.toggle('stockpile-cell', isStockpile);
            cell.classList.toggle('building-cell', !isStockpile);
            cell.dataset.building = 'true';
            cell.dataset.buildingOriginX = originX;
            cell.dataset.buildingOriginY = originY;
            cell.dataset.buildingName = label;
            if (slug) {
                cell.dataset.buildingType = slug;
            } else {
                delete cell.dataset.buildingType;
            }
            if (tier) {
                const tierClass = `building-tier-${tier}`;
                if (cell.dataset.buildingTierClass && cell.dataset.buildingTierClass !== tierClass) {
                    cell.classList.remove(cell.dataset.buildingTierClass);
                }
                cell.classList.add(tierClass);
                cell.dataset.buildingTierClass = tierClass;
            } else if (cell.dataset.buildingTierClass) {
                cell.classList.remove(cell.dataset.buildingTierClass);
                delete cell.dataset.buildingTierClass;
            }
            if (style) {
                cell.dataset.householdStyle = style;
            } else {
                delete cell.dataset.householdStyle;
            }
            const x = index % cols;
            const y = Math.floor(index / cols);
            cell.classList.toggle('building-origin', x === originX && y === originY);
            cell.title = `${label} (${x}, ${y})`;
        }

        mapOverlayCache = nextOverlayCache;
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
        initCharacterRosterContainer();

        const sortedCharacters = [...characters].sort((a, b) => a.name.localeCompare(b.name));
        const searchTerm = characterSearchTerm.trim().toLowerCase();
        const filteredCharacters = sortedCharacters.filter(char => {
            if (!searchTerm) return true;
            const haystack = `${char.name} ${char.job} ${extractGoal(char.current_goal).type}`.toLowerCase();
            return haystack.includes(searchTerm);
        });

        rosterState.filtered = filteredCharacters;
        rosterState.renderedStart = -1;
        rosterState.renderedEnd = -1;

        const visibleNames = new Set(filteredCharacters.map(char => char.name));
        for (const name of rosterCardCache.keys()) {
            if (!visibleNames.has(name)) {
                rosterCardCache.delete(name);
            }
        }

        if (!filteredCharacters.length) {
            rosterWindowEl.innerHTML = '<div class="empty-state">No citizens match your search.</div>';
            rosterSpacerTop.style.height = '0px';
            rosterSpacerBottom.style.height = '0px';
            rosterState.cardHeight = 0;
            return;
        }

        characterListDiv.scrollTop = Math.min(characterListDiv.scrollTop, filteredCharacters.length * (rosterState.cardHeight || 1));
        updateVirtualizedRoster(true);
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
            const response = await fetch(url, { method: 'GET' });
            if (!response.ok) {
                console.error(`Control action failed (${response.status}): ${url}`);
                return;
            }
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
            updateFamilyIntel(gameState);
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
        const surfaceElement = mapCanvas || mapStage;
        if (!surfaceElement) return;
        const surfaceRect = surfaceElement.getBoundingClientRect();
        const cursorX = event.clientX - surfaceRect.left;
        const cursorY = event.clientY - surfaceRect.top;
        const offsetX = (cursorX - viewportPan.x) / viewportZoom;
        const offsetY = (cursorY - viewportPan.y) / viewportZoom;
        viewportZoom = newZoom;
        viewportPan.x = cursorX - offsetX * viewportZoom;
        viewportPan.y = cursorY - offsetY * viewportZoom;
        updateViewportTransform();
    }

    function beginMapDrag(event) {
        const dragSurface = mapCanvas || mapStage;
        if (!dragSurface) return;
        if (event.pointerType === 'mouse' && event.button !== 0) return;
        if (activePointerId !== null) return;
        activePointerId = event.pointerId;
        lastPointerPosition = { x: event.clientX, y: event.clientY };
        dragSurface.setPointerCapture(activePointerId);
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
        const dragSurface = mapCanvas || mapStage;
        if (dragSurface) {
            dragSurface.releasePointerCapture(activePointerId);
        }
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

    const dragSurface = mapCanvas || mapStage;
    if (dragSurface) {
        dragSurface.addEventListener('pointerdown', beginMapDrag);
        dragSurface.addEventListener('pointermove', moveMapDrag);
        dragSurface.addEventListener('pointerup', endMapDrag);
        dragSurface.addEventListener('pointerleave', endMapDrag);
        dragSurface.addEventListener('wheel', handleWheelZoom, { passive: false });
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

    setupHudPopovers();

    // --- Initial State ---
    updateViewportTransform();

    // --- Initial Load & Interval ---
    updateUI();
    setInterval(updateUI, 2000);
});
