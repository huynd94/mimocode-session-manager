import http.server
import json
import sqlite3
import subprocess
import threading
import webbrowser
import shutil
import os
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(
    os.path.expanduser("~"),
    ".local", "share", "mimocode", "mimocode.db"
)

PORT = 7860
TZ_OFFSET = timedelta(hours=7)  # UTC+7 Vietnam
TZ = timezone(TZ_OFFSET)


def get_sessions():
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()

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
    return sessions


def open_session(session_id, directory):
    if not os.path.isdir(directory):
        return {"ok": False, "error": f"Directory not found: {directory}"}

    subprocess.Popen(
        ["wt.exe", "-d", directory, "cmd", "/k", f"mimo -s {session_id}"],
        shell=True,
    )
    return {"ok": True}


HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

JSON_HEADERS = [("Content-Type", "application/json; charset=utf-8")]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
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
        if parsed.path == "/api/open":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            result = open_session(body.get("session_id", ""), body.get("directory", ""))
            self._json_response(result)
        else:
            self.send_error(404)

    def _json_response(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        pass


def main():
    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Session Manager running at {url}")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
