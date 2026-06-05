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

class MinimapRadarModule:
    """PUBG 小地图视觉雷达子模块"""
    def __init__(self, root, region_manager = None, config_file="config.json"):
        self.root = root  
        self.region_manager = region_manager
        self.config_file = config_file

        # 默认颜色配置
        self.default_colors = {
            "Yellow": {"lower": [26, 150, 160], "upper": [30, 255, 255], "hex": "#E3D43C"},
            "Orange": {"lower": [10, 160, 160], "upper": [14, 255, 255], "hex": "#B3500D"},
            "Blue": {"lower": [110, 120, 160], "upper": [114, 255, 255], "hex": "#1A3EA3"},
            "Green": {"lower": [78, 150, 120], "upper": [82, 255, 255], "hex": "#109166"}
        }
        
        # 加载颜色配置
        self.colors = self.load_config()
        
        self.is_enabled = True     
        self.show_display = True      
        self._thread_running = False
        self.radar_thread = None
        self.latest_targets = []      
        self.calib_state = "IDLE"
        self.calib_pt1 = None
        self.overlay = None
        self.canvas = None
        self.monitor = None   # 会在循环中动态更新
        self._init_overlay()
        self.measured_distance = {"Yellow": 0.0, "Orange": 0.0, "Blue": 0.0, "Green": 0.0}

    def load_config(self):
        colors = self.default_colors
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    colors = config_data.get("minimap_colors", self.default_colors)
            except: 
                pass
        return colors

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)

        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 【修复】移除未定义的事件绑定，避免 AttributeError
        # self.canvas.bind("<Button-1>", self._on_canvas_left_click)
        # self.canvas.bind("<Button-3>", self._on_canvas_right_click)

        self.overlay.update_idletasks()

        try:
            hwnd = int(self.overlay.frame(), 16)

            # 1. 设置扩展样式 WS_EX_TOPMOST
            GWLP_EXSTYLE = -20
            WS_EX_TOPMOST = 0x00000008
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWLP_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWLP_EXSTYLE, ex_style | WS_EX_TOPMOST)

            # 2. 调用 SetWindowPos 将窗口插入顶层链
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)

            # 3. 主动激活窗口，确保它在前
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.BringWindowToTop(hwnd)

            # 4. 原有的窗口隐身保护
            result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
            if result == 0:
                hwnd_alt = self.overlay.winfo_id()
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd_alt, 17)
        except Exception as e:
            print(f"[雷达模块] 窗口置顶/隐身 API 调用失败: {e}")

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.radar_thread = threading.Thread(target=self._cv_process_loop, daemon=True)
            self.radar_thread.start()
            print("[雷达模块] 视觉线程已启动")
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            time.sleep(0.1) 
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

    def _draw_markers(self, points):
        if not self._thread_running or not self.show_display or not self.monitor:
            return
        self.canvas.delete("marker")
        
        # 画中心十字（基于当前小地图区域）
        cx = self.monitor["left"] + (self.monitor["width"] // 2)
        cy = self.monitor["top"] + (self.monitor["height"] // 2)
        self.canvas.create_line(cx-6, cy, cx+6, cy, fill="black", width=4, tags="marker")
        self.canvas.create_line(cx, cy-6, cx, cy+6, fill="black", width=4, tags="marker")
        self.canvas.create_line(cx-6, cy, cx+6, cy, fill="white", width=2, tags="marker")
        self.canvas.create_line(cx, cy-6, cx, cy+6, fill="white", width=2, tags="marker")
        
        # 画每个目标
        for pt in points:
            ax, ay, color = pt['x'], pt['y'], pt['color']
            self.canvas.create_oval(ax-3, ay-3, ax+3, ay+3, fill=color, outline="black", tags="marker")
            self.canvas.create_rectangle(ax-10, ay-20, ax+10, ay, outline=color, width=2, tags="marker")
            self.canvas.create_text(ax, ay+15, text=f"{pt['dist']:.1f}m", fill=color, font=("Arial", 12, "bold"), tags="marker")
    
    def _apply_nms(self, candidates, min_dist):
        final = []
        for c in candidates:
            if not any(math.sqrt((c['x'] - f['x'])**2 + (c['y'] - f['y'])**2) < min_dist for f in final):
                final.append(c)
        return final

    def _cv_process_loop(self):
        # 预加载模板
        tpl_list = []
        tpl_dir = "templates/pnt"
        if os.path.exists(tpl_dir):
            for f in os.listdir(tpl_dir):
                if f.endswith('.png'):
                    img_bgra = cv2.imread(os.path.join(tpl_dir, f), cv2.IMREAD_UNCHANGED)
                    if img_bgra is not None and img_bgra.shape[2] == 4:
                        alpha = img_bgra[:, :, 3]
                        _, binary_tpl = cv2.threshold(alpha, 128, 255, cv2.THRESH_BINARY)
                        tpl_list.append({
                            "img": binary_tpl,
                            "w": binary_tpl.shape[1],
                            "h": binary_tpl.shape[0]
                        })
        
        with mss.MSS() as sct:
            while self._thread_running:
                # 动态获取小地图区域（兼容 get_region 和 get_real_region）
                self.monitor = self.region_manager.get_real_region("minimap_region")
                
                try:
                    if not self.monitor:
                        time.sleep(0.5)
                        continue
                    
                    screenshot = sct.grab(self.monitor)
                    frame_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
                    frame_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
                    
                    side_len = self.monitor["width"]
                    center_local = side_len // 2
                    
                    candidates = []
                    current_distances = {c: 0.0 for c in self.colors.keys()}
                    
                    for color_name, config in self.colors.items():
                        lower = np.array(config["lower"], dtype=np.uint8)
                        upper = np.array(config["upper"], dtype=np.uint8)
                        color_mask = cv2.inRange(frame_hsv, lower, upper)
                        
                        for tpl in tpl_list:
                            res = cv2.matchTemplate(color_mask, tpl["img"], cv2.TM_CCOEFF_NORMED)
                            threshold = 0.75 
                            loc = np.where(res >= threshold)
                            for pt in zip(*loc[::-1]):
                                candidates.append({
                                    'x': pt[0] + (tpl["w"] // 2), 
                                    'y': pt[1] + tpl["h"],
                                    'color_name': color_name,
                                    'hex': config["hex"]
                                })
                    
                    # NMS 去重
                    final_targets = []
                    min_dist = 15
                    for c in candidates:
                        if not any(math.sqrt((c['x'] - f['x'])**2 + (c['y'] - f['y'])**2) < min_dist for f in final_targets):
                            final_targets.append(c)
                    
                    current_targets = []
                    for pt in final_targets:
                        dist_px = math.sqrt((pt['x'] - center_local)**2 + (pt['y'] - center_local)**2)
                        real_dist = (dist_px / side_len) * 700.0
                        current_distances[pt['color_name']] = real_dist
                        current_targets.append({
                            'x': self.monitor["left"] + pt['x'], 
                            'y': self.monitor["top"] + pt['y'],
                            'dist': real_dist, 
                            'color': pt['hex']
                        })
                    
                    self.measured_distance = current_distances
                    self.latest_targets = current_targets
                    
                    if self.show_display and self.calib_state == "IDLE":
                        self.root.after(0, self._draw_markers, current_targets)
                            
                except Exception as e:
                    print(f"[雷达模块线程错误] {e}")
                
                time.sleep(0.03)