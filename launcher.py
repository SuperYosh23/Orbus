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
SETTINGS_FILE = os.path.join(MINECRAFT_DIR, "orbus_settings.json")
ICON_PATH = os.path.join(MINECRAFT_DIR, "orbus_icon.png")
ICON_URL = "https://github.com/SuperYosh23/Orbus/blob/main/icon.png?raw=true"
MODRINTH_ICON_PATH = os.path.join(MINECRAFT_DIR, "rinth.png")
MODRINTH_ICON_URL = "https://cdn2.steamgriddb.com/icon/46bbc4a56de136ad319e59e37ef55644/32/256x256.png"

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
    def __init__(self, master, width=200, height=30, values=[], command=None, corner_radius=None, **kwargs):
        super().__init__(master, width=width, height=height, fg_color="transparent", **kwargs)
        self.command = command
        self.values = values
        self.width = width
        self.corner_radius = corner_radius
        self.is_open = False
        self.is_loading = False
        self.selected_value = values[0] if values else ""
        
        # Create main button frame
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.pack(fill="both", expand=True)
        
        # Get corner radius from settings if not provided
        if self.corner_radius is None:
            # Try to get from parent's settings
            try:
                if hasattr(master, 'settings'):
                    self.corner_radius = master.settings.get("corner_radius", 8)
                else:
                    self.corner_radius = 8
            except:
                self.corner_radius = 8
        
        self.main_button = ctk.CTkButton(self.button_frame, text=self.selected_value, width=width-30, height=height, fg_color="gray20", hover_color="gray30", corner_radius=self.corner_radius, command=self.toggle_dropdown)
        self.main_button.pack(side="left", fill="both", expand=True)
        
        # Loading spinner (hidden by default)
        self.loading_spinner = ctk.CTkProgressBar(self.button_frame, width=20, height=20)
        self.loading_spinner.configure(mode="indeterminate")
        
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
        
        # Create dropdown frame with corner radius
        self.dropdown_frame = ctk.CTkFrame(self.dropdown_window, fg_color="gray20", corner_radius=self.corner_radius)
        self.dropdown_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.search_var = ctk.StringVar()
        self.search_var.trace("w", self.filter_options)
        self.search_entry = ctk.CTkEntry(self.dropdown_frame, placeholder_text="Type to search...", textvariable=self.search_var, corner_radius=max(0, self.corner_radius-2))
        self.search_entry.pack(fill="x", padx=5, pady=5)
        self.search_entry.focus_set()
        self.scroll_frame = ctk.CTkScrollableFrame(self.dropdown_frame, width=self.width, height=250, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        self.populate_options(self.values)
        self.dropdown_window.bind("<FocusOut>", self._on_focus_out)
        
        # Bind global click to close dropdown when clicking outside using root tkinter widget
        try:
            # Get the root tkinter widget for global binding
            root = self.winfo_toplevel()
            while root.master:
                root = root.master
            self._global_click_binding = root.bind_all("<Button-1>", self._on_global_click)
        except:
            # Fallback: bind to the dropdown window itself
            self._global_click_binding = self.dropdown_window.bind("<Button-1>", self._on_global_click)

    def _on_focus_out(self, event):
        if self.dropdown_window:
            # Check if the new focus is still within our dropdown
            try:
                focused = self.focus_get()
                if focused:
                    # Check if focused widget is part of our dropdown
                    focused_str = str(focused)
                    dropdown_str = str(self.dropdown_window)
                    if focused_str.startswith(dropdown_str):
                        return  # Still focused within dropdown, don't close
            except:
                pass
            
            # If we get here, focus moved outside, so close dropdown
            self.close_dropdown()

    def populate_options(self, options):
        # Clear existing widgets
        for widget in self.scroll_frame.winfo_children(): 
            widget.destroy()
        
        if not options:
            ctk.CTkLabel(self.scroll_frame, text="No results found", text_color="gray").pack(pady=5)
        else:
            # Create buttons more efficiently
            for val in options:
                btn = ctk.CTkButton(self.scroll_frame, text=val, fg_color="transparent", text_color=("black", "white"), anchor="w", height=24, corner_radius=max(0, self.corner_radius-2), command=lambda v=val: self.select_option(v))
                btn.pack(fill="x", pady=1)

    def filter_options(self, *args):
        search_text = self.search_var.get().lower()
        self.populate_options([v for v in self.values if search_text in v.lower()])

    def select_option(self, value):
        self.selected_value = value
        self.main_button.configure(text=value)
        self.close_dropdown()
        if self.command: self.command(value)

    def _on_global_click(self, event):
        """Handle global clicks to close dropdown when clicking outside"""
        if not self.dropdown_window:
            return
            
        # Check if the clicked widget is part of our dropdown
        clicked_widget = event.widget
        try:
            # Walk up the widget hierarchy to see if any parent is our dropdown
            current = clicked_widget
            while current:
                if current == self.dropdown_window or current == self.dropdown_frame:
                    return  # Clicked within dropdown, don't close
                current = current.master
        except:
            pass
        
        # Clicked outside dropdown, close it
        self.close_dropdown()

    def close_dropdown(self):
        if self.dropdown_window:
            # Unbind global click handler
            try:
                if hasattr(self, '_global_click_binding'):
                    # Get the root tkinter widget to unbind
                    root = self.winfo_toplevel()
                    while root.master:
                        root = root.master
                    root.unbind_all("<Button-1>", self._global_click_binding)
            except:
                pass
                
            self.dropdown_window.destroy()
            self.dropdown_window = None
        self.is_open = False

    def get(self): return self.selected_value
    def set(self, value):
        self.selected_value = value
        self.main_button.configure(text=value)
    def configure(self, values=None, corner_radius=None):
        if values is not None:
            self.values = values
            if self.selected_value not in values and values:
                self.selected_value = values[0]
                self.main_button.configure(text=self.selected_value)
            
            # Check if we're in a loading state
            if values and len(values) == 1 and (values[0] == "Loading versions..." or values[0] == "Loading..."):
                self.show_loading_spinner()
            else:
                self.hide_loading_spinner()
        
        if corner_radius is not None:
            self.corner_radius = corner_radius
            self.main_button.configure(corner_radius=corner_radius)
    
    def show_loading_spinner(self):
        """Show loading spinner and hide button text"""
        self.is_loading = True
        self.main_button.configure(text="")
        self.loading_spinner.pack(side="right", padx=5)
        self.loading_spinner.start()
    
    def hide_loading_spinner(self):
        """Hide loading spinner and show button text"""
        self.is_loading = False
        self.loading_spinner.stop()
        self.loading_spinner.pack_forget()
        if self.selected_value:
            self.main_button.configure(text=self.selected_value)

# -------------------------
# Custom Themed Dialogs
# -------------------------
class ThemedDialog(ctk.CTkToplevel):
    def __init__(self, master, title, message, button_text="OK", button_color="#3B8ED0", width=400, height=200):
        super().__init__(master)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.transient(master)
        
        # Center the dialog
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Main frame
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Message label
        self.message_label = ctk.CTkLabel(main_frame, text=message, wraplength=width-60, justify="center", font=ctk.CTkFont(size=16))
        self.message_label.pack(expand=True, pady=20)
        
        # Button frame
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=10)
        
        # Action button
        self.action_button = ctk.CTkButton(button_frame, text=button_text, fg_color="#3B8ED0", 
                                         hover_color="#2E6DA4", command=self.on_action)
        self.action_button.pack(side="right", padx=5)
        
        # Result
        self.result = None
        
        # Schedule grab_set after window is visible
        self.after(10, self._grab_focus)
        
    def _grab_focus(self):
        """Set focus and grab after window is visible"""
        try:
            self.grab_set()
            self.focus_set()
        except:
            pass  # Ignore if grab fails
        
    def _get_hover_color(self, color):
        """Get a darker version of the color for hover effect"""
        # Simple color darkening - you can make this more sophisticated
        color_map = {
            "#3B8ED0": "#2E6DA4",
            "#1bd964": "#15a34a", 
            "#cf3838": "#8a2525",
            "#2d7a2d": "#1f5f1f"
        }
        return color_map.get(color, "#2E6DA4")
    
    def on_action(self):
        self.result = True
        self.destroy()
    
    def show(self):
        self.wait_window()
        return self.result

