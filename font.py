import os
import zipfile
import shutil
import json
import requests
from pathlib import Path
from tqdm import tqdm
import re
import subprocess
import platform
import sys
import argparse
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup

# Now Google Fonts API key is requested from the user if not provided
GOOGLE_API_KEY = ""  # Set to empty string to prompt for key
GOOGLE_API_URL = "https://www.googleapis.com/webfonts/v1/webfonts?key={key}"
TEMP_DIR = Path("temp")

# Alternative font provider session
alt_session = requests.Session()

# Function to get Google Fonts API key
def get_google_fonts_api_key():
    global GOOGLE_API_KEY, GOOGLE_API_URL
    
    # If key is already set, return it
    if GOOGLE_API_KEY:
        return GOOGLE_API_KEY
    
    # Check for environment variable
    env_key = os.environ.get("GOOGLE_FONTS_API_KEY")
    if env_key:
        GOOGLE_API_KEY = env_key
        GOOGLE_API_URL = GOOGLE_API_URL.format(key=GOOGLE_API_KEY)
        return GOOGLE_API_KEY
    
    # Check for API key file
    key_file = Path.home() / ".google_fonts_api_key"
    if key_file.exists():
        try:
            GOOGLE_API_KEY = key_file.read_text().strip()
            GOOGLE_API_URL = GOOGLE_API_URL.format(key=GOOGLE_API_KEY)
            return GOOGLE_API_KEY
        except:
            pass
    
    # Prompt user for API key
    print("\n🔑 Google Fonts API Key Required")
    print("To use this script, you need a Google Fonts API key from the Google Cloud Console.")
    print("Visit: https://console.cloud.google.com/apis/credentials")
    print("1. Create a project (or select existing project)")
    print("2. Enable the Google Fonts Developer API")
    print("3. Create an API key")
    print("\nThe key looks like: AIzaSyC_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    
    api_key = input("\n🔑 Enter your Google Fonts API key: ").strip()
    
    if not api_key:
        print("❌ No API key provided. Exiting.")
        sys.exit(1)
    
    # Save the API key for future use
    save_key = input("💾 Save this API key for future use? (y/n): "):strip().lower()  # Fixed: removed extra parenthesis
    if save_key == 'y' or save_key == 'yes':
        try:
            key_file.write_text(api_key)
            print(f"✅ API key saved to {key_file}")
        except Exception as e:
            print(f"⚠️ Could not save API key: {e}")
    
    GOOGLE_API_KEY = api_key
    GOOGLE_API_URL = GOOGLE_API_URL.format(key=GOOGLE_API_KEY)
    return GOOGLE_API_KEY

def convert_and_extract_drfx(drfx_path, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir.with_suffix(".zip")
    shutil.copy(drfx_path, zip_path)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
    except zipfile.BadZipFile:
        print(f"❌ Bad zip file: {zip_path}")
    zip_path.unlink()  # remove zip copy

def find_setting_files(root_dir):
    """Find all .setting files recursively in a directory"""
    print(f"🔍 Searching for .setting files in: {root_dir}")
    
    try:
        root_path = Path(root_dir)
        if not root_path.exists():
            print(f"❌ Path does not exist: {root_dir}")
            return []
        
        # Simple and direct approach to find all .setting files
        setting_files = list(root_path.rglob("*.setting"))
        
        print(f"✅ Found {len(setting_files)} .setting files")
        
        # Print some sample files to verify
        if setting_files:
            sample_count = min(5, len(setting_files))
            print(f"\n📄 Sample of found files (showing {sample_count} of {len(setting_files)}):")
            for i, f in enumerate(setting_files[:sample_count]):
                print(f"  - {f}")
            if len(setting_files) > sample_count:
                print(f"  ... and {len(setting_files) - sample_count} more")
        
        return setting_files
        
    except PermissionError as e:
        print(f"🚫 Permission error: {e}")
        return []
    except Exception as e:
        print(f"❌ Error searching for .setting files: {e}")
        return []

def parse_fonts_from_setting(file_path):
    """
    Extract font information from a .setting file.
    This is used both for .setting files inside .drfx files and for direct .setting file scanning.
    """
    fonts = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Find all font names
        matches = re.findall(r'Font\s*=\s*Input\s*{[^}]*Value\s*=\s*"([^"]+)"[^}]*}', content)
        # Find all style names (which might be fewer than fonts if some don't specify styles)
        style_matches = re.findall(r'Style\s*=\s*Input\s*{[^}]*Value\s*=\s*"([^"]+)"[^}]*}', content)
        
        for i, font in enumerate(matches):
            # Use the matching style if available, otherwise default to "Regular"
            style = style_matches[i] if i < len(style_matches) else "Regular"
            fonts.append((font.strip(), style.strip()))
    except PermissionError:
        print(f"🚫 Permission denied when reading {file_path}")
        print("   Check file permissions or run with elevated privileges.")
    except UnicodeDecodeError:
        # Try with different encodings
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
            matches = re.findall(r'Font\s*=\s*Input\s*{[^}]*Value\s*=\s*"([^"]+)"[^}]*}', content)
            style_matches = re.findall(r'Style\s*=\s*Input\s*{[^}]*Value\s*=\s*"([^"]+)"[^}]*}', content)
            for i, font in enumerate(matches):
                style = style_matches[i] if i < len(style_matches) else "Regular"
                fonts.append((font.strip(), style.strip()))
            print(f"⚠️ Had to use alternative encoding for {file_path}")
        except Exception as e:
            print(f"⚠️ Could not read {file_path}: {e}")
    except Exception as e:
        print(f"⚠️ Could not read {file_path}: {e}")
    return fonts

def get_bundled_fonts(folder):
    """Find font files bundled with .drfx files (only used in drfx mode, not settingfile mode)"""
    font_extensions = ['.ttf', '.otf']
    font_files = []
    for path in Path(folder).rglob("*"):
        if path.suffix.lower() in font_extensions:
            font_files.append(path.name.split(".")[0])
    return font_files

def get_system_fonts():
    """Get fonts installed on the system. Currently supports macOS."""
    installed_fonts = set()
    lowercase_map = {}
    
    system = platform.system()
    
    if system == "Darwin":  # macOS
        try:
            output = subprocess.check_output(["system_profiler", "SPFontsDataType", "-json"], stderr=subprocess.DEVNULL)
            fonts_info = json.loads(output)
            
            # Get fonts from system profiler
            for item in fonts_info.get("SPFontsDataType", []):
                name = item.get("_name")
                if name:
                    installed_fonts.add(name)
                    lowercase_map[name.lower()] = name
            
            # Also check standard macOS font locations
            mac_font_locations = [
                Path.home() / "Library" / "Fonts",
                Path("/Library/Fonts"),
                Path("/System/Library/Fonts")
            ]
            
            # Scan these directories for font files
            for location in mac_font_locations:
                if location.exists():
                    for file_path in location.glob("*.[ot]tf"):
                        font_name = file_path.stem
                        if font_name not in installed_fonts:
                            installed_fonts.add(font_name)
                            lowercase_map[font_name.lower()] = font_name
            
            print(f"✅ Detected macOS system with {len(installed_fonts)} fonts")
            
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            print(f"⚠️ Error getting macOS fonts: {e}")
    elif system == "Windows":
        print("⚠️ Windows font detection not fully implemented yet")
        # Basic Windows font detection - could be expanded
        windows_font_dir = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
        if windows_font_dir.exists():
            for file_path in windows_font_dir.glob("*.[ot]tf"):
                font_name = file_path.stem
                installed_fonts.add(font_name)
                lowercase_map[font_name.lower()] = font_name
    elif system == "Linux":
        print("⚠️ Linux font detection not fully implemented yet")
        # Basic Linux font detection
        linux_font_dirs = [
            Path.home() / ".local" / "share" / "fonts",
            Path.home() / ".fonts",
            Path("/usr/local/share/fonts"),
            Path("/usr/share/fonts")
        ]
        for dir_path in linux_font_dirs:
            if dir_path.exists():
                for file_path in dir_path.rglob("*.[ot]tf"):
                    font_name = file_path.stem
                    installed_fonts.add(font_name)
                    lowercase_map[font_name.lower()] = font_name
    else:
        print(f"⚠️ Unsupported operating system: {system}")

    return installed_fonts, lowercase_map

def normalize_font_name(name):
    """Normalize font name to improve matching chances"""
    # Remove common font name parts that might differ between systems
    normalized = name.lower()
    # Remove things like "PS", "MT", etc.
    normalized = re.sub(r'\b(ps|mt|std|pro|light|bold|regular|medium|italic)\b', '', normalized)
    # Remove any non-alphanumeric characters
    normalized = re.sub(r'[^a-z0-9]', '', normalized)
    return normalized.strip()

def is_font_installed(font_name, style, system_fonts, lowercase_map, normalized_map, installed_styles=None):
    """
    Check if a font is installed using different matching strategies.
    Also checks if the required style is available.
    """
    found = False
    match_type = ""
    matched_name = ""
    
    # Direct match
    if font_name in system_fonts:
        found = True
        match_type = "exact match"
        matched_name = font_name
    
    # Case-insensitive match
    elif font_name.lower() in lowercase_map:
        found = True
        match_type = f"case-insensitive match"
        matched_name = lowercase_map[font_name.lower()]
    
    # Normalized match
    else:
        normalized = normalize_font_name(font_name)
        if normalized in normalized_map:
            found = True
            match_type = f"normalized match"
            matched_name = normalized_map[normalized]
    
    # If font is found but we need to check styles
    if found and installed_styles is not None:
        # Check if the style is available for this font
        font_styles = installed_styles.get(matched_name, [])
        if style in font_styles or "Regular" in font_styles:  # Regular style often supports multiple weights
            return True, match_type, matched_name, True  # Font found, style found
        else:
            return True, match_type, matched_name, False  # Font found, style not found
    
    return found, match_type, matched_name, False

def get_system_fonts_with_styles():
    """Get fonts installed on the system with their available styles."""
    installed_fonts = set()
    lowercase_map = {}
    font_styles = {}  # Map of font name -> list of available styles
    
    system = platform.system()
    
    if system == "Darwin":  # macOS
        try:
            output = subprocess.check_output(["system_profiler", "SPFontsDataType", "-json"], stderr=subprocess.DEVNULL)
            fonts_info = json.loads(output)
            
            # Get fonts from system profiler
            for item in fonts_info.get("SPFontsDataType", []):
                name = item.get("_name")
                if name:
                    installed_fonts.add(name)
                    lowercase_map[name.lower()] = name
                    
                    # Try to detect style from the name
                    style = "Regular"  # Default
                    if "bold" in name.lower() and "italic" in name.lower():
                        style = "Bold Italic"
                    elif "bold" in name.lower():
                        style = "Bold"
                    elif "italic" in name.lower():
                        style = "Italic"
                    elif "light" in name.lower():
                        style = "Light"
                    
                    # Add the style to the font's style list
                    if name not in font_styles:
                        font_styles[name] = []
                    font_styles[name].append(style)
            
            # Also check standard macOS font locations
            mac_font_locations = [
                Path.home() / "Library" / "Fonts",
                Path("/Library/Fonts"),
                Path("/System/Library/Fonts")
            ]
            
            # Scan these directories for font files and try to detect styles
            for location in mac_font_locations:
                if location.exists():
                    for file_path in location.glob("*.[ot]tf"):
                        font_name = file_path.stem
                        if font_name not in installed_fonts:
                            installed_fonts.add(font_name)
                            lowercase_map[font_name.lower()] = font_name
                            
                            # Detect style from filename
                            style = "Regular"  # Default
                            name_lower = font_name.lower()
                            if "bold" in name_lower and "italic" in name_lower:
                                style = "Bold Italic"
                            elif "bold" in name_lower:
                                style = "Bold"
                            elif "italic" in name_lower:
                                style = "Italic"
                            elif "light" in name_lower:
                                style = "Light"
                            
                            # Add the style to the font's style list
                            if font_name not in font_styles:
                                font_styles[font_name] = []
                            font_styles[font_name].append(style)
            
            print(f"✅ Detected macOS system with {len(installed_fonts)} fonts")
            
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            print(f"⚠️ Error getting macOS fonts: {e}")
    # Windows and Linux detection code would be similar but with their paths
    
    return installed_fonts, lowercase_map, font_styles

def scan_all(path, use_drfx=True, use_settings=True, verbose=False, dry_run=False):
    """
    Scan a directory for font requirements from both .drfx files and/or .setting files
    """
    path = Path(path)
    
    if not path.exists():
        print(f"❌ Path does not exist: {path}")
        return []
    
    # Collect required fonts from all sources
    required_fonts = set()
    bundled_fonts = set()
    
    # Scan DRFX files if requested
    if use_drfx:
        drfx_files = list(path.rglob("*.drfx"))
        if drfx_files:
            print(f"🔍 Found {len(drfx_files)} DRFX files in {path}")
            
            # Create temp directory for extraction
            TEMP_DIR.mkdir(exist_ok=True)
            
            # Process each DRFX file
            for drfx in tqdm(drfx_files):
                folder_name = TEMP_DIR / drfx.stem
                convert_and_extract_drfx(drfx, folder_name)
                bundled_fonts.update(get_bundled_fonts(folder_name))
                setting_files = find_setting_files(folder_name)
                for sf in setting_files:
                    required_fonts.update(parse_fonts_from_setting(sf))
        else:
            print(f"ℹ️ No DRFX files found in {path}")
    
    # Scan setting files directly if requested
    if use_settings:
        if verbose:
            print(f"🔍 Searching for .setting files in {path}")
        setting_files = list(path.rglob("*.setting"))
        if setting_files:
            print(f"🔍 Found {len(setting_files)} .setting files in {path}")
            for sf in tqdm(setting_files):
                fonts = parse_fonts_from_setting(sf)
                if fonts:
                    required_fonts.update(fonts)
        else:
            print(f"ℹ️ No .setting files found in {path}")
    
    # Get unique required fonts
    required_fonts = sorted(set(required_fonts))
    
    # If no fonts found, exit
    if not required_fonts and not bundled_fonts:
        print("❌ No fonts found in the specified path.")
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        return []
    
    # Get system fonts with styles
    system_fonts, lowercase_map, installed_styles = get_system_fonts_with_styles()
    
    # Create normalized map for more flexible matching
    normalized_map = {}
    for font in system_fonts:
        normalized = normalize_font_name(font)
        if normalized:
            normalized_map[normalized] = font
    
    # Track fonts by status
    available = []  # Fully available fonts (both name and style)
    style_missing = []  # Font exists but style is missing
    completely_missing = []  # Font doesn't exist at all
    
    print("\n📝 Required fonts:")
    if verbose:
        # When verbose, show all fonts
        for name, style in required_fonts:
            # Check if font is in bundled fonts
            if name in bundled_fonts:
                available.append((name, style))
                print(f"✅ Found bundled: {name} [{style}]")
                continue
            
            # Check if font is already installed on the system
            font_installed, match_type, matched_name, style_available = is_font_installed(
                name, style, system_fonts, lowercase_map, normalized_map, installed_styles
            )
            
            if font_installed:
                if style_available:
                    available.append((name, style))
                    print(f"✅ Already installed: {name} [{style}] ({match_type})")
                else:
                    style_missing.append((name, style, matched_name))
                    print(f"⚠️ Font installed but style missing: {name} [{style}] - matched to {matched_name}")
            else:
                completely_missing.append((name, style))
                print(f"❌ Missing: {name} [{style}]")
    else:
        # When not verbose, only show missing fonts
        for name, style in required_fonts:
            # Check if font is in bundled fonts
            if name in bundled_fonts:
                available.append((name, style))
                continue
            
            # Check if font is already installed on the system
            font_installed, match_type, matched_name, style_available = is_font_installed(
                name, style, system_fonts, lowercase_map, normalized_map, installed_styles
            )
            
            if font_installed:
                if style_available:
                    available.append((name, style))
                else:
                    style_missing.append((name, style, matched_name))
                    print(f"⚠️ Font style missing: {name} [{style}]")
            else:
                completely_missing.append((name, style))
                print(f"❌ Missing: {name} [{style}]")
    
    # Calculate missing fonts for reporting
    missing = style_missing + completely_missing
    
    # If in dry run mode, just return missing fonts
    if dry_run:
        if missing:
            print(f"\n🔍 Dry run results: {len(available)} fonts available, {len(missing)} fonts missing")
            if style_missing:
                print(f"   - {len(style_missing)} fonts have missing styles")
            if completely_missing:
                print(f"   - {len(completely_missing)} fonts are completely missing")
        else:
            print(f"\n✅ Dry run results: All {len(available)} required fonts are available")
        
        # Clean up
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        
        return missing
    
    # Handle missing fonts
    if missing and not dry_run:
        print(f"\n🔍 Found {len(available)} fonts already available, {len(missing)} fonts missing")
        
        # Get Google Fonts index
        google_fonts_index = get_google_fonts_index()
        
        # Group missing fonts by family name
        missing_fonts = {}
        for info in missing:
            if len(info) == 2:  # Completely missing font
                name, style = info
                if name not in missing_fonts:
                    missing_fonts[name] = {"styles": [], "matched_name": None}
                missing_fonts[name]["styles"].append(style)
            else:  # Style missing font
                name, style, matched_name = info
                if name not in missing_fonts:
                    missing_fonts[name] = {"styles": [], "matched_name": matched_name}
                missing_fonts[name]["styles"].append(style)
        
        to_download = {}
        unavailable = []
        alternative_sources = {}  # New dictionary to track alternative sources
        
        # Check Google Fonts for all missing fonts
        for font, data in missing_fonts.items():
            styles = data["styles"]
            if font in google_fonts_index:
                available_variants = get_available_variants(font, google_fonts_index)
                to_download[font] = {
                    "styles": styles,
                    "variants": available_variants,
                    "source": "Google Fonts",
                    "matched_name": data["matched_name"]
                }
            else:
                # Try alternative font providers when not found on Google Fonts
                alt_source = search_alternative_font_providers(font)
                if alt_source:
                    alternative_sources[font] = {
                        "name": font,
                        "styles": styles,
                        "alt_source": alt_source,
                        "matched_name": data["matched_name"]
                    }
                    print(f"✅ Found '{font}' on {alt_source['source']}")
                else:
                    # Not available anywhere
                    unavailable.append((font, styles))
                    print(f"⚠️ Not found anywhere: {font} - styles: {', '.join(styles)}")

        # Handle font downloads with simplified options
        if to_download or alternative_sources:
            print("\n📥 Download and install missing fonts?")
            print("  1 - Yes, download and install all missing fonts")
            print("  0 - No, skip downloading")
            
            choice = input("\nYour choice (1/0): ").strip()
            if choice == "1":
                # Only ask about replacement if there are fonts with missing styles
                replace_existing = False
                if any(data["matched_name"] is not None for data in missing_fonts.values()):
                    replace_choice = input("\n🔄 Replace existing fonts to get missing styles? (y/n): ").strip().lower()
                    replace_existing = (replace_choice == 'y' or replace_choice == 'yes')
                
                unsuccessful_downloads = []
                
                # Process Google Fonts downloads
                if to_download:
                    print("\n🌐 Downloading from Google Fonts:")
                    for font, data in to_download.items():
                        print(f"⬇️ Downloading {font} with {len(data['variants'])} style variants...")
                        if download_google_font(font, data['styles'][0], data['variants']):
                            print(f"✅ Downloaded: {font}")
                        else:
                            unsuccessful_downloads.append((font, data['styles'], "Google Fonts"))
                
                # Process alternative source downloads
                if alternative_sources:
                    print("\n🌐 Downloading from alternative sources:")
                    for font, data in alternative_sources.items():
                        if download_font_from_alternative_source(data, data['styles'][0]):
                            print(f"✅ Downloaded: {font} from {data['alt_source']['source']}")
                        else:
                            unsuccessful_downloads.append((font, data['styles'], data['alt_source']['source']))
                
                if unsuccessful_downloads:
                    print("\n⚠️ The following fonts could not be downloaded:")
                    for font, styles, source in unsuccessful_downloads:
                        print(f"  - {font} [{', '.join(styles)}] (Source: {source})")
                
                install_fonts_from_temp(replace_existing)
            else:
                print("❌ Skipped downloading.")
        else:
            print("🔎 No downloadable fonts found.")
        
        # Print final report of unavailable fonts
        if unavailable:
            print("\n📊 Final report - Fonts not available on any provider:")
            for font, styles in unavailable:
                print(f"  - {font} [{', '.join(styles)}]")
            print("\n💡 These fonts are not available from any of our providers. You may need to:")
            print("   - Purchase them from commercial font providers")
            print("   - Find free versions on other sites and install manually")
            print("   - Use alternative fonts with similar appearance")
    
    # Clean up
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    
    return missing

def install_fonts_from_temp(replace_existing=False):
    """Install fonts from the temp directory to the system fonts directory"""
    fonts_path = TEMP_DIR / "fonts"
    installed_count = 0
    replaced_count = 0
    variable_count = 0
    skipped_count = 0
    
    # First, look for and prioritize variable fonts
    for font_file in fonts_path.rglob("*.[ot]tf"):
        is_variable = is_variable_font(font_file)
        dest_path = Path.home() / "Library" / "Fonts" / font_file.name
        
        # Check if font already exists - only replace if specifically requested
        # or if it's a variable font (which supports more styles)
        if dest_path.exists() and not (replace_existing or is_variable):
            print(f"⏭️ Skipping existing font: {font_file.name}")
            skipped_count += 1
            continue
        elif dest_path.exists():
            # Replace the font
            print(f"🔄 Replacing existing font: {font_file.name}")
            replaced_count += 1
        else:
            # Install the font
            installed_count += 1
        
        # Copy the font file
        shutil.copy(font_file, dest_path)
        
        if is_variable:
            variable_count += 1
            print(f"✅ {'Replaced' if dest_path.exists() else 'Installed'} variable font: {font_file.name}")
        else:
            print(f"✅ {'Replaced' if dest_path.exists() else 'Installed'}: {font_file.name}")
    
    # Print summary
    print(f"\n📊 Font Installation Summary:")
    print(f"   ✅ {installed_count} new fonts installed")
    if replaced_count > 0:
        print(f"   🔄 {replaced_count} fonts replaced")
    if skipped_count > 0:
        print(f"   ⏭️ {skipped_count} fonts skipped (already installed)")
    print(f"   🧩 {variable_count} variable fonts with multiple styles")

def print_help():
    """Display help message"""
    print("Font Scanner and Installer Tool")
    print("===============================")
    print("\nUsage: python font.py [OPTIONS] [PATH]")
    print("\nOptions:")
    print("  --help           Show help message")
    print("  --drffiles       Scan only .drfx files")
    print("  --settingfiles   Scan only .setting files")
    print("  --verbose        Display detailed output")
    print("  --dryrun         Only check which fonts are missing without downloading")
    print("  --downloadonly <path>  Download missing fonts to specified directory without installing")
    print("  --noask          Don't ask for DaVinci Resolve path (use path argument directly)")
    print("\nExamples:")
    print("  python font.py                         # Scan current directory for both .drfx and .setting files")
    print("  python font.py /path/to/files          # Scan specified path for both file types")
    print("  python font.py --settingfiles /path    # Scan only .setting files in path")
    print("  python font.py --drffiles --verbose    # Scan only .drfx files with detailed output")
    print("  python font.py --dryrun                # Check missing fonts without downloading")
    print("  python font.py --downloadonly FontDownloads  # Download missing fonts to FontDownloads folder")

def get_default_resolve_paths():
    """Get default DaVinci Resolve paths based on the operating system"""
    system = platform.system()
    paths = []
    
    if system == "Darwin":  # macOS
        # System-wide and user-specific paths on macOS
        paths = [
            Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve"),
            Path.home() / "Library/Application Support/Blackmagic Design/DaVinci Resolve",
            # Common project/asset paths
            Path.home() / "Movies/DaVinci Resolve",
            Path.home() / "Movies/DaVinci Resolve/DRX"
        ]
    
    elif system == "Windows":
        # System-wide and user-specific paths on Windows
        paths = [
            Path("C:/ProgramData/Blackmagic Design/DaVinci Resolve"),
            Path(os.environ.get("APPDATA", "")) / "Blackmagic Design/DaVinci Resolve",
            # Common project/asset paths
            Path(os.environ.get("USERPROFILE", "")) / "Documents/DaVinci Resolve",
            Path(os.environ.get("USERPROFILE", "")) / "Documents/DaVinci Resolve/DRX"
        ]
    
    elif system == "Linux":
        # Common Linux paths
        paths = [
            Path.home() / ".local/share/DaVinciResolve",
            Path("/opt/resolve"),
            # Common project/asset paths
            Path.home() / "Documents/DaVinci Resolve",
            Path.home() / "DaVinci Resolve"
        ]
    
    # Filter out paths that don't exist
    existing_paths = [p for p in paths if p.exists()]
    
    if existing_paths:
        # Also look for DRFX-specific directories
        for base_path in list(existing_paths):  # Create a copy of the list to avoid modifying during iteration
            drfx_dirs = ["Fusion", "Fusion/Templates", "Support", "Support/Resolve"]
            for drfx_dir in drfx_dirs:
                drfx_path = base_path / drfx_dir
                if drfx_path.exists():
                    existing_paths.append(drfx_path)
    
    # Sort paths by likelihood of containing DRFX files
    # Look for directories with .drfx files and prioritize them
    prioritized_paths = []
    other_paths = []
    
    for path in existing_paths:
        if list(path.glob("**/*.drfx")):  # Check if path contains any .drfx files
            prioritized_paths.append(path)
        else:
            other_paths.append(path)
    
    # Return prioritized paths first, then other existing paths
    return prioritized_paths + other_paths

def select_resolve_path():
    """Prompt user to select a DaVinci Resolve path or enter a custom path"""
    default_paths = get_default_resolve_paths()
    
    if not default_paths:
        print("❓ Could not find any default DaVinci Resolve paths on your system.")
        custom_path = input("📂 Please enter the path to your DaVinci Resolve files: ").strip()
        return Path(custom_path) if custom_path else Path(".")
    
    # Count total .drfx and .setting files in all standard locations
    total_drfx_count = 0
    total_setting_count = 0
    
    for path in default_paths:
        drfx_count = len(list(path.glob("**/*.drfx")))
        setting_count = len(list(path.glob("**/*.setting")))
        total_drfx_count += drfx_count
        total_setting_count += setting_count
    
    print("📂 Choose a path option:")
    file_counts = []
    if total_drfx_count > 0:
        file_counts.append(f"{total_drfx_count} .drfx files")
    if total_setting_count > 0:
        file_counts.append(f"{total_setting_count} .setting files")
    counts_str = f" ({', '.join(file_counts)})" if file_counts else ""
    
    print(f"  1. All standard DaVinci Resolve locations{counts_str}")
    print(f"  2. Enter a custom path")
    
    while True:
        try:
            choice = input("\nSelect an option (1-2): ").strip()
            if choice == "1":
                # Use default paths
                path = default_paths[0]  # Just use the first one for simplicity
                print(f"📂 Using default path: {path}")
                return path
            elif choice == "2":
                custom_path = input("📂 Enter your custom path: ").strip()
                return Path(custom_path) if custom_path else Path(".")
            else:
                print("⚠️ Invalid choice, please select 1 or 2.")
        except Exception as e:
            print(f"❌ Error: {e}")

def get_google_fonts_index():
    """Get a list of available Google Fonts"""
    global GOOGLE_API_KEY, GOOGLE_API_URL
    
    try:
        # Make sure we have an API key
        api_key = get_google_fonts_api_key()
        
        response = requests.get(GOOGLE_API_URL)
        response.raise_for_status()
        fonts = response.json().get("items", [])
        return {f["family"]: f for f in fonts}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(f"❌ Google Fonts API Error: Invalid API key or API not enabled")
            print("💡 Please visit: https://console.cloud.google.com/apis/credentials")
            print("   Make sure you have enabled the Google Fonts Developer API for your project")
            
            # Ask if they want to provide a new API key
            new_key = input("\n🔑 Enter a new Google Fonts API key (or press Enter to exit): ").strip()
            if new_key:
                GOOGLE_API_KEY = new_key
                GOOGLE_API_URL = f"https://www.googleapis.com/webfonts/v1/webfonts?key={GOOGLE_API_KEY}"
                return get_google_fonts_index()  # Try again with new key
        print(f"⚠️ Error fetching Google Fonts: {e}")
        return {}
    except Exception as e:
        print(f"⚠️ Error fetching Google Fonts: {e}")
        return {}

def style_to_variant(style):
    """Convert a font style name to Google's variant format"""
    style_map = {
        "Regular": "regular",
        "Bold": "700",
        "Italic": "italic",
        "Bold Italic": "700italic",
        "Light": "300",
        "Light Italic": "300italic",
        "Medium": "500",
        "Medium Italic": "500italic",
        "SemiBold": "600",
        "SemiBold Italic": "600italic",
        "ExtraBold": "800",
        "ExtraBold Italic": "800italic",
        "Black": "900",
        "Black Italic": "900italic",
        "Thin": "100",
        "Thin Italic": "100italic",
        "ExtraLight": "200",
        "ExtraLight Italic": "200italic",
    }
    return style_map.get(style, "regular")

def get_available_variants(font_family, google_fonts_index):
    """Get all available variants for a font from Google Fonts"""
    if font_family in google_fonts_index:
        return google_fonts_index[font_family].get("variants", ["regular"])
    return []

def is_variable_font(font_path):
    """Check if a font file is a variable font by looking for the 'fvar' table"""
    try:
        # Use fontTools library if available
        try:
            from fontTools.ttLib import TTFont
            font = TTFont(font_path)
            return 'fvar' in font
        except ImportError:
            # Fallback method - check for 'fvar' table signature in the file
            with open(font_path, 'rb') as f:
                data = f.read()
                return b'fvar' in data
    except Exception:
        return False

def download_google_font(family, style_info, variants=None):
    """Download a Google font with specified style or all available styles"""
    # Create required directories
    TEMP_DIR.mkdir(exist_ok=True)
    fonts_dir = TEMP_DIR / "fonts"
    fonts_dir.mkdir(exist_ok=True)
    
    # Convert our style to Google's variant format
    requested_variant = style_to_variant(style_info)
    
    # If no variants specified, only download the requested one
    if variants is None:
        variants = [requested_variant]
    
    # Try to download the font
    url = f"https://fonts.google.com/download?family={family.replace(' ', '+')}"
    try:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        
        download_path = TEMP_DIR / f"{family}.download"
        with open(download_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Try to process as a zip file
        try:
            with zipfile.ZipFile(download_path, 'r') as zip_ref:
                zip_ref.extractall(fonts_dir)
                print(f"  📦 Extracted zip archive for {family}")
                
                # Look for variable fonts in extracted files
                variable_fonts_found = False
                for font_file in fonts_dir.rglob("*.[ot]tf"):
                    if "variable" in font_file.stem.lower() or is_variable_font(font_file):
                        variable_fonts_found = True
                        print(f"  🧩 Found variable font: {font_file.name}")
                
                if variable_fonts_found:
                    print(f"  ✨ Variable font versions found - all styles will be available")
        except zipfile.BadZipFile:
            # Not a zip file, determine font type
            with open(download_path, 'rb') as f:
                header = f.read(4)
            
            # Determine font file extension based on signature
            ext = '.ttf'  # Default
            if header.startswith(b'OTTO'):  # OpenType font
                ext = '.otf'
            elif header.startswith(b'\x00\x01\x00\x00'):  # TrueType font
                ext = '.ttf'
            
            # Save with appropriate extension
            font_path = fonts_dir / f"{family}{ext}"
            shutil.copy(download_path, font_path)
            print(f"  🔤 Saved direct font file for {family} as {ext}")
            
            # Check if it's a variable font
            if is_variable_font(font_path):
                print(f"  ✨ This is a variable font - all styles will be available")
            
        # Clean up the temporary download
        download_path.unlink()
        return True
    except Exception as e:
        print(f"❌ Failed to download {family}: {e}")
        return False

def get_headers(referer=None):
    """Get headers for font provider requests"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/114.0.0.0 Safari/537.36"
    }
    if referer:
        headers["Referer"] = referer
    return headers

def search_1001fonts(font_name):
    """Search for a font on 1001fonts.com and return download URL if found"""
    query = quote(font_name)
    search_url = f"https://www.1001fonts.com/search.html?search={query}"
    print(f"  [1001Fonts] Searching: {font_name}")

    try:
        resp = alt_session.get(search_url, headers=get_headers(), timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠️ Failed to get search results (status {resp.status_code})")
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Find font links in search results
        font_links = []
        for a in soup.find_all('a', class_="preview-link"):
            href = a.get('href', '')
            if re.match(r"^/[a-z0-9\-]+-font\.html$", href):
                font_links.append(href)

        if not font_links:
            print("  ⚠️ No font pages found on 1001Fonts.")
            return None

        # Take the first font page link
        font_page_url = urljoin("https://www.1001fonts.com", font_links[0])
        print(f"  [1001Fonts] Font page found: {font_page_url.split('/')[-1]}")

        resp = alt_session.get(font_page_url, headers=get_headers(referer=search_url), timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠️ Failed to get font page (status {resp.status_code})")
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')
        download_btn = soup.select_one('a.btn-download[href^="/download/"]')
        if not download_btn:
            print("  ⚠️ Download button not found on font page.")
            return None

        download_url = urljoin("https://www.1001fonts.com", download_btn['href'])
        print(f"  ✅ [1001Fonts] Download URL found")
        return download_url
    except Exception as e:
        print(f"  ⚠️ Error searching 1001Fonts: {e}")
        return None

def search_dafont(font_name):
    """Search for a font on dafont.com and return download URL if found"""
    query = quote(font_name.lower().replace(' ', '+'))
    search_url = f"https://www.dafont.com/search.php?q={query}"
    print(f"  [DaFont] Searching: {font_name}")

    try:
        resp = alt_session.get(search_url, headers=get_headers(), timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠️ Failed to get search results (status {resp.status_code})")
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Find the first font result
        font_divs = soup.select('div.dffont2')
        if not font_divs:
            print("  ⚠️ No font results found on DaFont.")
            return None

        # Get the first font link
        first_font = font_divs[0]
        font_link = first_font.select_one('a')
        if not font_link or not font_link.get('href'):
            print("  ⚠️ Font link not found in DaFont results.")
            return None

        font_page_url = urljoin("https://www.dafont.com", font_link.get('href'))
        print(f"  [DaFont] Font page found: {font_page_url.split('/')[-1]}")

        # Visit the font page to get the download link
        resp = alt_session.get(font_page_url, headers=get_headers(referer=search_url), timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠️ Failed to get font page (status {resp.status_code})")
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')
        download_div = soup.select_one('div.dl')
        if not download_div:
            print("  ⚠️ Download section not found on DaFont page.")
            return None

        download_link = download_div.select_one('a')
        if not download_link or not download_link.get('href'):
            print("  ⚠️ Download link not found on DaFont page.")
            return None

        download_url = urljoin("https://www.dafont.com", download_link.get('href'))
        print(f"  ✅ [DaFont] Download URL found")
        return download_url
    except Exception as e:
        print(f"  ⚠️ Error searching DaFont: {e}")
        return None

def search_freefont(font_name):
    """Search for a font on freefonts.io and return download URL if found"""
    query = quote(font_name.replace(" ", "+"))
    search_url = f"https://www.freefonts.io/?s={query}"
    print(f"  [FreeFonts.io] Searching: {font_name}")

    try:
        # Get search results page
        resp = alt_session.get(search_url, headers=get_headers(), timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠️ Failed to get search results (status {resp.status_code})")
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Find the first result link - using the element structure from the new implementation
        first_result = soup.find("a", class_="elementor-post__thumbnail__link")
        if not first_result or not first_result.get("href"):
            print("  ⚠️ No font match found on FreeFonts.io.")
            return None
            
        # Get the font page URL
        font_page_url = first_result["href"]
        print(f"  [FreeFonts.io] Font page found: {font_page_url.split('/')[-2]}")

        # Visit the font page
        resp = alt_session.get(font_page_url, headers=get_headers(referer=search_url), timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠️ Failed to get font page (status {resp.status_code})")
            return None
            
        # Parse the font page to find the download button
        font_soup = BeautifulSoup(resp.text, 'html.parser')
        download_btn = font_soup.find("a", class_="mybtnleft")

        if not download_btn or not download_btn.get("href"):
            print("  ⚠️ Download button not found on FreeFonts.io page.")
            return None

        # Get and construct the download URL
        download_url = download_btn["href"]
        if download_url.startswith("/"):
            download_url = f"https://www.freefonts.io{download_url}"
            
        print(f"  ✅ [FreeFonts.io] Download URL found")
        return download_url
            
    except Exception as e:
        print(f"  ⚠️ Error searching FreeFonts.io: {e}")
        return None

def search_alternative_font_providers(font_name):
    """Search alternative font providers when Google Fonts doesn't have the font"""
    print(f"🔍 Searching alternative font providers for: {font_name}")
    
    # Try each provider in sequence, returning the first match found
    # 1. 1001Fonts (generally has more fonts)
    url = search_1001fonts(font_name)
    if url:
        return {"url": url, "source": "1001Fonts"}
        
    # 2. DaFont (popular alternative)
    url = search_dafont(font_name)
    if url:
        return {"url": url, "source": "DaFont"}
    
    # 3. FreeFonts.io (last resort)
    url = search_freefont(font_name)
    if url:
        return {"url": url, "source": "FreeFonts.io"}
    
    # No matching font found on any provider
    print(f"❌ Font '{font_name}' not found on any alternative providers")
    return None

def download_font_from_alternative_source(font_info, style_info):
    """Download font from alternative source using the URL directly"""
    font_name = font_info["name"]
    source_info = font_info["alt_source"]
    source_name = source_info["source"]
    download_url = source_info["url"]  # Use the URL directly from the search result
    
    # Create required directories
    TEMP_DIR.mkdir(exist_ok=True)
    fonts_dir = TEMP_DIR / "fonts"
    fonts_dir.mkdir(exist_ok=True)
    
    # Download the font archive
    print(f"  ⬇️ Downloading from {source_name}: {font_name}")
    try:
        download_path = TEMP_DIR / f"{font_name}_{source_name}.zip"
        
        # Download the file using the URL we found earlier
        resp = alt_session.get(download_url, headers=get_headers(), stream=True, timeout=30)
        resp.raise_for_status()
        
        # Write the downloaded content to disk first
        with open(download_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"  📥 Downloaded file to {download_path}")
        
        # Now that the file exists, try to extract it as a ZIP file
        try:
            with zipfile.ZipFile(download_path, 'r') as zip_ref:
                zip_ref.extractall(fonts_dir)
                print(f"  📦 Extracted zip archive from {source_name}")
                
                # Check for extracted font files
                font_files = list(fonts_dir.rglob("*.[ot]tf"))
                if font_files:
                    print(f"  ✅ Found {len(font_files)} font files in archive")
                else:
                    print(f"  ⚠️ No font files found in downloaded archive")
                    return False
                    
        except zipfile.BadZipFile:
            # Not a zip file, might be a direct font file
            print(f"  ⚠️ Downloaded file is not a zip archive, trying to process as direct font file")
            # Try to determine if it's a font file
            with open(download_path, 'rb') as f:
                header = f.read(4)
            
            is_font = False
            if header.startswith(b'OTTO') or header.startswith(b'\x00\x01\x00\x00'):
                is_font = True
                ext = '.otf' if header.startswith(b'OTTO') else '.ttf'
                font_path = fonts_dir / f"{font_name}{ext}"
                shutil.copy(download_path, font_path)
                print(f"  🔤 Saved direct font file as {ext}")
            
            if not is_font:
                print(f"  ❌ Downloaded file is not a recognized font file")
                return False
        
        # Clean up the temporary download
        download_path.unlink()
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to download from {source_name}: {e}")
        
        # Check if there's an HTTP status code we can report
        if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
            print(f"  ⚠️ HTTP Status Code: {e.response.status_code}")
            
        return False

# Main script execution
if __name__ == "__main__":
    # Argument parsing
    parser = argparse.ArgumentParser(description="Font Scanner and Installer for DaVinci Resolve")
    parser.add_argument("path", nargs="?", default=".", help="Path to scan for .drfx and .setting files")
    parser.add_argument("--drffiles", action="store_true", help="Scan only .drfx files")
    parser.add_argument("--settingfiles", action="store_true", help="Scan only .setting files")
    parser.add_argument("--verbose", action="store_true", help="Display detailed output")
    parser.add_argument("--dryrun", action="store_true", help="Only check which fonts are missing without downloading")
    parser.add_argument("--downloadonly", type=str, help="Download missing fonts to specified directory without installing")
    parser.add_argument("--noask", action="store_true", help="Don't ask for DaVinci Resolve path (use path argument directly)")
    
    args = parser.parse_args()
    
    # Determine scan modes
    use_drfx = not args.settingfiles
    use_settings = not args.drffiles
    
    # Print welcome message
    print("===============================")
    print("Font Scanner and Installer Tool")
    print("===============================")
    
    # Get Google Fonts API key
    google_api_key = get_google_fonts_api_key()
    
    # Select DaVinci Resolve path if not provided
    resolve_path = Path(args.path)
    if not args.noask:
        resolve_path = select_resolve_path()
    
    # Start scanning and processing
    missing_fonts = scan_all(resolve_path, use_drfx, use_settings, args.verbose, args.dryrun)
    
    # If there are missing fonts and we are not in dry run mode, proceed to download
    if missing_fonts and not args.dryrun:
        print("\n🔍 Missing fonts detected, proceeding to download...")
        # The download and install process is already handled in scan_all()
    else:
        print("\n✅ All required fonts are available.")
    
    # Add reminder to restart DaVinci Resolve
    if not args.dryrun and missing_fonts:
        print("\n⚠️ IMPORTANT: Please restart DaVinci Resolve to load the newly installed fonts!")
        print("   Your projects should now display correctly with all required fonts.")
