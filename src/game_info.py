import os
import json
import cv2
from dataclasses import dataclass
from typing import Dict, Optional, List
import numpy as np


@dataclass
class RoundRecord:
    round_id: int
    choices: Dict[str, Optional[str]]
    outcome: Dict[str, str]
    score: Dict[str, int]
    frames: Dict[str, Optional[np.ndarray]]


class GameInformation:
    def __init__(self, players: List[str]):
        if len(players) < 2:
            raise ValueError("GameInformation expects at least 2 players")
        self.players = players[:2]
        self.round_id = 0
        self.history: List[RoundRecord] = []

        p1, p2 = self.players
        self.score = {p1: 0, p2: 0, "draws": 0, "nulls": 0}

    # ----------------------------
    # Game logic helpers
    # ----------------------------
    @staticmethod
    def winner_rps(g1: Optional[str], g2: Optional[str]) -> str:
        if g1 is None or g2 is None:
            return "null"
        if g1 == g2:
            return "draw"

        beats = {"ROCK": "SCISSORS", "SCISSORS": "PAPER", "PAPER": "ROCK"}
        return "p1" if beats.get(g1) == g2 else "p2"

    @staticmethod
    def combine_masks(masks_dict: Dict[str, np.ndarray]) -> Optional[np.ndarray]:
        combined = None
        for m in masks_dict.values():
            if m is None:
                continue
            combined = m.copy() if combined is None else cv2.bitwise_or(combined, m)
        return combined

    def add_round(
        self,
        choices: Dict[str, Optional[str]],
        masks: Dict[str, Optional[np.ndarray]],
        frame_detection: Optional[np.ndarray],
    ) -> RoundRecord:
        p1, p2 = self.players
        g1, g2 = choices.get(p1), choices.get(p2)

        w = self.winner_rps(g1, g2)

        if w == "p1":
            self.score[p1] += 1
            outcome = {p1: "winner", p2: "loser"}
        elif w == "p2":
            self.score[p2] += 1
            outcome = {p1: "loser", p2: "winner"}
        elif w == "draw":
            self.score["draws"] += 1
            outcome = {p1: "draw", p2: "draw"}
        else:
            self.score["nulls"] += 1
            outcome = {p1: "null", p2: "null"}

        self.round_id += 1

        record = RoundRecord(
            round_id=self.round_id,
            choices={p1: g1, p2: g2},
            outcome=outcome,
            score=dict(self.score),
            frames={
                "frame_detection": None if frame_detection is None else frame_detection.copy(),
                "mask_all": self.combine_masks({k: v for k, v in masks.items() if v is not None}) if masks else None,
                "mask_red": masks.get("red") if masks else None,
                "mask_blue": masks.get("blue") if masks else None,
            },
        )

        self.history.append(record)
        return record

    # ----------------------------
    # Export
    # ----------------------------
    @staticmethod
    def _safe_imwrite(path: str, img: Optional[np.ndarray]) -> bool:
        if img is None:
            return False
        try:
            # masks are often 1-channel, frame is 3-channel -> both ok for imwrite
            return cv2.imwrite(path, img)
        except Exception:
            return False

    def export(self, out_dir: str) -> str:
        """
        Export the whole match to disk.

        out_dir/
          summary.json
          round_001/
            frame_detection.png
            mask_all.png
            mask_red.png
            mask_blue.png
          round_002/
            ...

        Returns out_dir.
        """
        os.makedirs(out_dir, exist_ok=True)

        rounds_manifest = []
        for rec in self.history:
            rid = rec.round_id
            rdir = os.path.join(out_dir, f"round_{rid:03d}")
            os.makedirs(rdir, exist_ok=True)

            files = {}

            # Save detection frame
            p = os.path.join(rdir, "frame_detection.png")
            if self._safe_imwrite(p, rec.frames.get("frame_detection")):
                files["frame_detection"] = f"round_{rid:03d}/frame_detection.png"

            # Save masks
            p = os.path.join(rdir, "mask_all.png")
            if self._safe_imwrite(p, rec.frames.get("mask_all")):
                files["mask_all"] = f"round_{rid:03d}/mask_all.png"

            p = os.path.join(rdir, "mask_red.png")
            if self._safe_imwrite(p, rec.frames.get("mask_red")):
                files["mask_red"] = f"round_{rid:03d}/mask_red.png"

            p = os.path.join(rdir, "mask_blue.png")
            if self._safe_imwrite(p, rec.frames.get("mask_blue")):
                files["mask_blue"] = f"round_{rid:03d}/mask_blue.png"

            rounds_manifest.append({
                "round": rid,
                "choices": rec.choices,
                "outcome": rec.outcome,
                "score_after_round": rec.score,
                "files": files
            })

        summary = {
            "players": self.players,
            "final_score": dict(self.score),
            "num_rounds": len(self.history),
            "rounds": rounds_manifest,
        }

        with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return out_dir
