import tkinter as tk
import threading
import time
import cv2
import numpy as np
import mss
import ctypes
import json
import os
import math

class ElevationRadarModule:
    """
    中心视野俯仰角传感器 (二值化模板匹配版)
    用途：获取四个颜色标点在屏幕垂直方向的相对位置 (0.0~1.0)
    未检测到时输出: None
    """
    def __init__(self, root, screen_width, screen_height, fps=30, config_file="config.json"):
        self.root = root
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.fps = fps
        self.config_file = config_file
        
        # 默认颜色配置 (保底方案，优先从 config.json 读取)
        self.default_colors = {
            "Yellow": {"lower": [26, 150, 180], "upper": [29, 250, 250], "hex": "#E3D43C"},
            "Orange": {"lower": [11, 200, 140], "upper": [13, 255, 255], "hex": "#B3500D"},
            "Blue": {"lower": [110, 120, 120], "upper": [114, 255, 255], "hex": "#1A3EA3"},
            "Green": {"lower": [76, 120, 100], "upper": [84, 255, 255], "hex": "#109166"}
        }

        # 加载配置
        self.monitor, self.colors = self.load_config()
        
        # 默认允许检测所有颜色集合
        self.valid_colors = set(self.colors.keys())
        
        self.is_enabled = False
        self.show_display = False 
        self._thread_running = False
        self.radar_thread = None
        
        self.latest_targets = []
        self.measured_elevations = {"Yellow": None, "Orange": None, "Blue": None, "Green": None}
        self.calib_state = "IDLE"
        self.calib_pt1 = None
        
        self.overlay = None
        self.canvas = None
        self._init_overlay()

    def load_config(self):
        monitor = None
        colors = self.default_colors
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    monitor = config_data.get("elevation_rect")
                    colors = config_data.get("elevation_colors", self.default_colors)
            except: 
                pass
        return monitor, colors

    def save_config(self):
        config_data = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except: 
                pass
        
        config_data["elevation_rect"] = self.monitor
        config_data["elevation_colors"] = self.colors
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True, "-topmost", True, "-transparentcolor", "black")
        self.overlay.overrideredirect(True)
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.bind("<Button-1>", self._on_canvas_left_click)
        self.canvas.bind("<Button-3>", self._on_canvas_right_click)
        
        # 窗口隐身
        self.overlay.update_idletasks()
        try:
            hwnd = int(self.overlay.frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception as e:
            pass

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.radar_thread = threading.Thread(target=self._cv_process_loop, daemon=True)
            self.radar_thread.start()
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            time.sleep(0.1)
            self.canvas.delete("elev_marker")
            self.latest_targets = []
            # 停止检测时，也将数据重置为 None
            self.measured_elevations = {c: None for c in self.colors.keys()}

    def set_display(self, show: bool):
        self.show_display = show
        if not self.show_display:
            self.canvas.delete("elev_marker")

    def set_valid_colors(self, colors):
        """接收外部传来的有效颜色列表，并更新集合"""
        if colors is not None:
            self.valid_colors = set(colors)
        else:
            self.valid_colors = set(self.colors.keys())

    def get_measured_elevations(self):
        return self.measured_elevations

    def trigger_calibration(self):
        self.calib_state = "CALIB_1"
        self.overlay.attributes("-transparentcolor", "")
        self.overlay.attributes("-alpha", 0.4)
        self.canvas.config(bg="#111111", cursor="crosshair")
        self.canvas.delete("all")
        print("[高低角模块] 请左键点击标尺区域左上角...")

    def _on_canvas_left_click(self, event):
        if self.calib_state == "CALIB_1":
            self.calib_pt1 = (event.x, event.y)
            self.calib_state = "CALIB_2"
            self.canvas.create_oval(event.x-3, event.y-3, event.x+3, event.y+3, fill="red", tags="temp_calib")
            print("[高低角模块] 请左键点击标尺区域右下角...")
        elif self.calib_state == "CALIB_2":
            x1, y1 = self.calib_pt1
            x2, y2 = event.x, event.y
            left, top = min(x1, x2), min(y1, y2)
            width, height = abs(x2 - x1), abs(y2 - y1)
            
            self.monitor = {"top": top, "left": left, "width": width, "height": height}
            self.save_config()
            self._exit_calibration()
            print(f"[高低角模块] 标定完成! 区域: {self.monitor}")

    def _on_canvas_right_click(self, event):
        if self.calib_state != "IDLE":
            self._exit_calibration()

    def _exit_calibration(self):
        self.calib_state = "IDLE"
        self.overlay.attributes("-alpha", 1.0)
        self.overlay.attributes("-transparentcolor", "black")
        self.canvas.config(bg="black", cursor="arrow")
        self.canvas.delete("temp_calib")

    def _cv_process_loop(self):
        tpl_list = []
        tpl_dir = "templates/pnt"
        if os.path.exists(tpl_dir):
            for f in os.listdir(tpl_dir):
                if f.endswith('.png'):
                    img_bgra = cv2.imread(os.path.join(tpl_dir, f), cv2.IMREAD_UNCHANGED)
                    if img_bgra is not None and img_bgra.shape[2] == 4:
                        alpha = img_bgra[:, :, 3]
                        _, binary_tpl = cv2.threshold(alpha, 128, 255, cv2.THRESH_BINARY)
                        tpl_list.append({"img": binary_tpl, "w": binary_tpl.shape[1], "h": binary_tpl.shape[0]})
        
        with mss.MSS() as sct:
            while self._thread_running:
                start_time = time.time()
                try:
                    if not self.monitor:
                        time.sleep(0.1)
                        continue
                    
                    screenshot = sct.grab(self.monitor)
                    frame_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
                    frame_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
                    
                    candidates = []
                    
                    temp_elevations = {c: None for c in self.colors.keys()}
                    
                    for color_name, config in self.colors.items():
                        if color_name not in self.valid_colors:
                            continue
                            
                        lower = np.array(config["lower"], dtype=np.uint8)
                        upper = np.array(config["upper"], dtype=np.uint8)
                        color_mask = cv2.inRange(frame_hsv, lower, upper)
                        
                        # 模板匹配
                        for tpl in tpl_list:
                            res = cv2.matchTemplate(color_mask, tpl["img"], cv2.TM_CCOEFF_NORMED)
                            threshold = 0.8
                            loc = np.where(res >= threshold)
                            
                            for pt in zip(*loc[::-1]):
                                candidates.append({
                                    'x': pt[0] + (tpl["w"] // 2),
                                    'y': pt[1] + tpl["h"], # 锚定下方中心点
                                    'color_name': color_name,
                                    'hex': config["hex"]
                                })
                                
                    final_targets = []
                    min_dist = 15
                    for c in candidates:
                        is_duplicate = False
                        for f in final_targets:
                            if math.sqrt((c['x'] - f['x'])**2 + (c['y'] - f['y'])**2) < min_dist:
                                is_duplicate = True
                                break
                        if not is_duplicate:
                            final_targets.append(c)
                            
                    # 计算绝对坐标及高低角比率
                    current_targets = []
                    for pt in final_targets:
                        pt_abs_x = self.monitor["left"] + pt['x']
                        pt_abs_y = self.monitor["top"] + pt['y']
                        
                        ratio = pt_abs_y / self.screen_height
                        
                        # 检测到了目标，才会将其对应颜色的字典值赋为具体的数字
                        temp_elevations[pt['color_name']] = ratio
                        current_targets.append({
                            'x': pt_abs_x, 
                            'y': pt_abs_y, 
                            'ratio': ratio, 
                            'color': pt['hex']
                        })
                        
                    self.measured_elevations = temp_elevations
                    self.latest_targets = current_targets
                    
                    if self.show_display and self.calib_state == "IDLE":
                        self.root.after(0, self._draw_markers, current_targets)
                        
                except Exception as e:
                    print(f"[高低角模块错误] {e}")
                    
                # 帧率控制
                elapsed = time.time() - start_time
                sleep_time = max(0, (1.0 / self.fps) - elapsed)
                time.sleep(sleep_time)

    def _draw_markers(self, points):
        self.canvas.delete("elev_marker")
        if not self._thread_running or not self.show_display: return
        
        # 画出标定框 (调试用)
        # if self.monitor:
        #     x1, y1 = self.monitor["left"], self.monitor["top"]
        #     x2, y2 = x1 + self.monitor["width"], y1 + self.monitor["height"]
        #     self.canvas.create_rectangle(x1, y1, x2, y2, outline="gray", dash=(4, 4), tags="elev_marker")
            
        # 画出标点和高度比率
        for pt in points:
            ax, ay, color = pt['x'], pt['y'], pt['color']
            # self.canvas.create_line(ax-10, ay, ax+10, ay, fill=color, width=2, tags="elev_marker")
            # self.canvas.create_polygon(ax-6, ay-8, ax+6, ay-8, ax, ay, fill=color, tags="elev_marker")
            # self.canvas.create_text(ax+15, ay, text=f"y:{pt['ratio']:.3f}", fill=color, font=("Consolas", 10, "bold"), anchor="w", tags="elev_marker")

            # 目标中心点 (2x2 像素)
            self.canvas.create_rectangle(ax-1, ay-1, ax+1, ay+1, fill=color, outline="", tags="elev_marker")
            
            # 绘制斜线：向左下和右下延伸 (空白4像素，直线长7像素)
            # 左下斜线: 起点 (x-4, y+4) -> 终点 (x-12, y+12)
            self.canvas.create_line(ax-5, ay+5, ax-12, ay+12, fill=color, width=1, tags="elev_marker")
            
            # 右下斜线: 起点 (x+4, y+4) -> 终点 (x+12, y+12)
            self.canvas.create_line(ax+5, ay+5, ax+12, ay+12, fill=color, width=1, tags="elev_marker")