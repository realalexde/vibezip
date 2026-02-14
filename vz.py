#!/usr/bin/env python3
import os, re, sys, zipfile, platform, subprocess, requests, hashlib, base64, shutil, time
from datetime import datetime

GITHUB_RAW_SELF = "https://raw.githubusercontent.com/realalexde/vibezip/main/vz.py"
TIMEOUT = 10

# --- базовые утилиты ---
def fetch_text(url):
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text

def fetch_bytes(url):
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

# --- разбор zip.txt ---
def parse_content(raw):
    lines = raw.splitlines()
    no_comments = [ln for ln in lines if not ln.strip().startswith("#")]
    text = "\n".join(no_comments)
    version_m = re.search(r'^vibezip\s+v([^\s]+)', text, re.MULTILINE)
    project_version = version_m.group(1) if version_m else None
    project_m = re.search(r'MAKE\s+"(.+?)"', text)
    project_name = project_m.group(1) if project_m else None
    update_m = re.search(r'update_link\(\s*(.*?)\s*\)', text)
    update_link = update_m.group(1).strip() if update_m else None
    commands = {}
    for key in ("commandsWIN", "commandsMAC", "commandsLINUX"):
        m = re.search(rf'{key}\(\n(.*?)\n\)', text, re.DOTALL)
        if m:
            commands[key] = m.group(1).strip()
            text = text.replace(m.group(0), "")
    pattern = re.compile(r'([^\s\(\n]+)\s*(?:\(\n(.*?)\n\)|DOWNLOAD\((.*?)\)|BASE64\(\n(.*?)\n\))', re.DOTALL)
    files = []
    for m in pattern.finditer(text):
        path = m.group(1).strip()
        plain = m.group(2)
        download_url = m.group(3)
        b64 = m.group(4)
        entry = {"path": path}
        if plain is not None and plain != "":
            entry["type"] = "text"
            entry["data"] = plain
        elif download_url:
            entry["type"] = "download"
            entry["url"] = download_url.strip()
        elif b64 is not None:
            entry["type"] = "base64"
            entry["data_b64"] = b64.strip()
        else:
            entry["type"] = "empty"
            entry["data"] = ""
        files.append(entry)
    return {
        "project_name": project_name,
        "project_version": project_version,
        "update_link": update_link,
        "commands": commands,
        "files": files,
        "raw_nocomment": text
    }

# --- сравнение версий ---
def compare_versions(a, b):
    if a is None or b is None: return None
    def to_tuple(x):
        parts = x.split(".")
        nums = []
        for p in parts:
            try: nums.append(int(p))
            except: nums.append(0)
        return tuple(nums)
    ta, tb = to_tuple(a), to_tuple(b)
    L = max(len(ta), len(tb))
    ta = ta + (0,)*(L - len(ta))
    tb = tb + (0,)*(L - len(tb))
    if ta < tb: return -1
    if ta > tb: return 1
    return 0

# --- вспомогательные ---
def ensure_dir_for_file(path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)

def backup_file(path):
    if not os.path.exists(path):
        return None
    ts = time.strftime("%Y%m%d%H%M%S")
    bak = f"{path}.bak.{ts}"
    try:
        shutil.copy2(path, bak)
    except:
        pass
    return bak

# --- создание проекта в папке ---
def write_project_folder(parsed, auto_yes=False, backup=False):
    pname = parsed["project_name"]
    pversion = parsed["project_version"]
    update_link = parsed["update_link"]
    files = parsed["files"]
    commands = parsed["commands"]
    os.makedirs(pname, exist_ok=True)
    for entry in files:
        rel = entry["path"].replace("/", os.sep)
        full = os.path.join(pname, rel)
        ensure_dir_for_file(full)
        if backup and os.path.exists(full):
            backup_file(full)
        try:
            if entry["type"] == "text":
                with open(full, "w", encoding="utf-8") as f:
                    f.write(entry.get("data",""))
            elif entry["type"] == "download":
                data = fetch_bytes(entry["url"])
                try:
                    text = data.decode("utf-8")
                    with open(full, "w", encoding="utf-8") as f:
                        f.write(text)
                except:
                    with open(full, "wb") as f:
                        f.write(data)
            elif entry["type"] == "base64":
                b = base64.b64decode(entry["data_b64"])
                with open(full, "wb") as f:
                    f.write(b)
            else:
                open(full, "a").close()
        except:
            pass
    # команды
    sys_type = platform.system()
    if sys_type == "Windows":
        cmds = commands.get("commandsWIN","")
        script_path = os.path.join(pname, "install.bat")
        if cmds:
            try:
                with open(script_path, "w", encoding="utf-8") as sc:
                    sc.write("@echo off\n")
                    for line in cmds.splitlines():
                        line = line.strip()
                        if not line: continue
                        try:
                            if auto_yes:
                                sc.write(f"{line}\n")
                                subprocess.run(line, shell=True)
                            else:
                                ans = input(f"Execute '{line}' now? (y/n): ").strip().lower()
                                if ans == "y":
                                    subprocess.run(line, shell=True)
                                else:
                                    sc.write(f"{line}\n")
                        except:
                            pass
            except:
                pass
    else:
        key = "commandsLINUX" if sys_type=="Linux" else "commandsMAC"
        cmds = commands.get(key,"")
        script_path = os.path.join(pname, "install.sh")
        if cmds:
            try:
                with open(script_path, "w", encoding="utf-8") as sc:
                    sc.write("#!/bin/bash\n\n")
                    for line in cmds.splitlines():
                        line = line.strip()
                        if not line: continue
                        try:
                            if auto_yes:
                                sc.write(f"{line}\n")
                                subprocess.run(line, shell=True)
                            else:
                                ans = input(f"Execute '{line}' now? (y/n): ").strip().lower()
                                if ans == "y":
                                    subprocess.run(line, shell=True)
                                else:
                                    sc.write(f"{line}\n")
                        except:
                            pass
                try:
                    os.chmod(script_path, 0o755)
                except:
                    pass
            except:
                pass
    meta_path = os.path.join(pname, "vibezip")
    meta = []
    meta.append(f"project:{pname}")
    if pversion: meta.append(f"project_version:{pversion}")
    meta.append("mode:FOLDER")
    meta.append(f"files_count:{len(files)}")
    if update_link: meta.append(f"update_link:{update_link}")
    meta.append(f"created_at:{datetime.now().isoformat()}")
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
