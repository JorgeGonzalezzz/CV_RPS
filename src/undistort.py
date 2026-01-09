import cv2
import numpy as np

class Undistorter:
    def __init__(self, K: np.ndarray, dist: np.ndarray, alpha: float = 0.0, crop: bool = False):
        self.K = K
        self.dist = dist
        self.alpha = float(alpha)
        self.crop = bool(crop)

        self._ready = False
        self._map1 = None
        self._map2 = None
        self._roi = None

    @classmethod
    def from_npz(cls, npz_path: str, alpha: float = 0.0, crop: bool = False):
        data = np.load(npz_path)
        return cls(K=data["K"], dist=data["dist"], alpha=alpha, crop=crop)

    def _setup(self, frame_shape):
        h, w = frame_shape[:2]
        newK, roi = cv2.getOptimalNewCameraMatrix(self.K, self.dist, (w, h), self.alpha, (w, h))
        map1, map2 = cv2.initUndistortRectifyMap(
            self.K, self.dist, None, newK, (w, h), cv2.CV_16SC2
        )
        self._map1, self._map2, self._roi = map1, map2, roi
        self._ready = True

    def __call__(self, frame):
        if not self._ready:
            self._setup(frame.shape)

        und = cv2.remap(frame, self._map1, self._map2, interpolation=cv2.INTER_LINEAR)

        if self.crop and self._roi is not None:
            x, y, w, h = self._roi
            if w > 0 and h > 0:
                und = und[y:y+h, x:x+w]
        return und
