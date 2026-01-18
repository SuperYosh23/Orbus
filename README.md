<div align="center">
  <img width="500" height="167" alt="Orbus Logo" src="https://github.com/user-attachments/assets/87ec403d-0485-4a7c-9133-908d7148d012" />
  
  # Orbus Launcher
  
  **A lightweight, open-source, offline-mode Minecraft launcher built with Python.**
</div>

---

## About
Orbus started as a fun project for me to learn Python and understand how game launchers work under the hood. Over time, it has evolved into a fully functional, offline-capable launcher that rivals standard options for quick and easy instance management.

It utilizes `minecraft-launcher-lib` for the heavy lifting and `CustomTkinter` for a modern, dark-mode UI.

## Key Features
* **Instance Management:** Create, delete, and rename separate Minecraft instances to keep your mods and worlds organized.
* **Drag & Drop Sorting:** Easily reorder your instances in the sidebar just by dragging them.
* **Modrinth Integration:** Browse, search, and install Modpacks directly from Modrinth within the launcher.
* **Import Support:** Import modpacks via `.zip` or `.mrpack` files.
* **Mod Loaders:** Native support for **Vanilla**, **Fabric**, and **Quilt** (with auto-version fetching).
* **Smart Java Detection:** Automatically scans your system for Java installations so you don't have to hunt for paths.
* **Live Console:** Optional log window to debug mods or watch game output in real-time.

## Screenshots
<img width="905" height="743" alt="Orbus Screenshot" src="https://github.com/user-attachments/assets/eec9a538-80ca-49c4-9cda-d52992fbee91" />

## Installation & Usage

### Prerequisites
* Python 3.10 or higher
* An internet connection (for first-time asset downloads)

### Running from Source
1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/SuperYosh23/Orbus.git](https://github.com/SuperYosh23/Orbus.git)
    cd Orbus
    ```

2.  **Install dependencies:**
    ```bash
    pip install customtkinter minecraft-launcher-lib requests Pillow
    ```

3.  **Run the launcher:**
    ```bash
    python launcher.py
    ```

## Built With
* [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern UI components.
* [Minecraft-Launcher-Lib](https://gitlab.com/JakobDev/minecraft-launcher-lib) - Handles downloading and launching logic.
* [Modrinth API](https://docs.modrinth.com/) - For modpack browsing.

## To-Do / Roadmap
- [ ] Microsoft Account Login support
- [ ] CurseForge Modpack support
- [ ] Skin management
- [ ] Auto-update functionality

## DISCLAIMER:
This project is mostly entirely AI generated. Sorry if that bothers or upsets you.
