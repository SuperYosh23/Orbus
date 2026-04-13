// Orbus Launcher - Electron Frontend Application

// State
let instances = {};
let currentInstance = null;
let settings = {};
let minecraftVersions = [];
let fabricVersions = [];
let dragSrcEl = null;

// DOM Elements
const elements = {
    instancesList: document.getElementById('instances-list'),
    noInstanceView: document.getElementById('no-instance-view'),
    instanceView: document.getElementById('instance-view'),
    instanceName: document.getElementById('instance-name'),
    usernameInput: document.getElementById('username-input'),
    versionSelect: document.getElementById('version-select'),
    loaderSelect: document.getElementById('loader-select'),
    loaderVersionGroup: document.getElementById('loader-version-group'),
    loaderVersionSelect: document.getElementById('loader-version-select'),
    javaInput: document.getElementById('java-input'),
    ramSlider: document.getElementById('ram-slider'),
    ramValue: document.getElementById('ram-value'),
    ramPercent: document.getElementById('ram-percent'),
    showLogsCheckbox: document.getElementById('show-logs-checkbox'),
    statusText: document.getElementById('status-text'),
    launchProgress: document.getElementById('launch-progress'),
    launchBtn: document.getElementById('launch-btn'),
    
    // Modals
    modrinthModal: document.getElementById('modrinth-modal'),
    settingsModal: document.getElementById('settings-modal'),
    javaModal: document.getElementById('java-modal'),
    
    // Modrinth
    modrinthSearch: document.getElementById('modrinth-search'),
    modrinthResults: document.getElementById('modrinth-results'),
    modrinthLoading: document.getElementById('modrinth-loading'),
};

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await loadData();
    setupEventListeners();
    setupModals();
    setupDragAndDrop();
});

// Load initial data
async function loadData() {
    try {
        // Load instances
        const instancesResult = await window.electronAPI.getInstances();
        if (instancesResult.success) {
            instances = instancesResult.data;
            renderInstances();
        }
        
        // Load settings
        const settingsResult = await window.electronAPI.getSettings();
        if (settingsResult.success) {
            settings = settingsResult.data;
            applySettings();
        }
        
        // Load versions
        loadVersions();
    } catch (error) {
        console.error('Error loading data:', error);
    }
}

async function loadVersions() {
    try {
        const [versionsResult, fabricResult] = await Promise.all([
            window.electronAPI.getVersions(),
            window.electronAPI.getFabricVersions()
        ]);
        
        if (versionsResult.success) {
            minecraftVersions = versionsResult.data;
            populateVersionSelect();
        }
        
        if (fabricResult.success) {
            fabricVersions = fabricResult.data;
            populateLoaderVersionSelect();
        }
    } catch (error) {
        console.error('Error loading versions:', error);
    }
}

// Render instances list
function renderInstances() {
    elements.instancesList.innerHTML = '';
    
    Object.keys(instances).forEach((name, index) => {
        const instance = instances[name];
        const item = document.createElement('div');
        item.className = 'instance-item';
        item.draggable = true;
        item.dataset.name = name;
        item.dataset.index = index;
        
        if (name === currentInstance) {
            item.classList.add('active');
        }
        
        const iconHtml = instance.icon_path 
            ? `<img src="file://${instance.icon_path}" class="instance-icon" alt="">`
            : `<div class="instance-icon-placeholder">🎮</div>`;
        
        item.innerHTML = `
            ${iconHtml}
            <span class="instance-name">${name}</span>
        `;
        
        item.addEventListener('click', () => selectInstance(name));
        item.addEventListener('contextmenu', (e) => showContextMenu(e, name));
        
        // Drag events
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragover', handleDragOver);
        item.addEventListener('drop', handleDrop);
        item.addEventListener('dragend', handleDragEnd);
        
        elements.instancesList.appendChild(item);
    });
}

