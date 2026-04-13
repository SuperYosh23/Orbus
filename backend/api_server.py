#!/usr/bin/env python3
"""
Orbus Launcher Backend API Server
Flask-based HTTP API for Electron frontend communication
"""

import os
import sys
import json
import shutil
import zipfile
import subprocess
import threading
import re
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import urllib.request

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def install_dependencies():
    """Try to install dependencies using available pip"""
    deps = ["minecraft-launcher-lib", "requests"]
    
    # Try different pip methods
    pip_commands = [
        [sys.executable, "-m", "pip"],
        ["pip3"],
        ["pip"],
    ]
    
    for pip_cmd in pip_commands:
        try:
            # Test if pip works
            result = subprocess.run(pip_cmd + ["--version"], 
                                   capture_output=True, check=False, timeout=5)
            if result.returncode == 0:
                print(f"Installing dependencies using {' '.join(pip_cmd)}...")
                subprocess.check_call(pip_cmd + ["install"] + deps + ["-q"])
                return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    return False

try:
    import minecraft_launcher_lib
    import requests
except ImportError:
    print("Required dependencies not found: minecraft-launcher-lib, requests")
    
    if install_dependencies():
        import minecraft_launcher_lib
        import requests
    else:
        print("\n" + "="*60)
        print("ERROR: Could not install dependencies automatically.")
        print("="*60)
        print("\nPlease install manually using one of these commands:")
        print(f"  {sys.executable} -m pip install minecraft-launcher-lib requests")
        print("  pip3 install minecraft-launcher-lib requests")
        print("  pip install minecraft-launcher-lib requests")
        print("\nOr use your system package manager:")
        if sys.platform.startswith("linux"):
            print("  sudo apt-get install python3-pip  # Debian/Ubuntu")
            print("  sudo dnf install python3-pip      # Fedora")
            print("  sudo pacman -S python-pip         # Arch")
        print("\nThen run the launcher again.")
        print("="*60)
        sys.exit(1)

# Configuration
def get_minecraft_dir():
    if sys.platform.startswith("win"):
        return os.path.join(os.environ["APPDATA"], ".minecraft")
    return os.path.expanduser("~/.minecraft")

MINECRAFT_DIR = get_minecraft_dir()
INSTANCES_DIR = os.path.join(MINECRAFT_DIR, "orbus_instances")
CONFIG_FILE = os.path.join(MINECRAFT_DIR, "orbus_config.json")
SETTINGS_FILE = os.path.join(MINECRAFT_DIR, "orbus_settings.json")

os.makedirs(INSTANCES_DIR, exist_ok=True)

# Global launch process reference
launch_processes = {}

# ============== Helper Functions ==============

def load_config():
    """Load instances configuration"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config):
    """Save instances configuration"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def load_settings():
    """Load application settings"""
    default_settings = {
        "corner_radius": 8,
        "sidebar_position": "left",
        "default_username": "",
        "show_logo": True
    }
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                loaded = json.load(f)
                return {**default_settings, **loaded}
        except:
            return default_settings
    return default_settings

def save_settings(settings):
    """Save application settings"""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

def find_system_javas(deep=False):
    """Find Java installations on the system"""
    java_paths = set()
    
    if os.environ.get("JAVA_HOME"):
        java_paths.add(os.path.join(os.environ["JAVA_HOME"], "bin", "javaw.exe" if sys.platform == "win32" else "java"))
    
    for candidate in ("javaw", "java", "java.exe", "javaw.exe"):
        p = shutil.which(candidate)
        if p:
            java_paths.add(os.path.abspath(p))
    
    for pdir in os.environ.get("PATH", "").split(os.pathsep):
        try:
            if not os.path.isdir(pdir):
                continue
            for fname in os.listdir(pdir):
                if fname.lower().startswith("java") and os.access(os.path.join(pdir, fname), os.X_OK):
                    java_paths.add(os.path.abspath(os.path.join(pdir, fname)))
        except:
            pass
    
    search_dirs = []
    if sys.platform == "win32":
        search_dirs = [
            r"C:\Program Files\Java", r"C:\Program Files (x86)\Java",
            r"C:\Program Files\Eclipse Adoptium", r"C:\Program Files\Microsoft",
            r"C:\Program Files\BellSoft", r"C:\Program Files\Azul Systems",
            r"C:\ProgramData\Oracle\Java", r"C:\Program Files\Amazon Corretto"
        ]
    elif sys.platform.startswith("linux"):
        search_dirs = ["/usr/lib/jvm", "/opt", "/usr/java"]
    elif sys.platform == "darwin":
        search_dirs = ["/Library/Java/JavaVirtualMachines"]
    
    for root_dir in search_dirs:
        if os.path.exists(root_dir):
            for dirpath, _, filenames in os.walk(root_dir):
                if dirpath.count(os.sep) - root_dir.count(os.sep) > (4 if not deep else 8):
                    continue
                targets = ("javaw.exe", "java.exe") if sys.platform == "win32" else ("java",)
                for t in targets:
                    if t in filenames:
                        java_paths.add(os.path.abspath(os.path.join(dirpath, t)))
    
    normalized = set()
    for p in java_paths:
        try:
            rp = os.path.realpath(p)
            if os.path.exists(rp) and os.access(rp, os.X_OK):
                normalized.add(rp)
        except:
            pass
    
    results = []
    for p in sorted(normalized):
        try:
            proc = subprocess.run([p, "-version"], capture_output=True, text=True, timeout=2)
            output = (proc.stderr or "") + (proc.stdout or "")
            if re.search(r'\b(java version|openjdk|hotspot|jre|jdk)\b', output, re.IGNORECASE):
                version_match = re.search(r'version "([^"]+)"', output)
                version = version_match.group(1) if version_match else "Unknown"
                arch = "64-bit" if "64-bit" in output else "32-bit"
                results.append({"path": p, "version": version, "arch": arch})
        except:
            pass
    
    return sorted(results, key=lambda x: x['version'], reverse=True)

