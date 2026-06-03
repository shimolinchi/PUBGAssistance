import tkinter as tk
import threading
import cv2
import numpy as np
import mss
import json
import os
import math
from pynput import mouse

class AutoMapDistanceAssistant:
    """PUBG 大地图半自动测距模块 (单次快照版)"""
    def __init__(self, root, screen_width, screen_height, config_file="config.json"):
        self.root = root
        self.sw = screen_width
        self.sh = screen_height
        self.config_file = config_file
        
        self.map_rect = None
        self.map_1km_pixels = 540.0
        self.colors = {}
        
        # 固定 UI 渲染顺序与基础颜色
        self.color_order = ["Yellow", "Orange", "Blue", "Green"]
        self.base_colors = {
            "Yellow": "#FBED21", "Orange": "#B3500D", 
            "Blue": "#1A3EA3", "Green": "#109166"
        }
        
        self.load_config()

        self.state = "IDLE"
        self.player_pt = None

        self.show_display = False  
        self.last_measured_dists = {c: None for c in self.color_order} 

        self.overlay = None
        self.canvas = None
        self._init_overlay()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                    regions = config.get("detection_regions", {})
                    if "largemap_region" in regions:
                        self.map_rect = regions["largemap_region"]
                        
                    scales = config.get("map_scales", {})
                    if "largemap_1km_px" in scales:
                        self.map_1km_pixels = scales["largemap_1km_px"]
                        
                    self.colors = config.get("minimap_colors", {})
            except Exception as e:
                print(f"[大地图自动测距] 配置文件读取失败: {e}")

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True, "-topmost", True, "-transparentcolor", "black")
        self.overlay.overrideredirect(True)
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.overlay.update_idletasks()
        try:
            import ctypes
            hwnd = int(self.overlay.frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except: pass

    def set_display(self, show: bool):
        """完全与主程序的 N 键 (combat_hud_active) 同步"""
        self.show_display = show
        if not show:
            self.canvas.delete("all")
        else:
            # 开启显示时，根据状态恢复 UI
            if self.state == "WAIT_PLAYER":
                self._update_wait_ui()
            elif self.state == "CALCULATING":
                self._update_calc_ui()
            else:
                self._render_auto_hud() # 恢复上次测量的数据

    def toggle_mode(self):
        """主程序快捷键触发测距"""
        if not self.show_display:
            print("[大地图自动测距] 提示: 主显示模式未开启，无法触发。")
            return
            
        self.load_config()
        if not self.map_rect:
            return

        if self.state == "IDLE":
            self.state = "WAIT_PLAYER"
            self.player_pt = None
            self._update_wait_ui()
        else:
            # 如果已经在选点了，再按一次快捷键视为取消当前选点
            self.cancel()

    def cancel(self):
        """右键或重复按快捷键触发：取消选点，但保留旧数据"""
        if self.state != "IDLE":
            self.state = "IDLE"
            self.player_pt = None
            print("[大地图自动测距] 取消本次标定")
            
            # 如果主显示开启着，恢复显示上一次的老数据
            if self.show_display:
                self._render_auto_hud()

    def on_mouse_click(self, x, y, button, pressed):
        if not pressed: return

        # 右键：仅用于取消等待点击的状态，不会清空已保存的雷达数据
        if button == mouse.Button.right:
            if self.state == "WAIT_PLAYER":
                self.cancel()
            return

        # 左键：确定玩家坐标，开始单次计算
        if button == mouse.Button.left and self.state == "WAIT_PLAYER":
            self.player_pt = (x, y)
            self.state = "CALCULATING"
            self._update_calc_ui()
            print(f"[大地图自动测距] 玩家位置确认 {self.player_pt}，开始瞬间快照计算...")
            
            # 开启一次性线程进行视觉识别
            threading.Thread(target=self._process_single_frame, daemon=True).start()

    # ================= 核心视觉：单次扫描 =================
    def _process_single_frame(self):
        """不再是死循环，只进行一次精准的截图和匹配"""
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
            try:
                grab_monitor = {
                    "top": int(self.map_rect["top"]),
                    "left": int(self.map_rect["left"]),
                    "width": int(self.map_rect.get("width", self.map_rect.get("side", 800))),
                    "height": int(self.map_rect.get("height", self.map_rect.get("side", 800)))
                }
                screenshot = sct.grab(grab_monitor)
                frame_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
                frame_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
                
                # 新的测距结果
                measured_dists = {c: None for c in self.color_order}
                
                for color_name in self.color_order:
                    if color_name not in self.colors: continue
                    
                    config = self.colors[color_name]
                    lower = np.array(config["lower"], dtype=np.uint8)
                    upper = np.array(config["upper"], dtype=np.uint8)
                    color_mask = cv2.inRange(frame_hsv, lower, upper)
                    
                    candidates = []
                    for tpl in tpl_list:
                        res = cv2.matchTemplate(color_mask, tpl["img"], cv2.TM_CCOEFF_NORMED)
                        loc = np.where(res >= 0.75)
                        for pt in zip(*loc[::-1]):
                            candidates.append({
                                'x': pt[0] + (tpl["w"] // 2),
                                'y': pt[1] + tpl["h"]
                            })
                    
                    if candidates:
                        best_pt = candidates[0] 
                        abs_x = self.map_rect["left"] + best_pt['x']
                        abs_y = self.map_rect["top"] + best_pt['y']
                        
                        dx = abs_x - self.player_pt[0]
                        dy = abs_y - self.player_pt[1]
                        dist_px = math.hypot(dx, dy)
                        dist_m = (dist_px / self.map_1km_pixels) * 1000.0
                        measured_dists[color_name] = dist_m

                # 无论是否测到，都更新内部缓存，并切回 IDLE
                self.last_measured_dists = measured_dists
                self.state = "IDLE"
                
                if self.show_display:
                    self.root.after(0, self._render_auto_hud)
                
            except Exception as e:
                print(f"[大地图快照错误] {e}")
                self.state = "IDLE"
                if self.show_display:
                    self.root.after(0, self._render_auto_hud)

    # ================= UI 渲染层 =================
    def _dim_color(self, hex_color, alpha_ratio=0.2):
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"#{int(r*alpha_ratio):02x}{int(g*alpha_ratio):02x}{int(b*alpha_ratio):02x}"

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [x1+radius, y1, x2-radius, y1, x2, y1, x2, y1+radius,
                  x2, y2-radius, x2, y2, x2-radius, y2, x1+radius, y2,
                  x1, y2, x1, y2-radius, x1, y1+radius, x1, y1]
        self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _update_wait_ui(self):
        """渲染等待点击的提示框"""
        self.canvas.delete("all")
        box_w, box_h = 240, 45
        mortar_total_width = 465 
        start_x = self.sw - mortar_total_width - 25
        x1 = start_x + (mortar_total_width - box_w) / 2
        y1 = self.sh * 0.465 - box_h - 15 
        
        self._draw_rounded_rect(x1, y1, x1+box_w, y1+box_h, radius=12, fill="#2980B9", outline="#34495E", width=2, tags="hud")
        self.canvas.create_text(x1 + box_w/2, y1 + box_h/2, text="📍 请左键点击你的当前位置", fill="#FFFFFF", font=("Microsoft YaHei", 12, "bold"), tags="hud")

    def _update_calc_ui(self):
        """渲染瞬间的计算提示"""
        self.canvas.delete("all")
        box_w, box_h = 240, 45
        mortar_total_width = 465 
        start_x = self.sw - mortar_total_width - 25
        x1 = start_x + (mortar_total_width - box_w) / 2
        y1 = self.sh * 0.465 - box_h - 15 
        
        self._draw_rounded_rect(x1, y1, x1+box_w, y1+box_h, radius=12, fill="#E67E22", outline="#34495E", width=2, tags="hud")
        self.canvas.create_text(x1 + box_w/2, y1 + box_h/2, text="⚙️ 正在分析战术地图...", fill="#FFFFFF", font=("Microsoft YaHei", 12, "bold"), tags="hud")

    def _render_auto_hud(self):
        """渲染最终距离，直接读取 self.last_measured_dists"""
        self.canvas.delete("all")
        if not self.show_display: return

        box_w, box_h, spacing = 105, 50, 15
        total_width = 4 * box_w + 3 * spacing
        
        start_x = self.sw - total_width - 25
        start_y = self.sh * 0.465 - box_h - 15 
        
        # 即使恢复数据时，如果 player_pt 还在，也可以重新把它画出来
        # if self.player_pt:
        #     px, py = self.player_pt
            # self.canvas.create_oval(px-4, py-4, px+4, py+4, fill="white", outline="black", width=2, tags="hud")

        for i, color_name in enumerate(self.color_order):
            dist = self.last_measured_dists.get(color_name)
            base_hex = self.base_colors[color_name]
            
            if dist is not None:
                bg_color = base_hex
                text = f"{dist:.0f}m"
            else:
                bg_color = self._dim_color(base_hex, 0.2)
                text = "---"

            x1 = start_x + i * (box_w + spacing)
            y1 = start_y
            x2 = x1 + box_w
            y2 = y1 + box_h
            
            self._draw_rounded_rect(x1, y1, x2, y2, radius=15, fill=bg_color, tags="hud")
            font_size = 14 if dist is not None else 12
            text_color = "#FFFFFF" if dist is not None else "#7F8C8D"
            self.canvas.create_text(x1 + box_w/2, y1 + box_h/2, text=text, fill=text_color, font=("Microsoft YaHei", font_size, "bold"), tags="hud")