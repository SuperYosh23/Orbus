const { contextBridge, ipcRenderer } = require('electron');

// Expose APIs to renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // Instances
  getInstances: () => ipcRenderer.invoke('get-instances'),
  createInstance: (name, data) => ipcRenderer.invoke('create-instance', name, data),
  updateInstance: (name, data) => ipcRenderer.invoke('update-instance', name, data),
  deleteInstance: (name) => ipcRenderer.invoke('delete-instance', name),
  renameInstance: (oldName, newName) => ipcRenderer.invoke('rename-instance', oldName, newName),
  reorderInstances: (order) => ipcRenderer.invoke('reorder-instances', order),
  launchInstance: (name) => ipcRenderer.invoke('launch-instance', name),
  
  // Versions
  getVersions: () => ipcRenderer.invoke('get-versions'),
  getFabricVersions: () => ipcRenderer.invoke('get-fabric-versions'),
  
  // Modrinth
  searchModrinth: (query) => ipcRenderer.invoke('search-modrinth', query),
  getProjectVersions: (projectId) => ipcRenderer.invoke('get-project-versions', projectId),
  installModpack: (projectId, versionId, title, iconUrl) => 
    ipcRenderer.invoke('install-modpack', projectId, versionId, title, iconUrl),
  importModpack: (filePath) => ipcRenderer.invoke('import-modpack', filePath),
  
  // Settings
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),
  
  // Java
  getJavaInstallations: (deep = false) => ipcRenderer.invoke('get-java-installations', deep),
  
  // Dialogs
  selectFile: (options) => ipcRenderer.invoke('select-file', options),
  selectJava: () => ipcRenderer.invoke('select-java'),
  selectIcon: () => ipcRenderer.invoke('select-icon'),
  
  // System
  openFolder: (path) => ipcRenderer.invoke('open-folder', path),
  getPlatform: () => ipcRenderer.invoke('get-platform'),
  
  // Event listeners
  onLaunchStatus: (callback) => {
    ipcRenderer.on('launch-status', (event, data) => callback(data));
  },
  onDownloadProgress: (callback) => {
    ipcRenderer.on('download-progress', (event, data) => callback(data));
  }
});