// Select instance
async function selectInstance(name) {
    if (!instances[name]) return;
    
    // Clear any pending poll timeout from previous instance
    if (pollTimeoutId) {
        clearTimeout(pollTimeoutId);
        pollTimeoutId = null;
    }
    
    currentInstance = name;
    const instance = instances[name];
    
    // Update UI
    elements.noInstanceView.style.display = 'none';
    elements.instanceView.style.display = 'flex';
    elements.instanceName.textContent = name;
    
    // Populate fields
    elements.usernameInput.value = instance.username || '';
    elements.versionSelect.value = instance.version || '1.21.1';
    elements.loaderSelect.value = instance.loader || 'Vanilla';
    elements.loaderVersionSelect.value = instance.loader_version || 'latest';
    elements.javaInput.value = instance.java_path || '';
    elements.ramSlider.value = instance.ram || 4;
    elements.showLogsCheckbox.checked = instance.show_console_logs || false;
    
    updateRamDisplay();
    toggleLoaderSettings();
    
    // Check if instance is running and update button (single check, no retries)
    try {
        console.log(`[Select] Checking status for: ${name}`);
        const result = await window.electronAPI.isInstanceRunning(name);
        console.log(`[Select] Status result:`, result);
        updateLaunchButtonState(result.running);
        if (result.running) {
            pollInstanceStatus();
        }
    } catch (error) {
        console.error('[Select] Error checking instance status:', error);
        updateLaunchButtonState(false);
    }
    
    // Update active state in list
    renderInstances();
}

// Populate version select
function populateVersionSelect() {
    elements.versionSelect.innerHTML = minecraftVersions
        .map(v => `<option value="${v}">${v}</option>`)
        .join('');
}

// Populate loader version select
function populateLoaderVersionSelect() {
    elements.loaderVersionSelect.innerHTML = fabricVersions
        .map(v => `<option value="${v}">${v}</option>`)
        .join('');
}

// Update RAM display
function updateRamDisplay() {
    const value = elements.ramSlider.value;
    elements.ramValue.textContent = `${value} GB`;
    elements.ramPercent.textContent = `${Math.round((value / 16) * 100)}%`;
}

// Toggle loader settings visibility
function toggleLoaderSettings() {
    const loader = elements.loaderSelect.value;
    if (loader === 'Fabric') {
        elements.loaderVersionGroup.style.display = 'block';
    } else {
        elements.loaderVersionGroup.style.display = 'none';
    }
}

// Save current instance
async function saveCurrentInstance() {
    if (!currentInstance) return;
    
    const data = {
        username: elements.usernameInput.value,
        version: elements.versionSelect.value,
        loader: elements.loaderSelect.value,
        loader_version: elements.loaderVersionSelect.value,
        java_path: elements.javaInput.value,
        ram: parseInt(elements.ramSlider.value),
        show_console_logs: elements.showLogsCheckbox.checked
    };
    
    try {
        await window.electronAPI.updateInstance(currentInstance, data);
        instances[currentInstance] = { ...instances[currentInstance], ...data };
    } catch (error) {
        console.error('Error saving instance:', error);
    }
}

