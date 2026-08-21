# 📦 vibezip
> A portable project format — pack an entire project into a single `.zip.txt` file you can copy, paste, and send anywhere.

vibezip turns your project into plain text. Send it in a chat, drop it in a prompt, paste it into a notes app. The other side runs one command and gets the full project extracted, with install scripts executed automatically.

---

## ⚡ Install

**Requirements:** Python 3 + `pip install requests`

```sh
# 1. Download installer
curl -O https://raw.githubusercontent.com/realalexde/vibezip/main/install.py

# 2. Run it
python install.py
```

The installer downloads `vz.py`, asks if you want to run it immediately, then removes itself.

---

## 🚀 Usage

```sh
python vz.py <url-to-zip.txt>
```

`vz.py` fetches the `.zip.txt` file from the URL, parses it, extracts all files into a folder, and runs the install commands for your platform (Windows/Linux/macOS).

**Flags:**
| Flag | What it does |
|---|---|
| `-y` / `--yes` | Auto-confirm all install commands |
| `--backup` | Back up existing files before overwriting |

---

## 📄 The `.zip.txt` Format

A `.zip.txt` is a plain-text file that describes a full project. You write it by hand or generate it with AI.

**Basic structure:**
```
vibezip v1.0
MAKE "my-project"

# optional install commands per platform
commandsLINUX(
pip install -r requirements.txt
)

# files
src/main.py(
print("hello world")
)

assets/logo.png DOWNLOAD(https://example.com/logo.png)
```

**Supported file types:**
- `filename(content)` — plain text file
- `filename DOWNLOAD(url)` — downloaded from URL at install time
- `filename BASE64(data)` — binary file as base64

**Optional metadata:**
- `update_link(url)` — URL to check for updates

---

## 🤖 AI Prompt

Use this prompt to have any AI generate a valid `.zip.txt` for your project:

```
You are generating a vibezip .zip.txt file.

Rules:
- First line: vibezip v1.0
- Second line: MAKE "project-name"
- Then optionally: commandsWIN(...), commandsMAC(...), commandsLINUX(...)
  with shell commands to run after extraction (one per line inside parens)
- Then list every file in this format:
    path/to/file.ext(
    file content here
    )
  For binary files use: filename BASE64(base64data)
  For downloaded files use: filename DOWNLOAD(https://...)
- Comments start with #
- No extra explanation, only the .zip.txt content

Generate a .zip.txt for the following project:
[describe your project here]
```

---

## 🔗 Repository

[github.com/realalexde/vibezip](https://github.com/realalexde/vibezip)
