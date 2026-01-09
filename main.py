# main.py
import json
from pathlib import Path

from src.game import Game
from src.tracker import Tracker
from src.tracker import TrackerVisualizer 


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    root = Path(__file__).resolve().parent

    config_path = root / "configs" / "test_set_3.json"
    calib_path = root / "configs" / "calibration_phone.npz"
    config = load_json(config_path)

    IP_CAM_URL = "http://172.20.10.5:8080/video"

    game = Game(
        config=config,
        tracker_cls=Tracker,
        visualizer_cls=TrackerVisualizer,

        camera_index=0,
        hide_required_frames=20,
        stable_required_frames=24,
        post_shoot_timeout_s=10.0,
        countdown_step_s=0.55,
        fps_smooth_every=10,
        enable_voice=True,

        camera_source=IP_CAM_URL,   
        use_dshow=False,
        calibration_npz=str(calib_path),
        undistort_alpha=0.0,
        undistort_crop=False,
        
        # export
        save_results=True,            
        results_root="results",

        password_enabled=True
    )

    game.run()


if __name__ == "__main__":
    main()
