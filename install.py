import os, re, sys, zipfile, platform, subprocess, requests, hashlib
from datetime import datetime

GITHUB_RAW_SELF = "https://raw.githubusercontent.com/realalexde/vibezip/main/vz.py"
auto_yes = False
args = sys.argv[1:]

if "-y" in args: auto_yes = True
if "-u" in args:
    try:
        r = requests.get(GITHUB_RAW_SELF, timeout=10)
        r.raise_for_status()
        remote_hash = hashlib.sha256(r.content).hexdigest()
        with open(__file__,"rb") as f: local_hash=hashlib.sha256(f.read()).hexdigest()
        if local_hash != remote_hash:
            with open(__file__,"wb") as f: f.write(r.content)
            print("vz.py updated successfully! Please rerun.")
        else: print("vz.py is already up-to-date.")
    except Exception as e:
        print(f"Update failed: {e}")
    sys.exit(0)

if len(args)<1: sys.exit("Usage: py vz.py <project_txt_or_url> [-f|-z] [-y]")

project_input = args[0]
flag = None
for a in args[1:]:
    if a in ("-f","-z"): flag=a

mode = "FOLDER" if flag in (None,"-f") else "ZIP"

if project_input.startswith("http"):
    try: r=requests.get(project_input, timeout=10); r.raise_for_status(); content=r.text
    except Exception as e: sys.exit(f"Failed to download {project_input}: {e}")
else:
    with open(project_input,"r",encoding="utf-8") as f: content=f.read()

content_lines=[l for l in content.splitlines() if not l.strip().startswith("#")]
content="\n".join(content_lines)

version_match = re.search(r'^vibezip\s+v[0-9.]+',content,re.M)
if not version_match: sys.exit("Invalid vibezip header")
version_line = version_match.group(0)

project_match = re.search(r'MAKE\s+"(.+?)"',content)
if not project_match: sys.exit("Project name not found")
project_name = project_match.group(1)

commands_blocks={}
for cmd_type in ["commandsWIN","commandsMAC","commandsLINUX"]:
    m=re.search(rf'{cmd_type}\(\n(.*?)\n\)',content,re.DOTALL)
    if m:
        commands_blocks[cmd_type]=m.group(1).strip()
        content=content.replace(m.group(0),"")

file_pattern = re.compile(r'([^\s\(\n]+)\s*(?:\(\n(.*?)\n\)|DOWNLOAD\((.*?)\))', re.DOTALL)
files=file_pattern.findall(content)

def write_file(path,data):
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path,"w",encoding="utf-8") as f: f.write(data)

def handle_commands(commands,script_path,is_windows=False):
    with open(script_path,"w",encoding="utf-8") as f_script:
        if not is_windows: f_script.write("#!/bin/bash\n\n")
        for line in commands.splitlines():
            ans = "y" if auto_yes else input(f"Execute '{line}' now? (y/n): ").strip().lower()
            if ans=="y": subprocess.run(line,shell=True)
            else: f_script.write(line+"\n")
    if not is_windows: os.chmod(script_path,0o755)

if mode=="FOLDER":
    os.makedirs(project_name,exist_ok=True)
    for path,fc,url in files:
        full=os.path.join(project_name,path.replace("/","\\"))
        if url: r=requests.get(url,timeout=10); r.raise_for_status(); data=r.text
        else: data=fc
        write_file(full,data)

    sys_type = platform.system()
    if sys_type=="Windows": cmds=commands_blocks.get("commandsWIN","")
    else: cmds=commands_blocks.get("commandsLINUX" if sys_type=="Linux" else "commandsMAC","")
    if cmds:
        handle_commands(cmds, os.path.join(project_name,"install.bat" if sys_type=="Windows" else "install.sh"), sys_type=="Windows")

    with open(os.path.join(project_name,"vibezip"),"w",encoding="utf-8") as f:
        f.write(f"version:{version_line}\nproject:{project_name}\nmode:{mode}\nfiles_count:{len(files)}\ncommands:{', '.join(commands_blocks.keys())}\ncreated_at:{datetime.now().isoformat()}\n")
    print(f"Project folder '{project_name}' created.")

elif mode=="ZIP":
    zipf = zipfile.ZipFile(f"{project_name}.zip","w")
    for path,fc,url in files:
        if url: r=requests.get(url,timeout=10); r.raise_for_status(); data=r.text
        else: data=fc
        zipf.writestr(path,data)

    for cmd_type,cmds in commands_blocks.items():
        if cmd_type=="commandsWIN": zipf.writestr("install.bat","\n".join([f"@echo off\necho Running: {line}" for line in cmds.splitlines()]))
        else: zipf.writestr("install.sh","#/bin/bash\n"+ "\n".join([f'echo "Running: {line}"' for line in cmds.splitlines()]))

    meta = (f"version:{version_line}\nproject:{project_name}\nmode:{mode}\nfiles_count:{len(files)}\ncommands:{', '.join(commands_blocks.keys())}\ncreated_at:{datetime.now().isoformat()}\n")
    zipf.writestr("vibezip",meta); zipf.close()
    print(f"Archive '{project_name}.zip' created with install scripts.")
