# MiMoCode Session Manager

A lightweight web UI for browsing and reopening [MiMoCode](https://github.com/XiaomiMiMo/MiMo-Code) chat sessions. Lists all previous conversations from the local MiMoCode database and lets you relaunch any session in Windows Terminal with one click.

## Features

- Lists all sessions with title, directory, creation time, and last update time
- Search by session name, directory, or session ID
- Sort by most recent, creation date, or alphabetical order
- One-click to reopen a session — opens Windows Terminal at the correct directory and runs `mimo -s <session_id>`
- Zero dependencies — uses Python's built-in `http.server` and `sqlite3`

## Requirements

- Python 3.8+
- [MiMoCode](https://github.com/XiaomiMiMo/MiMo-Code) installed and configured
- Windows (uses `wt.exe` / Windows Terminal)

## Usage

```bash
python server.py
```

Or double-click `start.bat`.

The browser will open automatically at `http://localhost:7860`.

## How It Works

1. Reads the MiMoCode SQLite database at `~/.local/share/mimocode/mimocode.db`
2. Serves a single-page HTML frontend via Python's built-in HTTP server
3. Clicking a session card sends a POST request that spawns `wt.exe -d <directory> cmd /k "mimo -s <session_id>"`

## Project Structure

```
.
├── server.py    # Python backend (HTTP server + SQLite queries)
├── index.html   # Single-page frontend (vanilla JS, no framework)
├── start.bat    # Quick-launch script
└── .gitignore
```

## License

MIT