class ThemedMessageBox(ThemedDialog):
    def __init__(self, master, title, message, icon_type="info"):
        colors = {
            "info": "#3B8ED0",
            "success": "#1bd964", 
            "warning": "#f39c12",
            "error": "#cf3838"
        }
        icons = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️", 
            "error": "❌"
        }
        
        super().__init__(master, title, f"{icons.get(icon_type, 'ℹ️')} {message}", 
                        button_color=colors.get(icon_type, "#3B8ED0"))

class ThemedYesNoDialog(ThemedDialog):
    def __init__(self, master, title, message):
        super().__init__(master, title, message, width=450, height=220)
        
        # Override button setup for Yes/No
        button_frame = self.winfo_children()[0].winfo_children()[1]  # Get button frame
        
        # Clear existing button
        for widget in button_frame.winfo_children():
            widget.destroy()
        
        # Yes button
        yes_btn = ctk.CTkButton(button_frame, text="Yes", fg_color="#1bd964", 
                              hover_color="#15a34a", command=self.on_yes)
        yes_btn.pack(side="right", padx=5)
        
        # No button  
        no_btn = ctk.CTkButton(button_frame, text="No", fg_color="#cf3838", 
                             hover_color="#8a2525", command=self.on_no)
        no_btn.pack(side="right", padx=5)
        
        self.result = False
    
    def on_yes(self):
        self.result = True
        self.destroy()
    
    def on_no(self):
        self.result = False
        self.destroy()

class ThemedInputDialog(ctk.CTkToplevel):
    def __init__(self, master, title, prompt, initial_text=""):
        super().__init__(master)
        self.title(title)
        self.geometry("400x200")
        self.resizable(False, False)
        self.transient(master)
        
        # Center the dialog
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 200
        y = (self.winfo_screenheight() // 2) - 100
        self.geometry(f"400x200+{x}+{y}")
        
        # Main frame
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Prompt label
        prompt_label = ctk.CTkLabel(main_frame, text=prompt, wraplength=340, justify="center", font=ctk.CTkFont(size=16))
        prompt_label.pack(pady=(20, 10))
        
        # Entry widget
        self.entry = ctk.CTkEntry(main_frame, width=300)
        self.entry.pack(pady=10)
        self.entry.insert(0, initial_text)
        
        # Button frame
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=10)
        
        # OK button
        ok_btn = ctk.CTkButton(button_frame, text="OK", fg_color="#3B8ED0", 
                              hover_color="#2E6DA4", command=self.on_ok)
        ok_btn.pack(side="right", padx=5)
        
        # Cancel button
        cancel_btn = ctk.CTkButton(button_frame, text="Cancel", fg_color="#cf3838", 
                                 hover_color="#8a2525", command=self.on_cancel)
        cancel_btn.pack(side="right", padx=5)
        
        # Result
        self.result = None
        
        # Schedule grab_set after window is visible
        self.after(10, self._grab_focus)
        
    def _grab_focus(self):
        """Set focus and grab after window is visible"""
        try:
            self.grab_set()
            self.entry.focus_set()
        except:
            pass  # Ignore if grab fails
    
    def on_ok(self):
        self.result = self.entry.get()
        self.destroy()
    
    def on_cancel(self):
        self.result = None
        self.destroy()
    
    def show(self):
        self.wait_window()
        return self.result

# Custom dialog functions to replace messagebox
def show_info(master, title, message):
    dialog = ThemedMessageBox(master, title, message, "info")
    dialog.show()

def show_success(master, title, message):
    dialog = ThemedMessageBox(master, title, message, "success") 
    dialog.show()

def show_warning(master, title, message):
    dialog = ThemedMessageBox(master, title, message, "warning")
    dialog.show()

