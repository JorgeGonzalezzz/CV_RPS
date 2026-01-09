import os
import json
import threading
import webbrowser
from flask import Flask, render_template_string, send_from_directory, abort, render_template




class ResultsDashboard:
    """
    Interactive Flask dashboard with tabs + keyboard navigation in Frames/Masks.
    Expects: out_dir/summary.json + round_XXX/*.png
    """

    def __init__(self, out_dir: str, host: str = "127.0.0.1", port: int = 5000, open_browser: bool = True):
        self.out_dir = os.path.abspath(out_dir)
        self.host = host
        self.port = port
        self.open_browser = open_browser


        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # raíz del proyecto
        WEB_DIR = os.path.join(BASE_DIR, "web")

        self.app = Flask(
            __name__,
            template_folder=os.path.join(WEB_DIR, "templates"),
            static_folder=os.path.join(WEB_DIR, "static"),
            static_url_path="/static",
        )

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
            s = self._load_summary()
            players = s.get("players", [])
            final_score = s.get("final_score", {})
            final_winner = self._compute_final_winner(players, final_score)

            return render_template(
                "dashboard.html",
                out_dir=self.out_dir,
                players=players,
                final_score=final_score,
                final_winner=final_winner,
                num_rounds=s.get("num_rounds", 0),
                rounds=s.get("rounds", []),
            )

        @self.app.get("/files/<path:filepath>")
        def files(filepath):
            full = os.path.abspath(os.path.join(self.out_dir, filepath))
            if not full.startswith(self.out_dir):
                abort(403)
            directory = os.path.dirname(full)
            filename = os.path.basename(full)
            if not os.path.exists(full):
                abort(404)
            return send_from_directory(directory, filename)

    def run(self, blocking: bool = True):
        url = f"http://{self.host}:{self.port}/"
        if self.open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        if blocking:
            self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
        else:
            t = threading.Thread(
                target=lambda: self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False),
                daemon=True
            )
            t.start()
            return t

# HTML = """
# <!doctype html>
# <html>
# <head>
#   <meta charset="utf-8"/>
#   <title>RPS Dashboard</title>
#   <style>
#     body { font-family: Arial, sans-serif; margin: 24px; }
#     .tabs { display:flex; gap:10px; margin: 16px 0 18px; flex-wrap:wrap; }
#     .tab-btn { border:1px solid #ddd; background:#f7f7f7; padding:10px 14px; border-radius:10px; cursor:pointer; }
#     .tab-btn.active { background:#111; color:#fff; border-color:#111; }
#     .panel { display:none; }
#     .panel.active { display:block; }
#     .card { border:1px solid #ddd; border-radius:14px; padding:14px; }
#     .muted { color:#666; }
#     .big { font-size: 28px; font-weight: 700; }
#     .topline { display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; }
#     .path { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 12px; color:#444; }

#     .kpi { display:flex; gap:24px; flex-wrap:wrap; margin-top: 10px; }
#     .kpi .box { border:1px solid #eee; border-radius:12px; padding:12px 14px; min-width: 160px; background:#fafafa; }
#     .k { font-size:12px; color:#666; }
#     .v { font-size:20px; font-weight:700; margin-top: 6px; }

#     img { width: 100%; max-height: 420px; object-fit: contain; border-radius: 10px; border:1px solid #eee; background:#fff; }
#     .two-col { display:grid; grid-template-columns: 1fr 1fr; gap:16px; }
#     @media (max-width: 900px) { .two-col { grid-template-columns: 1fr; } }

#     .nav { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; margin: 10px 0 14px; }
#     .btn { border:1px solid #ddd; background:#f7f7f7; padding:8px 12px; border-radius:10px; cursor:pointer; }
#     .btn:hover { background:#eee; }
#     .pill { display:inline-block; padding:3px 10px; border-radius:999px; background:#eee; font-size:12px; }
#     .hint { font-size: 12px; color:#666; }
#     a.link { text-decoration:none; color: inherit; }
#     a.link:hover { text-decoration: underline; }
#   </style>
# </head>
# <body>

#   <div class="topline">
#     <div>
#       <div class="big">RPS Results Dashboard</div>
#       <div class="muted">Players: <b>{{ players[0] }}</b> vs <b>{{ players[1] }}</b></div>
#     </div>
#     <div class="muted">
#       <div><b>Export folder</b></div>
#       <div class="path">{{ out_dir }}</div>
#     </div>
#   </div>

#   <div class="tabs">
#     <div class="tab-btn active" data-tab="score">Winner & Score</div>
#     <div class="tab-btn" data-tab="frames">Frames</div>
#     <div class="tab-btn" data-tab="masks">Masks</div>
#   </div>

#   <!-- SCORE -->
#   <div class="panel active" id="panel-score">
#     <div class="card">
#       <div style="display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap;">
#         <div>
#           <div class="muted">Final winner</div>
#           <div class="big">{{ final_winner }}</div>
#         </div>
#         <div class="pill">Rounds: {{ num_rounds }}</div>
#       </div>

