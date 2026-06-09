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
    def __init__(self, root, region_manager, fps=30, config_file="config.json"):
        self.root = root
        self.region_manager = region_manager
        self.fps = fps
        self.config_file = config_file
        self.screen_height = self.region_manager.real_h
        self.screen_width = self.region_manager.real_w

        self.default_colors = {
            "Yellow": {"lower": [26, 150, 180], "upper": [29, 250, 250], "hex": "#E3D43C"},
            "Orange": {"lower": [11, 200, 140], "upper": [13, 255, 255], "hex": "#B3500D"},
            "Blue":   {"lower": [110, 120, 120], "upper": [114, 255, 255], "hex": "#1A3EA3"},
            "Green":  {"lower": [76, 120, 100],  "upper": [84, 255, 255], "hex": "#109166"}
        }
        self.colors = self.default_colors
        self.load_config()
        self.valid_colors = set(self.colors.keys())
        self.is_enabled = False
        self.show_display = False
        self._thread_running = False
        self.radar_thread = None
        self.latest_targets = []
        self.measured_elevations = {c: None for c in self.colors.keys()}
        self._init_overlay()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.colors = config.get("pnt_colors", self.default_colors)
            except:
                pass

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True, "-topmost", True, "-transparentcolor", "black")
        self.overlay.overrideredirect(True)
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.overlay.update_idletasks()

        try:
            hwnd = int(self.overlay.frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception as e:
            print(f"[垂直测高模块] 隐身 API 调用失败: {e}")

        # ========== 一次性强制最高层（无定时器） ==========
        # try:
        #     hwnd = int(self.overlay.frame(), 16)

        #     # 1. 设置扩展样式 WS_EX_TOPMOST
        #     GWLP_EXSTYLE = -20
        #     WS_EX_TOPMOST = 0x00000008
        #     ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWLP_EXSTYLE)
        #     ctypes.windll.user32.SetWindowLongW(hwnd, GWLP_EXSTYLE, ex_style | WS_EX_TOPMOST)

        #     # 2. 调用 SetWindowPos 将窗口插入顶层链
        #     HWND_TOPMOST = -1
        #     SWP_NOMOVE = 0x0002
        #     SWP_NOSIZE = 0x0001
        #     ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)

        #     # 3. 主动激活窗口，确保它在前
        #     ctypes.windll.user32.SetForegroundWindow(hwnd)
        #     ctypes.windll.user32.BringWindowToTop(hwnd)

        #     # 4. 原有的窗口隐身保护
        #     ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        # except Exception as e:
        #     print(f"[高低角模块] 窗口置顶失败: {e}")

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
            self.measured_elevations = {c: None for c in self.colors.keys()}

    def set_display(self, show: bool):
        self.show_display = show
        if not self.show_display:
            self.canvas.delete("elev_marker")

    def set_valid_colors(self, colors):
        if colors is not None:
            self.valid_colors = set(colors)
        else:
            self.valid_colors = set(self.colors.keys())

    def get_measured_elevations(self):
        return self.measured_elevations

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

        with mss.mss() as sct:
            while self._thread_running:
                monitor = self.region_manager.get_real_region("elevation_region")
                if not monitor:
                    time.sleep(0.1)
                    continue

                start_time = time.time()
                try:
                    screenshot = sct.grab(monitor)
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

                        for tpl in tpl_list:
                            res = cv2.matchTemplate(color_mask, tpl["img"], cv2.TM_CCOEFF_NORMED)
                            threshold = 0.8
                            loc = np.where(res >= threshold)
                            for pt in zip(*loc[::-1]):
                                candidates.append({
                                    'x': pt[0] + (tpl["w"] // 2),
                                    'y': pt[1] + tpl["h"],
                                    'color_name': color_name,
                                    'hex': config["hex"]
                                })

                    final_targets = []
                    min_dist = 15
                    for c in candidates:
                        if not any(math.hypot(c['x'] - f['x'], c['y'] - f['y']) < min_dist for f in final_targets):
                            final_targets.append(c)

                    current_targets = []
                    for pt in final_targets:
                        abs_x = monitor["left"] + pt['x']
                        abs_y = monitor["top"] + pt['y']
                        ratio = abs_y / self.screen_height
                        temp_elevations[pt['color_name']] = ratio
                        current_targets.append({
                            'x': abs_x,
                            'y': abs_y,
                            'ratio': ratio,
                            'color': pt['hex']
                        })

                    self.measured_elevations = temp_elevations
                    self.latest_targets = current_targets

                    # 调试输出
                    # if current_targets:
                    #     print(f"[检测] {len(current_targets)}个标点, 首点({current_targets[0]['x']},{current_targets[0]['y']})")

                    if self.show_display:
                        self.root.after(0, self._draw_markers, current_targets)

                except Exception as e:
                    print(f"[高低角模块错误] {e}")

                elapsed = time.time() - start_time
                sleep_time = max(0, (1.0 / self.fps) - elapsed)
                time.sleep(sleep_time)

    def _draw_markers(self, points):
        if not self._thread_running or not self.show_display:
            return
        self.canvas.delete("elev_marker")
        
        # 可选：调试输出
        # print(f"[绘制] 点数: {len(points)}")
        
        for pt in points:
            ax, ay, color = pt['x'], pt['y'], pt['color']
            
            # 坐标安全裁剪（防止越界）
            if ax < 0 or ay < 0 or ax > self.screen_width or ay > self.screen_height:
                continue
            
            # 绘制中心点（更大更明显）
            self.canvas.create_oval(ax-1, ay-1, ax+1, ay+1, fill=color, outline="white", width=1, tags="elev_marker")
            # 左下斜线
            self.canvas.create_line(ax-8, ay+8, ax-16, ay+16, fill=color, width=1, tags="elev_marker")
            # 右下斜线
            self.canvas.create_line(ax+8, ay+8, ax+16, ay+16, fill=color, width=1, tags="elev_marker")
            # 显示比率数值
            # self.canvas.create_text(ax, ay-15, text=f"{pt['ratio']:.3f}", fill=color, font=("Arial", 10, "bold"), tags="elev_marker")