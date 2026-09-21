import http.server
import json
import re
import sqlite3
import subprocess
import threading
import webbrowser
import os
import sys
import logging
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("session-manager")

DB_PATH = os.path.join(
    os.path.expanduser("~"),
    ".local", "share", "mimocode", "mimocode.db"
)

PORT = 7860
TZ = datetime.now().astimezone().tzinfo

ALLOWED_ORIGIN = f"http://localhost:{PORT}"
SESSION_ID_RE = re.compile(r"^[0-9a-zA-Z_\-]{1,64}$")


def get_sessions():
    if not os.path.isfile(DB_PATH):
        return {"error": "MiMoCode database not found", "sessions": []}

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT id, title, directory, time_created, time_updated
                FROM session
                WHERE title NOT LIKE 'checkpoint-writer:%'
                  AND parent_id IS NULL
                ORDER BY time_updated DESC
            """)
            rows = cur.fetchall()
    except sqlite3.Error as e:
        log.error("Database error: %s", e)
        return {"error": str(e), "sessions": []}

    sessions = []
    for r in rows:
        created = datetime.fromtimestamp(r["time_created"] / 1000, tz=TZ)
        updated = datetime.fromtimestamp(r["time_updated"] / 1000, tz=TZ)
        sessions.append({
            "id": r["id"],
            "title": r["title"],
            "directory": r["directory"],
            "time_created": created.strftime("%Y-%m-%d %H:%M:%S"),
            "time_updated": updated.strftime("%Y-%m-%d %H:%M:%S"),
            "time_created_ts": r["time_created"],
            "time_updated_ts": r["time_updated"],
        })
    return {"sessions": sessions}


def open_session(session_id, directory):
    if not isinstance(session_id, str) or not SESSION_ID_RE.match(session_id):
        return {"ok": False, "error": "Invalid session ID"}

    if not isinstance(directory, str) or not os.path.isdir(directory):
        return {"ok": False, "error": "Directory not found"}

    try:
        subprocess.Popen(
            ["wt.exe", "-d", directory, "cmd", "/k", "mimo", "-s", session_id],
        )
    except FileNotFoundError:
        return {"ok": False, "error": "Windows Terminal (wt.exe) not found"}
    except OSError as e:
        return {"ok": False, "error": str(e)}

    return {"ok": True}


HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            with open(HTML_PATH, "r", encoding="utf-8") as f:
                self.wfile.write(f.read().encode("utf-8"))
        elif parsed.path == "/api/sessions":
            data = get_sessions()
            self._json_response(data)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/open":
            self.send_error(404)
            return

        # C2: reject cross-origin requests
        origin = self.headers.get("Origin", "")
        if origin and origin != ALLOWED_ORIGIN:
            self._json_response({"ok": False, "error": "Forbidden"}, 403)
            return

        # C2: require correct Content-Type
        ct = self.headers.get("Content-Type", "")
        if "application/json" not in ct:
            self._json_response({"ok": False, "error": "Content-Type must be application/json"}, 415)
            return

        # H2: safe JSON parsing
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self._json_response({"ok": False, "error": "Invalid Content-Length"}, 400)
            return

        try:
            raw = self.rfile.read(length)
            body = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            self._json_response({"ok": False, "error": "Invalid JSON"}, 400)
            return

        if not isinstance(body, dict):
            self._json_response({"ok": False, "error": "JSON body must be an object"}, 400)
            return

        # H1: type-safe extraction
        session_id = body.get("session_id")
        directory = body.get("directory")
        if not isinstance(session_id, str) or not isinstance(directory, str):
            self._json_response({"ok": False, "error": "session_id and directory must be strings"}, 400)
            return

        result = open_session(session_id, directory)
        status = 200 if result.get("ok") else 400
        self._json_response(result, status)

    def _json_response(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        log.info(fmt, *args)


def main():
    try:
        server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as e:
        print(f"Cannot bind to port {PORT}: {e}", file=sys.stderr)
        sys.exit(1)

    url = f"http://localhost:{PORT}"
    print(f"Session Manager running at {url}")
    timer = threading.Timer(0.5, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
