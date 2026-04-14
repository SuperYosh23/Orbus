const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const os = require('os');
const fs = require('fs');

// Global reference to prevent garbage collection
let mainWindow;
let consoleWindow;
let pythonBackend;
let runningInstances = new Map(); // Track running game processes

// Backend port
const BACKEND_PORT = 15556;

// Determine platform-specific Python command
function getPythonCommand() {
  // When packaged, check for bundled venv in resourcesPath first
  if (app.isPackaged) {
    const bundledVenv = path.join(process.resourcesPath, 'python_venv', 'bin', 'python');
    if (fs.existsSync(bundledVenv)) {
      return bundledVenv;
    }
    
    const bundledVenvWin = path.join(process.resourcesPath, 'python_venv', 'Scripts', 'python.exe');
    if (fs.existsSync(bundledVenvWin)) {
      return bundledVenvWin;
    }
  }
  
  // Check for venv Python in development
  const venvPython = path.join(__dirname, '..', 'backend', 'venv', 'bin', 'python');
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }
  
  // Check for venv on Windows (dev)
  const venvPythonWin = path.join(__dirname, '..', 'backend', 'venv', 'Scripts', 'python.exe');
  if (fs.existsSync(venvPythonWin)) {
    return venvPythonWin;
  }
  
  // Fall back to system Python
  if (process.platform === 'win32') {
    return 'python';
  }
  return 'python3';
}

// Start Python backend
function startPythonBackend() {
  // When packaged, extraResources are in process.resourcesPath
  // When dev, they're in the source directory
  const backendPath = app.isPackaged 
    ? path.join(process.resourcesPath, 'backend', 'api_server.py')
    : path.join(__dirname, '..', 'backend', 'api_server.py');
  const pythonCmd = getPythonCommand();
  
  console.log(`Starting Python backend: ${pythonCmd} ${backendPath}`);
  
  pythonBackend = spawn(pythonCmd, ['-u', backendPath, BACKEND_PORT.toString()], {
    stdio: 'pipe',
    detached: false,
    env: { ...process.env, PYTHONUNBUFFERED: '1' }
  });
  
  pythonBackend.stdout.on('data', (data) => {
    const output = data.toString();
    console.log(`[Python] ${output.trim()}`);
    
    // Forward console logs to console window if it exists
    // Filter out status checks and internal messages - only show Minecraft game output
    if (consoleWindow && !consoleWindow.isDestroyed()) {
      const lines = output.split('\n');
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed && 
            !trimmed.includes('[Status Check]') && 
            !trimmed.includes('[Kill Request]') &&
            !trimmed.includes('[Launch] Stored process') &&
            !trimmed.includes('[Launch] Removed process') &&
            !trimmed.includes('[Launch] Error')) {
          consoleWindow.webContents.send('console-log', { line: trimmed });
        }
      }
    }
  });
  
  pythonBackend.stderr.on('data', (data) => {
    console.error(`[Python Error] ${data.toString().trim()}`);
  });
  
  pythonBackend.on('close', (code) => {
    console.log(`Python backend exited with code ${code}`);
  });
  
  pythonBackend.on('error', (err) => {
    console.error('Failed to start Python backend:', err);
    dialog.showErrorBox('Backend Error', 'Failed to start the Python backend. Please ensure Python 3 is installed.');
  });
}

// Create the main window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 850,
    minWidth: 900,
    minHeight: 700,
    title: 'Orbus Launcher',
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    backgroundColor: '#0d1117',
    show: false,
    titleBarStyle: 'hiddenInset',
    autoHideMenuBar: true,
    menuBarVisible: false
  });
  
  // Remove the menu bar completely
  mainWindow.setMenuBarVisibility(false);

  // Load the renderer
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  // Show when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
  
  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Backend URL for communication
const axios = require('axios');
const backendUrl = `http://127.0.0.1:${BACKEND_PORT}`;

// Check if backend is ready
async function waitForBackend(maxRetries = 30, interval = 500) {
  console.log('Waiting for Python backend to be ready...');
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await axios.get(`${backendUrl}/api/instances`, { timeout: 1000 });
      console.log('Python backend is ready!');
      console.log('Config loaded:', Object.keys(response.data).length, 'instances');
      return true;
    } catch (error) {
      if (i === 0 || i === maxRetries - 1 || i % 5 === 0) {
        console.log(`Health check attempt ${i + 1}/${maxRetries}: ${error.message}`);
      }
      await new Promise(resolve => setTimeout(resolve, interval));
    }
  }
  console.error('Python backend failed to start within timeout');
  return false;
}

