"""Dashboard HTTP server — serves the Mission Control UI."""
import json
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from functools import partial

from .dashboard_data import generate_projects_data


DASHBOARD_DIR = Path(__file__).parent / "dashboard"


class DashboardHandler(SimpleHTTPRequestHandler):
    """Custom handler that serves dashboard files and API endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/projects":
            self._serve_api()
        else:
            super().do_GET()

    def _serve_api(self):
        """Return projects JSON."""
        try:
            data = generate_projects_data()
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            body = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress standard log noise, only log errors."""
        if args and "404" in str(args[0]):
            super().log_message(format, *args)


def run_dashboard(host: str = "127.0.0.1", port: int = 9109, open_browser: bool = True):
    """Start the dashboard server."""
    server = HTTPServer((host, port), DashboardHandler)
    url = f"http://{host}:{port}"
    print(f"🚀 Mission Control Dashboard: {url}")
    print("   Press Ctrl+C to stop")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✋ Dashboard stopped")
        server.server_close()
