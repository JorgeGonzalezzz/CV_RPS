import cv2
import numpy as np
import math
from collections import deque, Counter



class GestureSmoother:
    def __init__(self, n=10):
        self.buf = deque(maxlen=n)

    def update(self, gesture: str) -> str:
        self.buf.append(gesture)
        return Counter(self.buf).most_common(1)[0][0]


class Tracker:
    """
    Multi-color hand tracker using:
      - HSV color segmentation (from config)
      - Kalman filter (4D: x,y,vx,vy) per color
      - RPS recognition using convex hull + convexity defects
      - Temporal smoothing (majority vote)

    Expected config format:
    config["colors"] = {
        "blue": {"lower":[...], "upper":[...]},
        "red":  {"lower":[...], "upper":[...]}
        # OR (useful for red):
        "red":  {"ranges":[ {"lower":[...],"upper":[...]}, {"lower":[...],"upper":[...]} ]}
    }
    """

    def __init__(
        self,
        config: dict,
        *,
        min_area_detect: int = 1500,
        min_area_contour_roi: int = 800,
        mask_kernel: int = 7,
        mask_iters: int = 1,
        roi_pad: int = 20,
        smoother_n: int = 10,
        kalman_dt: float = 1.0,
        kalman_q: float = 1e-2,
        kalman_r: float = 1e-1,
        defect_angle_deg: float = 90.0,
        defect_depth: float = 10.0,
    ):
        self.colors = config.get("colors", {})
        if not self.colors:
            raise ValueError("Tracker config must contain a non-empty 'colors' dict")

        self.min_area_detect = min_area_detect
        self.min_area_contour_roi = min_area_contour_roi
        self.mask_kernel = mask_kernel
        self.mask_iters = mask_iters
        self.roi_pad = roi_pad

        self.defect_angle_deg = defect_angle_deg
        self.defect_depth = defect_depth

        # Per-color state
        self.tracks = {}
        for name in self.colors.keys():
            self.tracks[name] = {
                "kf": self._build_kalman(dt=kalman_dt, q=kalman_q, r=kalman_r),
                "init": False,
                "last_size": (120, 120),  # fallback 
                "smoother": GestureSmoother(n=smoother_n),
            }

    # -------------------------
    # Public API
    # -------------------------
    def update(self, frame_bgr: np.ndarray, *, return_masks: bool = False) -> dict:
        """
        Update tracker for all configured colors.

        Returns:
        {
          "blue": {
             "detected": bool,
             "bbox": (x,y,w,h) or None,
             "center_meas": (cx,cy) or None,
             "center_pred": (cx,cy) or None,
             "gesture": "ROCK"/"PAPER"/"SCISSORS"/None,
          },
          "red": {...},
          ...
          "_masks": { "blue": mask, "red": mask, ... }   # if return_masks=True
        }
        """
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        results = {}
        masks_out = {}

        for color_name, color_cfg in self.colors.items():
            st = self.tracks[color_name]
            kf = st["kf"]

            bbox, center, mask = self._detect_bbox_and_center(hsv, color_cfg)
            if return_masks:
                masks_out[color_name] = mask

            pred = kf.predict()
            pred_center = (float(pred[0, 0]), float(pred[1, 0])) if st["init"] else None

            gesture = None

            if center is not None:
                # Init if needed
                if not st["init"]:
                    self._init_kalman(kf, center)
                    st["init"] = True

                # Correct
                meas = np.array([[center[0]], [center[1]]], dtype=np.float32)
                kf.correct(meas)

                # Update size
                st["last_size"] = (bbox[2], bbox[3])

                # Recognize gesture from ROI
                gesture = self._recognize_rps_from_bbox(frame_bgr, color_cfg, bbox)
                if gesture is not None:
                    gesture = st["smoother"].update(gesture)

                results[color_name] = {
                    "detected": True,
                    "bbox": bbox,
                    "center_meas": center,
                    "center_pred": pred_center,
                    "gesture": gesture,
                }
            else:
                results[color_name] = {
                    "detected": False,
                    "bbox": None,
                    "center_meas": None,
                    "center_pred": pred_center,
                    "gesture": None,
                }

        if return_masks:
            results["_masks"] = masks_out

        return results

    # -------------------------
    # Internal: Kalman
    # -------------------------
    def _build_kalman(self, dt=1.0, q=1e-2, r=1e-1) -> cv2.KalmanFilter:
        kf = cv2.KalmanFilter(4, 2)
        kf.measurementMatrix = np.array([[1, 0, 0, 0],
                                         [0, 1, 0, 0]], dtype=np.float32)
        kf.transitionMatrix = np.array([[1, 0, dt, 0],
                                        [0, 1, 0, dt],
                                        [0, 0, 1,  0],
                                        [0, 0, 0,  1]], dtype=np.float32)
        kf.processNoiseCov = np.eye(4, dtype=np.float32) * q
        kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * r
        kf.errorCovPost = np.eye(4, dtype=np.float32)
        return kf

    def _init_kalman(self, kf: cv2.KalmanFilter, center_xy):
        cx, cy = center_xy
        kf.statePost = np.array([[cx], [cy], [0], [0]], dtype=np.float32)
        kf.errorCovPost = np.eye(4, dtype=np.float32)

    # -------------------------
    # Internal: Mask + detection
    # -------------------------
    def _clean_mask(self, mask: np.ndarray) -> np.ndarray:
        kernel = np.ones((self.mask_kernel, self.mask_kernel), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=self.mask_iters)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=self.mask_iters)
        return mask

    def _get_color_mask(self, hsv: np.ndarray, color_cfg: dict) -> np.ndarray:
        if "ranges" in color_cfg:
            mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
            for rr in color_cfg["ranges"]:
                lower = np.array(rr["lower"], dtype=np.uint8)
                upper = np.array(rr["upper"], dtype=np.uint8)
                m = cv2.inRange(hsv, lower, upper)
                mask = cv2.bitwise_or(mask, m)
            return mask
        else:
            lower = np.array(color_cfg["lower"], dtype=np.uint8)
            upper = np.array(color_cfg["upper"], dtype=np.uint8)
            return cv2.inRange(hsv, lower, upper)

    def _detect_bbox_and_center(self, hsv: np.ndarray, color_cfg: dict):
        mask = self._get_color_mask(hsv, color_cfg)
        mask = self._clean_mask(mask)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, None, mask

        cnt = max(contours, key=cv2.contourArea)
        if cv2.contourArea(cnt) < self.min_area_detect:
            return None, None, mask

        x, y, w, h = cv2.boundingRect(cnt)
        cx = x + w / 2.0
        cy = y + h / 2.0
        return (x, y, w, h), (cx, cy), mask

    def _crop_roi(self, frame: np.ndarray, bbox, pad: int = None):
        if pad is None:
            pad = self.roi_pad

        H, W = frame.shape[:2]
        x, y, w, h = bbox
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(W, x + w + pad)
        y2 = min(H, y + h + pad)
        return frame[y1:y2, x1:x2], (x1, y1)

    # -------------------------
    # Internal: RPS recognition
    # -------------------------
    def _largest_contour(self, mask: np.ndarray):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        cnt = max(contours, key=cv2.contourArea)
        return cnt if cv2.contourArea(cnt) >= self.min_area_contour_roi else None

    def _count_fingers(self, contour: np.ndarray) -> int:
        hull_idx = cv2.convexHull(contour, returnPoints=False)
        if hull_idx is None or len(hull_idx) < 3:
            return 0

        defects = cv2.convexityDefects(contour, hull_idx)
        if defects is None:
            return 0

        gaps = 0
        for s, e, f, d in defects[:, 0]:
            start = contour[s][0]
            end   = contour[e][0]
            far   = contour[f][0]

            a = np.linalg.norm(end - start)
            b = np.linalg.norm(far - start)
            c = np.linalg.norm(end - far)
            if b * c == 0:
                continue

            angle = math.degrees(math.acos((b*b + c*c - a*a) / (2*b*c)))
            depth = d / 256.0

            if angle < self.defect_angle_deg and depth > self.defect_depth:
                gaps += 1

        fingers = gaps + 1 if gaps > 0 else 0
        return min(fingers, 5)

    def _fingers_to_rps(self, fingers: int) -> str:
        if fingers <= 1:
            return "ROCK"
        elif fingers == 2:
            return "SCISSORS"
        else:
            return "PAPER"

    def _recognize_rps_from_bbox(self, frame_bgr: np.ndarray, color_cfg: dict, bbox):
        roi, _ = self._crop_roi(frame_bgr, bbox, pad=self.roi_pad)
        if roi.size == 0:
            return None

        roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        roi_mask = self._get_color_mask(roi_hsv, color_cfg)
        roi_mask = self._clean_mask(roi_mask)

        cnt = self._largest_contour(roi_mask)
        if cnt is None:
            return None

        fingers = self._count_fingers(cnt)
        return self._fingers_to_rps(fingers)


class TrackerVisualizer:
    def draw(self, frame, results):
        H, W = frame.shape[:2]

        lost_labels = []

        # PREDICTIONS 
        for color_name, info in results.items():
            if color_name == "_masks":
                continue

            pred = info.get("center_pred")
            if pred is not None:
                px, py = pred
                cv2.circle(frame, (int(px), int(py)), 5, (0, 0, 255), -1)

            if info.get("detected", False) and info.get("bbox") is not None:
                x, y, w, h = info["bbox"]
                cx, cy = info["center_meas"]

                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.circle(frame, (int(cx), int(cy)), 5, (0, 255, 0), -1)

                gesture = info.get("gesture")
                label = f"{color_name.upper()} {gesture}" if gesture else f"{color_name.upper()}"
                cv2.putText(
                    frame, label, (x, max(20, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
                )
            else:
                lost_labels.append(f"{color_name.upper()} HIDDEN")

        # LOST 
        x_margin = 20
        y0 = 30
        dy = 30

        for i, text in enumerate(lost_labels):
            y = y0 + i * dy

            # calcular ancho del texto para alinear a la derecha
            (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            x = max(0, W - x_margin - tw)

            cv2.putText(
                frame, text, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
            )

        return frame
