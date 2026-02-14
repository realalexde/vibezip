import os
import sys
import requests

GITHUB_RAW_URL = "https://raw.githubusercontent.com/realalexde/vibezip/main/vz.py"
LOCAL_FILE = "vz.py"

print("Downloading the latest vz.py from GitHub...")

try:
    r = requests.get(GITHUB_RAW_URL)
    r.raise_for_status()
except Exception as e:
    print(f"Failed to download vz.py: {e}")
    sys.exit(1)

with open(LOCAL_FILE, "wb") as f:
    f.write(r.content)

print(f"vz.py downloaded successfully!")

run_now = input("Do you want to run vz.py now? [y/n]: ").strip().lower()
if run_now == "y":
    os.system(f'python {LOCAL_FILE}')

installer_file = sys.argv[0]
try:
    os.remove(installer_file)
    print(f"{installer_file} removed. Installation complete.")
except Exception as e:
    print(f"Could not remove installer: {e}")
