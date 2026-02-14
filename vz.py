#!/usr/bin/env python3
import os, re, sys, zipfile, platform, subprocess, requests, hashlib, base64, shutil, time
from datetime import datetime

GITHUB_RAW_SELF = "https://raw.githubusercontent.com/realalexde/vibezip/main/vz.py"
TIMEOUT = 10

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
    # extract and remove commands blocks (they are after files but could be anywhere)
    commands = {}
    for key in ("commandsWIN", "commandsMAC", "commandsLINUX"):
        m = re.search(rf'{key}\(\n(.*?)\n\)', text, re.DOTALL)
        if m:
            commands[key] = m.group(1).strip()
            text = text.replace(m.group(0), "")
    # Now extract file entries: supports (content), DOWNLOAD(url), BASE64(content)
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

def ensure_dir_for_file(path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)

def backup_file(path):
    if not os.path.exists(path):
        return None
    ts = time.strftime("%Y%m%d%H%M%S")
    bak = f"{path}.bak.{ts}"
    shutil.copy2(path, bak)
    return bak

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
        if entry["type"] == "text":
            with open(full, "w", encoding="utf-8") as f:
                f.write(entry.get("data",""))
        elif entry["type"] == "download":
            data = fetch_bytes(entry["url"])
            # try decode as text, else write as bytes
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
    # install scripts per platform
    sys_type = platform.system()
    if sys_type == "Windows":
        cmds = commands.get("commandsWIN","")
        script_path = os.path.join(pname, "install.bat")
        if cmds:
            with open(script_path, "w", encoding="utf-8") as sc:
                sc.write("@echo off\n")
                for line in cmds.splitlines():
                    line = line.strip()
                    if not line: continue
                    if auto_yes:
                        sc.write(f"{line}\n")
                        try: subprocess.run(line, shell=True)
                        except: pass
                    else:
                        ans = input(f"Execute '{line}' now? (y/n): ").strip().lower()
                        if ans == "y":
                            try: subprocess.run(line, shell=True)
                            except: pass
                        else:
                            sc.write(f"{line}\n")
    else:
        key = "commandsLINUX" if sys_type=="Linux" else "commandsMAC"
        cmds = commands.get(key,"")
        script_path = os.path.join(pname, "install.sh")
        if cmds:
            with open(script_path, "w", encoding="utf-8") as sc:
                sc.write("#!/bin/bash\n\n")
                for line in cmds.splitlines():
                    line = line.strip()
                    if not line: continue
                    if auto_yes:
                        sc.write(f"{line}\n")
                        try: subprocess.run(line, shell=True)
                        except: pass
                    else:
                        ans = input(f"Execute '{line}' now? (y/n): ").strip().lower()
                        if ans == "y":
                            try: subprocess.run(line, shell=True)
                            except: pass
                        else:
                            sc.write(f"{line}\n")
            try: os.chmod(script_path, 0o755)
    # write vibezip metadata inside project folder
    meta_path = os.path.join(pname, "vibezip")
    meta = []
    meta.append(f"project:{pname}")
    if pversion: meta.append(f"project_version:{pversion}")
    meta.append(f"mode:FOLDER")
    meta.append(f"files_count:{len(files)}")
    if update_link: meta.append(f"update_link:{update_link}")
    meta.append(f"created_at:{datetime.now().isoformat()}")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("\n".join(meta))
    return pname

def write_project_zip(parsed, auto_yes=False, backup=False):
    pname = parsed["project_name"]
    pversion = parsed["project_version"]
    update_link = parsed["update_link"]
    files = parsed["files"]
    commands = parsed["commands"]
    zname = f"{pname}.zip"
    with zipfile.ZipFile(zname, "w") as zf:
        for entry in files:
            path = entry["path"]
            if entry["type"] == "text":
                zf.writestr(path, entry.get("data",""))
            elif entry["type"] == "download":
                data = fetch_bytes(entry["url"])
                zf.writestr(path, data)
            elif entry["type"] == "base64":
                b = base64.b64decode(entry["data_b64"])
                zf.writestr(path, b)
            else:
                zf.writestr(path, "")
        # commands: include install scripts (not executed for zip creation)
        win_cmds = commands.get("commandsWIN","")
        other_cmds = "\n".join(commands.get("commandsLINUX","").splitlines() + commands.get("commandsMAC","").splitlines())
        if win_cmds:
            bat = "@echo off\n" + "\n".join([ln for ln in win_cmds.splitlines() if ln.strip()])
            zf.writestr("install.bat", bat)
        if other_cmds:
            sh = "#!/bin/bash\n\n" + "\n".join([f'echo "Running: {ln}"\n{ln}' for ln in other_cmds.splitlines() if ln.strip()])
            zf.writestr("install.sh", sh)
        # vibezip metadata inside zip
        meta = []
        meta.append(f"project:{pname}")
        if pversion: meta.append(f"project_version:{pversion}")
        meta.append("mode:ZIP")
        meta.append(f"files_count:{len(files)}")
        if update_link: meta.append(f"update_link:{update_link}")
        meta.append(f"created_at:{datetime.now().isoformat()}")
        zf.writestr("vibezip", "\n".join(meta))
    return zname