// Event listeners
function setupEventListeners() {
    // Instance actions
    document.getElementById('add-instance-btn').addEventListener('click', addInstance);
    document.getElementById('rename-btn').addEventListener('click', renameInstance);
    document.getElementById('delete-btn').addEventListener('click', deleteInstance);
    document.getElementById('change-icon-btn').addEventListener('click', changeInstanceIcon);
    
    // Sidebar actions
    document.getElementById('import-btn').addEventListener('click', importModpack);
    document.getElementById('browse-modrinth-btn').addEventListener('click', openModrinthBrowser);
    document.getElementById('settings-btn').addEventListener('click', openSettings);
    
    // Settings changes
    elements.usernameInput.addEventListener('change', saveCurrentInstance);
    elements.versionSelect.addEventListener('change', saveCurrentInstance);
    elements.loaderSelect.addEventListener('change', () => {
        toggleLoaderSettings();
        saveCurrentInstance();
    });
    elements.loaderVersionSelect.addEventListener('change', saveCurrentInstance);
    elements.javaInput.addEventListener('change', saveCurrentInstance);
    elements.showLogsCheckbox.addEventListener('change', saveCurrentInstance);
    
    // RAM slider
    elements.ramSlider.addEventListener('input', updateRamDisplay);
    elements.ramSlider.addEventListener('change', saveCurrentInstance);
    
    // Java buttons (instance settings)
    document.getElementById('auto-java-btn').addEventListener('click', openJavaDetector);
    document.getElementById('browse-java-btn').addEventListener('click', async () => {
        const result = await window.electronAPI.selectJava();
        if (!result.canceled && result.filePaths.length > 0) {
            elements.javaInput.value = result.filePaths[0];
            saveCurrentInstance();
        }
    });
    
    // Default Java buttons (settings modal)
    document.getElementById('default-auto-java-btn').addEventListener('click', async () => {
        const javaList = document.getElementById('java-list');
        const scanningDiv = document.getElementById('java-scanning');
        const resultsDiv = document.getElementById('java-results');
        
        scanningDiv.style.display = 'flex';
        resultsDiv.style.display = 'none';
        openModal('java-modal');
        
        try {
            const result = await window.electronAPI.getJavaInstallations(false);
            scanningDiv.style.display = 'none';
            resultsDiv.style.display = 'block';
            
            if (result.success && result.data.length > 0) {
                javaList.innerHTML = result.data.map(java => `
                    <div class="java-item">
                        <div class="java-info">
                            <div class="java-version">Java ${java.version} (${java.arch})</div>
                            <div class="java-path">${java.path}</div>
                        </div>
                        <button class="viso-btn viso-btn-primary viso-btn-sm select-default-java-btn" data-path="${java.path}">Select</button>
                    </div>
                `).join('');
                
                javaList.querySelectorAll('.select-default-java-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        document.getElementById('default-java-input').value = btn.dataset.path;
                        closeModal('java-modal');
                    });
                });
            } else {
                javaList.innerHTML = '<p class="viso-body" style="text-align: center;">No Java installations found.</p>';
            }
        } catch (error) {
            scanningDiv.style.display = 'none';
            resultsDiv.style.display = 'block';
            javaList.innerHTML = '<p class="viso-body" style="text-align: center; color: var(--viso-red);">Error scanning for Java.</p>';
        }
    });
    
    document.getElementById('default-browse-java-btn').addEventListener('click', async () => {
        const result = await window.electronAPI.selectJava();
        if (!result.canceled && result.filePaths.length > 0) {
            document.getElementById('default-java-input').value = result.filePaths[0];
        }
    });
    
    // Folder buttons
    document.getElementById('open-folder-btn').addEventListener('click', async () => {
        if (currentInstance) {
            await window.electronAPI.openFolder(`instances/${currentInstance}`);
        }
    });
    
    document.getElementById('open-mods-btn').addEventListener('click', async () => {
        if (currentInstance) {
            await window.electronAPI.openFolder(`instances/${currentInstance}/mods`);
        }
    });
    
    // Launch button
    elements.launchBtn.addEventListener('click', launchGame);
    
    // Settings modal
    document.getElementById('settings-save').addEventListener('click', saveSettings);
    document.getElementById('settings-reset').addEventListener('click', resetSettings);
    
    // Tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
    
    // Modrinth search
    document.getElementById('modrinth-search-btn').addEventListener('click', searchModrinth);
    elements.modrinthSearch.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchModrinth();
    });
    
    // Deep scan button
    document.getElementById('deep-scan-btn').addEventListener('click', () => scanJava(true));
}

// Modal handling
function setupModals() {
    // Close modals on backdrop click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-backdrop') || e.target.classList.contains('modal-close')) {
                modal.style.display = 'none';
            }
        });
    });
}

