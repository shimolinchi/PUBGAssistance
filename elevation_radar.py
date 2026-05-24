import tkinter as tk
import threading
import time
import cv2
import numpy as np
import mss
import ctypes

# ================= 颜色配置 (BGR) =================
# 补全了用于显示的 hex 颜色代码
COLORS_HSV = {
    "Yellow": {
        # 你的 H 换算是 27~28。我们给 22~35 的区间。
        # SV 下限给到 120 容错暗光，上限 255。
        "lower": [26, 150, 180], 
        "upper": [29, 250, 250], 
        "hex": "#E3D43C"
    },
    "Orange": {
        # 你的 H 换算是 10。我们给 5~18 的区间。
        "lower": [10, 200, 140], 
        "upper": [14, 255, 255], 
        "hex": "#B3500D"
    },
    "Blue": {
        # 你的 H 换算是 112。我们给 100~125 的区间。
        "lower": [110, 120, 120], 
        "upper": [114, 255, 255], 
        "hex": "#1A3EA3"
    },
    "Green": {
        # 你的 H 换算是 80。我们给 65~95 的区间。
        # 绿色在有些地形可能偏暗，V 的下限可以再稍微拉低一点点到 100。
        "lower": [76, 120, 100], 
        "upper": [84, 255, 255], 
        "hex": "#109166"
    }
}

class ElevationRadarModule:
    """
    中心视野俯仰角传感器
    用途：获取四个颜色标点在屏幕垂直方向的相对位置 (0.0 ~ 1.0)
    """
    def __init__(self, root, screen_width=1920, screen_height=1080, strip_width=300, fps=30):
        self.root = root
        self.screen_height = screen_height
        self.fps = fps # 刷新率控制
        
        # 截取屏幕正中间的一条竖条
        left_pos = (screen_width // 2) - (strip_width // 2)
        self.monitor = {"top": 162, "left": 902, "width": 116, "height": 850}
        
        # 核心数据：四个标点的高度值 (找不到则为 None)
        self.measured_elevations = {
            "Yellow": None,
            "Orange": None,
            "Blue": None,
            "Green": None
        }
        
        self.is_enabled = False
        self.show_display = True
        self._thread_running = False
        self.radar_thread = None
        self.latest_targets = [] # 用于渲染的目标列表
        
        # 初始化透明显示层
        self.overlay = None
        self.canvas = None
        self._init_overlay()

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)
        
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 防截图黑科技
        self.overlay.update_idletasks()
        try:
            hwnd = int(self.overlay.frame(), 16)
            result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
            if result == 0:
                hwnd_alt = self.overlay.winfo_id()
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd_alt, 17)
        except Exception as e:
            print(f"[高低角模块] 窗口隐身 API 调用失败: {e}")

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.radar_thread = threading.Thread(target=self._cv_process_loop, daemon=True)
            self.radar_thread.start()
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            self.canvas.delete("marker")
            self.latest_targets = []
            self.measured_elevations = {k: None for k in COLORS_HSV}

    def set_display(self, show: bool):
        self.show_display = show
        if not self.show_display:
            self.canvas.delete("marker")

    def get_measured_elevations(self):
        """返回包含四个颜色高度比例的字典"""
        return self.measured_elevations

    def _draw_markers(self, points):
        if not self._thread_running or not self.show_display: 
            return
        self.canvas.delete("marker")
        
        for pt in points:
            x, y, color = pt['x'], pt['y'], pt['color']
            
            # 1. 目标中心点 (2x2 像素)
            self.canvas.create_rectangle(x-1, y-1, x+1, y+1, fill=color, outline="", tags="marker")
            
            # 2. 绘制斜线：向左下和右下延伸 (空白4像素，直线长7像素)
            # 左下斜线: 起点 (x-4, y+4) -> 终点 (x-12, y+12)
            self.canvas.create_line(x-5, y+5, x-12, y+12, fill=color, width=1, tags="marker")
            
            # 右下斜线: 起点 (x+4, y+4) -> 终点 (x+12, y+12)
            self.canvas.create_line(x+5, y+5, x+12, y+12, fill=color, width=1, tags="marker")
            
            # 3. 数字标在末端下面之间 (居中位置大约在 x, y+18)
            self.canvas.create_text(x, y+18, text=f"{pt['ratio']:.3f}", 
                                    fill=color, font=("Arial", 12, "bold"), tags="marker")

    def _cv_process_loop(self):
        kernel = np.ones((2, 2), np.uint8)
        
        with mss.mss() as sct:
            while self._thread_running:
                start_time = time.time()
                try:
                    center_y_local = self.monitor["height"] // 2
                    screenshot = sct.grab(self.monitor)
                    frame_bgr = np.array(screenshot)
                    frame_bgr = cv2.cvtColor(frame_bgr, cv2.COLOR_BGRA2BGR)
                    
                    # 【核心黑科技】：转换为 HSV 空间
                    frame_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
                    
                    temp_elevations = {k: None for k in COLORS_HSV}
                    current_targets = []
                    
                    for color_name, config in COLORS_HSV.items():
                        # 直接读取配置好的绝对上下限，不需要再计算 tol
                        lower = np.array(config["lower"], dtype=np.uint8)
                        upper = np.array(config["upper"], dtype=np.uint8)
                        
                        # 重点：对 frame_hsv 进行 inRange 过滤
                        mask = cv2.inRange(frame_hsv, lower, upper)
                        
                        mask = cv2.dilate(mask, kernel, iterations=1)
                        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        
                        max_area = 0
                        best_target = None
                        
                        for cnt in contours:
                            area = cv2.contourArea(cnt)
                            if 2 < area < 400 and area > max_area:
                                x, y, w, h = cv2.boundingRect(cnt)
                                
                                if abs((y + h//2) - center_y_local) < 15:
                                    continue
                                    
                                max_area = area
                                pt_abs_y = self.monitor["top"] + y + h
                                pt_abs_x = self.monitor["left"] + x + w // 2
                                ratio = pt_abs_y / self.screen_height
                                
                                best_target = {
                                    'x': pt_abs_x, 
                                    'y': pt_abs_y, 
                                    'ratio': ratio, 
                                    'color': config["hex"]
                                }
                                
                        if best_target:
                            temp_elevations[color_name] = best_target['ratio']
                            current_targets.append(best_target)
                            
                    # 更新核心数据与渲染列表
                    self.measured_elevations = temp_elevations
                    self.latest_targets = current_targets
                    
                    if self.show_display:
                        self.root.after(0, self._draw_markers, current_targets)
                        
                except Exception as e:
                    print(f"[高低角模块错误] {e}")
                    
                # 精确的帧率控制
                elapsed = time.time() - start_time
                sleep_time = max(0, (1.0 / self.fps) - elapsed)
                time.sleep(sleep_time)