#       <div class="kpi">
#         <div class="box"><div class="k">{{ players[0] }} wins</div><div class="v">{{ final_score.get(players[0], 0) }}</div></div>
#         <div class="box"><div class="k">{{ players[1] }} wins</div><div class="v">{{ final_score.get(players[1], 0) }}</div></div>
#         <div class="box"><div class="k">Draws</div><div class="v">{{ final_score.get("draws", 0) }}</div></div>
#         <div class="box"><div class="k">Null rounds</div><div class="v">{{ final_score.get("nulls", 0) }}</div></div>
#       </div>

#       <div class="hint" style="margin-top:10px;">
#         Tip: go to <b>Frames</b> or <b>Masks</b> and use <b>← / →</b> (or <b>A / D</b>) to navigate rounds.
#       </div>
#     </div>
#   </div>

#   <!-- FRAMES (single-round viewer) -->
#   <div class="panel" id="panel-frames">
#     <div class="nav">
#       <div>
#         <b>Frames</b>
#         <span class="pill" id="framesRoundPill">Round 1 / {{ num_rounds }}</span>
#         <span class="pill" id="framesChoicePill"></span>
#       </div>

#       <div style="display:flex; gap:10px; flex-wrap:wrap;">
#         <button class="btn" id="prevFrameBtn">← Prev</button>
#         <button class="btn" id="nextFrameBtn">Next →</button>
#       </div>
#     </div>

#     <div class="card">
#       <div class="muted" id="framesOutcome"></div>
#       <div style="margin-top:10px;">
#         <a class="link" id="framesLink" href="#" target="_blank">
#           <img id="framesImg" src="" alt="frame_detection"/>
#         </a>
#         <div class="hint" style="margin-top:8px;">Keyboard: ← / → or A / D</div>
#       </div>
#     </div>
#   </div>

#   <!-- MASKS (single-round viewer) -->
#   <div class="panel" id="panel-masks">
#     <div class="nav">
#       <div>
#         <b>Masks</b>
#         <span class="pill" id="masksRoundPill">Round 1 / {{ num_rounds }}</span>
#         <span class="pill" id="masksChoicePill"></span>
#       </div>

#       <div style="display:flex; gap:10px; flex-wrap:wrap;">
#         <button class="btn" id="prevMaskBtn">← Prev</button>
#         <button class="btn" id="nextMaskBtn">Next →</button>
#       </div>
#     </div>

#     <div class="card">
#       <div class="muted" id="masksOutcome"></div>
#       <div class="two-col" style="margin-top:10px;">
#         <div>
#           <div class="hint">mask_all</div>
#           <a class="link" id="maskAllLink" href="#" target="_blank"><img id="maskAllImg" src="" alt="mask_all"/></a>
#         </div>
#         <div>
#           <div class="hint">mask_red</div>
#           <a class="link" id="maskRedLink" href="#" target="_blank"><img id="maskRedImg" src="" alt="mask_red"/></a>
#         </div>
#         <div>
#           <div class="hint">mask_blue</div>
#           <a class="link" id="maskBlueLink" href="#" target="_blank"><img id="maskBlueImg" src="" alt="mask_blue"/></a>
#         </div>
#       </div>
#       <div class="hint" style="margin-top:10px;">Keyboard: ← / → or A / D</div>
#     </div>
#   </div>

# <script>
#   // ---------- Data from server ----------
#   const PLAYERS = {{ players | tojson }};
#   const ROUNDS = {{ rounds | tojson }};
#   const NUM = ROUNDS.length;

#   // ---------- Tabs ----------
#   const buttons = document.querySelectorAll(".tab-btn");
#   const panels = {
#     score: document.getElementById("panel-score"),
#     frames: document.getElementById("panel-frames"),
#     masks: document.getElementById("panel-masks"),
#   };

#   let activeTab = "score";
#   function activate(tab) {
#     activeTab = tab;
#     buttons.forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
#     Object.entries(panels).forEach(([k, el]) => el.classList.toggle("active", k === tab));
#     // update view for the current tab
#     if (tab === "frames") renderFrames();
#     if (tab === "masks") renderMasks();
#   }
#   buttons.forEach(btn => btn.addEventListener("click", () => activate(btn.dataset.tab)));

#   // ---------- Round index state ----------
#   let idx = 0; // shared between frames and masks

#   function clampIndex() {
#     if (NUM <= 0) idx = 0;
#     if (idx < 0) idx = 0;
#     if (idx > NUM - 1) idx = NUM - 1;
#   }

#   function roundLabel() {
#     return `Round ${idx + 1} / ${NUM}`;
#   }

#   function choiceLabel(r) {
#     const p1 = PLAYERS[0], p2 = PLAYERS[1];
#     const c1 = (r.choices && r.choices[p1]) ? r.choices[p1] : "None";
#     const c2 = (r.choices && r.choices[p2]) ? r.choices[p2] : "None";
#     return `${p1}: ${c1}  |  ${p2}: ${c2}`;
#   }