function openModal(modalId) {
    document.getElementById(modalId).style.display = 'flex';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Instance management
async function addInstance() {
    const baseName = 'New Instance';
    let name = baseName;
    let counter = 1;
    
    while (instances[name]) {
        name = `${baseName} (${counter})`;
        counter++;
    }
    
    const data = {
        username: settings.default_username || '',
        version: '1.21.1',
        loader: 'Vanilla',
        loader_version: 'latest',
        ram: 4,
        java_path: '',
        show_console_logs: false
    };
    
    try {
        const result = await window.electronAPI.createInstance(name, data);
        if (result.success) {
            instances[name] = data;
            renderInstances();
            selectInstance(name);
        }
    } catch (error) {
        console.error('Error creating instance:', error);
    }
}

async function renameInstance() {
    if (!currentInstance) {
        console.log('Rename: No instance selected');
        return;
    }
    
    const newName = prompt(`Rename "${currentInstance}" to:`, currentInstance);
    console.log(`Rename: Prompt returned "${newName}"`);
    
    if (!newName) {
        console.log('Rename: Cancelled or empty name');
        return;
    }
    if (newName === currentInstance) {
        console.log('Rename: Same name');
        return;
    }
    if (instances[newName]) {
        alert(`Instance "${newName}" already exists!`);
        return;
    }
    
    try {
        console.log(`Rename: Calling API with old="${currentInstance}", new="${newName}"`);
        const result = await window.electronAPI.renameInstance(currentInstance, newName);
        console.log('Rename: API result:', result);
        
        if (result.success) {
            instances[newName] = instances[currentInstance];
            delete instances[currentInstance];
            currentInstance = newName;
            renderInstances();
            selectInstance(newName);
            console.log('Rename: Success');
        } else {
            console.error('Rename: Failed:', result.error);
            alert(`Rename failed: ${result.error}`);
        }
    } catch (error) {
        console.error('Rename: Error:', error);
        alert(`Rename error: ${error.message}`);
    }
}

async function deleteInstance() {
    if (!currentInstance) {
        console.log('Delete: No instance selected');
        return;
    }
    
    if (!confirm(`Are you sure you want to delete "${currentInstance}"?`)) return;
    
    console.log(`Deleting instance: ${currentInstance}`);
    try {
        const result = await window.electronAPI.deleteInstance(currentInstance);
        console.log('Delete result:', result);
        if (result.success) {
            delete instances[currentInstance];
            currentInstance = null;
            renderInstances();
            elements.instanceView.style.display = 'none';
            elements.noInstanceView.style.display = 'flex';
            console.log('Instance deleted successfully');
        } else {
            console.error('Delete failed:', result.error);
            alert(`Delete failed: ${result.error}`);
        }
    } catch (error) {
        console.error('Error deleting instance:', error);
        alert(`Delete error: ${error.message}`);
    }
}

async function changeInstanceIcon() {
    if (!currentInstance) return;
    
    const result = await window.electronAPI.selectIcon();
    if (result.canceled || result.filePaths.length === 0) return;
    
    // The backend will handle copying the icon
    // For now, just reload instances
    const instancesResult = await window.electronAPI.getInstances();
    if (instancesResult.success) {
        instances = instancesResult.data;
        renderInstances();
    }
}

// Context menu
function showContextMenu(e, name) {
    e.preventDefault();
    
    // Remove existing context menu
    const existing = document.querySelector('.context-menu');
    if (existing) existing.remove();
    
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.left = `${e.clientX}px`;
    menu.style.top = `${e.clientY}px`;
    
    menu.innerHTML = `
        <div class="context-menu-item" data-action="rename">Rename Instance</div>
        <div class="context-menu-item" data-action="icon">Change Icon</div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item" data-action="delete" style="color: var(--viso-red);">Delete Instance</div>
    `;
    
    menu.querySelectorAll('.context-menu-item').forEach(item => {
        item.addEventListener('click', () => {
            selectInstance(name);
            switch (item.dataset.action) {
                case 'rename': renameInstance(); break;
                case 'icon': changeInstanceIcon(); break;
                case 'delete': deleteInstance(); break;
            }
            menu.remove();
        });
    });
    
    document.body.appendChild(menu);
    
    // Close on click outside
    setTimeout(() => {
        document.addEventListener('click', function closeMenu() {
            menu.remove();
            document.removeEventListener('click', closeMenu);
        }, { once: true });
    }, 0);
}

// Drag and drop
function setupDragAndDrop() {
    // Handled in renderInstances
}

function handleDragStart(e) {
    dragSrcEl = this;
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
}

function handleDragOver(e) {
    if (e.preventDefault) e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDrop(e) {
    if (e.stopPropagation) e.stopPropagation();
    
    if (dragSrcEl !== this) {
        const fromIndex = parseInt(dragSrcEl.dataset.index);
        const toIndex = parseInt(this.dataset.index);
        
        // Reorder instances
        const keys = Object.keys(instances);
        const [moved] = keys.splice(fromIndex, 1);
        keys.splice(toIndex, 0, moved);
        
        // Rebuild instances object
        const newInstances = {};
        keys.forEach(key => newInstances[key] = instances[key]);
        instances = newInstances;
        
        // Save order
        window.electronAPI.reorderInstances(keys);
        
        // Re-render
        renderInstances();
    }
    
    return false;
}

function handleDragEnd() {
    this.classList.remove('dragging');
    document.querySelectorAll('.instance-item').forEach(item => {
        item.classList.remove('drag-over');
    });
}

// Track if instance is currently running
let isInstanceRunning = false;
let pollTimeoutId = null;

// Update launch button state
function updateLaunchButtonState(running) {
    console.log(`[Button State] Setting to: ${running ? 'KILL' : 'LAUNCH'}`);
    isInstanceRunning = running;
    const btn = elements.launchBtn;
    
    if (running) {
        // Change to kill button
        btn.className = 'viso-btn viso-btn-danger viso-btn-lg';
        btn.innerHTML = '<i class="fas fa-stop" style="margin-right: 8px;"></i><span id="launch-btn-text">KILL INSTANCE</span>';
        btn.disabled = false;
        elements.statusText.textContent = 'Game running';
    } else {
        // Change to launch button
        btn.className = 'viso-btn viso-btn-primary viso-btn-lg';
        btn.innerHTML = '<i class="fas fa-play" style="margin-right: 8px;"></i><span id="launch-btn-text">LAUNCH GAME</span>';
        btn.disabled = false;
        elements.statusText.textContent = 'Ready';
    }
}

// Launch or kill game
async function launchGame() {
    if (!currentInstance) {
        console.log('Launch/Kill: No instance selected');
        return;
    }
    
    if (isInstanceRunning) {
        // Kill the instance
        console.log(`Killing instance: ${currentInstance}`);
        try {
            elements.launchBtn.disabled = true;
            const result = await window.electronAPI.killInstance(currentInstance);
            console.log('Kill result:', result);
            
            if (result.success) {
                updateLaunchButtonState(false);
                elements.statusText.textContent = 'Instance killed';
                // Clear any pending poll timeout
                if (pollTimeoutId) {
                    clearTimeout(pollTimeoutId);
                    pollTimeoutId = null;
                }
            } else {
                elements.launchBtn.disabled = false;
                alert(`Kill failed: ${result.error}`);
            }
        } catch (error) {
            elements.launchBtn.disabled = false;
            console.error('Kill error:', error);
            alert(`Kill error: ${error.message}`);
        }
    } else {
        // Launch the instance
        console.log(`Launching instance: ${currentInstance}`);
        await saveCurrentInstance();
        
        elements.launchBtn.disabled = true;
        elements.launchBtn.innerHTML = '<div class="btn-spinner"></div> Launching...';
        elements.statusText.textContent = 'Preparing launch...';
        elements.launchProgress.style.display = 'block';
        
        if (elements.showLogsCheckbox.checked) {
            window.electronAPI.openConsole();
        }
        
        try {
            console.log('Calling launchInstance API...');
            const result = await window.electronAPI.launchInstance(currentInstance);
            console.log('Launch result:', result);
            
            if (result.success) {
                // Retry checking status up to 30 times (backend may take time to register process)
                let launchCheckAttempts = 0;
                const maxLaunchChecks = 30;
                
                async function checkLaunchStatus() {
                    try {
                        const statusResult = await window.electronAPI.isInstanceRunning(currentInstance);
                        if (statusResult.running) {
                            updateLaunchButtonState(true);
                            pollInstanceStatus();
                            return;
                        }
                        
                        launchCheckAttempts++;
                        if (launchCheckAttempts < maxLaunchChecks) {
                            setTimeout(checkLaunchStatus, 200);
                        } else {
                            // Process didn't register but launch succeeded - still show as running
                            updateLaunchButtonState(true);
                            pollInstanceStatus();
                        }
                    } catch (err) {
                        launchCheckAttempts++;
                        if (launchCheckAttempts < maxLaunchChecks) {
                            setTimeout(checkLaunchStatus, 200);
                        } else {
                            updateLaunchButtonState(true);
                            pollInstanceStatus();
                        }
                    }
                }
                
                checkLaunchStatus();
            } else {
                elements.statusText.textContent = 'Launch failed';
                updateLaunchButtonState(false);
                console.error('Launch failed:', result.error);
                alert(`Launch failed: ${result.error}`);
            }
        } catch (error) {
            elements.statusText.textContent = 'Launch error';
            updateLaunchButtonState(false);
            console.error('Launch error:', error);
            alert(`Launch error: ${error.message}`);
        }
    }
}

// Poll to check if instance is still running
async function pollInstanceStatus() {
    if (!currentInstance || !isInstanceRunning) {
        console.log(`[Poll] Skipping - currentInstance: ${currentInstance}, isInstanceRunning: ${isInstanceRunning}`);
        return;
    }
    
    try {
        console.log(`[Poll] Checking status for: ${currentInstance}`);
        const result = await window.electronAPI.isInstanceRunning(currentInstance);
        console.log(`[Poll] Status result:`, result);
        if (!result.running) {
            // Instance stopped
            console.log(`[Poll] Instance stopped, resetting button`);
            updateLaunchButtonState(false);
            elements.statusText.textContent = 'Game stopped';
            pollTimeoutId = null;
        } else {
            // Still running, poll again in 0.2 seconds
            console.log(`[Poll] Still running, scheduling next check`);
            pollTimeoutId = setTimeout(pollInstanceStatus, 200);
        }
    } catch (error) {
        console.error('[Poll] Error polling status:', error);
    }
}

// Modrinth Browser
function openModrinthBrowser() {
    openModal('modrinth-modal');
    searchModrinth(true); // Load featured modpacks
}

async function searchModrinth(isInitial = false) {
    const query = elements.modrinthSearch.value;
    
    elements.modrinthResults.style.display = 'none';
    elements.modrinthLoading.style.display = 'flex';
    
    try {
        const result = await window.electronAPI.searchModrinth(isInitial ? '' : query);
        
        elements.modrinthLoading.style.display = 'none';
        elements.modrinthResults.style.display = 'flex';
        
        if (result.success) {
            renderModrinthResults(result.data);
        }
    } catch (error) {
        elements.modrinthLoading.style.display = 'none';
        elements.modrinthResults.innerHTML = '<p class="viso-body">Error searching Modrinth.</p>';
    }
}

function renderModrinthResults(results) {
    elements.modrinthResults.innerHTML = '';
    
    if (results.length === 0) {
        elements.modrinthResults.innerHTML = '<p class="viso-body">No results found.</p>';
        return;
    }
    
    results.forEach(modpack => {
        const card = document.createElement('div');
        card.className = 'modpack-card';
        
        const iconHtml = modpack.icon_url
            ? `<img src="${modpack.icon_url}" class="modpack-icon" alt="">`
            : `<div class="modpack-icon-placeholder">📦</div>`;
        
        card.innerHTML = `
            ${iconHtml}
            <div class="modpack-info">
                <div class="modpack-title">${modpack.title}</div>
                <div class="modpack-author">by ${modpack.author}</div>
                <div class="modpack-version-select">
                    <span class="viso-caption">Version:</span>
                    <select class="viso-select" id="version-${modpack.project_id}">
                        <option>Loading...</option>
                    </select>
                </div>
            </div>
            <div class="modpack-actions">
                <button class="viso-btn viso-btn-primary viso-btn-sm install-btn" data-project="${modpack.project_id}">Install</button>
            </div>
        `;
        
        // Load versions
        loadModpackVersions(modpack.project_id);
        
        // Install button
        card.querySelector('.install-btn').addEventListener('click', () => {
            const versionSelect = document.getElementById(`version-${modpack.project_id}`);
            installModpack(modpack.project_id, versionSelect.value, modpack.title, modpack.icon_url);
        });
        
        elements.modrinthResults.appendChild(card);
    });
}

async function loadModpackVersions(projectId) {
    try {
        const result = await window.electronAPI.getProjectVersions(projectId);
        if (result.success) {
            const select = document.getElementById(`version-${projectId}`);
            select.innerHTML = result.data
                .map(v => `<option value="${v.id}">${v.name}</option>`)
                .join('');
        }
    } catch (error) {
        console.error('Error loading versions:', error);
    }
}

async function installModpack(projectId, versionId, title, iconUrl) {
    if (!confirm(`Install "${title}"?`)) return;
    
    try {
        const result = await window.electronAPI.installModpack(projectId, versionId, title, iconUrl);
        
        if (result.success) {
            alert('Modpack installed successfully!');
            closeModal('modrinth-modal');
            loadData(); // Refresh instances
        } else {
            alert(`Installation failed: ${result.error}`);
        }
    } catch (error) {
        console.error('Error installing modpack:', error);
        alert('Installation failed.');
    }
}

// Import modpack
async function importModpack() {
    const result = await window.electronAPI.selectFile({
        title: 'Select Modpack',
        filters: [
            { name: 'Modpacks', extensions: ['mrpack', 'zip'] },
            { name: 'All Files', extensions: ['*'] }
        ],
        properties: ['openFile']
    });
    
    if (result.canceled || result.filePaths.length === 0) return;
    
    try {
        const importResult = await window.electronAPI.importModpack(result.filePaths[0]);
        
        if (importResult.success) {
            alert('Modpack imported successfully!');
            loadData();
        } else {
            alert(`Import failed: ${importResult.error}`);
        }
    } catch (error) {
        console.error('Error importing modpack:', error);
        alert('Import failed.');
    }
}

// Settings
function openSettings() {
    document.getElementById('show-logo-checkbox').checked = settings.show_logo !== false;
    document.getElementById('sidebar-right-checkbox').checked = settings.sidebar_right || false;
    document.getElementById('default-username-input').value = settings.default_username || '';
    document.getElementById('default-java-input').value = settings.default_java || '';
    
    openModal('settings-modal');
}

async function saveSettings() {
    const newSettings = {
        show_logo: document.getElementById('show-logo-checkbox').checked,
        sidebar_right: document.getElementById('sidebar-right-checkbox').checked,
        default_username: document.getElementById('default-username-input').value,
        default_java: document.getElementById('default-java-input').value
    };
    
    try {
        const result = await window.electronAPI.saveSettings(newSettings);
        
        if (result.success) {
            settings = { ...settings, ...newSettings };
            applySettings();
            closeModal('settings-modal');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
    }
}

async function resetSettings() {
    if (!confirm('Reset all settings to defaults?')) return;
    
    const defaultSettings = {
        show_logo: true,
        sidebar_right: false,
        default_username: '',
        default_java: ''
    };
    
    try {
        await window.electronAPI.saveSettings(defaultSettings);
        settings = defaultSettings;
        applySettings();
        openSettings(); // Refresh modal
    } catch (error) {
        console.error('Error resetting settings:', error);
    }
}

function applySettings() {
    // Apply sidebar position
    const appContainer = document.getElementById('app');
    if (settings.sidebar_right) {
        appContainer.classList.add('sidebar-right');
    } else {
        appContainer.classList.remove('sidebar-right');
    }
    
    // Apply show logo
    const logoHeader = document.getElementById('sidebar-logo');
    if (logoHeader) {
        logoHeader.style.display = settings.show_logo !== false ? 'flex' : 'none';
    }
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
    
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`${tabName}-tab`).classList.add('active');
}

// Java Detector
async function openJavaDetector() {
    openModal('java-modal');
    await scanJava(false);
}

async function scanJava(deep = false) {
    const scanningDiv = document.getElementById('java-scanning');
    const resultsDiv = document.getElementById('java-results');
    const listDiv = document.getElementById('java-list');
    
    scanningDiv.style.display = 'flex';
    resultsDiv.style.display = 'none';
    
    try {
        const result = await window.electronAPI.getJavaInstallations(deep);
        
        scanningDiv.style.display = 'none';
        resultsDiv.style.display = 'block';
        
        if (result.success && result.data.length > 0) {
            listDiv.innerHTML = result.data.map(java => `
                <div class="java-item">
                    <div class="java-info">
                        <div class="java-version">Java ${java.version} (${java.arch})</div>
                        <div class="java-path">${java.path}</div>
                    </div>
                    <button class="viso-btn viso-btn-primary viso-btn-sm select-java-btn" data-path="${java.path}">Select</button>
                </div>
            `).join('');
            
            listDiv.querySelectorAll('.select-java-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    elements.javaInput.value = btn.dataset.path;
                    saveCurrentInstance();
                    closeModal('java-modal');
                });
            });
        } else {
            listDiv.innerHTML = '<p class="viso-body" style="text-align: center;">No Java installations found.</p>';
        }
    } catch (error) {
        scanningDiv.style.display = 'none';
        resultsDiv.style.display = 'block';
        listDiv.innerHTML = '<p class="viso-body" style="text-align: center; color: var(--viso-red);">Error scanning for Java.</p>';
    }
}
