#!/usr/bin/env python3
"""
unity_ripper_enhanced_modern.py
Enhanced Unity asset ripper with modern GUI, Unity version detection, and comprehensive extraction.
"""
import os
import sys
import argparse
import UnityPy
from pathlib import Path
import traceback
import logging
from datetime import datetime
import json
import re
import struct

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, scrolledtext, messagebox
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    print("Warning: tkinter not available. GUI mode disabled.")

# Setup logging
logfile = Path("unity_ripper.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(logfile, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    return p

def sanitize_name(name: str) -> str:
    keep = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ0123456789"
    return "".join(c if c in keep else "_" for c in (name or "unnamed"))

def detect_unity_version(path: Path) -> dict:
    """Detect Unity version from asset files"""
    version_info = {
        "version": "Unknown",
        "detected_from": None,
        "compatible": True,
        "warning": None
    }
    
    try:
        # Try to load and get version from UnityPy
        env = UnityPy.load(str(path))
        if hasattr(env, 'version'):
            version_info["version"] = env.version
            version_info["detected_from"] = path.name
            return version_info
        
        # Alternative: Read file header for version info
        with open(path, 'rb') as f:
            header = f.read(1024)
            # Look for version strings in header
            version_patterns = [
                rb'(\d+\.\d+\.\d+[a-z0-9]*)',
                rb'Unity (\d+\.\d+\.\d+)',
                rb'UnityFS.*?(\d+\.\d+)'
            ]
            
            for pattern in version_patterns:
                match = re.search(pattern, header)
                if match:
                    version_str = match.group(1).decode('utf-8', errors='ignore')
                    version_info["version"] = version_str
                    version_info["detected_from"] = path.name
                    break
                    
    except Exception as e:
        logging.warning(f"Could not detect Unity version from {path}: {e}")
        version_info["warning"] = str(e)
    
    return version_info

def check_version_compatibility(version_str: str) -> tuple:
    """Check if detected Unity version is compatible with UnityPy"""
    try:
        # Extract major version
        match = re.match(r'(\d+)\.(\d+)', version_str)
        if match:
            major = int(match.group(1))
            minor = int(match.group(2))
            
            # UnityPy supports Unity 3.4 - 2023.x
            if major < 3 or (major == 3 and minor < 4):
                return False, "Unity version too old (< 3.4)"
            elif major > 2023:
                return True, "Newer version - may have limited support"
            else:
                return True, "Fully supported"
    except:
        pass
    
    return True, "Version check inconclusive"

def find_input_files(root: Path, exts=None):
    if exts is None:
        exts = {".assets", ".unity3d", ".assetbundle", ".bundle", ".resS", ".sharedassets", 
                ".resources", ".resource", ".dat", ".ress"}
    logging.info(f"Scanning {root} for asset files...")
    files = []
    try:
        for p in root.rglob("*"):
            if p.is_file():
                if p.suffix.lower() in exts or any(k in p.name.lower() for k in 
                    ("sharedassets", "resources", ".unity3d", "assetbundle", "globalgamemanagers", "level")):
                    files.append(p)
    except Exception as e:
        logging.error(f"Error scanning directory {root}: {e}")
    
    if not files:
        logging.info("No candidates found - checking top-level files.")
        try:
            for p in root.iterdir():
                if p.is_file():
                    files.append(p)
        except Exception as e:
            logging.error(f"Fallback scanning error: {e}")
    
    logging.info(f"Found {len(files)} candidate files.")
    return files

def extract_sprite(sprite_obj, out_dir: Path, path_id):
    """Extract sprite to PNG"""
    try:
        sprite = sprite_obj.read()
        name = sanitize_name(getattr(sprite, "m_Name", f"sprite_{path_id}"))
        
        if hasattr(sprite, "image") and sprite.image:
            out_path = out_dir / f"{name}_{path_id}.png"
            sprite.image.save(out_path)
            logging.info(f"    - Sprite saved: {out_path}")
            return True
        else:
            logging.warning(f"    ! Sprite {name} has no image data")
            return False
    except Exception as e:
        logging.error(f"    ! Error extracting sprite: {e}")
        return False

def extract_mono_script(script_obj, out_dir: Path, path_id):
    """Extract MonoBehaviour/MonoScript"""
    try:
        script = script_obj.read()
        name = sanitize_name(getattr(script, "m_Name", f"script_{path_id}"))
        
        script_data = None
        if hasattr(script, "m_Script"):
            script_data = script.m_Script
        elif hasattr(script, "script"):
            script_data = script.script
        
        if not script_data:
            try:
                tree = script.read_typetree()
                if tree:
                    out_path = out_dir / f"{name}_{path_id}.json"
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(tree, f, indent=2, ensure_ascii=False)
                    logging.info(f"    - Script (JSON) saved: {out_path}")
                    return True
            except Exception:
                pass
        
        if script_data:
            ext = ".cs" if any(x in str(script_data)[:100] for x in ["using ", "namespace ", "class "]) else ".txt"
            out_path = out_dir / f"{name}_{path_id}{ext}"
            
            if isinstance(script_data, str):
                with open(out_path, "w", encoding="utf-8", errors="surrogateescape") as f:
                    f.write(script_data)
            elif isinstance(script_data, (bytes, bytearray)):
                with open(out_path, "wb") as f:
                    f.write(script_data)
            
            logging.info(f"    - Script saved: {out_path}")
            return True
        
        return False
    except Exception as e:
        logging.error(f"    ! Error extracting script: {e}")
        return False

def extract_from_file(src_path: Path, out_root: Path, verbose=False, options=None):
    """Extract assets from a Unity file"""
    if options is None:
        options = {
            "textures": True, "sprites": True, "audio": True, "meshes": True,
            "texts": True, "fonts": True, "scripts": True, "materials": True
        }
    
    logging.info(f"[+] Processing: {src_path}")
    try:
        env = UnityPy.load(str(src_path))
    except Exception as e:
        logging.error(f"  ! failed to load {src_path}: {e}")
        return None

    stats = {k: 0 for k in ["textures", "sprites", "audio", "meshes", "texts", "fonts", "scripts", "materials", "other"]}

    for obj in env.objects:
        try:
            tname = getattr(obj.type, "name", str(obj.type))

            if tname == "Texture2D" and options.get("textures"):
                data = obj.read()
                if getattr(data, "image", None):
                    tex_name = sanitize_name(getattr(data, "name", None) or 
                                            getattr(data, "m_Name", None) or 
                                            f"texture_{obj.path_id}")
                    out_dir = ensure_dir(out_root / "textures")
                    out_path = out_dir / f"{tex_name}_{obj.path_id}.png"
                    data.image.save(out_path)
                    logging.info(f"    - Texture saved: {out_path}")
                    stats["textures"] += 1

            elif tname == "Sprite" and options.get("sprites"):
                out_dir = ensure_dir(out_root / "sprites")
                if extract_sprite(obj, out_dir, obj.path_id):
                    stats["sprites"] += 1

            elif tname == "AudioClip" and options.get("audio"):
                clip = obj.read()
                samples = getattr(clip, "samples", None)
                out_dir = ensure_dir(out_root / "audio")
                
                if samples:
                    for name, b in samples.items():
                        fname = sanitize_name(name or f"audio_{obj.path_id}")
                        out_path = out_dir / f"{fname}.wav"
                        with open(out_path, "wb") as f:
                            f.write(b)
                        logging.info(f"    - Audio saved: {out_path}")
                        stats["audio"] += 1

            elif tname == "Mesh" and options.get("meshes"):
                mesh = obj.read()
                try:
                    mesh_text = mesh.export()
                    out_dir = ensure_dir(out_root / "meshes")
                    name = sanitize_name(getattr(mesh, "m_Name", f"mesh_{obj.path_id}"))
                    out_path = out_dir / f"{name}.obj"
                    with open(out_path, "w", newline="") as f:
                        f.write(mesh_text)
                    logging.info(f"    - Mesh saved: {out_path}")
                    stats["meshes"] += 1
                except Exception as e:
                    logging.warning(f"    ! Can't export mesh: {e}")

            elif tname == "TextAsset" and options.get("texts"):
                ta = obj.read()
                out_dir = ensure_dir(out_root / "texts")
                name = sanitize_name(getattr(ta, "m_Name", f"text_{obj.path_id}"))
                out_path = out_dir / f"{name}.txt"
                data = getattr(ta, "m_Script", None) or getattr(ta, "script", None) or getattr(ta, "text", None)
                
                if isinstance(data, str):
                    with open(out_path, "w", encoding="utf-8", errors="surrogateescape") as f:
                        f.write(data)
                elif isinstance(data, (bytes, bytearray)):
                    with open(out_path, "wb") as f:
                        f.write(data)
                logging.info(f"    - TextAsset saved: {out_path}")
                stats["texts"] += 1

            elif tname == "Font" and options.get("fonts"):
                font = obj.read()
                out_dir = ensure_dir(out_root / "fonts")
                name = sanitize_name(getattr(font, "m_Name", f"font_{obj.path_id}"))
                font_data = getattr(font, "m_FontData", None)
                if font_data:
                    extension = ".ttf"
                    if isinstance(font_data, (bytes, bytearray)) and font_data[0:4] == b"OTTO":
                        extension = ".otf"
                    out_path = out_dir / f"{name}{extension}"
                    with open(out_path, "wb") as f:
                        f.write(font_data)
                    logging.info(f"    - Font saved: {out_path}")
                    stats["fonts"] += 1

            elif tname in ["MonoBehaviour", "MonoScript"] and options.get("scripts"):
                out_dir = ensure_dir(out_root / "scripts")
                if extract_mono_script(obj, out_dir, obj.path_id):
                    stats["scripts"] += 1

            elif tname == "Material" and options.get("materials"):
                mat = obj.read()
                try:
                    tree = mat.read_typetree()
                    if tree:
                        out_dir = ensure_dir(out_root / "materials")
                        name = sanitize_name(getattr(mat, "m_Name", f"material_{obj.path_id}"))
                        out_path = out_dir / f"{name}_{obj.path_id}.json"
                        with open(out_path, "w", encoding="utf-8") as f:
                            json.dump(tree, f, indent=2, ensure_ascii=False)
                        logging.info(f"    - Material saved: {out_path}")
                        stats["materials"] += 1
                except Exception as e:
                    logging.warning(f"    ! Can't export material: {e}")
            else:
                stats["other"] += 1

        except Exception as e:
            logging.error(f"    ! error handling object: {e}")

    logging.info(f"Stats: {stats}")
    return stats


class ModernUnityRipperGUI:
    """Modern GUI for Unity Asset Ripper with dark theme"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Unity Asset Ripper Pro")
        self.root.geometry("1000x800")
        
        # Modern color scheme
        self.colors = {
            'bg': '#1e1e2e',
            'secondary_bg': '#2a2a3e',
            'accent': '#7c3aed',
            'accent_hover': '#9333ea',
            'text': '#e0e0e0',
            'text_dim': '#a0a0b0',
            'success': '#10b981',
            'warning': '#f59e0b',
            'error': '#ef4444',
            'border': '#3a3a4e'
        }
        
        # Configure root window
        self.root.configure(bg=self.colors['bg'])
        
        # Variables
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar(value="exported_assets")
        self.verbose = tk.BooleanVar(value=False)
        self.unity_version = tk.StringVar(value="Not detected")
        
        # Extraction options
        self.opt_textures = tk.BooleanVar(value=True)
        self.opt_sprites = tk.BooleanVar(value=True)
        self.opt_audio = tk.BooleanVar(value=True)
        self.opt_meshes = tk.BooleanVar(value=True)
        self.opt_texts = tk.BooleanVar(value=True)
        self.opt_fonts = tk.BooleanVar(value=True)
        self.opt_scripts = tk.BooleanVar(value=True)
        self.opt_materials = tk.BooleanVar(value=True)
        
        self.apply_modern_style()
        self.create_widgets()
        
    def apply_modern_style(self):
        """Apply modern styling to ttk widgets"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('Modern.TFrame', background=self.colors['bg'])
        style.configure('Card.TFrame', background=self.colors['secondary_bg'], borderwidth=1, relief='flat')
        style.configure('Modern.TLabel', background=self.colors['bg'], foreground=self.colors['text'], 
                       font=('Segoe UI', 10))
        style.configure('Title.TLabel', background=self.colors['bg'], foreground=self.colors['text'], 
                       font=('Segoe UI', 16, 'bold'))
        style.configure('Subtitle.TLabel', background=self.colors['secondary_bg'], 
                       foreground=self.colors['text_dim'], font=('Segoe UI', 9))
        
        # Entry styling
        style.configure('Modern.TEntry', fieldbackground=self.colors['secondary_bg'], 
                       foreground=self.colors['text'], borderwidth=1)
        
        # Button styling
        style.configure('Accent.TButton', background=self.colors['accent'], foreground='white',
                       borderwidth=0, font=('Segoe UI', 10, 'bold'), padding=10)
        style.map('Accent.TButton', background=[('active', self.colors['accent_hover'])])
        
        style.configure('Modern.TButton', background=self.colors['secondary_bg'], 
                       foreground=self.colors['text'], borderwidth=1, font=('Segoe UI', 9), padding=8)
        
        # Checkbutton styling
        style.configure('Modern.TCheckbutton', background=self.colors['secondary_bg'], 
                       foreground=self.colors['text'], font=('Segoe UI', 9))
        
        # Progressbar
        style.configure('Modern.Horizontal.TProgressbar', background=self.colors['accent'], 
                       troughcolor=self.colors['secondary_bg'], borderwidth=0, thickness=8)
        
    def create_widgets(self):
        # Main container with padding
        main_frame = ttk.Frame(self.root, style='Modern.TFrame', padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Header
        header_frame = ttk.Frame(main_frame, style='Modern.TFrame')
        header_frame.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(0, 20))
        
        ttk.Label(header_frame, text="🎮 Unity Asset Ripper Pro", 
                 style='Title.TLabel').pack(anchor=tk.W)
        ttk.Label(header_frame, text="Extract and analyze Unity game assets with version detection", 
                 style='Modern.TLabel').pack(anchor=tk.W, pady=(5, 0))
        
        # Input Card
        input_card = ttk.Frame(main_frame, style='Card.TFrame', padding="15")
        input_card.grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(0, 15))
        
        ttk.Label(input_card, text="📁 Input Source", style='Modern.TLabel', 
                 font=('Segoe UI', 11, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 10), columnspan=4)
        
        ttk.Entry(input_card, textvariable=self.input_path, width=60, 
                 style='Modern.TEntry').grid(row=1, column=0, padx=(0, 10), sticky=(tk.W, tk.E))
        ttk.Button(input_card, text="📄 File", command=self.browse_input_file,
                  style='Modern.TButton').grid(row=1, column=1, padx=2)
        ttk.Button(input_card, text="📂 Folder", command=self.browse_input_folder,
                  style='Modern.TButton').grid(row=1, column=2, padx=2)
        ttk.Button(input_card, text="🔍 Detect Version", command=self.detect_version,
                  style='Modern.TButton').grid(row=1, column=3, padx=2)
        
        # Unity Version Info
        version_frame = ttk.Frame(input_card, style='Card.TFrame')
        version_frame.grid(row=2, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Label(version_frame, text="Unity Version:", style='Subtitle.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        self.version_label = ttk.Label(version_frame, textvariable=self.unity_version, 
                                      style='Modern.TLabel', font=('Segoe UI', 10, 'bold'))
        self.version_label.pack(side=tk.LEFT)
        
        input_card.columnconfigure(0, weight=1)
        
        # Output Card
        output_card = ttk.Frame(main_frame, style='Card.TFrame', padding="15")
        output_card.grid(row=2, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(0, 15))
        
        ttk.Label(output_card, text="💾 Output Destination", style='Modern.TLabel',
                 font=('Segoe UI', 11, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        ttk.Entry(output_card, textvariable=self.output_path, width=60,
                 style='Modern.TEntry').grid(row=1, column=0, padx=(0, 10), sticky=(tk.W, tk.E))
        ttk.Button(output_card, text="Browse", command=self.browse_output,
                  style='Modern.TButton').grid(row=1, column=1)
        
        output_card.columnconfigure(0, weight=1)
        
        # Options Card
        options_card = ttk.Frame(main_frame, style='Card.TFrame', padding="15")
        options_card.grid(row=3, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(0, 15))
        
        ttk.Label(options_card, text="⚙️ Extraction Options", style='Modern.TLabel',
                 font=('Segoe UI', 11, 'bold')).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 10))
        
        options = [
            ("🖼️ Textures", self.opt_textures),
            ("🎨 Sprites", self.opt_sprites),
            ("🔊 Audio", self.opt_audio),
            ("🗿 Meshes", self.opt_meshes),
            ("📝 Text Assets", self.opt_texts),
            ("🔤 Fonts", self.opt_fonts),
            ("📜 Scripts", self.opt_scripts),
            ("✨ Materials", self.opt_materials)
        ]
        
        for i, (text, var) in enumerate(options):
            row = 1 + i // 4
            col = i % 4
            ttk.Checkbutton(options_card, text=text, variable=var,
                           style='Modern.TCheckbutton').grid(row=row, column=col, sticky=tk.W, padx=10, pady=5)
        
        ttk.Checkbutton(options_card, text="🔬 Verbose logging", variable=self.verbose,
                       style='Modern.TCheckbutton').grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=10, pady=5)
        
        # Action Buttons
        button_frame = ttk.Frame(main_frame, style='Modern.TFrame')
        button_frame.grid(row=4, column=0, columnspan=4, pady=15)
        
        ttk.Button(button_frame, text="🚀 Start Extraction", command=self.start_extraction,
                  style='Accent.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🗑️ Clear Log", command=self.clear_log,
                  style='Modern.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ Exit", command=self.root.quit,
                  style='Modern.TButton').pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate', 
                                       style='Modern.Horizontal.TProgressbar')
        self.progress.grid(row=5, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # Log area with modern styling
        log_card = ttk.Frame(main_frame, style='Card.TFrame', padding="10")
        log_card.grid(row=6, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(log_card, text="📋 Extraction Log", style='Modern.TLabel',
                 font=('Segoe UI', 11, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        self.log_text = scrolledtext.ScrolledText(
            log_card, height=18, width=110,
            bg=self.colors['bg'], fg=self.colors['text'],
            insertbackground=self.colors['text'],
            font=('Consolas', 9),
            borderwidth=0, highlightthickness=0
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
    def browse_input_file(self):
        filename = filedialog.askopenfilename(
            title="Select Unity Asset File",
            filetypes=[("Unity Assets", "*.assets *.unity3d *.assetbundle *.bundle"), ("All Files", "*.*")]
        )
        if filename:
            self.input_path.set(filename)
            self.detect_version()
            
    def browse_input_folder(self):
        folder = filedialog.askdirectory(title="Select Unity Game Folder")
        if folder:
            self.input_path.set(folder)
            self.detect_version()
            
    def browse_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_path.set(folder)
    
    def detect_version(self):
        """Detect Unity version from selected input"""
        inp = self.input_path.get()
        if not inp:
            return
        
        inp_path = Path(inp)
        if not inp_path.exists():
            self.unity_version.set("Path not found")
            return
        
        self.log("🔍 Detecting Unity version...")
        
        try:
            if inp_path.is_file():
                files = [inp_path]
            else:
                files = find_input_files(inp_path)
                if not files:
                    self.unity_version.set("No asset files found")
                    self.log("❌ No asset files found for version detection")
                    return
            
            # Try to detect from first file
            version_info = detect_unity_version(files[0])
            
            if version_info["version"] != "Unknown":
                compatible, msg = check_version_compatibility(version_info["version"])
                
                version_display = f"{version_info['version']} ({msg})"
                self.unity_version.set(version_display)
                
                if compatible:
                    self.log(f"✅ Detected Unity version: {version_info['version']}")
                    self.log(f"   Source: {version_info['detected_from']}")
                    self.log(f"   Status: {msg}")
                else:
                    self.log(f"⚠️ Detected Unity version: {version_info['version']}")
                    self.log(f"   Warning: {msg}")
            else:
                self.unity_version.set("Could not detect version")
                self.log("⚠️ Could not detect Unity version from files")
                
        except Exception as e:
            self.unity_version.set("Detection failed")
            self.log(f"❌ Version detection error: {e}")
            
    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def clear_log(self):
        self.log_text.delete(1.0, tk.END)
        
    def start_extraction(self):
        inp = self.input_path.get()
        if not inp:
            messagebox.showerror("Error", "Please select an input file or folder")
            return
            
        inp_path = Path(inp)
        if not inp_path.exists():
            messagebox.showerror("Error", f"Input path does not exist: {inp}")
            return
            
        out_root = Path(self.output_path.get())
        ensure_dir(out_root)
        
        if self.verbose.get():
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)
        
        options = {
            "textures": self.opt_textures.get(),
            "sprites": self.opt_sprites.get(),
            "audio": self.opt_audio.get(),
            "meshes": self.opt_meshes.get(),
            "texts": self.opt_texts.get(),
            "fonts": self.opt_fonts.get(),
            "scripts": self.opt_scripts.get(),
            "materials": self.opt_materials.get()
        }
        
        self.progress.start()
        self.log("═" * 80)
        self.log(f"🚀 Starting extraction from: {inp}")
        self.log(f"💾 Output directory: {out_root}")
        self.log(f"🎮 Unity Version: {self.unity_version.get()}")
        self.log(f"⚙️ Options: {', '.join([k for k, v in options.items() if v])}")
        self.log("═" * 80)
        
        try:
            if inp_path.is_file():
                files = [inp_path]
            else:
                files = find_input_files(inp_path)
            
            if not files:
                self.log("❌ ERROR: No asset files found in input")
                messagebox.showerror("Error", "No asset files found")
                self.progress.stop()
                return
            
            total_stats = {k: 0 for k in ["textures", "sprites", "audio", "meshes", "texts", "fonts", "scripts", "materials", "other"]}
            
            for idx, f in enumerate(files, 1):
                try:
                    sub_out = out_root / f.stem
                    ensure_dir(sub_out)
                    self.log(f"\n📦 [{idx}/{len(files)}] Processing: {f.name}")
                    stats = extract_from_file(f, sub_out, verbose=self.verbose.get(), options=options)
                    if stats:
                        for k, v in stats.items():
                            total_stats[k] += v
                        total_extracted = sum(v for k, v in stats.items() if k != "other")
                        self.log(f"   ✅ Extracted: {total_extracted} assets")
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    self.log(f"   ❌ ERROR processing {f.name}: {e}")
                    logging.error(traceback.format_exc())
            
            self.log("\n" + "═" * 80)
            self.log("✨ EXTRACTION COMPLETE!")
            self.log(f"📊 Total Statistics:")
            
            icon_map = {
                "textures": "🖼️", "sprites": "🎨", "audio": "🔊", "meshes": "🗿",
                "texts": "📝", "fonts": "🔤", "scripts": "📜", "materials": "✨"
            }
            
            for k, v in total_stats.items():
                if v > 0 and k != "other":
                    icon = icon_map.get(k, "📌")
                    self.log(f"   {icon} {k.capitalize()}: {v}")
            
            total_assets = sum(v for k, v in total_stats.items() if k != "other")
            self.log(f"\n🎉 Total assets extracted: {total_assets}")
            self.log("═" * 80)
            
            messagebox.showinfo("Success", 
                              f"✅ Extraction complete!\n\n"
                              f"Total assets: {total_assets}\n"
                              f"Output: {out_root}")
            
        except Exception as e:
            self.log(f"\n💥 FATAL ERROR: {e}")
            logging.error(traceback.format_exc())
            messagebox.showerror("Error", f"Extraction failed:\n{e}")
        finally:
            self.progress.stop()


def main():
    ap = argparse.ArgumentParser(description="Unity asset ripper with modern GUI and version detection")
    ap.add_argument("input", nargs="?", help="File or folder to scan (optional if using GUI)")
    ap.add_argument("-o", "--out", default="exported_assets", help="Output folder")
    ap.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    ap.add_argument("--gui", action="store_true", help="Launch GUI mode")
    ap.add_argument("--no-textures", action="store_true", help="Skip textures")
    ap.add_argument("--no-sprites", action="store_true", help="Skip sprites")
    ap.add_argument("--no-audio", action="store_true", help="Skip audio")
    ap.add_argument("--no-meshes", action="store_true", help="Skip meshes")
    ap.add_argument("--no-scripts", action="store_true", help="Skip scripts")
    ap.add_argument("--detect-version", action="store_true", help="Detect Unity version only")
    args = ap.parse_args()

    # Launch GUI if requested or if no input provided
    if args.gui or (not args.input and GUI_AVAILABLE):
        if not GUI_AVAILABLE:
            print("ERROR: tkinter not available. Cannot launch GUI.")
            sys.exit(1)
        root = tk.Tk()
        app = ModernUnityRipperGUI(root)
        root.mainloop()
        return

    # Command-line mode
    if not args.input:
        print("ERROR: No input specified. Use --gui for GUI mode or provide an input path.")
        sys.exit(1)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    inp = Path(args.input)
    
    if not inp.exists():
        logging.error(f"Input path does not exist: {inp}")
        sys.exit(1)
    
    # Version detection mode
    if args.detect_version:
        print(f"🔍 Detecting Unity version from: {inp}")
        if inp.is_file():
            files = [inp]
        else:
            files = find_input_files(inp)
        
        if not files:
            print("❌ No asset files found")
            sys.exit(1)
        
        for f in files[:3]:  # Check first 3 files
            version_info = detect_unity_version(f)
            if version_info["version"] != "Unknown":
                compatible, msg = check_version_compatibility(version_info["version"])
                print(f"\n✅ File: {f.name}")
                print(f"   Unity Version: {version_info['version']}")
                print(f"   Status: {msg}")
                if not compatible:
                    print(f"   ⚠️ Warning: {msg}")
            else:
                print(f"\n⚠️ File: {f.name}")
                print(f"   Could not detect version")
        sys.exit(0)

    out_root = Path(args.out)
    ensure_dir(out_root)

    options = {
        "textures": not args.no_textures,
        "sprites": not args.no_sprites,
        "audio": not args.no_audio,
        "meshes": not args.no_meshes,
        "texts": True,
        "fonts": True,
        "scripts": not args.no_scripts,
        "materials": True
    }

    if inp.is_file():
        files = [inp]
    else:
        files = find_input_files(inp)

    if not files:
        logging.error("No asset files found in input. Exiting.")
        sys.exit(1)
    
    # Detect version
    version_info = detect_unity_version(files[0])
    if version_info["version"] != "Unknown":
        logging.info(f"Detected Unity version: {version_info['version']}")
        compatible, msg = check_version_compatibility(version_info["version"])
        logging.info(f"Compatibility: {msg}")

    for f in files:
        try:
            sub_out = out_root / (f.stem + "_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
            ensure_dir(sub_out)
            extract_from_file(f, sub_out, verbose=args.verbose, options=options)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logging.error(f"Failed processing {f}: {e}")
            logging.error(traceback.format_exc())

if __name__ == "__main__":
    main()