#   function outcomeLabel(r) {
#     const p1 = PLAYERS[0], p2 = PLAYERS[1];
#     const o1 = (r.outcome && r.outcome[p1]) ? r.outcome[p1] : "-";
#     const o2 = (r.outcome && r.outcome[p2]) ? r.outcome[p2] : "-";
#     return `Outcome: ${p1}=${o1}, ${p2}=${o2}`;
#   }

#   function fileOrEmpty(r, key) {
#     if (!r.files) return "";
#     return r.files[key] || "";
#   }

#   // ---------- Render Frames ----------
#   const framesRoundPill = document.getElementById("framesRoundPill");
#   const framesChoicePill = document.getElementById("framesChoicePill");
#   const framesOutcome = document.getElementById("framesOutcome");
#   const framesImg = document.getElementById("framesImg");
#   const framesLink = document.getElementById("framesLink");

#   function renderFrames() {
#     if (NUM === 0) return;
#     clampIndex();
#     const r = ROUNDS[idx];

#     framesRoundPill.textContent = roundLabel();
#     framesChoicePill.textContent = choiceLabel(r);
#     framesOutcome.textContent = outcomeLabel(r);

#     const fp = fileOrEmpty(r, "frame_detection");
#     if (fp) {
#       framesImg.src = `/files/${fp}`;
#       framesLink.href = `/files/${fp}`;
#       framesImg.style.opacity = 1.0;
#     } else {
#       framesImg.src = "";
#       framesLink.href = "#";
#       framesImg.style.opacity = 0.25;
#     }
#   }

#   // ---------- Render Masks ----------
#   const masksRoundPill = document.getElementById("masksRoundPill");
#   const masksChoicePill = document.getElementById("masksChoicePill");
#   const masksOutcome = document.getElementById("masksOutcome");

#   const maskAllImg = document.getElementById("maskAllImg");
#   const maskRedImg = document.getElementById("maskRedImg");
#   const maskBlueImg = document.getElementById("maskBlueImg");

#   const maskAllLink = document.getElementById("maskAllLink");
#   const maskRedLink = document.getElementById("maskRedLink");
#   const maskBlueLink = document.getElementById("maskBlueLink");

#   function setImg(imgEl, linkEl, path) {
#     if (path) {
#       imgEl.src = `/files/${path}`;
#       linkEl.href = `/files/${path}`;
#       imgEl.style.opacity = 1.0;
#     } else {
#       imgEl.src = "";
#       linkEl.href = "#";
#       imgEl.style.opacity = 0.25;
#     }
#   }

#   function renderMasks() {
#     if (NUM === 0) return;
#     clampIndex();
#     const r = ROUNDS[idx];

#     masksRoundPill.textContent = roundLabel();
#     masksChoicePill.textContent = choiceLabel(r);
#     masksOutcome.textContent = outcomeLabel(r);

#     setImg(maskAllImg, maskAllLink, fileOrEmpty(r, "mask_all"));
#     setImg(maskRedImg, maskRedLink, fileOrEmpty(r, "mask_red"));
#     setImg(maskBlueImg, maskBlueLink, fileOrEmpty(r, "mask_blue"));
#   }

#   // ---------- Navigation controls ----------
#   function prev() {
#     idx -= 1;
#     clampIndex();
#     if (activeTab === "frames") renderFrames();
#     if (activeTab === "masks") renderMasks();
#   }

#   function next() {
#     idx += 1;
#     clampIndex();
#     if (activeTab === "frames") renderFrames();
#     if (activeTab === "masks") renderMasks();
#   }

#   document.getElementById("prevFrameBtn").addEventListener("click", prev);
#   document.getElementById("nextFrameBtn").addEventListener("click", next);
#   document.getElementById("prevMaskBtn").addEventListener("click", prev);
#   document.getElementById("nextMaskBtn").addEventListener("click", next);

#   // Keyboard: arrows + A/D
#   document.addEventListener("keydown", (e) => {
#     // Only handle on frames/masks tabs
#     if (activeTab !== "frames" && activeTab !== "masks") return;

#     if (e.key === "ArrowLeft" || e.key === "a" || e.key === "A") {
#       e.preventDefault();
#       prev();
#     } else if (e.key === "ArrowRight" || e.key === "d" || e.key === "D") {
#       e.preventDefault();
#       next();
#     } else if (e.key === "Home") {
#       idx = 0; clampIndex();
#       if (activeTab === "frames") renderFrames(); else renderMasks();
#     } else if (e.key === "End") {
#       idx = NUM - 1; clampIndex();
#       if (activeTab === "frames") renderFrames(); else renderMasks();
#     }
#   });

#   // Initial render
#   // Start in score tab; when user opens frames/masks, it renders.
#   // But if they refresh on frames, ensure correct state:
#   renderFrames();
#   renderMasks();
# </script>

# </body>
# </html>
# """
