# Orbus Launcher - Electron Overhaul

This is the Electron-based overhaul of the Orbus Minecraft Launcher, featuring a modern glassmorphism UI powered by [VisoDesign](https://github.com/SuperYosh23/VisoDesign).

## Architecture

The new architecture separates concerns into two main components:

1. **Frontend (Electron)**: Beautiful HTML/CSS/JS UI using the actual VisoDesign CSS framework
2. **Backend (Python)**: HTTP API server that handles all Minecraft launcher logic via `minecraft-launcher-lib`

### Communication

The Electron frontend communicates with the Python backend via:
- IPC (preload.js) between renderer and main process
- HTTP REST API on localhost:15556 (main process ↔ Python backend)

## File Structure

```
Orbus/
├── src/
│   ├── main.js              # Electron main process
│   ├── preload.js           # IPC bridge (secure context isolation)
│   └── renderer/
│       ├── index.html       # Main UI layout
│       ├── console.html     # Console window for Minecraft logs
│       ├── styles.css       # Orbus-specific VisoDesign customizations
│       ├── viso.css         # Official VisoDesign CSS (from GitHub)
│       └── app.js           # Frontend application logic
├── backend/
│   └── api_server.py        # Python HTTP API server
├── assets/
│   └── icon.png             # App icon
├── package.json             # Electron dependencies
└── README.md                # This file
```

## Features

- **Glassmorphism Design**: Dark theme with translucent glass effects and vibrant green accents powered by VisoDesign
- **Instance Management**: Create, rename (with Viso modal), delete, and reorder Minecraft instances
- **Live Status Tracking**: Real-time game status with 0.2s polling - button auto-updates to "Kill Instance" when running
- **Drag & Drop**: Reorder instances by dragging in the sidebar
- **Mod Loader Support**: Vanilla, Fabric, and Quilt with automatic installation
- **Modrinth Integration**: Browse and install modpacks directly from Modrinth
- **Java Auto-Detection**: Per-instance Java path + default Java in settings, with auto-detect and browse
- **Import Support**: Import .zip and .mrpack modpack files via drag-and-drop or file picker
- **Console Window**: Separate window for Minecraft logs (filtered to show only game output)
- **Settings**: Sidebar position toggle, show/hide logo, default Java path, default username

## Development

### Prerequisites

- Node.js 18+
- Python 3.10+
- Git

### Setup

1. **Install Node dependencies**:
   ```bash
   npm install
   ```

2. **The Python backend will auto-install its dependencies on first run**

### Running in Development

```bash
npm run dev
```

This starts both the Python backend and Electron frontend.

### Building for Production

```bash
# Build for current platform
npm run build

# Build for specific platforms
npm run build:win
npm run build:mac
npm run build:linux
```

## VisoDesign Integration

This project uses the **actual VisoDesign CSS** from the official repository. The `viso.css` file is a direct copy of the design system, providing:

- CSS custom properties (design tokens) for colors, typography, spacing
- Glassmorphism effects with backdrop blur
- Button variants: primary, secondary, glass, ghost, danger
- Form elements: inputs, selects, checkboxes, toggles, sliders
- Cards and surfaces with translucent backgrounds
- Progress indicators and spinners
- Utility classes for flexbox layouts

To customize the theme, modify the CSS variables in `viso.css`:

```css
:root {
    --viso-accent: #3ddc84;        /* Change accent color */
    --viso-bg-primary: #0d1117;    /* Change background */
}
```

## Differences from Python/CustomTkinter Version

| Feature | Python Version | Electron Version |
|---------|---------------|------------------|
| UI Framework | CustomTkinter | Electron + VisoDesign |
| Styling | Limited theming | Full glassmorphism CSS |
| Performance | Single-threaded | Multi-process (main + renderer) |
| Responsiveness | Fixed layout | Flexible CSS Grid/Flexbox |
| Animations | Limited | CSS transitions & animations |
| Web Content | N/A | Can embed web views |

## API Endpoints

The Python backend exposes these REST endpoints:

### Instances
- `GET /api/instances` - List all instances
- `POST /api/instances` - Create new instance
- `PUT /api/instances/:name` - Update instance
- `DELETE /api/instances/:name` - Delete instance
- `POST /api/instances/:name/rename` - Rename instance
- `POST /api/instances/:name/launch` - Launch instance
- `POST /api/instances/reorder` - Reorder instances

### Versions
- `GET /api/versions` - List Minecraft versions
- `GET /api/fabric-versions` - List Fabric loader versions

### Modrinth
- `POST /api/modrinth/search` - Search modpacks
- `GET /api/modrinth/project/:id/versions` - Get project versions
- `POST /api/modrinth/install` - Install modpack

### System
- `GET /api/java/detect` - Find Java installations
- `POST /api/import` - Import modpack file
- `POST /api/folder/open` - Open folder in file manager

### Settings
- `GET /api/settings` - Get app settings
- `PUT /api/settings` - Update settings

## Credits

- **VisoDesign**: Glassmorphism design system by SuperYosh23
- **minecraft-launcher-lib**: Minecraft launching functionality by JakobDev
- **Electron**: Cross-platform desktop framework

## License

MIT License - See LICENSE file for details.