def show_error(master, title, message):
    dialog = ThemedMessageBox(master, title, message, "error")
    dialog.show()

def ask_yes_no(master, title, message):
    dialog = ThemedYesNoDialog(master, title, message)
    return dialog.show()

def ask_string(master, title, prompt, initial_text=""):
    dialog = ThemedInputDialog(master, title, prompt, initial_text)
    return dialog.show()
# Custom Themed Context Menu
# -------------------------
class ThemedContextMenu(ctk.CTkToplevel):
    def __init__(self, parent, x, y):
        super().__init__(parent)
        
        # Store parent reference for cleanup
        self.parent = parent
        
        # Remove window decorations
        self.overrideredirect(True)
        
        # Set position
        self.geometry(f"+{x}+{y}")
        
        # Make it stay on top
        self.attributes('-topmost', True)
        
        # Main frame
        self.frame = ctk.CTkFrame(self, fg_color="gray20", corner_radius=8)
        self.frame.pack(padx=2, pady=2)
        
        # Menu items
        self.menu_items = []
        self.result = None
        
        # Schedule focus and grab after window is visible
        self.after(10, self._setup_focus)
        
    def _setup_focus(self):
        """Set focus and grab after window is visible"""
        try:
            self.grab_set()
            self.focus_set()
        except:
            pass
    
    def add_command(self, label, command=None, icon=""):
        """Add a menu item"""
        item_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        item_frame.pack(fill="x", padx=5, pady=2)
        
        # Create button with icon if provided
        text = f"  {icon} {label}" if icon else label
        btn = ctk.CTkButton(
            item_frame, 
            text=text, 
            fg_color="transparent", 
            hover_color="gray30",
            text_color=("gray10", "gray90"),
            anchor="w",
            height=30,
            command=self._create_command(command, self.destroy)
        )
        btn.pack(fill="x", padx=5, pady=1)
        
        self.menu_items.append(btn)
        
    def add_separator(self):
        """Add a separator"""
        separator = ctk.CTkFrame(self.frame, height=1, fg_color="gray40")
        separator.pack(fill="x", padx=10, pady=5)
        
    def _create_command(self, original_command, close_action):
        """Create a wrapper command that closes the menu immediately and executes the original"""
        def wrapped():
            # Close menu immediately
            close_action()
            # Execute original command after a small delay to allow menu to close
            if original_command:
                self.after(10, original_command)
        return wrapped
    
    def show(self):
        """Show the menu and wait for it to close"""
        # Bind events to close menu
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Escape>", lambda e: self.destroy())
        
        # Bind to parent window to detect clicks outside
        self.master.bind("<Button-1>", self._on_parent_click)
        self.master.bind("<FocusIn>", self._on_parent_focus_in)
        
    def _on_focus_out(self, event):
        """Close menu when losing focus"""
        try:
            # Check if focus went to something outside our menu
            focused = self.focus_get()
            if not focused or not self._is_child_of(focused, self):
                self.destroy()
        except:
            pass
    
    def _on_parent_click(self, event):
        """Close menu when parent window is clicked"""
        try:
            # Check if the clicked widget is not part of our menu
            if not self._is_child_of(event.widget, self) and not self._is_child_of(event.widget, self.frame):
                self.destroy()
        except:
            pass
    
    def _on_parent_focus_in(self, event):
        """Close menu when parent window regains focus"""
        try:
            focused = self.focus_get()
            if focused and not self._is_child_of(focused, self):
                self.destroy()
        except:
            pass
    
    def _is_child_of(self, widget, parent):
        """Check if a widget is a child of another widget"""
        try:
            current = widget
            while current:
                if current == parent:
                    return True
                current = current.master
            return False
        except:
            return False
    
    def destroy(self):
        """Override destroy to cleanup parent bindings"""
        try:
            # Unbind parent window events
            if hasattr(self, 'parent') and self.parent:
                self.parent.unbind("<Button-1>", self._on_parent_click)
                self.parent.unbind("<FocusIn>", self._on_parent_focus_in)
        except:
            pass
        
        # Call parent destroy method
        super().destroy()

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
        self.settings = self.load_settings()
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
        self.orbus_text_label = ctk.CTkLabel(self.sidebar_frame, text="ORBUS", font=ctk.CTkFont(size=26, weight="bold"))
        self.orbus_text_label.grid(row=1, column=0, pady=(0, 20))

        # Custom header for instances with + button
        self.instances_header_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.instances_header_frame.grid(row=2, column=0, padx=15, pady=(10, 0), sticky="ew")
        self.instances_header_frame.grid_columnconfigure(0, weight=1)
        
        self.instances_label = ctk.CTkLabel(self.instances_header_frame, text="My Instances", font=ctk.CTkFont(weight="bold"))
        self.instances_label.grid(row=0, column=0, sticky="w")
        
        self.add_instance_btn = ctk.CTkButton(self.instances_header_frame, text="+", width=30, height=30, 
                                              command=self.quick_add_instance, fg_color="gray25", hover_color="gray15")
        self.add_instance_btn.grid(row=0, column=1, sticky="e")

        self.scrollable_list = ctk.CTkScrollableFrame(self.sidebar_frame, label_text="")
        self.scrollable_list.grid(row=3, column=0, padx=15, pady=(5, 10), sticky="nsew")

        self.import_btn = ctk.CTkButton(self.sidebar_frame, text="↓ Import .zip/.mrpack", command=self.import_modpack, fg_color="gray25")
        self.import_btn.grid(row=4, column=0, padx=20, pady=5)

        # Setup mod icon for Browse Modrinth button
        mod_icon_path = self.get_mod_icon()
        mod_icon_img = None
        btn_text = "Browse Modrinth"
        
        if mod_icon_path and os.path.exists(mod_icon_path):
            try:
                pil_img = Image.open(mod_icon_path)
                mod_icon_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(20, 20))
            except: pass
        else:
            # Use globe emoji as fallback
            btn_text = "🌐 Browse Modrinth"

        self.browse_btn = ctk.CTkButton(self.sidebar_frame, text=btn_text, image=mod_icon_img, compound="left", fg_color="gray25", hover_color="#2d7a2d", command=self.open_modrinth_search)
        self.browse_btn.grid(row=5, column=0, padx=20, pady=5)

        self.settings_btn = ctk.CTkButton(self.sidebar_frame, text="⚙️ Settings", command=self.open_settings, fg_color="gray25")
        self.settings_btn.grid(row=6, column=0, padx=20, pady=(5, 20))

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
        self.loader_combo = ScrollableComboBox(self.settings_frame, values=["Vanilla", "Fabric", "Quilt"], command=self.toggle_loader_settings)
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

        self.folder_btn = ctk.CTkButton(self.settings_frame, text="▤ Open Instance Folder", command=self.open_instance_folder, fg_color="gray30")
        self.folder_btn.pack(fill="x", padx=20, pady=(10, 5))
        self.mods_btn = ctk.CTkButton(self.settings_frame, text="⧉ Open Mods Folder", command=self.open_mods_folder, fg_color="gray30")
        self.mods_btn.pack(fill="x", padx=20, pady=(0, 20))

        self.status_label = ctk.CTkLabel(self.main_frame, text="Ready", text_color="gray")
        self.status_label.pack(side="bottom", pady=5)
        self.launch_btn = ctk.CTkButton(self.main_frame, text="LAUNCH GAME", height=55, font=ctk.CTkFont(size=20, weight="bold"), command=self.start_launch_thread)
        self.launch_btn.pack(side="bottom", fill="x", padx=20, pady=10)

        # No instance selected view
        self.no_instance_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.no_instance_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.no_instance_label = ctk.CTkLabel(
            self.no_instance_frame, 
            text="Select an instance from the sidebar", 
            font=ctk.CTkFont(size=18),
            text_color="gray"
        )
        self.no_instance_label.pack(expand=True)

        self.refresh_instance_buttons()
        threading.Thread(target=self.download_icon_bg, daemon=True).start()
        threading.Thread(target=self.load_versions_bg, daemon=True).start()
        threading.Thread(target=self.load_fabric_versions_bg, daemon=True).start()
        
        # Apply settings on startup
        self.apply_corner_radius()
        self.apply_sidebar_position()
        self.apply_logo_visibility()
        
        # Show correct initial view
        self.update_main_view()
        
    def update_ram_label(self, val):
        self.ram_label.configure(text=f"{int(val)} GB")

    def update_main_view(self):
        """Update main panel to show either settings or 'select instance' message"""
        if self.current_instance_name:
            # Show settings view
            self.no_instance_frame.pack_forget()
            self.settings_frame.pack(fill="both", expand=True, padx=20, pady=10)
            self.header_label.configure(text=self.current_instance_name)
            self.launch_btn.pack(side="bottom", fill="x", padx=20, pady=10)
            self.status_label.pack(side="bottom", pady=5)
        else:
            # Show "select instance" view
            self.settings_frame.pack_forget()
            self.launch_btn.pack_forget()
            self.status_label.pack_forget()
            self.no_instance_frame.pack(fill="both", expand=True, padx=20, pady=10)
            self.header_label.configure(text="Select an Instance")

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

    def get_default_icon(self):
        """Get default icon for new instances"""
        mine_icon_path = os.path.join(MINECRAFT_DIR, "mine.png")
        
        # Check if mine.png exists
        if os.path.exists(mine_icon_path):
            return mine_icon_path
        
        # Try to download the default icon
        try:
            response = requests.get("https://gyazo.com/a4abc5fdb965d1b97db38453012efc73/thumb/1000", timeout=10)
            if response.status_code == 200:
                with open(mine_icon_path, 'wb') as f:
                    f.write(response.content)
                return mine_icon_path
        except:
            pass
        
        # Fallback to empty string (will use game controller emoji in UI)
        return ""

    def get_mod_icon(self):
        """Get mod icon for Browse Modrinth button"""
        mod_icon_path = os.path.join(MINECRAFT_DIR, "mod.png")
        
        # Check if mod.png exists
        if os.path.exists(mod_icon_path):
            return mod_icon_path
        
        # Try to download the mod icon
        try:
            response = requests.get("https://cdn2.steamgriddb.com/icon/46bbc4a56de136ad319e59e37ef55644/32/256x256.png", timeout=10)
            if response.status_code == 200:
                with open(mod_icon_path, 'wb') as f:
                    f.write(response.content)
                return mod_icon_path
        except:
            pass
        
        # Fallback to empty string (will use globe emoji in UI)
        return ""

    def browse_java_path(self):
        filename = filedialog.askopenfilename(filetypes=[("Java Executable", "java javaw java.exe javaw.exe"), ("All Files", "*.*")])
        if filename:
            self.java_entry.delete(0, 'end')
            self.java_entry.insert(0, filename)

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

    def load_settings(self):
        """Load application settings from file"""
        default_settings = {
            "corner_radius": 8,
            "sidebar_position": "left",
            "default_username": "",
            "sidebar_width": 220,
            "sidebar_collapsed": False,
            "show_logo": True
        }
        
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return {**default_settings, **loaded_settings}
            except:
                return default_settings
        return default_settings

    def save_settings(self):
        """Save application settings to file"""
        with open(SETTINGS_FILE, 'w') as f: json.dump(self.settings, f, indent=4)

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

    # --- Settings Window ---
    def open_settings(self):
        self.settings_win = ctk.CTkToplevel(self)
        self.settings_win.title("Settings")
        self.settings_win.geometry("600x500")
        self.settings_win.resizable(False, False)
        
        # Create tabview for organized settings
        settings_tabview = ctk.CTkTabview(self.settings_win)
        settings_tabview.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Appearance Tab
        appearance_tab = settings_tabview.add("Appearance")
        
        # Corner Radius Settings
        ctk.CTkLabel(appearance_tab, text="Corner Radius", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 10))
        
        corner_radius_frame = ctk.CTkFrame(appearance_tab, fg_color="transparent")
        corner_radius_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(corner_radius_frame, text="Buttons:").pack(side="left", padx=10)
        self.button_radius_slider = ctk.CTkSlider(corner_radius_frame, from_=0, to=20, number_of_steps=20)
        self.button_radius_slider.set(self.settings.get("corner_radius", 8))
        self.button_radius_slider.pack(side="left", fill="x", expand=True, padx=10)
        self.button_radius_label = ctk.CTkLabel(corner_radius_frame, text=f"{self.settings.get('corner_radius', 8)}px")
        self.button_radius_label.pack(side="right", padx=10)
        self.button_radius_slider.configure(command=lambda v: self.update_settings_label("button", v))
        
        # Sidebar Position
        sidebar_frame = ctk.CTkFrame(appearance_tab, fg_color="transparent")
        sidebar_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(sidebar_frame, text="Sidebar Position:").pack(side="left", padx=10)
        self.sidebar_var = ctk.StringVar(value=self.settings.get("sidebar_position", "left"))
        sidebar_left_radio = ctk.CTkRadioButton(sidebar_frame, text="Left", variable=self.sidebar_var, value="left")
        sidebar_left_radio.pack(side="left", padx=20)
        sidebar_right_radio = ctk.CTkRadioButton(sidebar_frame, text="Right", variable=self.sidebar_var, value="right")
        sidebar_right_radio.pack(side="left", padx=5)
        
        # Logo Visibility
        logo_frame = ctk.CTkFrame(appearance_tab, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=10)
        
        self.show_logo_var = ctk.BooleanVar(value=self.settings.get("show_logo", True))
        logo_checkbox = ctk.CTkCheckBox(logo_frame, text="Show Orbus Logo", variable=self.show_logo_var)
        logo_checkbox.pack(side="left", padx=10)
        
        # Default Settings Tab
        defaults_tab = settings_tabview.add("Defaults")
        
        ctk.CTkLabel(defaults_tab, text="Default Settings", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 10))
        
        # Username
        username_frame = ctk.CTkFrame(defaults_tab, fg_color="transparent")
        username_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(username_frame, text="Default Username:").pack(side="left", padx=10)
        self.default_username_entry = ctk.CTkEntry(username_frame, width=200)
        self.default_username_entry.pack(side="left", padx=10)
        self.default_username_entry.insert(0, self.settings.get("default_username", ""))
        
        # Save/Cancel buttons
        button_frame = ctk.CTkFrame(self.settings_win, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=20)
        
        save_btn = ctk.CTkButton(button_frame, text="Save Settings", fg_color="#1bd964", hover_color="#15a34a", command=self.save_and_apply_settings)
        save_btn.pack(side="right", padx=10)
        
        cancel_btn = ctk.CTkButton(button_frame, text="Cancel", fg_color="#cf3838", hover_color="#8a2525", command=self.settings_win.destroy)
        cancel_btn.pack(side="right", padx=5)
        
        # Reset button
        reset_btn = ctk.CTkButton(button_frame, text="Reset to Defaults", fg_color="gray25", command=self.reset_settings)
        reset_btn.pack(side="left", padx=5)
    
    def update_settings_label(self, setting_type, value):
        """Update settings label dynamically"""
        if setting_type == "button":
            self.button_radius_label.configure(text=f"{int(value)}px")
        elif setting_type == "ram":
            self.default_ram_label.configure(text=f"{int(value)} GB")
    
    def browse_default_java(self):
        filename = filedialog.askopenfilename(filetypes=[("Java Executable", "java javaw java.exe javaw.exe"), ("All Files", "*.*")])
        if filename:
            self.default_java_entry.delete(0, 'end')
            self.default_java_entry.insert(0, filename)
    
    def save_and_apply_settings(self):
        """Save settings and apply them to the UI"""
        # Update settings dictionary
        self.settings["corner_radius"] = int(self.button_radius_slider.get())
        self.settings["sidebar_position"] = self.sidebar_var.get()
        self.settings["default_username"] = self.default_username_entry.get()
        self.settings["show_logo"] = self.show_logo_var.get()
        
        # Save to file
        self.save_settings()
        
        # Apply corner radius to existing widgets
        self.apply_corner_radius()
        
        # Apply sidebar position
        self.apply_sidebar_position()
        
        # Apply logo visibility
        self.apply_logo_visibility()
        
        # Show success message
        show_success(self, "Settings", "Settings saved successfully!")
        self.settings_win.destroy()
    
    def reset_settings(self):
        """Reset settings to defaults"""
        if ask_yes_no(self, "Reset Settings", "Are you sure you want to reset all settings to defaults?"):
            # Reset to defaults - create fresh default settings
            default_settings = {
                "corner_radius": 8,
                "sidebar_position": "left",
                "default_username": "",
                "sidebar_width": 220,
                "sidebar_collapsed": False,
                "show_logo": True
            }
            self.settings = default_settings
            
            # Update UI elements in settings window
            self.button_radius_slider.set(self.settings["corner_radius"])
            self.update_settings_label("button", self.settings["corner_radius"])  # Update the label
            self.sidebar_var.set(self.settings["sidebar_position"])
            self.default_username_entry.delete(0, 'end')
            self.default_username_entry.insert(0, self.settings["default_username"])
            self.show_logo_var.set(self.settings["show_logo"])
            
            # Apply the reset settings to the main UI
            self.apply_corner_radius()
            self.apply_sidebar_position()
            self.apply_logo_visibility()
            
            # Save the reset settings
            self.save_settings()
            
            show_success(self, "Settings", "Settings reset to defaults!")

    def apply_corner_radius(self):
        """Apply corner radius to all relevant widgets"""
        radius = self.settings["corner_radius"]
        # Apply to main buttons
        for widget in [self.browse_btn, self.import_btn, self.settings_btn, self.add_instance_btn, self.launch_btn]:
            widget.configure(corner_radius=radius)
        
        # Apply to instance buttons
        for widget in self.instance_widgets:
            widget.configure(corner_radius=radius)
        
        # Apply to other UI elements
        for widget in [self.username_entry, self.java_entry, self.ram_slider]:
            widget.configure(corner_radius=radius)
        
        # Apply to ScrollableComboBox widgets
        for widget in [self.version_combo, self.loader_combo, self.loader_ver_combo]:
            if hasattr(widget, 'configure'):
                widget.configure(corner_radius=radius)

    def apply_sidebar_position(self):
        """Apply sidebar position setting"""
        position = self.settings["sidebar_position"]
        
        if position == "right":
            # Move sidebar to right
            self.sidebar_frame.grid_forget()
            self.sidebar_frame.grid(row=0, column=2, sticky="nsew")
            self.main_frame.grid_forget()
            self.main_frame.grid(row=0, column=1, sticky="nsew", padx=(30, 30), pady=30)
        else:
            # Move sidebar to left
            self.sidebar_frame.grid_forget()
            self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
            self.main_frame.grid_forget()
            self.main_frame.grid(row=0, column=1, sticky="nsew", padx=(30, 30), pady=30)

    def apply_logo_visibility(self):
        """Apply logo visibility setting"""
        show_logo = self.settings.get("show_logo", True)
        
        if show_logo:
            # Show logo and text in their original positions
            self.logo_label.grid(row=0, column=0, pady=(20, 5))
            self.orbus_text_label.grid(row=1, column=0, pady=(0, 20))
        else:
            # Hide logo and text
            self.logo_label.grid_forget()
            self.orbus_text_label.grid_forget()

    # --- Instance Buttons with Icons & Context Menu ---
    def refresh_instance_buttons(self):
        for w in self.scrollable_list.winfo_children(): w.destroy()
        self.instance_widgets = []
        self.scrollable_list.grid_columnconfigure(0, weight=1)

        keys = list(self.instances.keys())
        for i, name in enumerate(keys):
            icon_img = None
            icon_path = self.instances[name].get("icon_path")
            btn_text = name
            
            if icon_path and os.path.exists(icon_path):
                try:
                    pil_img = Image.open(icon_path)
                    icon_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(24, 24))
                except: pass
            else:
                # Use game controller emoji as fallback
                btn_text = f"🎮 {name}"

            btn = ctk.CTkButton(
                self.scrollable_list, 
                text=btn_text, 
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
        
        # Apply corner radius to newly created instance buttons
        self.apply_corner_radius()

    def show_context_menu(self, event, instance_name):
        # 1. Close any existing menu
        if self.context_menu_ref:
            try: self.context_menu_ref.destroy()
            except: pass
        
        # 2. Create new themed context menu
        menu = ThemedContextMenu(self, event.x_root, event.y_root)
        
        # Add menu items with icons
        menu.add_command("Rename Instance", lambda: self.rename_instance(instance_name), "")
        menu.add_command("Change Instance Icon", lambda: self.change_instance_icon(instance_name), "")
        menu.add_separator()
        menu.add_command("Delete Instance", lambda: self.delete_instance(instance_name), "")
        
        self.context_menu_ref = menu
        
        # 3. Show the menu
        menu.show()

    def change_instance_icon(self, name):
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
                show_error(self, "Error", f"Failed to set icon: {e}")

    # --- Drag & Drop Logic ---
    def on_drag_start(self, event, widget, index):
        self.drag_data["widget"] = widget
        self.drag_data["index"] = index
        self.drag_data["start_y"] = event.y_root
        widget.configure(fg_color="#3B8ED0")
        # Close any existing context menu when starting drag
        if self.context_menu_ref:
            try: self.context_menu_ref.destroy()
            except: pass

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
        self.update_main_view()

    def add_instance(self):
        n = ask_string(self, "New Instance", "Instance Name:")
        if n and n not in self.instances:
            # Use default username from settings file
            self.instances[n] = {
                "username": self.settings.get("default_username", ""),
                "version": "1.21.1", 
                "loader": "Vanilla", 
                "loader_version": "latest", 
                "ram": 4, 
                "java_path": "", 
                "icon_path": self.get_default_icon(),
                "show_console_logs": False
            }
            self.save_config(); self.refresh_instance_buttons(); self.select_instance(n)

    def quick_add_instance(self):
        """Quick add instance with automatic naming"""
        base_name = "New Instance"
        if base_name not in self.instances:
            n = base_name
        else:
            i = 1
            while f"{base_name} ({i})" in self.instances:
                i += 1
            n = f"{base_name} ({i})"
        
        # Use default username from settings file
        self.instances[n] = {
            "username": self.settings.get("default_username", ""),
            "version": "1.21.1", 
            "loader": "Vanilla", 
            "loader_version": "latest", 
            "ram": 4, 
            "java_path": "", 
            "icon_path": self.get_default_icon(),
            "show_console_logs": False
        }
        self.save_config(); self.refresh_instance_buttons(); self.select_instance(n)

    def delete_instance(self, instance_name=None):
        target = instance_name if instance_name else self.current_instance_name
        if not target: return
        if ask_yes_no(self, "Confirm", f"Delete '{target}'?"):
            if target in self.instances: del self.instances[target]
            folder = os.path.join(INSTANCES_DIR, target)
            if os.path.exists(folder): shutil.rmtree(folder, ignore_errors=True)
            if self.current_instance_name == target:
                self.current_instance_name = None
                self.update_main_view()
            self.save_config(); self.refresh_instance_buttons()

    def rename_instance(self, target_name=None):
        target = target_name if target_name else self.current_instance_name
        
        if not target:
            show_warning(self, "Warning", "Select an instance to rename.")
            return

        new_name = ask_string(self, "Rename Instance", f"Rename '{target}' to:", initial_text=target)
        if not new_name: return
        new_name = new_name.strip()
        if new_name == target: return
        if new_name in self.instances:
            show_error(self, "Error", f"'{new_name}' already exists.")
            return

        old_folder = os.path.join(INSTANCES_DIR, target)
        new_folder = os.path.join(INSTANCES_DIR, new_name)
        try:
            if os.path.exists(old_folder):
                if os.path.exists(new_folder):
                    show_error(self, "Error", "Target folder already exists.")
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
            show_error(self, "Rename Error", "An error occurred while renaming the instance.")

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
        self.search_entry.bind("<Return>", lambda e: self.perform_modrinth_search())
        ctk.CTkButton(container, text="Search", fg_color="#2d7a2d", hover_color="#1f5f1f", command=self.perform_modrinth_search).pack(side="right")
        self.results_frame = ctk.CTkScrollableFrame(self.search_win, label_text="Results")
        self.results_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.perform_modrinth_search(True)

    def perform_modrinth_search(self, is_rec=False):
        q = self.search_entry.get() if not is_rec else ""
        for w in self.results_frame.winfo_children(): w.destroy()
        
        # Add loading indicator
        loading_frame = ctk.CTkFrame(self.results_frame)
        loading_frame.pack(fill="x", pady=20)
        loading_label = ctk.CTkLabel(loading_frame, text="🔍 Searching Modrinth...", font=ctk.CTkFont(size=14))
        loading_label.pack()
        loading_spinner = ctk.CTkProgressBar(loading_frame, width=200, progress_color="#2d7a2d")
        loading_spinner.pack(pady=10)
        loading_spinner.configure(mode="indeterminate")
        loading_spinner.start()
        
        # Track loading state
        self.loading_results = True
        self.total_modpacks = 0
        self.loaded_modpacks = 0
        
        def run():
            try:
                f = json.dumps([["project_type:modpack"], ["categories:fabric", "categories:quilt"]])
                u = f"https://api.modrinth.com/v2/search?query={q}&facets={f}&limit=20"
                d = requests.get(u, headers={"User-Agent": "Orbus/3.3"}).json()
                
                # Update loading text to show we're loading versions
                self.after(0, lambda: loading_label.configure(text="📦 Loading modpack versions..."))
                
                hits = d.get("hits", [])
                self.total_modpacks = len(hits)
                
                # Add results
                for h in hits: 
                    self.after(0, lambda x=h: self.add_search_result(x))
                    
                # Show "no results" message if needed
                if not hits:
                    self.after(0, lambda: self.finish_loading(loading_frame))
            except Exception as e:
                self.after(0, lambda: self.remove_loading_indicator(loading_frame))
                self.after(0, lambda: self.show_search_error(str(e)))
        threading.Thread(target=run, daemon=True).start()
    
    def finish_loading(self, loading_frame):
        """Call this when all modpack versions are loaded"""
        self.loading_results = False
        self.remove_loading_indicator(loading_frame)
    
    def check_all_loaded(self):
        """Check if all modpacks have loaded their versions"""
        if hasattr(self, 'total_modpacks') and hasattr(self, 'loaded_modpacks'):
            if self.loaded_modpacks >= self.total_modpacks and self.loading_results:
                # Find and remove loading indicator
                for widget in self.results_frame.winfo_children():
                    if isinstance(widget, ctk.CTkFrame) and any(isinstance(child, ctk.CTkProgressBar) for child in widget.winfo_children()):
                        self.finish_loading(widget)
                        break

    def remove_loading_indicator(self, loading_frame):
        loading_frame.destroy()

    def show_no_results(self):
        no_results_frame = ctk.CTkFrame(self.results_frame)
        no_results_frame.pack(fill="x", pady=20)
        no_results_label = ctk.CTkLabel(no_results_frame, text="No results found.", font=ctk.CTkFont(size=14))
        no_results_label.pack()

    def show_search_error(self, error):
        error_frame = ctk.CTkFrame(self.results_frame)
        error_frame.pack(fill="x", pady=20)
        error_label = ctk.CTkLabel(error_frame, text=f"Error: {error}", font=ctk.CTkFont(size=14), text_color="red")
        error_label.pack()

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
        
        # Main content frame
        content_frame = ctk.CTkFrame(fr, fg_color="transparent")
        content_frame.pack(side="left", padx=10, fill="x", expand=True)
        # Title and author
        ctk.CTkLabel(content_frame, text=f"{h['title']}", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        ctk.CTkLabel(content_frame, text=f"by {h['author']}", text_color="gray").pack(anchor="w")
        
        # Version selection with scrollable dropdown
        version_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        version_frame.pack(fill="x", pady=(5, 0))
        ctk.CTkLabel(version_frame, text="Version:").pack(side="left")
        
        # Use ScrollableComboBox for better version handling
        version_combo = ScrollableComboBox(version_frame, width=150, values=["Loading..."])
        version_combo.pack(side="left", padx=(5, 0))
        version_combo.project_id = h['project_id']
        version_combo.icon_url = h.get('icon_url')
        version_combo.title = h['title']
        
        # Load versions in background
        threading.Thread(target=self.load_project_versions, args=(h['project_id'], version_combo), daemon=True).start()
        
        # Install button
        install_btn = ctk.CTkButton(fr, text="Install", width=80, fg_color="#2d7a2d", hover_color="#1f5f1f", command=lambda cb=version_combo: self.install_from_modrinth(cb))
        install_btn.pack(side="right", padx=10)

        # Load icon
        if h.get("icon_url"):
            threading.Thread(target=self.load_modpack_icon, args=(h["icon_url"], icon_label), daemon=True).start()

    def load_project_versions(self, project_id, version_combo):
        # Set loading state
        self.after(0, lambda: version_combo.configure(values=["Loading versions..."]))
        
        try:
            response = requests.get(f"https://api.modrinth.com/v2/project/{project_id}/version", headers={"User-Agent": "Orbus/3.3"})
            versions = response.json()
            version_list = []
            version_data = {}
            
            for version in versions:
                version_name = version.get("name", version.get("version_number", "Unknown"))
                version_list.append(version_name)
                version_data[version_name] = version
            
            # Sort versions (newest first)
            version_list.sort(key=lambda x: version_data[x].get("date_published", ""), reverse=True)
            
            # Update combo box in main thread
            self.after(0, lambda: self.update_version_combo(version_combo, version_list, version_data))
        except Exception as e:
            print(f"Error loading versions: {e}")
            self.after(0, lambda: version_combo.configure(values=["Error loading versions"]))
    
    def update_version_combo(self, version_combo, version_list, version_data):
        if version_combo.winfo_exists():
            version_combo.configure(values=version_list)
            if version_list:
                version_combo.set(version_list[0])
            version_combo.version_data = version_data
            
            # Track loaded modpacks
            if hasattr(self, 'loaded_modpacks'):
                self.loaded_modpacks += 1
                self.check_all_loaded()

    def install_from_modrinth(self, version_combo):
        selected_version = version_combo.get()
        if not selected_version or selected_version == "Loading..." or selected_version == "Error loading versions":
            show_error(self, "Error", "Please select a valid version")
            return
        
        def run():
            try:
                self.after(0, lambda: self.show_progress_ui("Downloading..."))
                version_info = version_combo.version_data[selected_version]
                download_url = version_info['files'][0]['url']
                temp_path = os.path.join(INSTANCES_DIR, "download.mrpack")
                
                with open(temp_path, "wb") as f:
                    f.write(requests.get(download_url).content)
                
                # Pass additional info for icon handling
                self.process_modpack(temp_path, version_combo.title, version_combo.icon_url)
            except Exception as e:
                self.after(0, lambda: show_error(self, "Error", str(e)))
        threading.Thread(target=run, daemon=True).start()

    def install_mrpack(self, z, pack_title=None, icon_url=None):
        idx = json.loads(z.read("modrinth.index.json"))
        n = pack_title or idx.get("name", "Pack")
        d = idx["dependencies"]
        ldr = "Fabric" if "fabric-loader" in d else "Quilt" if "quilt-loader" in d else "Vanilla"
        
        # Download and save icon if available, otherwise use default
        icon_path = ""
        if icon_url:
            try:
                icon_response = requests.get(icon_url, timeout=10)
                if icon_response.status_code == 200:
                    instance_dir = os.path.join(INSTANCES_DIR, n)
                    os.makedirs(instance_dir, exist_ok=True)
                    icon_path = os.path.join(instance_dir, "icon.png")
                    with open(icon_path, "wb") as f:
                        f.write(icon_response.content)
            except:
                pass  # Icon download failed, continue without it
        
        # If no icon was successfully downloaded, use default icon
        if not icon_path:
            icon_path = self.get_default_icon()
        
        # Use default username from settings file
        self.instances[n] = {
            "username": self.settings.get("default_username", ""),
            "version": d["minecraft"], 
            "loader": ldr, 
            "loader_version": "latest", 
            "ram": 4, 
            "java_path": "", 
            "icon_path": icon_path,
            "show_console_logs": False
        }
        self.save_config(); p = os.path.join(INSTANCES_DIR, n); os.makedirs(p, exist_ok=True)
        fs = idx.get("files", [])
        for i, f_o in enumerate(fs):
            self.after(0, lambda v=(i+1)/len(fs): self.prog_bar.set(v))
            dst = os.path.join(p, f_o["path"]); os.makedirs(os.path.dirname(dst), exist_ok=True)
            # Download the file from the URL instead of reading from zip
            with open(dst, "wb") as f:
                f.write(requests.get(f_o["downloads"][0]).content)
        for file in z.namelist():
            if file.startswith("overrides/"):
                rel_path = file.replace("overrides/", "")
                if rel_path:
                    dest = os.path.join(p, rel_path)
                    if file.endswith("/"): os.makedirs(dest, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with open(dest, "wb") as f: f.write(z.read(file))

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
        else: show_warning(self, "Warning", "Select an instance.")

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
            self.after(0, lambda: show_error(self, "Launch Error", str(e)))
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

    def import_modpack(self):
        p = filedialog.askopenfilename(filetypes=[("Modpacks", "*.mrpack *.zip")])
        if p: 
            self.show_progress_ui("Importing...")
            threading.Thread(target=self.process_modpack, args=(p, None, None), daemon=True).start()

    def process_modpack(self, path, pack_title=None, icon_url=None):
        try:
            with zipfile.ZipFile(path, 'r') as z:
                if "modrinth.index.json" in z.namelist(): self.install_mrpack(z, pack_title, icon_url)
                else: self.install_basic_zip(z, path, pack_title, icon_url)
            self.after(0, self.cleanup_installation)
        except Exception as e: self.after(0, lambda: show_error(self, "Error", str(e)))

    def install_basic_zip(self, z, path, pack_title=None, icon_url=None):
        """Install basic zip modpack without modrinth.index.json"""
        # Extract filename without extension as default name
        filename = os.path.basename(path)
        name = pack_title or os.path.splitext(filename)[0] or "Imported Pack"
        
        # Use default icon since basic zips don't have icon info
        icon_path = self.get_default_icon()
        
        # Use default username from settings file
        self.instances[name] = {
            "username": self.settings.get("default_username", ""),
            "version": "1.21.1", 
            "loader": "Vanilla", 
            "loader_version": "latest", 
            "ram": 4, 
            "java_path": "", 
            "icon_path": icon_path,
            "show_console_logs": False
        }
        self.save_config()
        
        # Extract all files to instance directory
        instance_dir = os.path.join(INSTANCES_DIR, name)
        os.makedirs(instance_dir, exist_ok=True)
        
        # Extract all files from zip
        for file in z.namelist():
            if file.startswith("overrides/"):
                # Handle overrides folder
                rel_path = file.replace("overrides/", "")
                if rel_path:
                    dest = os.path.join(instance_dir, rel_path)
                    if file.endswith("/"): 
                        os.makedirs(dest, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with open(dest, "wb") as f: 
                            f.write(z.read(file))
            elif not file.startswith("modrinth.index.json"):
                # Handle other files (excluding modrinth index)
                dest = os.path.join(instance_dir, file)
                if file.endswith("/"): 
                    os.makedirs(dest, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, "wb") as f: 
                        f.write(z.read(file))

    def cleanup_installation(self):
        if self.progress_win: self.progress_win.destroy()
        self.refresh_instance_buttons(); show_success(self, "Success", "Done!")

if __name__ == "__main__":
    app = OrbusLauncher()
    app.mainloop()