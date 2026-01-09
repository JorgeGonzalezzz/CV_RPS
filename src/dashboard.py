import os
import json
import threading
import webbrowser
import time
from flask import Flask, send_from_directory, abort, render_template, make_response


class ResultsDashboard:
    """
    Interactive Flask dashboard with tabs + keyboard navigation in Frames/Masks.
    Expects: out_dir/summary.json + round_XXX/*.png
    """

    def __init__(self, out_dir: str, host: str = "127.0.0.1", port: int = 5000, open_browser: bool = True):
        self.out_dir = os.path.abspath(out_dir)
        self.host = host
        self.port = int(port)
        self.open_browser = open_browser

        # Project root (.. from src/)
        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        WEB_DIR = os.path.join(BASE_DIR, "web")

        self.app = Flask(
            __name__,
            template_folder=os.path.join(WEB_DIR, "templates"),
            static_folder=os.path.join(WEB_DIR, "static"),
            static_url_path="/static",
        )

        # Disable Flask static cache
        self.app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

        # Disable browser cache for EVERYTHING
        @self.app.after_request
        def add_no_cache_headers(resp):
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
            return resp

        self._register_routes()

    def _load_summary(self):
        p = os.path.join(self.out_dir, "summary.json")
        if not os.path.exists(p):
            raise FileNotFoundError(f"summary.json not found in {self.out_dir}")
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _compute_final_winner(players, final_score):
        if not players or len(players) < 2:
            return "N/A"
        p1, p2 = players[0], players[1]
        s1 = final_score.get(p1, 0)
        s2 = final_score.get(p2, 0)
        if s1 > s2:
            return f"{p1.upper()} WINS"
        if s2 > s1:
            return f"{p2.upper()} WINS"
        return "DRAW"

    def _register_routes(self):
        @self.app.get("/")
        def index():
            # Always load fresh summary (no caching)
            s = self._load_summary()
            players = s.get("players", [])
            final_score = s.get("final_score", {})
            final_winner = self._compute_final_winner(players, final_score)

            # Make response explicitly no-cache
            html = render_template(
                "dashboard.html",
                out_dir=self.out_dir,
                players=players,
                final_score=final_score,
                final_winner=final_winner,
                num_rounds=s.get("num_rounds", 0),
                rounds=s.get("rounds", []),
            )
            resp = make_response(html)
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
            return resp

        @self.app.get("/files/<path:filepath>")
        def files(filepath):
            # Secure path
            full = os.path.abspath(os.path.join(self.out_dir, filepath))
            if not full.startswith(self.out_dir):
                abort(403)

            if not os.path.exists(full):
                abort(404)

            directory = os.path.dirname(full)
            filename = os.path.basename(full)

            # cache_timeout=0 -> do not cache images
            return send_from_directory(directory, filename, cache_timeout=0)

    def run(self, blocking: bool = True):
        # IMPORTANT: even if host is 0.0.0.0, browser must open 127.0.0.1 for local PC
        open_host = "127.0.0.1"
        cache_bust = int(time.time() * 1000)
        url = f"http://{open_host}:{self.port}/?t={cache_bust}"

        if self.open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        if blocking:
            self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False, threaded=True)
        else:
            t = threading.Thread(
                target=lambda: self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False, threaded=True),
                daemon=True
            )
            t.start()
            return t