def process_project_text(raw_text, mode="FOLDER", auto_yes=False, backup=False):
    parsed = parse_content(raw_text)
    if not parsed["project_name"]:
        raise RuntimeError("Project name not found in content")
    if mode == "FOLDER":
        return write_project_folder(parsed, auto_yes=auto_yes, backup=backup)
    else:
        return write_project_zip(parsed, auto_yes=auto_yes, backup=backup)

def self_update(auto_yes=False):
    try:
        remote = fetch_bytes(GITHUB_RAW_SELF)
        remote_hash = sha256_bytes(remote)
        with open(__file__,"rb") as f:
            local = f.read()
        local_hash = sha256_bytes(local)
        if local_hash != remote_hash:
            print("New vz.py is available on GitHub.")
            if auto_yes:
                ans = "y"
            else:
                ans = input("Install update to vz.py now? [y/n]: ").strip().lower()
            if ans == "y":
                bak = __file__ + ".bak." + time.strftime("%Y%m%d%H%M%S")
                try: shutil.copy2(__file__, bak)
                except: pass
                with open(__file__,"wb") as f:
                    f.write(remote)
                print("vz.py updated. Please rerun the script.")
                return True
            else:
                print("Update skipped.")
                return False
        else:
            print("vz.py is up-to-date.")
            return False
    except Exception as e:
        print("Self-update failed:", e)
        return False

def check_project_update_current_folder(auto_yes=False, backup=False):
    vibep = os.path.join(os.getcwd(), "vibezip")
    if not os.path.exists(vibep):
        print("vibezip metadata not found in current folder.")
        return
    with open(vibep,"r",encoding="utf-8") as f:
        meta = f.read()
    m_link = re.search(r'update_link:(.+)', meta)
    m_ver = re.search(r'project_version:(.+)', meta)
    m_mode = re.search(r'mode:(.+)', meta)
    link = m_link.group(1).strip() if m_link else None
    local_ver = m_ver.group(1).strip() if m_ver else None
    mode = m_mode.group(1).strip() if m_mode else "FOLDER"
    if not link:
        print("No update_link in vibezip.")
        return
    try:
        remote_text = fetch_text(link)
    except Exception as e:
        print("Failed to fetch update:", e)
        return
    parsed_remote = parse_content(remote_text)
    remote_ver = parsed_remote.get("project_version")
    if remote_ver is None:
        print("Remote project has no version header.")
        return
    cmp = compare_versions(local_ver, remote_ver)
    if cmp is None:
        print("Cannot compare versions.")
        return
    if cmp >= 0:
        print("Project is up-to-date.")
        return
    print(f"New project version available: {remote_ver}")
    print(f"Current version: {local_ver}")
    if auto_yes:
        ans = "y"
    else:
        ans = input("Install update? [y/n]: ").strip().lower()
    if ans == "y":
        # perform update: overwrite files according to mode in vibezip metadata (use remote parsed content)
        if backup:
            # backup current files by copying project folder to .backup.timestamp
            folder = os.getcwd()
            bname = f"{folder}.backup.{time.strftime('%Y%m%d%H%M%S')}"
            shutil.copytree(folder, bname)
            print(f"Backup created: {bname}")
        # write project according to mode
        if mode.upper() == "ZIP":
            write_project_zip(parsed_remote, auto_yes=auto_yes, backup=backup)
            print("Project ZIP updated.")
        else:
            write_project_folder(parsed_remote, auto_yes=auto_yes, backup=backup)
            print("Project folder updated.")
    else:
        print("Update cancelled.")

def usage_and_exit():
    print("Usage:")
    print("  py vz.py <project_txt_or_url>          # create project folder (default)")
    print("  py vz.py <project_txt_or_url> -z       # create ZIP instead")
    print("  py vz.py <project_txt_or_url> -f       # explicit folder")
    print("  py vz.py -u                            # self update vz.py from GitHub")
    print("  py vz.py -c                            # check update for project in current folder")
    print("Optional flags: -y  (auto yes), -b (backup before overwrite)")
    sys.exit(1)

def main():
    args = sys.argv[1:]
    if not args:
        usage_and_exit()
    auto_yes = "-y" in args
    backup = "-b" in args
    if "-u" in args:
        self_update(auto_yes=auto_yes)
        return
    if "-c" in args:
        check_project_update_current_folder(auto_yes=auto_yes, backup=backup)
        return
    # process create/update from given input
    # first arg should be project_txt_or_url
    src = args[0]
    flag = None
    for a in args[1:]:
        if a in ("-z","-f"):
            flag = a
    # default behavior: folder (same as no flag)
    mode = "ZIP" if flag == "-z" else "FOLDER"
    # read content
    try:
        if src.startswith("http://") or src.startswith("https://"):
            raw = fetch_text(src)
        else:
            with open(src,"r",encoding="utf-8") as f:
                raw = f.read()
    except Exception as e:
        print("Failed to read project source:", e)
        return
    try:
        result = process_project_text(raw, mode=mode, auto_yes=auto_yes, backup=backup)
        if mode == "FOLDER":
            print(f"Project folder '{result}' created/updated.")
        else:
            print(f"Project archive '{result}' created.")
        # if update_link present -> write vibezip inside project (already done), ensure included
        parsed = parse_content(raw)
        # if project created as folder and update_link exists, it's already in vibezip metadata
    except Exception as e:
        print("Error processing project:", e)

if __name__ == "__main__":
    main()
