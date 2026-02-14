import os
import re
import sys
import zipfile
import platform
import subprocess
import requests
from datetime import datetime
import hashlib

# ------------------------
# GitHub self-check
# ------------------------
GITHUB_RAW_URL = "YOUR_RAW_GITHUB_URL_HERE"  # <-- вставь ссылку на raw vz.py на GitHub

try:
    with open(__file__, "rb") as f:
        local_hash = hashlib.sha256(f.read()).hexdigest()
    r = requests.get(GITHUB_RAW_URL)
    r.raise_for_status()
    remote_hash = hashlib.sha256(r.content).hexdigest()
    if local_hash != remote_hash:
        print("vibecode updated on Github!")
        ans = input("Do you want to install an update? [y/n]: ").strip().lower()
        if ans == "y":
            with open(__file__, "wb") as f:
                f.write(r.content)
            print("vz.py updated successfully! Please rerun the script.")
            sys.exit(0)
except Exception as e:
    print(f"GitHub check skipped: {e}")

# ------------------------
# Input args
# ------------------------
if len(sys.argv) != 3:
    print("Usage: python vz.py <file.txt> <ZIP|FOLDER>")
    sys.exit(1)

input_file = sys.argv[1]
mode = sys.argv[2].upper()
if mode not in ("ZIP", "FOLDER"):
    print("Mode must be ZIP or FOLDER")
    sys.exit(1)

with open(input_file, "r", encoding="utf-8") as f:
    content = f.read()

# ------------------------
# Parse version and project
# ------------------------
version_match = re.search(r'^vibezip\s+v[0-9.]+', content, re.MULTILINE)
if not version_match:
    print("Invalid vibezip header")
    sys.exit(1)
version_line = version_match.group(0)

project_match = re.search(r'MAKE\s+"(.+?)"', content)
if not project_match:
    print("Project name not found")
    sys.exit(1)
project_name = project_match.group(1)

# ------------------------
# Extract command blocks
# ------------------------
commands_blocks = {}
for cmd_type in ["commandsWIN", "commandsMAC", "commandsLINUX"]:
    match = re.search(rf'{cmd_type}\(\n(.*?)\n\)', content, re.DOTALL)
    if match:
        commands_blocks[cmd_type] = match.group(1).strip()
        content = content.replace(match.group(0), "")

# ------------------------
# Extract files
# ------------------------
file_pattern = re.compile(
    r'([^\s\(\n]+)\s*(?:\(\n(.*?)\n\)|DOWNLOAD\((.*?)\))',
    re.DOTALL
)
files = file_pattern.findall(content)

# ------------------------
# Helper: write files
# ------------------------
def write_file(full_path, data):
    os.makedirs(os.path.dirname(full_path), exist_ok=True) if os.path.dirname(full_path) else None
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(data)

# ------------------------
# Execute commands with y/n
# ------------------------
def handle_commands(commands, script_path, is_windows=False):
    with open(script_path, "w", encoding="utf-8") as f_script:
        if not is_windows:
            f_script.write("#!/bin/bash\n\n")
        for line in commands.splitlines():
            ans = input(f"Execute '{line}' now? (y/n): ").strip().lower()
            if ans == "y":
                subprocess.run(line, shell=True)
            else:
                f_script.write(line + ("\n" if is_windows else "\n"))
    if not is_windows:
        os.chmod(script_path, 0o755)

# ------------------------
# FOLDER MODE
# ------------------------
if mode == "FOLDER":
    os.makedirs(project_name, exist_ok=True)

    for path, file_content, url in files:
        full_path = os.path.join(project_name, path.replace("/", os.sep))
        if url:
            print(f"Downloading {url} -> {path}")
            r = requests.get(url)
            r.raise_for_status()
            data = r.text
        else:
            data = file_content
        write_file(full_path, data)

    # Determine system
    system_type = platform.system()
    if system_type == "Windows":
        cmds = commands_blocks.get("commandsWIN", "")
        if cmds:
            handle_commands(cmds, os.path.join(project_name, "install.bat"), is_windows=True)
    else:
        cmds = commands_blocks.get("commandsLINUX" if system_type=="Linux" else "commandsMAC", "")
        if cmds:
            handle_commands(cmds, os.path.join(project_name, "install.sh"))

    # vibezip metadata
    with open(os.path.join(project_name, "vibezip"), "w", encoding="utf-8") as f:
        f.write(f"version: {version_line}\n")
        f.write(f"project: {project_name}\n")
        f.write(f"mode: {mode}\n")
        f.write(f"files_count: {len(files)}\n")
        f.write(f"commands: {', '.join(commands_blocks.keys())}\n")
        f.write(f"created_at: {datetime.now().isoformat()}\n")

    print(f"Project folder '{project_name}' created.")

# ------------------------
# ZIP MODE
# ------------------------
elif mode == "ZIP":
    zip_filename = f"{project_name}.zip"
    with zipfile.ZipFile(zip_filename, "w") as zipf:
        for path, file_content, url in files:
            if url:
                print(f"Downloading {url} -> {path}")
                r = requests.get(url)
                r.raise_for_status()
                data = r.text
            else:
                data = file_content
            zipf.writestr(path, data)

        # commands scripts
        for cmd_type, cmds in commands_blocks.items():
            if cmd_type == "commandsWIN":
                zipf.writestr("install.bat", "\n".join([f"@echo off\necho Running: {line}" for line in cmds.splitlines()]))
            else:
                zipf.writestr("install.sh", "#!/bin/bash\n" + "\n".join([f'echo "Running: {line}"' for line in cmds.splitlines()]))

        # vibezip metadata
        metadata = (
            f"version: {version_line}\n"
            f"project: {project_name}\n"
            f"mode: {mode}\n"
            f"files_count: {len(files)}\n"
            f"commands: {', '.join(commands_blocks.keys())}\n"
            f"created_at: {datetime.now().isoformat()}\n"
        )
        zipf.writestr("vibezip", metadata)

    print(f"Archive '{zip_filename}' created with install scripts.")
