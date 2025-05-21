# Font Scanner and Installer for DaVinci Resolve

A Python tool to scan DaVinci Resolve project files (.drfx) and setting files (.setting) for font requirements, check which fonts are missing on your system, and automatically download and install missing fonts from Google Fonts and alternative sources.

## License

This tool is **open source software** released under the **MIT License**. You are free to:
- Use it for any purpose, including commercial applications
- Modify, distribute, and sublicense it
- Use it privately or commercially

This permissive license requires only that you include the original copyright notice and license text when redistributing.

## Disclaimer About Font Usage

**IMPORTANT:** While this tool is open source, the fonts it helps you find may have different licensing terms:
- Many fonts require a paid license for commercial use
- Always check the license of each font before using it commercially
- This tool doesn't verify font licensing - it only helps locate and install fonts

The creators of this tool are not liable for any misuse of fonts or violations of font licensing agreements.

## Features

- Scan both .drfx files and .setting files for font requirements
- Check which fonts are already installed on your system
- Automatically download missing fonts from Google Fonts
- Search alternative sources like 1001Fonts, DaFont, and FreeFonts.io when not found on Google Fonts
- Support for variable fonts with multiple styles
- Detailed reports of font availability status

## Requirements

### Prerequisites

- Python 3.7 or higher
- Currently only fully tested on macOS (basic support for Windows/Linux)

### Dependencies

Install the required packages using pip:

```bash
pip install requests tqdm beautifulsoup4 fonttools
```

### Google Fonts API Key

You'll need a Google Fonts API key to use the script:

1. Visit the [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a new project (or select an existing one)
3. Enable the "Google Fonts Developer API"
4. Create an API key
5. The script will prompt you for this key on first run and offer to save it for future use

## Usage

### Basic Usage

```bash
python font.py
```

The script will guide you through selecting a DaVinci Resolve path to scan.

### Command-line Options

- `--drffiles`: Scan only .drfx files
- `--settingfiles`: Scan only .setting files
- `--verbose`: Display detailed output
- `--dryrun`: Only check which fonts are missing without downloading
- `--noask`: Use the provided path directly without asking for DaVinci Resolve location

### Examples

Scan a specific path for both file types:

```bash
python font.py /path/to/files
```

Scan only .setting files with detailed output:

```bash
python font.py --settingfiles --verbose /path/to/files
```

Check missing fonts without downloading:

```bash
python font.py --dryrun
```

