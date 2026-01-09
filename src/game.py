# src/game.py
import time
import cv2
import os
from datetime import datetime
from typing import Optional, Union

from src.voice import Voice
from src.game_info import GameInformation
from src.password_lock import PasswordLock, PasswordConfig

# Dashboard opcional (para que no reviente si el dashboard falla/importa mal)
try:
    from src.dashboard import ResultsDashboard
    _DASH_AVAILABLE = True
except Exception as e:
    ResultsDashboard = None
    _DASH_AVAILABLE = False
    print("Dashboard not available:", e)


class Game:
    def __init__(
        self,
        config: dict,
        tracker_cls,
        visualizer_cls,

        # Camera
        camera_source: Optional[Union[int, str]] = None,  # ✅ int (0) o URL
        camera_index: int = 0,
        use_dshow: bool = True,

        # RPS game params
        hide_required_frames: int = 20,
        stable_required_frames: int = 24,
        post_shoot_timeout_s: float = 10.0,
        countdown_step_s: float = 0.55,
        fps_smooth_every: int = 10,
        enable_voice: bool = True,

        # Export
        save_results: bool = True,
        results_root: str = "results",

        # Password
        password_enabled: bool = True,

        # ✅ NEW: Undistort (calibration)
        calibration_npz: Optional[str] = None,   # e.g. "calibration_phone.npz"
        undistort_alpha: float = 0.0,            # 0.0 recorta más, 1.0 conserva más FOV
        undistort_crop: bool = False,            # recomiendo False para no cambiar tamaño
    ):
        self.config = config
        self.colors = list(config.get("colors", {}).keys())
        if len(self.colors) < 2:
            raise ValueError("Game expects at least 2 colors/players in config['colors'].")

        self.tracker = tracker_cls(config)
        self.viz = visualizer_cls()

        # ============================
        # ✅ VideoCapture: local o URL
        # ============================
        if camera_source is None:
            camera_source = camera_index

        if isinstance(camera_source, int):
            api = cv2.CAP_DSHOW if use_dshow else 0
            self.cap = cv2.VideoCapture(camera_source, api)
        else:
            # URL (IP cam). CAP_FFMPEG suele ir mejor si está disponible
            self.cap = cv2.VideoCapture(camera_source, cv2.CAP_FFMPEG)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(camera_source)

        if not self.cap.isOpened():
            raise RuntimeError(f"Could not access the camera/stream: {camera_source}")

        # Opcional: reduce latencia (depende backend)
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        self.camera_source = camera_source

        # ============================
        # ✅ Undistort (optional)
        # ============================
        self.undistorter = None
        if calibration_npz is not None:
            try:
                from src.undistort import Undistorter
                self.undistorter = Undistorter.from_npz(
                    calibration_npz,
                    alpha=undistort_alpha,
                    crop=undistort_crop
                )
                print(f"Undistort ENABLED using: {calibration_npz} (alpha={undistort_alpha}, crop={undistort_crop})")
            except Exception as e:
                self.undistorter = None
                print(f"[WARN] Could not load/apply undistort calibration ({calibration_npz}): {e}")

        # Game params
        self.hide_required_frames = hide_required_frames
        self.stable_required_frames = stable_required_frames
        self.post_shoot_timeout_s = post_shoot_timeout_s
        self.countdown_step_s = countdown_step_s
        self.fps_smooth_every = fps_smooth_every

        self._show_masks = False
        self._fps = 0.0
        self._t0 = time.time()
        self._frames_count = 0

        self.voice = Voice(enabled=enable_voice, rate=170)

        # Game memory (rounds, score, snapshots)
        self.info = GameInformation(players=self.colors[:2])

        # HUD layout
        self._hud_status_y = 40
        self._hud_score_y = 100

        # Export config
        self.save_results = save_results
        self.results_root = results_root
        self._export_out_dir: Optional[str] = None

        # PASSWORD CONFIG
        self.password_enabled = password_enabled
        self.password_cfg = PasswordConfig(
            steps=[
                ("ROCK", "SCISSORS"),
                ("SCISSORS", "ROCK"),
                ("PAPER", "PAPER"), 
                ("SCISSORS", "SCISSORS"),
            ],
            confirm_pair=("ROCK", "ROCK"),
            stable_required_frames=14,
            settle_frames_after_step=12,
            timeout_s=12.0,
        )
        self.password = PasswordLock(self.info.players, self.password_cfg)

    # ----------------------------
    # HUD helpers
    # ----------------------------
    def _put_text_centered(self, frame, text, y, scale=0.75, thickness=2):
        H, W = frame.shape[:2]
        (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
        x = max(0, (W - tw) // 2)
        cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), thickness)

    def _draw_scoreboard(self, frame, y):
        p1, p2 = self.info.players
        s = self.info.score
        text = (
            f"{p1.upper()} W:{s.get(p1, 0)}   "
            f"{p2.upper()} W:{s.get(p2, 0)}   "
            f"DRAWS:{s.get('draws', 0)}   "
            f"NULL:{s.get('nulls', 0)}"
        )
        self._put_text_centered(frame, text, y=y, scale=0.75, thickness=2)

    # ----------------------------
    # Public
    cv2.namedWindow("Game", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Game", 1280, 720) 
    # ----------------------------
    def run(self):
        print("Game started. Keys: [q]=quit | [m]=toggle masks")
        try:
            # PASSWORD FIRST
            if self.password_enabled:
                ok = self._unlock_password()
                if not ok:
                    return

            # GAME LOOP
            while True:
                result = self.round()
                if result is None:
                    break

                p1, p2 = self.info.players
                print(f"ROUND RESULT -> {p1.upper()}: {result.get(p1)} | {p2.upper()}: {result.get(p2)}")
                print(f"SCORE -> {self.info.score}")

        finally:
            self._release()

    def round(self):
        self.voice.say("Hide your hands")
        if not self._wait_hands_hidden():
            return None

        if not self._countdown_rps():
            return None

        return self._wait_stable_gestures(timeout_s=self.post_shoot_timeout_s)

    # ----------------------------
    # PASSWORD PHASE
    # ----------------------------
    def _unlock_password(self) -> bool:
        self.password.reset()
        self.voice.say("Show rock rock to confirm password")

        while True:
            frame, results, key = self._read_and_render(overlay_text=self.password.status_text())
            if frame is None or results is None:
                return False
            if key == ord("q"):
                return False

            ok = self.password.update(results)

            if self.password.last_event == "armed":
                self.voice.say("Password armed")
            elif self.password.last_event == "selected":
                self.voice.say("Selected")
            elif self.password.last_event == "confirmed":
                self.voice.say("Confirmed")
            elif self.password.last_event == "wrong":
                self.voice.say("PASSWORD WRONG")
                t0 = time.time()
                while time.time() - t0 < 0.9:
                    if self._ui_tick(overlay_text=self.password.status_text()) is False:
                        return False
            elif self.password.last_event == "unlocked":
                self.voice.say("Password accepted")

            if ok:
                t0 = time.time()
                while time.time() - t0 < 0.7:
                    if self._ui_tick(overlay_text="PASSWORD OK") is False:
                        return False
                return True

    # ----------------------------
    # Internal: read + render
    # ----------------------------
    def _read_and_render(self, overlay_text=None):
        ret, frame = self.cap.read()
        if not ret or frame is None:
            return None, None, None

        # ✅ Apply undistort BEFORE tracker (if enabled)
        if self.undistorter is not None:
            try:
                frame = self.undistorter(frame)
            except Exception as e:
                print(f"[WARN] Undistort failed on frame: {e}")

        results = self.tracker.update(frame, return_masks=self._show_masks)

        # FPS smoothing
        self._frames_count += 1
        if self._frames_count % self.fps_smooth_every == 0:
            t1 = time.time()
            self._fps = self.fps_smooth_every / max(1e-6, (t1 - self._t0))
            self._t0 = t1

        frame = self.viz.draw(frame, results)

        # Status line (top-left)
        if overlay_text:
            cv2.putText(frame, overlay_text, (20, self._hud_status_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Scoreboard (top centered)
        self._draw_scoreboard(frame, y=self._hud_score_y)

        # FPS bottom-left
        cv2.putText(frame, f"FPS: {self._fps:.1f}", (20, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        try:
            _, _, w, h = cv2.getWindowImageRect("Game")
            frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)
        except Exception:
            pass

        cv2.imshow("Game", frame)

        # Mask windows (optional)
        if self._show_masks and "_masks" in results:
            for cname, m in results["_masks"].items():
                cv2.imshow(f"mask_{cname}", m)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("m"):
            self._toggle_masks(results)

        self.voice.tick()
        return frame, results, key

    def _ui_tick(self, overlay_text=None):
        frame, results, key = self._read_and_render(overlay_text=overlay_text)
        if frame is None or results is None:
            return False
        if key == ord("q"):
            return False
        return True

    # ----------------------------
    # Phase 1: hide hands
    # ----------------------------
    def _wait_hands_hidden(self):
        hidden_streak = 0
        p1, p2 = self.info.players

        while True:
            frame, results, key = self._read_and_render(
                overlay_text=f"Hide hands. {hidden_streak}/{self.hide_required_frames}"
            )
            if frame is None or results is None:
                return False
            if key == ord("q"):
                return False

            both_hidden = (
                (not results.get(p1, {}).get("detected", False)) and
                (not results.get(p2, {}).get("detected", False))
            )

            hidden_streak = hidden_streak + 1 if both_hidden else 0
            if hidden_streak >= self.hide_required_frames:
                return True

    # ----------------------------
    # Phase 2: countdown
    # ----------------------------
    def _countdown_rps(self):
        words = ["Rock", "Paper", "Scissors", "Shoot!"]
        for w in words:
            self.voice.say(w)

            ok = self.voice.wait_done(
                game_tick_fn=lambda: self._ui_tick(overlay_text=w.upper()),
                timeout_s=3.5
            )
            if ok is False:
                return False

            t0 = time.time()
            while time.time() - t0 < self.countdown_step_s:
                if self._ui_tick(overlay_text=w.upper()) is False:
                    return False
        return True

    # ----------------------------
    # Snapshot (frames + masks)
    # ----------------------------
    def _snapshot_with_masks(self, overlay_text="SHOT"):
        ret, frame = self.cap.read()
        if not ret or frame is None:
            return None, None

        # ✅ Apply undistort here too (export matches tracker space)
        if self.undistorter is not None:
            try:
                frame = self.undistorter(frame)
            except Exception as e:
                print(f"[WARN] Undistort failed on snapshot: {e}")

        results = self.tracker.update(frame, return_masks=True)

        frame_det = frame.copy()
        frame_det = self.viz.draw(frame_det, results)

        if overlay_text:
            cv2.putText(frame_det, overlay_text, (20, self._hud_status_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            self._draw_scoreboard(frame_det, y=self._hud_score_y)

        masks = results.get("_masks", {})
        return frame_det, masks

    # ----------------------------
    # Phase 3: stable gestures + SAVE ROUND
    # ----------------------------
    def _wait_stable_gestures(self, timeout_s=4.0):
        p1, p2 = self.info.players
        last_g1, last_g2 = None, None
        streak1, streak2 = 0, 0
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout_s:
                choices = {p1: last_g1, p2: last_g2}
                frame_det, masks = self._snapshot_with_masks(overlay_text="TIMEOUT")

                record = self.info.add_round(
                    choices=choices,
                    masks=masks if masks is not None else {},
                    frame_detection=frame_det
                )
                print(f"[ROUND {record.round_id}] TIMEOUT choices={record.choices} outcome={record.outcome} score={record.score}")
                return choices

            overlay = (
                f"Stabilizing. {p1}:{streak1}/{self.stable_required_frames} "
                f"{p2}:{streak2}/{self.stable_required_frames}"
            )

            frame, results, key = self._read_and_render(overlay_text=overlay)
            if frame is None or results is None:
                return None
            if key == ord("q"):
                return None

            info1 = results.get(p1, {})
            info2 = results.get(p2, {})
            d1, g1 = info1.get("detected", False), info1.get("gesture")
            d2, g2 = info2.get("detected", False), info2.get("gesture")

            if d1 and g1 is not None and g1 == last_g1:
                streak1 += 1
            else:
                streak1 = 1 if (d1 and g1 is not None) else 0
                last_g1 = g1 if (d1 and g1 is not None) else None

            if d2 and g2 is not None and g2 == last_g2:
                streak2 += 1
            else:
                streak2 = 1 if (d2 and g2 is not None) else 0
                last_g2 = g2 if (d2 and g2 is not None) else None

            if streak1 >= self.stable_required_frames and streak2 >= self.stable_required_frames:
                choices = {p1: last_g1, p2: last_g2}
                frame_det, masks = self._snapshot_with_masks(overlay_text="SHOT")

                record = self.info.add_round(
                    choices=choices,
                    masks=masks if masks is not None else {},
                    frame_detection=frame_det
                )
                print(f"[ROUND {record.round_id}] choices={record.choices} outcome={record.outcome} score={record.score}")
                return choices

    # ----------------------------
    # Utilities
    # ----------------------------
    def _toggle_masks(self, results):
        self._show_masks = not self._show_masks
        if not self._show_masks and results and "_masks" in results:
            for cname in results["_masks"].keys():
                try:
                    cv2.destroyWindow(f"mask_{cname}")
                except cv2.error:
                    pass

    def _release(self):
        # close voice/cam/windows
        try:
            self.voice.close()
        except Exception:
            pass
        try:
            self.cap.release()
        except Exception:
            pass
        cv2.destroyAllWindows()

        # export
        if self.save_results:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = os.path.join(self.results_root, ts)
            self._export_out_dir = out_dir
            try:
                os.makedirs(out_dir, exist_ok=True)
                self.info.export(out_dir)
                print(f"Results saved to: {out_dir}")
            except Exception as e:
                print(f"Could not save results: {e}")
                out_dir = None

            # launch dashboard (non-blocking)
            if out_dir and _DASH_AVAILABLE:
                try:
                    ResultsDashboard(out_dir, open_browser=True).run(blocking=True)
                except Exception as e:
                    print(f"[WARN] Could not open dashboard: {e}")

        print("Done")
