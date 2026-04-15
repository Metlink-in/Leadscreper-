const API_BASE = "http://localhost:8000";
const HIGH_VALUE_REGIONS = ["USA", "United Kingdom", "Canada", "Australia", "UAE", "Germany", "Singapore"];

let state = {
    leads: [],
    category: "Direct Clients",
    engine: "ddgs",
    loading: false
};

// DOM Elements
const elements = {
    requirement: document.getElementById('requirement'),
    location: document.getElementById('location'),
    engine: document.getElementById('engine'),
    searchBtn: document.getElementById('search-btn'),
    searchIcon: document.getElementById('search-icon'),
    btnText: document.getElementById('btn-text'),
    leadsGrid: document.getElementById('leads-grid'),
    emptyState: document.getElementById('empty-state'),
    toolsBar: document.getElementById('tools-bar'),
    resultsCount: document.getElementById('results-count'),
    presetList: document.getElementById('preset-list'),
    tabs: document.querySelectorAll('.tab'),
    modal: document.getElementById('modal-overlay'),
    closeModal: document.getElementById('close-modal'),
    openModal: document.getElementById('export-sheets'),
    sheetsForm: document.getElementById('sheets-form'),
    sheetIdInput: document.getElementById('sheet-id'),
    exportStatus: document.getElementById('export-status'),
    exportCsv: document.getElementById('export-csv'),
    exportJson: document.getElementById('export-json')
};

// Initialization
function init() {
    renderPresets();
    setupEventListeners();
}

function renderPresets() {
    HIGH_VALUE_REGIONS.forEach(region => {
        const btn = document.createElement('button');
        btn.className = 'preset-btn';
        btn.textContent = region;
        btn.onclick = () => {
            elements.location.value = region;
        };
        elements.presetList.appendChild(btn);
    });
}

function setupEventListeners() {
    // Search
    elements.searchBtn.onclick = handleSearch;

    // Tabs
    elements.tabs.forEach(tab => {
        tab.onclick = () => {
            elements.tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            state.category = tab.dataset.category;
            elements.requirement.placeholder = `Search for ${state.category.toLowerCase()}...`;
        };
    });

    // Engine
    elements.engine.onchange = (e) => {
        state.engine = e.target.value;
    };

    // Modal
    elements.openModal.onclick = () => elements.modal.classList.remove('hidden');
    elements.closeModal.onclick = () => elements.modal.classList.add('hidden');
    window.onclick = (e) => { if (e.target === elements.modal) elements.modal.classList.add('hidden'); };

    // Sheet Export
    elements.sheetsForm.onsubmit = handleSheetsExport;

    // Direct Export
    elements.exportCsv.onclick = exportToCSV;
    elements.exportJson.onclick = exportToJSON;
}

async function handleSearch() {
    const requirement = elements.requirement.value.trim();
    if (!requirement) return alert("Please enter a requirement.");

    setLoading(true);
    
    try {
        // Step 1: Refine
        const refineRes = await fetch(`${API_BASE}/refine-query?requirement=${encodeURIComponent(requirement)}&category=${encodeURIComponent(state.category)}`);
        const { query } = await refineRes.json();

        // Step 2: Search
        const location = elements.location.value.trim();
        const searchRes = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}&location=${encodeURIComponent(location)}&engine=${state.engine}`);
        const data = await searchRes.json();

        state.leads = data.leads;
        renderLeads();
    } catch (err) {
        console.error(err);
        alert("Search failed. Ensure backend is running.");
    } finally {
        setLoading(false);
    }
}

function setLoading(isLoading) {
    state.loading = isLoading;
    elements.searchBtn.disabled = isLoading;
    if (isLoading) {
        elements.searchIcon.setAttribute('data-lucide', 'loader-2');
        elements.searchIcon.classList.add('spin');
        elements.btnText.textContent = "AI Tuning...";
    } else {
        elements.searchIcon.setAttribute('data-lucide', 'search');
        elements.searchIcon.classList.remove('spin');
        elements.btnText.textContent = "Launch Scraper";
    }
    lucide.createIcons();
}

function renderLeads() {
    elements.leadsGrid.innerHTML = '';
    
    if (state.leads.length > 0) {
        elements.emptyState.classList.add('hidden');
        elements.toolsBar.classList.remove('hidden');
        elements.resultsCount.textContent = `Found ${state.leads.length} Potential Leads`;

        state.leads.forEach((lead, idx) => {
            const card = document.createElement('div');
            card.className = 'glass lead-card';
            card.style.animationDelay = `${idx * 0.05}s`;
            
            card.innerHTML = `
                <div class="lead-header">
                    <h3 class="lead-title">${lead.title}</h3>
                    <div class="lead-rating">
                        <i data-lucide="star" style="fill: #fbbf24; stroke: none;"></i>
                        ${lead.rating || 'N/A'}
                    </div>
                </div>
                <div class="lead-info">
                    <i data-lucide="map-pin"></i>
                    <span>${lead.address || 'Location Hidden'}</span>
                </div>
                ${lead.phone ? `
                <div class="lead-info">
                    <i data-lucide="phone"></i>
                    <span>${lead.phone}</span>
                </div>` : ''}
                <div class="lead-links">
                    ${lead.website ? `
                    <a href="${lead.website}" target="_blank" class="lead-link">
                        <i data-lucide="globe"></i> Site
                    </a>` : `
                    <span class="no-website">No Website (Hot)</span>`}
                    <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(lead.title + ' ' + (lead.address || ''))}" target="_blank" class="lead-link">
                        <i data-lucide="external-link"></i> Maps
                    </a>
                </div>
            `;
            elements.leadsGrid.appendChild(card);
        });
        lucide.createIcons();
    } else {
        elements.emptyState.classList.remove('hidden');
        elements.toolsBar.classList.add('hidden');
    }
}

// Exports
function exportToCSV() {
    const headers = ["Title", "Address", "Phone", "Website", "Rating", "Type"];
    const rows = state.leads.map(l => [
        `"${l.title}"`,
        `"${l.address || ''}"`,
        `"${l.phone || ''}"`,
        `"${l.website || ''}"`,
        l.rating || '0',
        state.category
    ].join(","));
    
    const csv = [headers.join(","), ...rows].join("\n");
    downloadFile(csv, `leads_${Date.now()}.csv`, 'text/csv');
}

function exportToJSON() {
    downloadFile(JSON.stringify(state.leads, null, 2), `leads_${Date.now()}.json`, 'application/json');
}

function downloadFile(content, filename, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
}

async function handleSheetsExport(e) {
    e.preventDefault();
    const sheetId = elements.sheetIdInput.value.trim();
    if (!sheetId) return;

    elements.exportStatus.textContent = "Syncing...";
    try {
        const response = await fetch(`${API_BASE}/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                leads: state.leads,
                spreadsheet_id: sheetId
            })
        });
        const data = await response.json();
        if (data.error) throw new Error(data.error);
        
        elements.exportStatus.textContent = "Success! Data synced.";
        setTimeout(() => {
            elements.modal.classList.add('hidden');
            elements.exportStatus.textContent = "";
        }, 2000);
    } catch (err) {
        alert("Export failed: " + err.message);
        elements.exportStatus.textContent = "";
    }
}

init();
