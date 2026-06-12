import cv2
import mss
import numpy as np


class ScopeMotionTracker:
    """Track relative motion of the scope's top inner edge for SR breath control."""

    def __init__(self, screen_width, screen_height, region_manager=None, config=None, region_name=None):
        self.sw = screen_width
        self.sh = screen_height
        self.region_manager = region_manager
        self.config = config or {}
        self.region_name = region_name or "scope_top_edge_4x_region"
        self.monitor = self._default_region()
        self._load_region_from_manager()

        self.black_threshold = int(self.config.get("black_threshold", 70))
        self.min_bright_ratio = float(self.config.get("min_bright_ratio", 0.35))
        self.min_gradient = float(self.config.get("min_gradient", 0.12))
        self.max_edge_jump = float(self.config.get("max_edge_jump", 45.0))
        self.min_points = int(self.config.get("min_points", 8))
        self.last_edge_y = None
        self.last_confidence = 0.0

    def _default_region(self):
        width = max(24, int(round(self.sw * 0.025)))
        height = max(80, int(round(self.sh * 0.33)))
        return {
            "left": int(round(self.sw / 2 - width / 2)),
            "top": int(round(self.sh * 0.05)),
            "width": width,
            "height": height,
        }

    def _load_region_from_manager(self):
        if not self.region_manager:
            return
        try:
            region = self.region_manager.get_real_region(self.region_name)
            if region and region.get("width", 0) > 0 and region.get("height", 0) > 0:
                self.monitor = region
                print(f"[ScopeMotion] loaded {self.region_name}: {self.monitor}")
        except Exception as e:
            print(f"[ScopeMotion] failed to load {self.region_name}: {e}")

    def set_region_name(self, region_name):
        if region_name == self.region_name:
            return
        self.region_name = region_name
        self.monitor = self._default_region()
        self._load_region_from_manager()
        self.reset()

    def reset(self):
        self.last_edge_y = None
        self.last_confidence = 0.0

    def detect_motion(self, sct=None):
        owns_sct = sct is None
        if owns_sct:
            sct = mss.mss()
        try:
            screenshot = sct.grab(self.monitor)
            frame = np.asarray(screenshot)
            edge_y, confidence, found = self._detect_top_edge(frame)
            if not found:
                self.last_confidence = 0.0
                return 0.0, confidence, False

            if self.last_edge_y is None:
                self.last_edge_y = edge_y
                self.last_confidence = confidence
                return 0.0, confidence, True

            dy = edge_y - self.last_edge_y
            if abs(dy) > self.max_edge_jump:
                self.last_edge_y = edge_y
                self.last_confidence = 0.0
                return 0.0, 0.0, False

            self.last_edge_y = edge_y
            self.last_confidence = confidence
            return dy, confidence, True
        finally:
            if owns_sct:
                try:
                    sct.close()
                except Exception:
                    pass

    def _detect_top_edge(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        h, w = gray.shape
        if h < 12 or w < 6:
            return 0.0, 0.0, False

        col_edges = []
        col_scores = []
        for x in range(w):
            column = gray[:, x].astype(np.float32)
            smooth = cv2.GaussianBlur(column.reshape(-1, 1), (1, 9), 0).ravel()
            bright = (smooth > self.black_threshold).astype(np.float32)
            bright_ratio = cv2.GaussianBlur(bright.reshape(-1, 1), (1, 11), 0).ravel()
            grad = np.diff(bright_ratio)

            candidates = np.where((grad >= self.min_gradient) & (bright_ratio[1:] >= self.min_bright_ratio))[0]
            if candidates.size == 0:
                continue
            y = int(candidates[0] + 1)
            if y < 2 or y > h - 3:
                continue
            col_edges.append((x, float(y)))
            col_scores.append(float(grad[candidates[0]]))

        if len(col_edges) < self.min_points:
            return 0.0, 0.0, False

        points = np.array(col_edges, dtype=np.float32)
        median_y = float(np.median(points[:, 1]))
        mad = float(np.median(np.abs(points[:, 1] - median_y))) or 1.0
        keep = np.abs(points[:, 1] - median_y) <= max(6.0, 3.5 * mad)
        inliers = points[keep]
        if len(inliers) < self.min_points:
            return 0.0, 0.0, False

        center_x = (w - 1) / 2.0
        try:
            if len(inliers) >= 12 and np.ptp(inliers[:, 0]) >= 6:
                coeff = np.polyfit(inliers[:, 0], inliers[:, 1], 2)
                edge_y_local = float(np.polyval(coeff, center_x))
            else:
                edge_y_local = float(np.median(inliers[:, 1]))
        except Exception:
            edge_y_local = float(np.median(inliers[:, 1]))

        if edge_y_local < 0 or edge_y_local >= h:
            return 0.0, 0.0, False

        inlier_ratio = len(inliers) / max(1, w)
        score = float(np.mean(col_scores)) if col_scores else 0.0
        confidence = max(0.0, min(1.0, inlier_ratio * 1.5 + score))
        return self.monitor["top"] + edge_y_local, confidence, confidence >= 0.25