def get_default_icon():
    """Get default icon for new instances"""
    mine_icon_path = os.path.join(MINECRAFT_DIR, "mine.png")
    if os.path.exists(mine_icon_path):
        return mine_icon_path
    
    try:
        response = requests.get("https://gyazo.com/a4abc5fdb965d1b97db38453012efc73/thumb/1000", timeout=10)
        if response.status_code == 200:
            with open(mine_icon_path, 'wb') as f:
                f.write(response.content)
            return mine_icon_path
    except:
        pass
    
    return ""

def open_path(path):
    """Open a folder in the system file manager"""
    full_path = os.path.join(INSTANCES_DIR, path) if not os.path.isabs(path) else path
    
    if sys.platform == "win32":
        os.startfile(full_path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", full_path])
    else:
        subprocess.Popen(["xdg-open", full_path])

# ============== API Handler ==============

class APIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass
    
    def send_json_response(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def read_json_body(self):
        """Read JSON from request body"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length).decode()
            return json.loads(body)
        return {}
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)  # Decode URL-encoded characters
        query = urllib.parse.parse_qs(parsed.query)
        
        # API Routes
        if path == '/api/instances':
            config = load_config()
            self.send_json_response(config)
        
        elif path == '/api/versions':
            try:
                versions = minecraft_launcher_lib.utils.get_version_list()
                releases = [v["id"] for v in versions if v["type"] == "release"]
                self.send_json_response(releases)
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
        
        elif path == '/api/fabric-versions':
            try:
                data = requests.get("https://meta.fabricmc.net/v2/versions/loader").json()
                versions = ["latest"] + [v["version"] for v in data]
                self.send_json_response(versions)
            except Exception as e:
                self.send_json_response(["latest"])
        
        elif path == '/api/settings':
            self.send_json_response(load_settings())
        
        elif path == '/api/java/detect':
            deep = query.get('deep', ['false'])[0] == 'true'
            javas = find_system_javas(deep=deep)
            self.send_json_response(javas)
        
        elif path.startswith('/api/modrinth/project/'):
            parts = path.split('/')
            if len(parts) >= 5:
                project_id = parts[4]
                try:
                    response = requests.get(
                        f"https://api.modrinth.com/v2/project/{project_id}/version",
                        headers={"User-Agent": "Orbus/4.0"}
                    )
                    versions = response.json()
                    version_list = []
                    for v in versions:
                        version_list.append({
                            "id": v["id"],
                            "name": v.get("name", v.get("version_number", "Unknown")),
                            "version_number": v.get("version_number", ""),
                            "date_published": v.get("date_published", "")
                        })
                    self.send_json_response(version_list)
                except Exception as e:
                    self.send_json_response({"error": str(e)}, 500)
        
        else:
            self.send_json_response({"error": "Not found"}, 404)
    
    def do_POST(self):
        """Handle POST requests"""
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)  # Decode URL-encoded characters
        body = self.read_json_body()
        
        if path == '/api/instances':
            # Create new instance
            name = body.get('name')
            if not name:
                self.send_json_response({"error": "Name required"}, 400)
                return
            
            config = load_config()
            if name in config:
                self.send_json_response({"error": "Instance already exists"}, 400)
                return
            
            config[name] = {
                "username": body.get('username', ''),
                "version": body.get('version', '1.21.1'),
                "loader": body.get('loader', 'Vanilla'),
                "loader_version": body.get('loader_version', 'latest'),
                "ram": body.get('ram', 4),
                "java_path": body.get('java_path', ''),
                "icon_path": get_default_icon(),
                "show_console_logs": body.get('show_console_logs', False)
            }
            
            # Create instance directory
            instance_dir = os.path.join(INSTANCES_DIR, name)
            os.makedirs(instance_dir, exist_ok=True)
            
            save_config(config)
            self.send_json_response({"success": True})
        
        elif path.startswith('/api/instances/') and path.endswith('/launch'):
            # Launch instance
            parts = path.split('/')
            name = parts[3]
            config = load_config()
            
            if name not in config:
                self.send_json_response({"error": "Instance not found"}, 404)
                return
            
            instance = config[name]
            
            # Launch in background thread
            def launch():
                try:
                    target_dir = os.path.join(INSTANCES_DIR, name)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    v = instance.get("version")
                    loader = instance.get("loader", "Vanilla")
                    user = instance.get("username", "Player")
                    l_ver = instance.get("loader_version", "latest")
                    ram = instance.get("ram", 4)
                    custom_java = instance.get("java_path", "").strip()
                    
                    # Install Minecraft
                    minecraft_launcher_lib.install.install_minecraft_version(v, MINECRAFT_DIR)
                    
                    # Install loader
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
                    
                    # Determine Java path
                    if custom_java and os.path.exists(custom_java):
                        java = custom_java
                    else:
                        if sys.platform.startswith("linux"):
                            java_path = shutil.which("java") or shutil.which("javaw")
                        else:
                            java_path = shutil.which("javaw") or shutil.which("java")
                        
                        if not java_path:
                            raise Exception("Java not found in PATH")
                        java = os.path.abspath(java_path)
                    
                    # Launch options
                    import uuid as uuidlib
                    jvm_args = [f"-Xmx{ram}G", f"-Xms{ram}G", "-XX:+UseG1GC"]
                    opts = {
                        "username": user,
                        "uuid": str(uuidlib.uuid3(uuidlib.NAMESPACE_DNS, user)),  # Generate valid UUID from username
                        "token": "",
                        "gameDir": target_dir,
                        "executablePath": java,
                        "jvmArguments": jvm_args
                    }
                    
                    cmd = minecraft_launcher_lib.command.get_minecraft_command(l_id, MINECRAFT_DIR, opts)
                    
                    # Ensure gameDir is set correctly
                    if "--gameDir" not in cmd:
                        cmd.extend(["--gameDir", target_dir])
                    else:
                        for i, arg in enumerate(cmd):
                            if arg == "--gameDir":
                                cmd[i+1] = target_dir
                    
                    # Launch process
                    process = subprocess.Popen(
                        cmd,
                        cwd=target_dir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    
                    launch_processes[name] = process
                    
                    # Stream output to both console and log file
                    log_lines = []
                    def stream_output(stream):
                        for line in iter(stream.readline, ""):
                            log_lines.append(line)
                            print(f"[{name}] {line}", end="", flush=True)
                        stream.close()
                    
                    # Start output streaming thread
                    output_thread = threading.Thread(target=stream_output, args=(process.stdout,))
                    output_thread.daemon = True
                    output_thread.start()
                    
                    # Wait for process
                    process.wait()
                    
                    # Save log to file
                    log_dir = os.path.join(target_dir, "logs")
                    os.makedirs(log_dir, exist_ok=True)
                    with open(os.path.join(log_dir, "latest.log"), "w") as f:
                        f.writelines(log_lines)
                    
                    if name in launch_processes:
                        del launch_processes[name]
                    
                except Exception as e:
                    print(f"Launch error: {e}")
            
            thread = threading.Thread(target=launch, daemon=True)
            thread.start()
            
            self.send_json_response({"success": True})
        
        elif path.startswith('/api/instances/') and path.endswith('/rename'):
            # Rename instance
            parts = path.split('/')
            old_name = parts[3]
            new_name = body.get('new_name')
            
            if not new_name:
                self.send_json_response({"error": "New name required"}, 400)
                return
            
            config = load_config()
            
            if old_name not in config:
                self.send_json_response({"error": "Instance not found"}, 404)
                return
            
            if new_name in config:
                self.send_json_response({"error": "Name already exists"}, 400)
                return
            
            # Rename directory
            old_dir = os.path.join(INSTANCES_DIR, old_name)
            new_dir = os.path.join(INSTANCES_DIR, new_name)
            
            if os.path.exists(old_dir):
                shutil.move(old_dir, new_dir)
            
            # Update config
            config[new_name] = config.pop(old_name)
            
            # Update icon path
            icon_path = config[new_name].get("icon_path", "")
            if icon_path and old_name in icon_path:
                config[new_name]["icon_path"] = icon_path.replace(old_name, new_name)
            
            save_config(config)
            self.send_json_response({"success": True})
        
        elif path == '/api/instances/reorder':
            # Reorder instances
            new_order = body.get('order', [])
            config = load_config()
            
            new_config = {}
            for name in new_order:
                if name in config:
                    new_config[name] = config[name]
            
            # Add any missing instances
            for name in config:
                if name not in new_config:
                    new_config[name] = config[name]
            
            save_config(new_config)
            self.send_json_response({"success": True})
        
        elif path == '/api/modrinth/search':
            # Search Modrinth
            query = body.get('query', '')
            try:
                facets = json.dumps([["project_type:modpack"], ["categories:fabric", "categories:quilt"]])
                url = f"https://api.modrinth.com/v2/search?query={urllib.parse.quote(query)}&facets={facets}&limit=20"
                response = requests.get(url, headers={"User-Agent": "Orbus/4.0"})
                data = response.json()
                
                hits = data.get("hits", [])
                results = []
                for h in hits:
                    results.append({
                        "project_id": h.get("project_id"),
                        "title": h.get("title"),
                        "author": h.get("author"),
                        "icon_url": h.get("icon_url")
                    })
                
                self.send_json_response(results)
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
        
        elif path == '/api/modrinth/install':
            # Install modpack
            project_id = body.get('project_id')
            version_id = body.get('version_id')
            title = body.get('title', 'Modpack')
            icon_url = body.get('icon_url')
            
            try:
                # Get version info
                response = requests.get(
                    f"https://api.modrinth.com/v2/version/{version_id}",
                    headers={"User-Agent": "Orbus/4.0"}
                )
                version_info = response.json()
                
                # Download modpack
                download_url = version_info['files'][0]['url']
                temp_path = os.path.join(INSTANCES_DIR, "download.mrpack")
                
                r = requests.get(download_url)
                with open(temp_path, "wb") as f:
                    f.write(r.content)
                
                # Extract modpack
                with zipfile.ZipFile(temp_path, 'r') as z:
                    idx = json.loads(z.read("modrinth.index.json"))
                    pack_name = title or idx.get("name", "Pack")
                    deps = idx["dependencies"]
                    
                    loader = "Vanilla"
                    if "fabric-loader" in deps:
                        loader = "Fabric"
                    elif "quilt-loader" in deps:
                        loader = "Quilt"
                    
                    # Download icon
                    icon_path = ""
                    if icon_url:
                        try:
                            icon_response = requests.get(icon_url, timeout=10)
                            if icon_response.status_code == 200:
                                instance_dir = os.path.join(INSTANCES_DIR, pack_name)
                                os.makedirs(instance_dir, exist_ok=True)
                                icon_path = os.path.join(instance_dir, "icon.png")
                                with open(icon_path, "wb") as f:
                                    f.write(icon_response.content)
                        except:
                            pass
                    
                    if not icon_path:
                        icon_path = get_default_icon()
                    
                    # Create instance config
                    config = load_config()
                    config[pack_name] = {
                        "username": "",
                        "version": deps["minecraft"],
                        "loader": loader,
                        "loader_version": "latest",
                        "ram": 4,
                        "java_path": "",
                        "icon_path": icon_path,
                        "show_console_logs": False
                    }
                    
                    # Extract files
                    instance_dir = os.path.join(INSTANCES_DIR, pack_name)
                    os.makedirs(instance_dir, exist_ok=True)
                    
                    for f_o in idx.get("files", []):
                        dst = os.path.join(instance_dir, f_o["path"])
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        with open(dst, "wb") as f:
                            f.write(requests.get(f_o["downloads"][0]).content)
                    
                    # Extract overrides
                    for file in z.namelist():
                        if file.startswith("overrides/"):
                            rel_path = file.replace("overrides/", "")
                            if rel_path:
                                dest = os.path.join(instance_dir, rel_path)
                                if file.endswith("/"):
                                    os.makedirs(dest, exist_ok=True)
                                else:
                                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                                    with open(dest, "wb") as f:
                                        f.write(z.read(file))
                    
                    save_config(config)
                
                # Clean up
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                self.send_json_response({"success": True})
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
        
        elif path == '/api/import':
            # Import modpack from file
            file_path = body.get('file_path')
            
            try:
                with zipfile.ZipFile(file_path, 'r') as z:
                    if "modrinth.index.json" in z.namelist():
                        # Install as modrinth pack
                        idx = json.loads(z.read("modrinth.index.json"))
                        pack_name = idx.get("name", "Imported Pack")
                        deps = idx["dependencies"]
                        
                        loader = "Vanilla"
                        if "fabric-loader" in deps:
                            loader = "Fabric"
                        elif "quilt-loader" in deps:
                            loader = "Quilt"
                        
                        config = load_config()
                        config[pack_name] = {
                            "username": "",
                            "version": deps["minecraft"],
                            "loader": loader,
                            "loader_version": "latest",
                            "ram": 4,
                            "java_path": "",
                            "icon_path": get_default_icon(),
                            "show_console_logs": False
                        }
                        
                        instance_dir = os.path.join(INSTANCES_DIR, pack_name)
                        os.makedirs(instance_dir, exist_ok=True)
                        
                        # Extract files
                        for f_o in idx.get("files", []):
                            dst = os.path.join(instance_dir, f_o["path"])
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            with open(dst, "wb") as f:
                                f.write(requests.get(f_o["downloads"][0]).content)
                        
                        # Extract overrides
                        for file in z.namelist():
                            if file.startswith("overrides/"):
                                rel_path = file.replace("overrides/", "")
                                if rel_path:
                                    dest = os.path.join(instance_dir, rel_path)
                                    if file.endswith("/"):
                                        os.makedirs(dest, exist_ok=True)
                                    else:
                                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                                        with open(dest, "wb") as f:
                                            f.write(z.read(file))
                    else:
                        # Basic zip import
                        pack_name = os.path.splitext(os.path.basename(file_path))[0]
                        
                        config = load_config()
                        config[pack_name] = {
                            "username": "",
                            "version": "1.21.1",
                            "loader": "Vanilla",
                            "loader_version": "latest",
                            "ram": 4,
                            "java_path": "",
                            "icon_path": get_default_icon(),
                            "show_console_logs": False
                        }
                        
                        instance_dir = os.path.join(INSTANCES_DIR, pack_name)
                        os.makedirs(instance_dir, exist_ok=True)
                        
                        # Extract all files
                        for file in z.namelist():
                            if file.startswith("overrides/"):
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
                                dest = os.path.join(instance_dir, file)
                                if file.endswith("/"):
                                    os.makedirs(dest, exist_ok=True)
                                else:
                                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                                    with open(dest, "wb") as f:
                                        f.write(z.read(file))
                    
                    save_config(config)
                
                self.send_json_response({"success": True})
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
        
        elif path == '/api/folder/open':
            # Open folder
            folder_path = body.get('path', '')
            try:
                open_path(folder_path)
                self.send_json_response({"success": True})
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
        
        else:
            self.send_json_response({"error": "Not found"}, 404)
    
    def do_PUT(self):
        """Handle PUT requests"""
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)  # Decode URL-encoded characters
        body = self.read_json_body()
        
        if path.startswith('/api/instances/'):
            # Update instance
            parts = path.split('/')
            name = parts[3]
            
            config = load_config()
            
            if name not in config:
                self.send_json_response({"error": "Instance not found"}, 404)
                return
            
            # Update fields
            for key, value in body.items():
                if key in ['username', 'version', 'loader', 'loader_version', 'java_path', 'ram', 'show_console_logs']:
                    config[name][key] = value
            
            save_config(config)
            self.send_json_response({"success": True})
        
        elif path == '/api/settings':
            # Update settings
            current = load_settings()
            current.update(body)
            save_settings(current)
            self.send_json_response({"success": True})
        
        else:
            self.send_json_response({"error": "Not found"}, 404)
    
    def do_DELETE(self):
        """Handle DELETE requests"""
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)  # Decode URL-encoded characters
        
        if path.startswith('/api/instances/'):
            # Delete instance
            parts = path.split('/')
            name = parts[3]
            
            config = load_config()
            
            if name not in config:
                self.send_json_response({"error": "Instance not found"}, 404)
                return
            
            del config[name]
            
            # Remove directory
            instance_dir = os.path.join(INSTANCES_DIR, name)
            if os.path.exists(instance_dir):
                shutil.rmtree(instance_dir, ignore_errors=True)
            
            save_config(config)
            self.send_json_response({"success": True})
        
        else:
            self.send_json_response({"error": "Not found"}, 404)

# ============== Main ==============

def run_server(port=15556):
    server = HTTPServer(('localhost', port), APIHandler)
    print(f"Orbus Backend API running on http://localhost:{port}")
    server.serve_forever()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 15556
    run_server(port)
