import os
import sys
import subprocess
import threading
import json
import shutil
import zipfile
import requests
import io
import re
import customtkinter as ctk
from tkinter import filedialog, messagebox, simpledialog, Menu
from PIL import Image, ImageTk
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
ICON_PATH = os.path.join(MINECRAFT_DIR, "orbus_icon.png")
ICON_URL = "https://github.com/SuperYosh23/Orbus/blob/main/icon.png?raw=true"

os.makedirs(INSTANCES_DIR, exist_ok=True)

# -------------------------
# Helper Function: Java Scanner
# -------------------------
def find_system_javas_enhanced(deep=False):
    java_paths = set()
    if os.environ.get("JAVA_HOME"):
        java_paths.add(os.path.join(os.environ["JAVA_HOME"], "bin", "javaw.exe" if sys.platform == "win32" else "java"))

    for candidate in ("javaw", "java", "java.exe", "javaw.exe"):
        p = shutil.which(candidate)
        if p: java_paths.add(os.path.abspath(p))

    for pdir in os.environ.get("PATH", "").split(os.pathsep):
        try:
            if not os.path.isdir(pdir): continue
            for fname in os.listdir(pdir):
                if fname.lower().startswith("java") and os.access(os.path.join(pdir, fname), os.X_OK):
                    java_paths.add(os.path.abspath(os.path.join(pdir, fname)))
        except: pass

    search_dirs = []
    if sys.platform == "win32":
        search_dirs = [r"C:\Program Files\Java", r"C:\Program Files (x86)\Java", r"C:\Program Files\Eclipse Adoptium", r"C:\Program Files\Microsoft", r"C:\Program Files\BellSoft", r"C:\Program Files\Azul Systems", r"C:\ProgramData\Oracle\Java", r"C:\Program Files\Amazon Corretto"]
    elif sys.platform.startswith("linux"):
        search_dirs = ["/usr/lib/jvm", "/opt", "/usr/java"]
    elif sys.platform == "darwin":
        search_dirs = ["/Library/Java/JavaVirtualMachines"]

    for root_dir in search_dirs:
        if os.path.exists(root_dir):
            for dirpath, _, filenames in os.walk(root_dir):
                if dirpath.count(os.sep) - root_dir.count(os.sep) > (4 if not deep else 8): continue
                targets = ("javaw.exe", "java.exe") if sys.platform == "win32" else ("java",)
                for t in targets:
                    if t in filenames: java_paths.add(os.path.abspath(os.path.join(dirpath, t)))

    normalized = set()
    for p in java_paths:
        try:
            rp = os.path.realpath(p)
            if os.path.exists(rp) and os.access(rp, os.X_OK): normalized.add(rp)
        except: pass

    def _probe_java(path):
        try:
            proc = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=2)
            output = (proc.stderr or "") + (proc.stdout or "")
            if not re.search(r'(?i)\b(java version|openjdk|hotspot|graalvm|jre|jdk|java\(tm\)|java virtual machine|runtime environment)\b', output): return None
            version_match = re.search(r'version "([^\"]+)"', output)
            return {"path": path, "version": version_match.group(1) if version_match else "Unknown", "arch": "64-bit" if "64-bit" in output else "32-bit"}
        except: return None

    results = []
    for p in sorted(normalized):
        info = _probe_java(p)
        if info: results.append(info)
    return sorted(results, key=lambda x: x['version'], reverse=True)