// App ready
app.whenReady().then(async () => {
  startPythonBackend();
  
  // Wait for backend to be ready
  const backendReady = await waitForBackend();
  
  if (!backendReady) {
    dialog.showErrorBox(
      'Backend Error',
      'The Python backend failed to start. Please check:\n\n' +
      '1. Python dependencies are installed (run ./setup.sh)\n' +
      '2. Port 15556 is not in use by another application\n' +
      '3. Check the terminal for Python error messages'
    );
  }
  
  createWindow();
  
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit handling
app.on('window-all-closed', () => {
  if (pythonBackend) {
    pythonBackend.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (pythonBackend) {
    pythonBackend.kill();
  }
});

// IPC handlers for Python backend communication
// Helper function for backend requests
async function backendRequest(endpoint, method = 'GET', data = null) {
  try {
    // Split endpoint into path and query, encode only the path parts
    const [pathPart, queryPart] = endpoint.split('?');
    const encodedPath = pathPart.split('/').map(part => encodeURIComponent(part)).join('/');
    const encodedEndpoint = queryPart ? `${encodedPath}?${queryPart}` : encodedPath;
    
    const config = {
      method,
      url: `${backendUrl}${encodedEndpoint}`,
      timeout: 30000
    };
    if (data) {
      config.data = data;
      config.headers = { 'Content-Type': 'application/json' };
    }
    console.log(`[Backend] ${method} ${endpoint}`, data ? '(with data)' : '');
    const response = await axios(config);
    console.log(`[Backend] ${method} ${endpoint} -> OK`);
    return { success: true, data: response.data };
  } catch (error) {
    const errorMsg = error.response?.data?.error || error.message;
    console.error(`[Backend] ${method} ${endpoint} -> Error: ${errorMsg}`);
    return { 
      success: false, 
      error: errorMsg
    };
  }
}

// IPC handlers
ipcMain.handle('get-instances', async () => {
  return await backendRequest('/api/instances');
});

ipcMain.handle('create-instance', async (event, name, data) => {
  return await backendRequest('/api/instances', 'POST', { name, ...data });
});

ipcMain.handle('update-instance', async (event, name, data) => {
  return await backendRequest(`/api/instances/${name}`, 'PUT', data);
});

ipcMain.handle('delete-instance', async (event, name) => {
  return await backendRequest(`/api/instances/${name}`, 'DELETE');
});

ipcMain.handle('rename-instance', async (event, oldName, newName) => {
  return await backendRequest(`/api/instances/${oldName}/rename`, 'POST', { new_name: newName });
});

ipcMain.handle('reorder-instances', async (event, order) => {
  return await backendRequest('/api/instances/reorder', 'POST', { order });
});

ipcMain.handle('launch-instance', async (event, name) => {
  const result = await backendRequest(`/api/instances/${name}/launch`, 'POST');
  if (result.success) {
    runningInstances.set(name, true);
  }
  return result;
});

ipcMain.handle('kill-instance', async (event, name) => {
  // Kill the process via backend
  const result = await backendRequest(`/api/instances/${name}/kill`, 'POST');
  if (result.success) {
    runningInstances.delete(name);
  }
  return result;
});

ipcMain.handle('is-instance-running', async (event, name) => {
  // Query the backend for actual process status
  const result = await backendRequest(`/api/instances/${name}/status`);
  if (result.success) {
    // Sync local tracking with backend status
    if (result.data.running) {
      runningInstances.set(name, true);
    } else {
      runningInstances.delete(name);
    }
    return { running: result.data.running };
  }
  return { running: false };
});

ipcMain.handle('get-versions', async () => {
  return await backendRequest('/api/versions');
});

ipcMain.handle('get-fabric-versions', async () => {
  return await backendRequest('/api/fabric-versions');
});

ipcMain.handle('search-modrinth', async (event, query) => {
  return await backendRequest('/api/modrinth/search', 'POST', { query });
});

ipcMain.handle('get-project-versions', async (event, projectId) => {
  return await backendRequest(`/api/modrinth/project/${projectId}/versions`);
});

ipcMain.handle('install-modpack', async (event, projectId, versionId, title, iconUrl) => {
  return await backendRequest('/api/modrinth/install', 'POST', { 
    project_id: projectId, 
    version_id: versionId,
    title,
    icon_url: iconUrl
  });
});

ipcMain.handle('import-modpack', async (event, filePath) => {
  return await backendRequest('/api/import', 'POST', { file_path: filePath });
});

ipcMain.handle('get-settings', async () => {
  return await backendRequest('/api/settings');
});

ipcMain.handle('save-settings', async (event, settings) => {
  return await backendRequest('/api/settings', 'PUT', settings);
});

ipcMain.handle('get-java-installations', async (event, deep = false) => {
  const result = await backendRequest(`/api/java/detect?deep=${deep}`);
  console.log('Java detect result:', result);
  return result;
});

ipcMain.handle('open-folder', async (event, folderPath) => {
  return await backendRequest('/api/folder/open', 'POST', { path: folderPath });
});

ipcMain.handle('select-file', async (event, options) => {
  const result = await dialog.showOpenDialog(mainWindow, options);
  return result;
});

ipcMain.handle('select-java', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Select Java Executable',
    filters: [
      { name: 'Java Executable', extensions: ['*'] }
    ],
    properties: ['openFile']
  });
  return result;
});

ipcMain.handle('select-icon', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Select Instance Icon',
    filters: [
      { name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'ico', 'bmp'] }
    ],
    properties: ['openFile']
  });
  return result;
});

ipcMain.handle('get-platform', () => {
  return process.platform;
});

ipcMain.handle('get-app-version', () => {
  const packageJson = require('../package.json');
  return packageJson.version;
});

// Create console window
function createConsoleWindow() {
  if (consoleWindow && !consoleWindow.isDestroyed()) {
    consoleWindow.focus();
    return;
  }
  
  consoleWindow = new BrowserWindow({
    width: 900,
    height: 600,
    minWidth: 600,
    minHeight: 400,
    title: 'Minecraft Console',
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      preload: path.join(__dirname, 'preload.js')
    },
    backgroundColor: '#0d1117',
    autoHideMenuBar: true,
    show: true
  });
  
  consoleWindow.loadFile(path.join(__dirname, 'renderer', 'console.html'));
  
  consoleWindow.on('closed', () => {
    consoleWindow = null;
  });
}

// IPC handler to open console window
ipcMain.handle('open-console', () => {
  createConsoleWindow();
});
