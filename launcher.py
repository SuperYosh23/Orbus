import os
import sys
import subprocess
import threading
import json
import shutil
import zipfile
import requests
import io
import customtkinter as ctk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image
import minecraft_launcher_lib

# -------------------------
# Configuration & Globals
# -------------------------
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def get_minecraft_dir():
    if sys.platform.startswith("win"):
        return os.path.join(os.environ["APPDATA"], ".minecraft")
    return os.path.expanduser("~/.minecraft")

MINECRAFT_DIR = get_minecraft_dir()
INSTANCES_DIR = os.path.join(MINECRAFT_DIR, "orbus_instances")
CONFIG_FILE = os.path.join(MINECRAFT_DIR, "orbus_config.json")

os.makedirs(INSTANCES_DIR, exist_ok=True)

class OrbusLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Orbus Launcher")
        self.geometry("1000x750")

        self.instances = self.load_config()
        self.current_instance_name = None
        self.progress_win = None 

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === SIDEBAR ===
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self.sidebar_frame, text="ORBUS", font=ctk.CTkFont(size=26, weight="bold")).grid(row=0, column=0, pady=20)
        
        self.browse_btn = ctk.CTkButton(self.sidebar_frame, text="🌐 Browse Modrinth", fg_color="#1bd964", hover_color="#15a34a", text_color="black", font=ctk.CTkFont(weight="bold"), command=self.open_modrinth_search)
        self.browse_btn.grid(row=1, column=0, padx=20, pady=10)

        self.scrollable_list = ctk.CTkScrollableFrame(self.sidebar_frame, label_text="My Instances")
        self.scrollable_list.grid(row=2, column=0, padx=15, pady=10, sticky="nsew")

        self.add_btn = ctk.CTkButton(self.sidebar_frame, text="+ New Instance", command=self.add_instance, fg_color="gray25")
        self.add_btn.grid(row=3, column=0, padx=20, pady=5)
        
        self.import_btn = ctk.CTkButton(self.sidebar_frame, text="📥 Import .zip/.mrpack", command=self.import_modpack, fg_color="gray25")
        self.import_btn.grid(row=4, column=0, padx=20, pady=5)

        self.del_btn = ctk.CTkButton(self.sidebar_frame, text="Delete Instance", fg_color="#cf3838", hover_color="#8a2525", command=self.delete_instance)
        self.del_btn.grid(row=5, column=0, padx=20, pady=(10, 20))

        # === MAIN PANEL ===
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)

        self.header_label = ctk.CTkLabel(self.main_frame, text="Select an Instance", font=ctk.CTkFont(size=32, weight="bold"))
        self.header_label.pack(pady=(10, 30))

        self.settings_frame = ctk.CTkFrame(self.main_frame)
        self.settings_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(self.settings_frame, text="Username").pack(anchor="w", padx=20, pady=(15, 0))
        self.username_entry = ctk.CTkEntry(self.settings_frame)
        self.username_entry.pack(fill="x", padx=20, pady=(5, 10))

        ctk.CTkLabel(self.settings_frame, text="MC Version").pack(anchor="w", padx=20)
        self.version_combo = ctk.CTkComboBox(self.settings_frame, values=["1.21.1", "1.20.1"])
        self.version_combo.pack(fill="x", padx=20, pady=(5, 10))

        ctk.CTkLabel(self.settings_frame, text="Mod Loader").pack(anchor="w", padx=20)
        self.loader_combo = ctk.CTkComboBox(self.settings_frame, values=["Vanilla", "Fabric", "Quilt"], command=self.toggle_loader_settings)
        self.loader_combo.pack(fill="x", padx=20, pady=(5, 10))

        self.loader_ver_label = ctk.CTkLabel(self.settings_frame, text="Fabric Loader Version")
        self.loader_ver_combo = ctk.CTkComboBox(self.settings_frame, values=["latest"])
        
        # --- NEW BUTTONS ---
        self.folder_btn = ctk.CTkButton(self.settings_frame, text="📂 Open Instance Folder", command=self.open_instance_folder, fg_color="gray30")
        self.folder_btn.pack(fill="x", padx=20, pady=(10, 5))

        self.mods_btn = ctk.CTkButton(self.settings_frame, text="🧩 Open Mods Folder", command=self.open_mods_folder, fg_color="gray30")
        self.mods_btn.pack(fill="x", padx=20, pady=(0, 20))

        self.status_label = ctk.CTkLabel(self.main_frame, text="Ready", text_color="gray")
        self.status_label.pack(side="bottom", pady=5)

        self.launch_btn = ctk.CTkButton(self.main_frame, text="LAUNCH GAME", height=55, font=ctk.CTkFont(size=20, weight="bold"), command=self.start_launch_thread)
        self.launch_btn.pack(side="bottom", fill="x", padx=20, pady=10)

        self.refresh_instance_buttons()
        threading.Thread(target=self.load_versions_bg, daemon=True).start()
        threading.Thread(target=self.load_fabric_versions_bg, daemon=True).start()

    # --- UI Logic ---
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f: return json.load(f)
            except: return {}
        return {}

    def save_config(self):
        if self.current_instance_name and self.current_instance_name in self.instances:
            self.instances[self.current_instance_name] = {
                "username": self.username_entry.get(),
                "version": self.version_combo.get(),
                "loader": self.loader_combo.get(),
                "loader_version": self.loader_ver_combo.get()
            }
        with open(CONFIG_FILE, 'w') as f: json.dump(self.instances, f, indent=4)

    def load_versions_bg(self):
        try:
            versions = minecraft_launcher_lib.utils.get_version_list()
            rel = [v["id"] for v in versions if v["type"] == "release"]
            self.after(0, lambda: self.version_combo.configure(values=rel[:50]))
        except: pass

    def load_fabric_versions_bg(self):
        try:
            data = requests.get("https://meta.fabricmc.net/v2/versions/loader").json()
            versions = ["latest"] + [v["version"] for v in data]
            self.after(0, lambda: self.loader_ver_combo.configure(values=versions[:50]))
        except: pass

    def toggle_loader_settings(self, choice):
        if choice == "Fabric":
            self.loader_ver_label.pack(anchor="w", padx=20)
            self.loader_ver_combo.pack(fill="x", padx=20, pady=(5, 10))
        else:
            self.loader_ver_label.pack_forget()
            self.loader_ver_combo.pack_forget()

    def refresh_instance_buttons(self):
        for w in self.scrollable_list.winfo_children(): w.destroy()
        for name in self.instances:
            ctk.CTkButton(self.scrollable_list, text=name, fg_color="transparent", border_width=1, anchor="w", 
                          command=lambda n=name: self.select_instance(n)).pack(fill="x", pady=2)

    def select_instance(self, name):
        if self.current_instance_name: self.save_config()
        self.current_instance_name = name
        d = self.instances[name]
        self.header_label.configure(text=name)
        self.username_entry.delete(0, 'end')
        self.username_entry.insert(0, d.get("username", ""))
        self.version_combo.set(d.get("version", "1.21.1"))
        self.loader_combo.set(d.get("loader", "Vanilla"))
        self.loader_ver_combo.set(d.get("loader_version", "latest"))
        self.toggle_loader_settings(d.get("loader", "Vanilla"))

    def add_instance(self):
        n = simpledialog.askstring("New", "Instance Name:")
        if n and n not in self.instances:
            self.instances[n] = {"username": "", "version": "1.21.1", "loader": "Vanilla", "loader_version": "latest"}
            self.save_config(); self.refresh_instance_buttons(); self.select_instance(n)

    def delete_instance(self):
        if not self.current_instance_name: return
        if messagebox.askyesno("Confirm", f"Delete '{self.current_instance_name}'?"):
            name = self.current_instance_name
            if name in self.instances: del self.instances[name]
            folder = os.path.join(INSTANCES_DIR, name)
            if os.path.exists(folder): shutil.rmtree(folder, ignore_errors=True)
            self.current_instance_name = None
            self.save_config(); self.refresh_instance_buttons()
            self.header_label.configure(text="Select an Instance")
            self.username_entry.delete(0, 'end')

    def open_mods_folder(self):
        if self.current_instance_name:
            p = os.path.join(INSTANCES_DIR, self.current_instance_name, "mods")
            os.makedirs(p, exist_ok=True)
            self.open_path(p)

    def open_instance_folder(self):
        if self.current_instance_name:
            p = os.path.join(INSTANCES_DIR, self.current_instance_name)
            self.open_path(p)

    def open_path(self, path):
        if sys.platform == "win32": os.startfile(path)
        else: subprocess.Popen(["xdg-open", path])

    # --- MODPACK FIX: Extracting Overrides ---
    def open_modrinth_search(self):
        self.search_win = ctk.CTkToplevel(self)
        self.search_win.title("Modrinth Browser")
        self.search_win.geometry("750x650")
        container = ctk.CTkFrame(self.search_win)
        container.pack(fill="x", padx=20, pady=20)
        self.search_entry = ctk.CTkEntry(container, placeholder_text="Search modpacks...")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(container, text="Search", command=self.perform_modrinth_search).pack(side="right")
        self.results_frame = ctk.CTkScrollableFrame(self.search_win, label_text="Results")
        self.results_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.perform_modrinth_search(True)

    def perform_modrinth_search(self, is_rec=False):
        q = self.search_entry.get() if not is_rec else ""
        for w in self.results_frame.winfo_children(): w.destroy()
        def run():
            try:
                f = json.dumps([["project_type:modpack"], ["categories:fabric", "categories:quilt"]])
                u = f"https://api.modrinth.com/v2/search?query={q}&facets={f}&limit=20"
                d = requests.get(u, headers={"User-Agent": "Orbus/3.1"}).json()
                for h in d.get("hits", []): self.after(0, lambda x=h: self.add_search_result(x))
            except: pass
        threading.Thread(target=run, daemon=True).start()

    def add_search_result(self, h):
        fr = ctk.CTkFrame(self.results_frame)
        fr.pack(fill="x", pady=5, padx=5)
        ctk.CTkLabel(fr, text="📦", width=50).pack(side="left", padx=10)
        ctk.CTkLabel(fr, text=f"{h['title']}\nby {h['author']}", anchor="w", justify="left").pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(fr, text="Install", width=80, command=lambda p=h['project_id']: self.install_from_modrinth(p)).pack(side="right", padx=10)

    def install_from_modrinth(self, pid):
        def run():
            try:
                self.after(0, lambda: self.show_progress_ui("Downloading..."))
                v = requests.get(f"https://api.modrinth.com/v2/project/{pid}/version").json()
                u = v[0]['files'][0]['url']
                t = os.path.join(INSTANCES_DIR, "download.mrpack")
                with open(t, "wb") as f: f.write(requests.get(u).content)
                self.process_modpack(t)
            except Exception as e: self.after(0, lambda: messagebox.showerror("Error", str(e)))
        threading.Thread(target=run, daemon=True).start()

    def import_modpack(self):
        p = filedialog.askopenfilename(filetypes=[("Modpacks", "*.mrpack *.zip")])
        if p: self.show_progress_ui("Importing..."); threading.Thread(target=self.process_modpack, args=(p,), daemon=True).start()

    def process_modpack(self, path):
        try:
            with zipfile.ZipFile(path, 'r') as z:
                if "modrinth.index.json" in z.namelist(): self.install_mrpack(z)
                else: self.install_basic_zip(z, path)
            self.after(0, self.cleanup_installation)
        except Exception as e: self.after(0, lambda: messagebox.showerror("Error", str(e)))

    def cleanup_installation(self):
        if self.progress_win: self.progress_win.destroy()
        self.refresh_instance_buttons(); messagebox.showinfo("Success", "Done!")

    def install_mrpack(self, z):
        idx = json.loads(z.read("modrinth.index.json"))
        n = idx.get("name", "Pack"); d = idx["dependencies"]
        ldr = "Fabric" if "fabric-loader" in d else "Quilt" if "quilt-loader" in d else "Vanilla"
        self.instances[n] = {"username": self.username_entry.get(), "version": d["minecraft"], "loader": ldr, "loader_version": "latest"}
        self.save_config(); p = os.path.join(INSTANCES_DIR, n); os.makedirs(p, exist_ok=True)
        
        # 1. Download Mods
        fs = idx.get("files", [])
        for i, f_o in enumerate(fs):
            self.after(0, lambda v=(i+1)/len(fs): self.prog_bar.set(v))
            dst = os.path.join(p, f_o["path"]); os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f: f.write(requests.get(f_o["downloads"][0]).content)
        
        # 2. Extract Overrides (This is where CONFIGS are hidden!)
        for file in z.namelist():
            if file.startswith("overrides/"):
                rel_path = file.replace("overrides/", "")
                if rel_path:
                    dest = os.path.join(p, rel_path)
                    if file.endswith("/"): os.makedirs(dest, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with open(dest, "wb") as f: f.write(z.read(file))

    def install_basic_zip(self, z, p_orig):
        n = os.path.splitext(os.path.basename(p_orig))[0]
        self.instances[n] = {"username": "", "version": "1.21.1", "loader": "Vanilla", "loader_version": "latest"}
        self.save_config(); p = os.path.join(INSTANCES_DIR, n); os.makedirs(p, exist_ok=True)
        z.extractall(p)

    def show_progress_ui(self, txt):
        if self.progress_win: self.progress_win.destroy()
        self.progress_win = ctk.CTkToplevel(self); self.progress_win.geometry("400x150")
        ctk.CTkLabel(self.progress_win, text=txt).pack(pady=20)
        self.prog_bar = ctk.CTkProgressBar(self.progress_win, width=300); self.prog_bar.pack(); self.prog_bar.set(0)

    # --- LAUNCH LOGIC ---
    def start_launch_thread(self):
        if self.current_instance_name:
            self.save_config()
            self.launch_btn.configure(state="disabled", text="Launching...")
            threading.Thread(target=self.launch, daemon=True).start()
        else: messagebox.showwarning("Warning", "Select an instance.")

    def launch(self):
        try:
            target = self.current_instance_name
            d = self.instances[target].copy()
            v, loader, user = d.get("version"), d.get("loader", "Vanilla"), d.get("username")
            l_ver = d.get("loader_version", "latest")
            
            if not v or not user: raise Exception("Version or Username missing.")

            inst_dir = os.path.abspath(os.path.join(INSTANCES_DIR, target))
            os.makedirs(inst_dir, exist_ok=True)
            # Create config dir if missing
            os.makedirs(os.path.join(inst_dir, "config"), exist_ok=True)

            def set_st(t): self.after(0, lambda: self.status_label.configure(text=t))
            set_st(f"Preparing {target}...")

            minecraft_launcher_lib.install.install_minecraft_version(v, MINECRAFT_DIR, callback={'setStatus': set_st})

            l_id = str(v)
            if loader == "Fabric":
                actual_loader = l_ver
                if l_ver == "latest":
                    fabric_meta = requests.get("https://meta.fabricmc.net/v2/versions/loader").json()
                    actual_loader = fabric_meta[0]["version"]
                minecraft_launcher_lib.fabric.install_fabric(v, MINECRAFT_DIR, loader_version=actual_loader)
                l_id = f"fabric-loader-{actual_loader}-{v}"
            elif loader == "Quilt":
                minecraft_launcher_lib.quilt.install_quilt(v, MINECRAFT_DIR)
                l_id = f"quilt-loader-{v}"

            set_st("Checking files...")
            java = shutil.which("javaw") or shutil.which("java") or "java"
            opts = {"username": user, "uuid": "0", "token": "0", "gameDir": inst_dir, "executablePath": java}
            
            cmd = minecraft_launcher_lib.command.get_minecraft_command(l_id, MINECRAFT_DIR, opts)
            
            # STRENGTHENED GameDir Enforcement
            if "--gameDir" not in cmd: cmd.extend(["--gameDir", inst_dir])
            else:
                for i, arg in enumerate(cmd):
                    if arg == "--gameDir": cmd[i+1] = inst_dir

            log_win = ctk.CTkToplevel(self)
            log_win.title(f"Logs - {target}")
            log_win.geometry("800x400")
            log_text = ctk.CTkTextbox(log_win, font=("Courier New", 12))
            log_text.pack(expand=True, fill="both", padx=10, pady=10)

            # Important: set cwd to inst_dir so the game looks there first
            process = subprocess.Popen(cmd, cwd=inst_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

            def stream_logs():
                for line in iter(process.stdout.readline, ""):
                    if line: self.after(0, lambda l=line: self.append_log(log_text, l))
                process.stdout.close()

            threading.Thread(target=stream_logs, daemon=True).start()
            self.withdraw()
            
            def check_alive():
                if process.poll() is None: self.after(1000, check_alive)
                else:
                    self.after(0, self.deiconify)
                    self.after(0, lambda: self.launch_btn.configure(state="normal", text="LAUNCH GAME"))
                    self.after(0, lambda: self.status_label.configure(text="Ready"))

            check_alive()
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Launch Error", f"Failure: {str(e)}"))
            self.after(0, lambda: self.launch_btn.configure(state="normal", text="LAUNCH GAME"))

    def append_log(self, widget, line):
        widget.insert("end", line)
        widget.see("end")

if __name__ == "__main__":
    app = OrbusLauncher(); app.mainloop()