# -------------------------
# Custom Scrollable Dropdown Widget
# -------------------------
class ScrollableComboBox(ctk.CTkFrame):
    def __init__(self, master, width=200, height=30, values=[], command=None, **kwargs):
        super().__init__(master, width=width, height=height, fg_color="transparent", **kwargs)
        self.command = command
        self.values = values
        self.width = width
        self.is_open = False
        self.selected_value = values[0] if values else ""
        self.main_button = ctk.CTkButton(self, text=self.selected_value, width=width, height=height, fg_color="gray20", hover_color="gray30", command=self.toggle_dropdown)
        self.main_button.pack(fill="both", expand=True)
        self.dropdown_window = None

    def toggle_dropdown(self):
        if self.is_open: self.close_dropdown()
        else: self.open_dropdown()

    def open_dropdown(self):
        if self.dropdown_window: return
        self.is_open = True
        x = self.main_button.winfo_rootx()
        y = self.main_button.winfo_rooty() + self.main_button.winfo_height() + 5
        self.dropdown_window = ctk.CTkToplevel(self)
        self.dropdown_window.geometry(f"{self.width}x300+{x}+{y}")
        self.dropdown_window.overrideredirect(True)
        self.dropdown_window.attributes('-topmost', True)
        self.search_var = ctk.StringVar()
        self.search_var.trace("w", self.filter_options)
        self.search_entry = ctk.CTkEntry(self.dropdown_window, placeholder_text="Type to search...", textvariable=self.search_var)
        self.search_entry.pack(fill="x", padx=5, pady=5)
        self.search_entry.focus_set()
        self.scroll_frame = ctk.CTkScrollableFrame(self.dropdown_window, width=self.width, height=250)
        self.scroll_frame.pack(fill="both", expand=True)
        self.populate_options(self.values)
        self.dropdown_window.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_out(self, event):
        if self.dropdown_window:
            new_focus = event.widget.focus_get()
            try:
                if new_focus and (str(new_focus).startswith(str(self.dropdown_window))): return
            except: pass
            self.close_dropdown()

    def populate_options(self, options):
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        if not options:
            ctk.CTkLabel(self.scroll_frame, text="No results found", text_color="gray").pack(pady=5)
        else:
            for val in options:
                btn = ctk.CTkButton(self.scroll_frame, text=val, fg_color="transparent", text_color=("black", "white"), anchor="w", height=24, command=lambda v=val: self.select_option(v))
                btn.pack(fill="x", pady=1)

    def filter_options(self, *args):
        search_text = self.search_var.get().lower()
        self.populate_options([v for v in self.values if search_text in v.lower()])

    def select_option(self, value):
        self.selected_value = value
        self.main_button.configure(text=value)
        self.close_dropdown()
        if self.command: self.command(value)

    def close_dropdown(self):
        if self.dropdown_window:
            self.dropdown_window.destroy()
            self.dropdown_window = None
        self.is_open = False

    def get(self): return self.selected_value
    def set(self, value):
        self.selected_value = value
        self.main_button.configure(text=value)
    def configure(self, values=None):
        if values is not None:
            self.values = values
            if self.selected_value not in values and values:
                self.selected_value = values[0]
                self.main_button.configure(text=self.selected_value)

# -------------------------
# Main App
# -------------------------
class LogWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Minecraft Console Logs")
        self.geometry("900x500")
        self.textbox = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.textbox.pack(fill="both", expand=True, padx=10, pady=10)

    def log(self, text):
        self.textbox.insert("end", text)
        self.textbox.see("end")

class OrbusLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Orbus Launcher")
        self.geometry("1000x850")

        self.instances = self.load_config()
        self.current_instance_name = None
        self.progress_win = None
        self.tk_icon = None
        self.context_menu_ref = None # Reference to active context menu

        # Drag and Drop variables
        self.drag_data = {"widget": None, "index": None, "start_y": 0}
        self.instance_widgets = []

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === SIDEBAR ===
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(3, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="O", font=ctk.CTkFont(size=32, weight="bold"))
        self.logo_label.grid(row=0, column=0, pady=(20, 5))
        ctk.CTkLabel(self.sidebar_frame, text="ORBUS", font=ctk.CTkFont(size=26, weight="bold")).grid(row=1, column=0, pady=(0, 20))

        self.browse_btn = ctk.CTkButton(self.sidebar_frame, text="🌐 Browse Modrinth", fg_color="#1bd964", hover_color="#15a34a", text_color="black", font=ctk.CTkFont(weight="bold"), command=self.open_modrinth_search)
        self.browse_btn.grid(row=2, column=0, padx=20, pady=10)

        self.scrollable_list = ctk.CTkScrollableFrame(self.sidebar_frame, label_text="My Instances")
        self.scrollable_list.grid(row=3, column=0, padx=15, pady=10, sticky="nsew")

        self.add_btn = ctk.CTkButton(self.sidebar_frame, text="+ New Instance", command=self.add_instance, fg_color="gray25")
        self.add_btn.grid(row=4, column=0, padx=20, pady=5)

        self.import_btn = ctk.CTkButton(self.sidebar_frame, text="📥 Import .zip/.mrpack", command=self.import_modpack, fg_color="gray25")
        self.import_btn.grid(row=5, column=0, padx=20, pady=5)

        # Removed Rename Button, moved Delete Button up
        self.del_btn = ctk.CTkButton(self.sidebar_frame, text="Delete Instance", fg_color="#cf3838", hover_color="#8a2525", command=self.delete_instance)
        self.del_btn.grid(row=6, column=0, padx=20, pady=(10, 5))

        # === MAIN PANEL ===
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)

        self.header_label = ctk.CTkLabel(self.main_frame, text="Select an Instance", font=ctk.CTkFont(size=32, weight="bold"))
        self.header_label.pack(pady=(10, 20))

        self.settings_frame = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        self.settings_frame.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(self.settings_frame, text="Username").pack(anchor="w", padx=20, pady=(15, 0))
        self.username_entry = ctk.CTkEntry(self.settings_frame)
        self.username_entry.pack(fill="x", padx=20, pady=(5, 10))

        ctk.CTkLabel(self.settings_frame, text="MC Version").pack(anchor="w", padx=20)
        self.version_combo = ScrollableComboBox(self.settings_frame, values=["Loading..."])
        self.version_combo.pack(fill="x", padx=20, pady=(5, 10))

        ctk.CTkLabel(self.settings_frame, text="Mod Loader").pack(anchor="w", padx=20)
        self.loader_combo = ctk.CTkComboBox(self.settings_frame, values=["Vanilla", "Fabric", "Quilt"], command=self.toggle_loader_settings)
        self.loader_combo.pack(fill="x", padx=20, pady=(5, 10))

        self.loader_ver_label = ctk.CTkLabel(self.settings_frame, text="Fabric Loader Version")
        self.loader_ver_combo = ScrollableComboBox(self.settings_frame, values=["latest"])

        ctk.CTkLabel(self.settings_frame, text="Java Executable").pack(anchor="w", padx=20, pady=(10, 0))
        self.java_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.java_frame.pack(fill="x", padx=20, pady=(5, 10))
        self.java_entry = ctk.CTkEntry(self.java_frame, placeholder_text="Default: java/javaw")
        self.java_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.java_auto_btn = ctk.CTkButton(self.java_frame, text="Auto Detect", width=80, fg_color="#3B8ED0", command=self.open_java_detector)
        self.java_auto_btn.pack(side="right", padx=(5, 0))
        self.java_browse_btn = ctk.CTkButton(self.java_frame, text="Browse", width=80, command=self.browse_java_path)
        self.java_browse_btn.pack(side="right")

        ctk.CTkLabel(self.settings_frame, text="RAM Allocation (GB)").pack(anchor="w", padx=20, pady=(10, 0))
        self.ram_label = ctk.CTkLabel(self.settings_frame, text="4 GB", font=ctk.CTkFont(weight="bold"))
        self.ram_label.pack(anchor="w", padx=20)
        self.ram_slider = ctk.CTkSlider(self.settings_frame, from_=2, to=12, number_of_steps=10, command=self.update_ram_label)
        self.ram_slider.pack(fill="x", padx=20, pady=(5, 15))
        self.ram_slider.set(4)

        self.show_logs_var = ctk.BooleanVar(value=False)
        self.logs_chk = ctk.CTkCheckBox(self.settings_frame, text="Show Console Logs", variable=self.show_logs_var)
        self.logs_chk.pack(anchor="w", padx=20, pady=(10, 5))

        self.folder_btn = ctk.CTkButton(self.settings_frame, text="📂 Open Instance Folder", command=self.open_instance_folder, fg_color="gray30")
        self.folder_btn.pack(fill="x", padx=20, pady=(10, 5))
        self.mods_btn = ctk.CTkButton(self.settings_frame, text="🧩 Open Mods Folder", command=self.open_mods_folder, fg_color="gray30")
        self.mods_btn.pack(fill="x", padx=20, pady=(0, 20))

        self.status_label = ctk.CTkLabel(self.main_frame, text="Ready", text_color="gray")
        self.status_label.pack(side="bottom", pady=5)
        self.launch_btn = ctk.CTkButton(self.main_frame, text="LAUNCH GAME", height=55, font=ctk.CTkFont(size=20, weight="bold"), command=self.start_launch_thread)
        self.launch_btn.pack(side="bottom", fill="x", padx=20, pady=10)

        self.refresh_instance_buttons()
        threading.Thread(target=self.download_icon_bg, daemon=True).start()
        threading.Thread(target=self.load_versions_bg, daemon=True).start()
        threading.Thread(target=self.load_fabric_versions_bg, daemon=True).start()

    # --- Icon Handling ---
    def setup_icon(self):
        if os.path.exists(ICON_PATH):
            try:
                img = Image.open(ICON_PATH)
                icon_img = img.resize((32, 32), Image.Resampling.LANCZOS)
                self.tk_icon = ImageTk.PhotoImage(icon_img)
                self.wm_iconphoto(True, self.tk_icon)
                self.reload_sidebar_logo()
            except: pass

    def download_icon_bg(self):
        if not os.path.exists(ICON_PATH):
            try:
                r = requests.get(ICON_URL, timeout=10)
                if r.status_code == 200:
                    with open(ICON_PATH, 'wb') as f: f.write(r.content)
                    self.after(500, self.setup_icon)
            except: pass
        else: self.after(200, self.setup_icon)

    def reload_sidebar_logo(self):
        try:
            logo_img = ctk.CTkImage(light_image=Image.open(ICON_PATH), dark_image=Image.open(ICON_PATH), size=(60, 60))
            self.logo_label.configure(image=logo_img, text="")
        except: pass

    # --- UI Logic ---
    def browse_java_path(self):
        filename = filedialog.askopenfilename(filetypes=[("Java Executable", "java javaw java.exe javaw.exe"), ("All Files", "*.*")])
        if filename:
            self.java_entry.delete(0, 'end')
            self.java_entry.insert(0, filename)

    def update_ram_label(self, val):
        self.ram_label.configure(text=f"{int(val)} GB")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f: return json.load(f)
            except: return {}
        return {}

    def save_config(self):
        if self.current_instance_name and self.current_instance_name in self.instances:
            self.instances[self.current_instance_name].update({
                "username": self.username_entry.get(),
                "version": self.version_combo.get(),
                "loader": self.loader_combo.get(),
                "loader_version": self.loader_ver_combo.get(),
                "ram": int(self.ram_slider.get()),
                "java_path": self.java_entry.get()
            })
        with open(CONFIG_FILE, 'w') as f: json.dump(self.instances, f, indent=4)

    def load_versions_bg(self):
        try:
            versions = minecraft_launcher_lib.utils.get_version_list()
            rel = [v["id"] for v in versions if v["type"] == "release"]
            self.after(0, lambda: self.version_combo.configure(values=rel))
        except: pass

    def load_fabric_versions_bg(self):
        try:
            data = requests.get("https://meta.fabricmc.net/v2/versions/loader").json()
            versions = ["latest"] + [v["version"] for v in data]
            self.after(0, lambda: self.loader_ver_combo.configure(values=versions))
        except: pass

    def toggle_loader_settings(self, choice):
        if choice == "Fabric":
            self.loader_ver_label.pack(anchor="w", padx=20)
            self.loader_ver_combo.pack(fill="x", padx=20, pady=(5, 10))
        else:
            self.loader_ver_label.pack_forget()
            self.loader_ver_combo.pack_forget()

    # --- Instance Buttons with Icons & Context Menu ---
    def refresh_instance_buttons(self):
        for w in self.scrollable_list.winfo_children(): w.destroy()
        self.instance_widgets = []
        self.scrollable_list.grid_columnconfigure(0, weight=1)

        keys = list(self.instances.keys())
        for i, name in enumerate(keys):
            icon_img = None
            icon_path = self.instances[name].get("icon_path")
            if icon_path and os.path.exists(icon_path):
                try:
                    pil_img = Image.open(icon_path)
                    icon_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(24, 24))
                except: pass

            btn = ctk.CTkButton(
                self.scrollable_list, 
                text=name, 
                image=icon_img,
                compound="left",
                fg_color="transparent", 
                border_width=1, 
                anchor="w",
                height=40,
                command=lambda n=name: self.select_instance(n)
            )
            btn.grid(row=i, column=0, sticky="ew", pady=2)
            
            btn.bind("<Button-1>", lambda event, b=btn, idx=i: self.on_drag_start(event, b, idx))
            btn.bind("<B1-Motion>", lambda event: self.on_drag_motion(event))
            btn.bind("<ButtonRelease-1>", self.on_drag_end)

            btn.bind("<Button-3>", lambda event, n=name: self.show_context_menu(event, n))
            if sys.platform == "darwin": 
                 btn.bind("<Button-2>", lambda event, n=name: self.show_context_menu(event, n))

            self.instance_widgets.append(btn)

    def show_context_menu(self, event, instance_name):
        # 1. Close any existing menu
        if self.context_menu_ref:
            try: self.context_menu_ref.unpost()
            except: pass
        
        # 2. Create new menu
        menu = Menu(self, tearoff=0)
        menu.add_command(label="Rename Instance", command=lambda: self.rename_instance(instance_name))
        menu.add_command(label="Change Instance Icon", command=lambda: self.change_instance_icon(instance_name))
        
        self.context_menu_ref = menu
        
        # 3. Post the menu at coordinates
        menu.post(event.x_root, event.y_root)

        # 4. Bind a generic click to the entire window to close the menu
        # 'add=+' ensures we don't overwrite other click functionality in the app
        self.bind("<Button-1>", self.close_context_menu, add="+")

    def close_context_menu(self, event=None):
        if self.context_menu_ref:
            try: self.context_menu_ref.unpost()
            except: pass
            self.context_menu_ref = None
        # Clean up the binding so we don't keep firing this function
        self.unbind("<Button-1>")

    def change_instance_icon(self, name):
        self.close_context_menu()
        file_path = filedialog.askopenfilename(
            title="Select Icon",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.ico *.bmp")]
        )
        if file_path:
            dest_dir = os.path.join(INSTANCES_DIR, name)
            if not os.path.exists(dest_dir): os.makedirs(dest_dir)
            
            ext = os.path.splitext(file_path)[1]
            dest_path = os.path.join(dest_dir, f"icon{ext}")
            
            try:
                shutil.copy(file_path, dest_path)
                self.instances[name]["icon_path"] = dest_path
                self.save_config()
                self.refresh_instance_buttons()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to set icon: {e}")

    # --- Drag & Drop Logic ---
    def on_drag_start(self, event, widget, index):
        self.drag_data["widget"] = widget
        self.drag_data["index"] = index
        self.drag_data["start_y"] = event.y_root
        widget.configure(fg_color="#3B8ED0")
        self.close_context_menu() # Safety close

    def on_drag_motion(self, event):
        if not self.drag_data["widget"]: return
        dy = event.y_root - self.drag_data["start_y"]
        current_index = self.drag_data["index"]
        slot_height = 44 

        if dy > slot_height / 2:
            target_index = current_index + 1
            if target_index < len(self.instance_widgets):
                self.swap_widgets(current_index, target_index)
                self.drag_data["start_y"] += slot_height 
                self.drag_data["index"] = target_index
        elif dy < -slot_height / 2:
            target_index = current_index - 1
            if target_index >= 0:
                self.swap_widgets(current_index, target_index)
                self.drag_data["start_y"] -= slot_height
                self.drag_data["index"] = target_index

    def swap_widgets(self, i1, i2):
        self.instance_widgets[i1], self.instance_widgets[i2] = self.instance_widgets[i2], self.instance_widgets[i1]
        self.instance_widgets[i1].grid(row=i1)
        self.instance_widgets[i2].grid(row=i2)
        w1, w2 = self.instance_widgets[i1], self.instance_widgets[i2]
        w1.bind("<Button-1>", lambda e, b=w1, idx=i1: self.on_drag_start(e, b, idx))
        w2.bind("<Button-1>", lambda e, b=w2, idx=i2: self.on_drag_start(e, b, idx))

    def on_drag_end(self, event):
        if not self.drag_data["widget"]: return
        self.drag_data["widget"].configure(fg_color="transparent")
        new_order_keys = [w.cget("text") for w in self.instance_widgets]
        self._reorder_instances(new_order_keys)
        self.drag_data = {"widget": None, "index": None, "start_y": 0}

    # --- CRUD Operations ---
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
        self.ram_slider.set(d.get("ram", 4))
        self.update_ram_label(self.ram_slider.get())
        self.java_entry.delete(0, 'end')
        self.java_entry.insert(0, d.get("java_path", ""))
        self.toggle_loader_settings(d.get("loader", "Vanilla"))

    def add_instance(self):
        n = simpledialog.askstring("New", "Instance Name:")
        if n and n not in self.instances:
            self.instances[n] = {"username": "", "version": "1.21.1", "loader": "Vanilla", "loader_version": "latest", "ram": 4, "java_path": "", "icon_path": ""}
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

    def rename_instance(self, target_name=None):
        self.close_context_menu()
        target = target_name if target_name else self.current_instance_name
        
        if not target:
            messagebox.showwarning("Warning", "Select an instance to rename.")
            return

        new_name = simpledialog.askstring("Rename Instance", f"Rename '{target}' to:", initialvalue=target)
        if not new_name: return
        new_name = new_name.strip()
        if new_name == target: return
        if new_name in self.instances:
            messagebox.showerror("Error", f"'{new_name}' already exists.")
            return

        old_folder = os.path.join(INSTANCES_DIR, target)
        new_folder = os.path.join(INSTANCES_DIR, new_name)
        try:
            if os.path.exists(old_folder):
                if os.path.exists(new_folder):
                    messagebox.showerror("Error", "Target folder already exists.")
                    return
                shutil.move(old_folder, new_folder)
            
            self.instances[new_name] = self.instances.pop(target)
            icon_path = self.instances[new_name].get("icon_path", "")
            if icon_path and target in icon_path:
                 self.instances[new_name]["icon_path"] = icon_path.replace(target, new_name)

            if self.current_instance_name == target:
                self.current_instance_name = new_name
                self.header_label.configure(text=new_name)

            self.save_config()
            self.refresh_instance_buttons()
            if self.current_instance_name == new_name:
                self.select_instance(new_name)
                
        except Exception as e:
            messagebox.showerror("Rename Error", str(e))

    def _reorder_instances(self, new_order):
        try:
            old = self.instances.copy()
            new = {}
            for n in new_order: new[n] = old[n]
            self.instances = new
            if self.current_instance_name not in self.instances: self.current_instance_name = None
            self.save_config(); self.refresh_instance_buttons()
            if self.current_instance_name: self.select_instance(self.current_instance_name)
        except: pass

    # --- Other Actions ---
    def open_mods_folder(self):
        if self.current_instance_name:
            p = os.path.join(INSTANCES_DIR, self.current_instance_name, "mods")
            os.makedirs(p, exist_ok=True); self.open_path(p)

    def open_instance_folder(self):
        if self.current_instance_name:
            p = os.path.join(INSTANCES_DIR, self.current_instance_name); self.open_path(p)

    def open_path(self, path):
        if sys.platform == "win32": os.startfile(path)
        else: subprocess.Popen(["xdg-open", path])

    # --- Modpack Logic ---
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
                d = requests.get(u, headers={"User-Agent": "Orbus/3.3"}).json()
                for h in d.get("hits", []): self.after(0, lambda x=h: self.add_search_result(x))
            except: pass
        threading.Thread(target=run, daemon=True).start()

    def load_modpack_icon(self, url, label_widget):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                image_data = io.BytesIO(response.content)
                pil_image = Image.open(image_data)
                icon = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(48, 48))
                self.after(0, lambda: self.update_icon_label(label_widget, icon))
        except: pass

    def update_icon_label(self, label, icon):
        try:
            if label.winfo_exists(): label.configure(image=icon, text="")
        except: pass

    def add_search_result(self, h):
        fr = ctk.CTkFrame(self.results_frame)
        fr.pack(fill="x", pady=5, padx=5)
        icon_label = ctk.CTkLabel(fr, text="📦", width=50, height=50, font=ctk.CTkFont(size=24))
        icon_label.pack(side="left", padx=10)
        ctk.CTkLabel(fr, text=f"{h['title']}\nby {h['author']}", anchor="w", justify="left").pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(fr, text="Install", width=80, command=lambda p=h['project_id']: self.install_from_modrinth(p)).pack(side="right", padx=10)
        if h.get("icon_url"):
            threading.Thread(target=self.load_modpack_icon, args=(h["icon_url"], icon_label), daemon=True).start()

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
        self.instances[n] = {"username": self.username_entry.get(), "version": d["minecraft"], "loader": ldr, "loader_version": "latest", "ram": 4, "java_path": "", "icon_path": ""}
        self.save_config(); p = os.path.join(INSTANCES_DIR, n); os.makedirs(p, exist_ok=True)
        fs = idx.get("files", [])
        for i, f_o in enumerate(fs):
            self.after(0, lambda v=(i+1)/len(fs): self.prog_bar.set(v))
            dst = os.path.join(p, f_o["path"]); os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f: f.write(requests.get(f_o["downloads"][0]).content)
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
        self.instances[n] = {"username": "", "version": "1.21.1", "loader": "Vanilla", "loader_version": "latest", "ram": 4, "java_path": "", "icon_path": ""}
        self.save_config(); p = os.path.join(INSTANCES_DIR, n); os.makedirs(p, exist_ok=True)
        z.extractall(p)

    def show_progress_ui(self, txt):
        if self.progress_win: self.progress_win.destroy()
        self.progress_win = ctk.CTkToplevel(self); self.progress_win.geometry("400x150")
        ctk.CTkLabel(self.progress_win, text=txt).pack(pady=20)
        self.prog_bar = ctk.CTkProgressBar(self.progress_win, width=300); self.prog_bar.pack(); self.prog_bar.set(0)

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
            l_ver, ram = d.get("loader_version", "latest"), d.get("ram", 4)
            custom_java = d.get("java_path", "").strip()
            if not v or not user: raise Exception("Version or Username missing.")
            inst_dir = os.path.abspath(os.path.join(INSTANCES_DIR, target))
            os.makedirs(inst_dir, exist_ok=True)
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
            set_st("Launching...")
            if custom_java and os.path.exists(custom_java): java = custom_java
            else: java = shutil.which("javaw") or shutil.which("java") or "java"
            jvm_args = [f"-Xmx{ram}G", f"-Xms{ram}G", "-XX:+UseG1GC"]
            opts = {"username": user, "uuid": "0", "token": "0", "gameDir": inst_dir, "executablePath": java, "jvmArguments": jvm_args}
            cmd = minecraft_launcher_lib.command.get_minecraft_command(l_id, MINECRAFT_DIR, opts)
            if "--gameDir" not in cmd: cmd.extend(["--gameDir", inst_dir])
            else:
                for i, arg in enumerate(cmd):
                    if arg == "--gameDir": cmd[i+1] = inst_dir
            process = subprocess.Popen(cmd, cwd=inst_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            log_win = None
            if self.show_logs_var.get():
                log_win = LogWindow(self)
            self.withdraw()
            def stream_reader():
                for line in iter(process.stdout.readline, ""):
                    if log_win and log_win.winfo_exists():
                        self.after(0, lambda l=line: log_win.log(l))
                process.stdout.close()
            threading.Thread(target=stream_reader, daemon=True).start()
            def check_alive():
                if process.poll() is None: self.after(1000, check_alive)
                else:
                    if log_win and log_win.winfo_exists(): log_win.destroy()
                    self.after(0, self.deiconify)
                    self.after(0, lambda: self.launch_btn.configure(state="normal", text="LAUNCH GAME"))
                    self.after(0, lambda: self.status_label.configure(text="Ready"))
            check_alive()
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Launch Error", str(e)))
            self.after(0, lambda: self.launch_btn.configure(state="normal", text="LAUNCH GAME"))

    # --- Java Auto Detect ---
    def open_java_detector(self):
        self.detect_win = ctk.CTkToplevel(self)
        self.detect_win.title("Java Auto-Detect")
        self.detect_win.geometry("600x400")
        self.detect_win.attributes('-topmost', True)
        self.detect_status = ctk.CTkLabel(self.detect_win, text="Scanning system for Java...", font=ctk.CTkFont(size=16))
        self.detect_status.pack(pady=20)
        self.detect_progress = ctk.CTkProgressBar(self.detect_win)
        self.detect_progress.pack(pady=10)
        self.detect_progress.set(0)
        self.detect_progress.start()
        self.detect_scroll = ctk.CTkScrollableFrame(self.detect_win, label_text="Found Installations")
        self.deep_scan_btn = ctk.CTkButton(self.detect_win, text="Deep Scan (may take longer)", fg_color="#3B8ED0", command=lambda: threading.Thread(target=self.run_java_scan_thread, kwargs={'deep': True}, daemon=True).start())
        self.deep_scan_btn.pack(pady=8)
        threading.Thread(target=self.run_java_scan_thread, kwargs={'deep': False}, daemon=True).start()

    def run_java_scan_thread(self, deep=False):
        if hasattr(self, 'deep_scan_btn'):
            try: self.after(0, lambda: self.deep_scan_btn.configure(state="disabled"))
            except: pass
        if deep: self.after(0, lambda: self.detect_status.configure(text="Deep scanning system for Java... (may take a while)"))
        else: self.after(0, lambda: self.detect_status.configure(text="Scanning system for Java..."))
        try: self.after(0, lambda: (self.detect_progress.pack(pady=10), self.detect_progress.set(0), self.detect_progress.start()))
        except: pass
        try:
            found_javas = find_system_javas_enhanced(deep=deep)
            self.after(0, lambda: self.display_java_results(found_javas))
        finally:
            if hasattr(self, 'deep_scan_btn'):
                try: self.after(0, lambda: self.deep_scan_btn.configure(state="normal"))
                except: pass

    def display_java_results(self, javas):
        if not self.detect_win.winfo_exists(): return
        self.detect_progress.stop()
        self.detect_progress.pack_forget()
        self.detect_status.configure(text=f"Found {len(javas)} Java versions")
        self.detect_scroll.pack(fill="both", expand=True, padx=20, pady=20)
        for widget in self.detect_scroll.winfo_children(): widget.destroy()
        if not javas:
            ctk.CTkLabel(self.detect_scroll, text="No Java installations found.").pack(pady=10)
            return
        for j in javas:
            card = ctk.CTkFrame(self.detect_scroll)
            card.pack(fill="x", pady=5)
            lbl = ctk.CTkLabel(card, text=f"Java {j['version']} ({j['arch']})", font=ctk.CTkFont(weight="bold"))
            lbl.pack(side="left", padx=10, pady=5)
            path_lbl = ctk.CTkLabel(card, text=j['path'], text_color="gray", font=ctk.CTkFont(size=10))
            path_lbl.pack(side="left", padx=10)
            btn = ctk.CTkButton(card, text="Select", width=60, command=lambda p=j['path']: self.apply_detected_java(p))
            btn.pack(side="right", padx=10, pady=5)

    def apply_detected_java(self, path):
        self.java_entry.delete(0, 'end')
        self.java_entry.insert(0, path)
        self.detect_win.destroy()
        self.save_config()

if __name__ == "__main__":
    app = OrbusLauncher(); app.mainloop()