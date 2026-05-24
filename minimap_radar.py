import tkinter as tk
import threading
import time
import cv2
import numpy as np
import mss
import json
import os
import math
import ctypes

# ================= 颜色配置 (BGR) =================
COLORS_BGR = {
    "Yellow": {"bgr": [33, 237, 251], "tol": 20, "hex": "#FBED21"},
    "Orange": {"bgr": [22, 112, 244],  "tol": 20, "hex": "#B3500D"},
    "Blue":   {"bgr": [224, 89, 40],  "tol": 20, "hex": "#1A3EA3"},
    "Green":  {"bgr": [141, 198, 26], "tol": 20, "hex": "#109166"}
}

class MinimapRadarModule:
    """
    PUBG 小地图视觉雷达子模块
    负责：独立截屏、识别标点、换算距离、管理防截图透明画板
    """
    def __init__(self, root, config_file="minimap_config.json"):
        self.root = root  
        self.config_file = config_file
        self.monitor = self.load_config()
        
        self.is_enabled = False       
        self.show_display = True      
        
        self._thread_running = False
        self.radar_thread = None
        self.latest_targets = []      
        
        self.calib_state = "IDLE"
        self.calib_pt1 = None
        
        self.overlay = None
        self.canvas = None
        self._init_overlay()

        self.measured_distance = {
            "Yellow": 0.0,
            "Orange": 0.0,
            "Blue": 0.0,
            "Green": 0.0
        }

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f).get("minimap_rect")
            except: pass
        return None

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump({"minimap_rect": self.monitor}, f)

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)
        
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        
        self.overlay.update_idletasks()
        try:
            hwnd = int(self.overlay.frame(), 16)
            result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
            if result == 0:
                hwnd_alt = self.overlay.winfo_id()
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd_alt, 17)
        except Exception as e:
            print(f"[雷达模块] 窗口隐身 API 调用失败: {e}")

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.radar_thread = threading.Thread(target=self._cv_process_loop, daemon=True)
            self.radar_thread.start()
            print("[雷达模块] 视觉线程已启动")
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            self.canvas.delete("marker")
            self.latest_targets = []
            print("[雷达模块] 视觉线程已停止")

    def set_display(self, show: bool):
        self.show_display = show
        if not self.show_display:
            self.canvas.delete("marker")

    def get_latest_targets(self):
        return self.latest_targets

    def get_measured_distance(self):
        return self.measured_distance

    def trigger_calibration(self):
        self.calib_state = "CALIB_1"
        self.overlay.attributes("-transparentcolor", "")
        self.overlay.attributes("-alpha", 0.4)
        self.canvas.config(bg="#111111", cursor="crosshair")
        self.canvas.delete("all")
        print("[雷达模块] 请点击小地图左上角...")

    def _on_canvas_click(self, event):
        if self.calib_state == "CALIB_1":
            self.calib_pt1 = (event.x, event.y)
            self.calib_state = "CALIB_2"
            self.canvas.create_oval(event.x-3, event.y-3, event.x+3, event.y+3, fill="red", tags="temp_calib")
            print("[雷达模块] 请点击小地图右下角...")
            
        elif self.calib_state == "CALIB_2":
            x1, y1 = self.calib_pt1
            x2, y2 = event.x, event.y
            
            side = max(abs(x2 - x1), abs(y2 - y1))
            left, top = min(x1, x2), min(y1, y2)
            
            self.monitor = {"top": top, "left": left, "width": side, "height": side}
            self.save_config()
            
            self.calib_state = "IDLE"
            self.overlay.attributes("-alpha", 1.0)
            self.overlay.attributes("-transparentcolor", "black")
            self.canvas.config(bg="black", cursor="arrow")
            self.canvas.delete("all")
            print(f"[雷达模块] 标定完成! 区域: {self.monitor}")

    def _draw_markers(self, points):
        if not self._thread_running or not self.show_display: 
            return
        self.canvas.delete("marker")
        
        if self.monitor:
            cx = self.monitor["left"] + (self.monitor["width"] // 2)
            cy = self.monitor["top"] + (self.monitor["height"] // 2)
            self.canvas.create_line(cx-6, cy, cx+6, cy, fill="black", width=4, tags="marker")
            self.canvas.create_line(cx, cy-6, cx, cy+6, fill="black", width=4, tags="marker")
            self.canvas.create_line(cx-6, cy, cx+6, cy, fill="white", width=2, tags="marker")
            self.canvas.create_line(cx, cy-6, cx, cy+6, fill="white", width=2, tags="marker")
        
        for pt in points:
            ax, ay, color = pt['x'], pt['y'], pt['color']
            self.canvas.create_oval(ax-3, ay-3, ax+3, ay+3, fill=color, outline="black", tags="marker")
            self.canvas.create_rectangle(ax-10, ay-20, ax+10, ay, outline=color, width=2, tags="marker")
            self.canvas.create_text(ax, ay+15, text=f"{pt['dist']:.1f}m", fill=color, font=("Arial", 12, "bold"), tags="marker")
    
    def _cv_process_loop(self):
        with mss.MSS() as sct:
            while self._thread_running:
                try:
                    if not self.monitor:
                        time.sleep(0.1)
                        continue
                    
                    screenshot = sct.grab(self.monitor)
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    
                    side_len = self.monitor["width"]
                    center_local_x, center_local_y = side_len // 2, side_len // 2
                    
                    current_targets = []

                    current_frame_distances = {
                        "Yellow": 0.0, "Orange": 0.0, "Blue": 0.0, "Green": 0.0
                    }
                    
                    for color_name, config in COLORS_BGR.items():
                        b, g, r = config["bgr"]
                        tol = config["tol"]
                        
                        lower = np.array([max(0, b - tol), max(0, g - tol), max(0, r - tol)], dtype=np.uint8)
                        upper = np.array([min(255, b + tol), min(255, g + tol), min(255, r + tol)], dtype=np.uint8)
                        
                        mask = cv2.inRange(frame, lower, upper)
                        
                        kernel = np.ones((5, 5), np.uint8)
                        
                        mask_closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

                        contours, _ = cv2.findContours(mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        for cnt in contours:
                            area = cv2.contourArea(cnt)
                            if 10 < area < 400:
                                x, y, w, h = cv2.boundingRect(cnt)
                                
                                pt_local_x = x + (w // 2)
                                pt_local_y = y + h
                                
                                if abs(pt_local_x - center_local_x) < 20 and abs(pt_local_y - center_local_y) < 20:
                                    continue
                                    
                                # 【修复点】：正确的平方运算是 **2
                                dist_px = math.sqrt((pt_local_x - center_local_x)**2 + (pt_local_y - center_local_y)**2)
                                real_dist = (dist_px / side_len) * 700.0

                                current_frame_distances[color_name] = real_dist
                                
                                # self.measured_distance[color_name] = real_dist
                                
                                abs_x = self.monitor["left"] + pt_local_x
                                abs_y = self.monitor["top"] + pt_local_y
                                
                                current_targets.append({
                                    'x': abs_x, 'y': abs_y, 
                                    'dist': real_dist, 'color': config["hex"]
                                })

                    self.measured_distance = current_frame_distances
                    self.latest_targets = current_targets
                    
                    if self.show_display and self.calib_state == "IDLE":
                        self.root.after(0, self._draw_markers, current_targets)
                        
                except Exception as e:
                    print(f"[雷达模块错误] {e}")
                    
                time.sleep(0.03)