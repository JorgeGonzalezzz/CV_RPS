from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any

Gesture = Optional[str]
Pair = Tuple[Gesture, Gesture]


@dataclass
class PasswordConfig:
    # sequence of expected pairs, in order
    steps: List[Tuple[str, str]] = field(default_factory=list)

    # confirm gesture (also used to ARM/start the lock)
    confirm_pair: Tuple[str, str] = ("ROCK", "ROCK")

    # stabilization
    stable_required_frames: int = 14          # frames needed to accept a selection/confirm
    settle_frames_after_step: int = 12        # cooldown frames after transitions
    timeout_s: float = 12.0                   # (optional, if you want to enforce timeout externally)

    # UX
    wrong_flash_frames: int = 45              # how long "PASSWORD WRONG" stays on screen


class PasswordLock:
    """
    Flow (per step):
      ARM:        require confirm_pair stable -> go SELECT (step 1)
      SELECT:     require ANY stable pair (both present, not confirm_pair) -> store as selected -> go CONFIRM
      CONFIRM:    require confirm_pair stable -> if selected == expected -> step++ -> go SELECT
                                            -> else WRONG -> reset to ARM (step=0) + flash "PASSWORD WRONG"
      DONE: unlocked
    """

    def __init__(self, players: List[str], cfg: PasswordConfig):
        if len(players) < 2:
            raise ValueError("PasswordLock expects at least 2 players.")
        self.p1, self.p2 = players[0], players[1]
        self.cfg = cfg

        # transient UI state
        self._flash_wrong = 0
        self._last_wrong_selected: Optional[Tuple[str, str]] = None
        self._last_wrong_expected: Optional[Tuple[str, str]] = None

        self.reset()

    def reset(self):
        self.state = "ARM"          # ARM -> SELECT -> CONFIRM -> DONE
        self.step_idx = 0
        self.selected_step: Optional[Tuple[str, str]] = None

        self._streak = 0
        self._cooldown = 0

        self.last_pair: Pair = (None, None)
        self.last_event: Optional[str] = None  # "armed", "selected", "confirmed", "wrong", "unlocked"

    # -------------------------
    # Helpers
    # -------------------------
    def _norm_g(self, g: Any) -> Optional[str]:
        if g is None:
            return None
        if isinstance(g, str):
            s = g.strip().upper()
            return s if s else None
        return None

    def _current_pair(self, results: Dict[str, Any]) -> Pair:
        i1 = results.get(self.p1, {}) if results else {}
        i2 = results.get(self.p2, {}) if results else {}

        d1 = bool(i1.get("detected", False))
        d2 = bool(i2.get("detected", False))

        g1 = self._norm_g(i1.get("gesture")) if d1 else None
        g2 = self._norm_g(i2.get("gesture")) if d2 else None
        return (g1, g2)

    def _pair_eq(self, a: Pair, b: Tuple[str, str]) -> bool:
        return (a[0] == b[0]) and (a[1] == b[1])

    def _both_present(self, a: Pair) -> bool:
        return (a[0] is not None) and (a[1] is not None)

    def _bump_or_reset(self, condition: bool):
        self._streak = self._streak + 1 if condition else 0

    def _set_cooldown(self):
        self._cooldown = max(0, int(self.cfg.settle_frames_after_step))

    def _wrong_and_reset(self, selected: Optional[Tuple[str, str]], expected: Optional[Tuple[str, str]]):
        self._last_wrong_selected = selected
        self._last_wrong_expected = expected
        self._flash_wrong = int(self.cfg.wrong_flash_frames)
        self.reset()
        self.last_event = "wrong"
        self._set_cooldown()

    # -------------------------
    # Public API
    # -------------------------
    def update(self, results: Dict[str, Any]) -> bool:
        """
        Call once per frame.
        Returns True when unlocked (DONE).
        """
        self.last_event = None

        # decrement wrong flash
        if self._flash_wrong > 0:
            self._flash_wrong -= 1

        # cooldown between transitions (keeps it stable / prevents accidental double-triggers)
        if self._cooldown > 0:
            self._cooldown -= 1
            self.last_pair = self._current_pair(results)
            return self.state == "DONE"

        pair = self._current_pair(results)
        self.last_pair = pair

        if self.state == "DONE":
            return True

        has_steps = len(self.cfg.steps) > 0

        # -------------------------
        # ARM: need confirm_pair stable to start
        # -------------------------
        if self.state == "ARM":
            want = self.cfg.confirm_pair
            self._bump_or_reset(self._pair_eq(pair, want))

            if self._streak >= self.cfg.stable_required_frames:
                self._streak = 0
                if has_steps:
                    self.state = "SELECT"
                    self.last_event = "armed"
                    self._set_cooldown()
                else:
                    self.state = "DONE"
                    self.last_event = "unlocked"
                    return True
            return False

        # -------------------------
        # SELECT: accept ANY stable pair (both present) except confirm_pair
        # -------------------------
        if self.state == "SELECT":
            if self.step_idx >= len(self.cfg.steps):
                self.state = "DONE"
                self.last_event = "unlocked"
                return True

            selectable = self._both_present(pair) and (not self._pair_eq(pair, self.cfg.confirm_pair))
            self._bump_or_reset(selectable)

            if self._streak >= self.cfg.stable_required_frames:
                self._streak = 0
                self.selected_step = (pair[0], pair[1])
                self.state = "CONFIRM"
                self.last_event = "selected"
                self._set_cooldown()
            return False

        # -------------------------
        # CONFIRM: require confirm_pair stable; then verify selection vs expected
        # wrong + confirmed => RESET to ARM (start)
        # -------------------------
        if self.state == "CONFIRM":
            want = self.cfg.confirm_pair
            self._bump_or_reset(self._pair_eq(pair, want))

            if self._streak >= self.cfg.stable_required_frames:
                self._streak = 0

                expected = self.cfg.steps[self.step_idx] if self.step_idx < len(self.cfg.steps) else None
                chosen = self.selected_step

                if expected is None or chosen is None:
                    self._wrong_and_reset(chosen, expected)
                    return False

                if chosen == expected:
                    # ✅ step confirmed correct
                    self.selected_step = None
                    self.step_idx += 1
                    self.last_event = "confirmed"
                    self._set_cooldown()

                    if self.step_idx >= len(self.cfg.steps):
                        self.state = "DONE"
                        self.last_event = "unlocked"
                        return True

                    self.state = "SELECT"
                    return False

                # ❌ wrong but confirmed -> reset to start
                self._wrong_and_reset(chosen, expected)
                return False

            return False

        return False

    # -------------------------
    # UI text (clean)
    # -------------------------
    def status_text(self) -> str:
        # flash wrong message on top
        if self._flash_wrong > 0:
            return "PASSWORD WRONG"

        total = len(self.cfg.steps)
        step_num = min(self.step_idx + 1, max(total, 1))

        if self.state == "ARM":
            a, b = self.cfg.confirm_pair
            return f"LOCK | SHOW {a}+{b} TO START ({self._streak}/{self.cfg.stable_required_frames})"

        if self.state == "SELECT":
            # 🔒 expected is NOT shown (secret password)
            return (
                f"LOCK | STEP {step_num}/{total} | "
                f"SELECT GESTURE ({self._streak}/{self.cfg.stable_required_frames})"
            )

        if self.state == "CONFIRM":
            sel = self.selected_step if self.selected_step else ("?", "?")
            ca, cb = self.cfg.confirm_pair
            return (
                f"LOCK | STEP {step_num}/{total} | "
                f"SELECTED {sel[0]}+{sel[1]} | "
                f"CONFIRM {ca}+{cb} ({self._streak}/{self.cfg.stable_required_frames})"
            )

        if self.state == "DONE":
            return "LOCK | UNLOCKED"

        return "LOCK"

