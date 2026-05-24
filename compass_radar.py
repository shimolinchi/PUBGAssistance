import threading
import time
import cv2
import numpy as np
import mss

# ================= 颜色配置 (BGR) =================
COLORS_BGR = {
    "Yellow": {"bgr": [33, 237, 251], "tol": 20},
    "Orange": {"bgr": [13, 80, 179],  "tol": 20},
    "Blue":   {"bgr": [163, 62, 26],  "tol": 20},
    "Green":  {"bgr": [102, 145, 16], "tol": 20}
}

class CompassRadarModule:
    """
    顶部罗盘方位传感器
    用途：获取标点在屏幕水平方向的相对位置 (0.0 ~ 1.0)
    """
    def __init__(self, screen_width=1920, compass_height=120):
        self.screen_width = screen_width
        # 截取屏幕最上方的一条横幅
        self.monitor = {"top": 0, "left": 0, "width": screen_width, "height": compass_height}
        
        self.is_enabled = False
        self._thread_running = False
        self.radar_thread = None
        self.latest_h_ratio = None  # 结果: 0.0 ~ 1.0，None 表示未找到

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.radar_thread = threading.Thread(target=self._cv_process_loop, daemon=True)
            self.radar_thread.start()
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            self.latest_h_ratio = None

    def get_horizontal_ratio(self):
        """返回 0.0(最左) 到 1.0(最右) 的水平比例"""
        return self.latest_h_ratio

    def _cv_process_loop(self):
        with mss.MSS() as sct:
            while self._thread_running:
                screenshot = sct.grab(self.monitor)
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                found_ratio = None
                max_area = 0
                
                for color_name, config in COLORS_BGR.items():
                    b, g, r = config["bgr"]
                    tol = config["tol"]
                    
                    lower = np.array([max(0, b - tol), max(0, g - tol), max(0, r - tol)], dtype=np.uint8)
                    upper = np.array([min(255, b + tol), min(255, g + tol), min(255, r + tol)], dtype=np.uint8)
                    
                    mask = cv2.inRange(frame, lower, upper)
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    for cnt in contours:
                        area = cv2.contourArea(cnt)
                        # 找到最大的有效标点，防止噪点干扰
                        if 10 < area < 400 and area > max_area:
                            max_area = area
                            x, y, w, h = cv2.boundingRect(cnt)
                            
                            # 获取标点的水平中心绝对坐标
                            pt_abs_x = self.monitor["left"] + x + (w // 2)
                            # 换算为 0~1 的比例
                            found_ratio = pt_abs_x / self.screen_width
                            
                self.latest_h_ratio = found_ratio
                time.sleep(0.03)  # 约 30FPS