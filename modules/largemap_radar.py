import tkinter as tk
import threading
import cv2
import numpy as np
import mss
import json
import os
import math
import ctypes
from pynput import mouse

class AutoMapDistanceAssistant:
    """PUBG 大地图半自动测距模块 (单次快照版，集成 RegionManager)"""
    def __init__(self, root, region_manager, config_file="config.json"):
        self.root = root
        self.region_manager = region_manager
        self.config_file = config_file

        # 获取屏幕尺寸
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()

        # 从 RegionManager 获取大地图区域和比例尺
        self.map_rect = self.region_manager.get_real_region("largemap_region")
        self.map_1km_pixels = self.region_manager.get_real_scale("largemap_1km_px") or 540.0

        # 颜色配置（与小地图共用 minimap_colors）
        self.colors = self.region_manager.get_templates_region("minimap_colors")  # 注意：RegionManager 中没有此方法，需直接读取 config
        # 替代方案：从 region_manager 内部配置获取，但 region_manager 只提供了 detection_regions 和 map_scales
        # 我们仍从 config.json 读取颜色，或者从 region_manager 中暴露颜色配置。为了简洁，直接从原 config_file 读取颜色部分
        self._load_colors_from_config()

        self.color_order = ["Yellow", "Orange", "Blue", "Green"]
        self.base_colors = {
            "Yellow": "#FBED21", "Orange": "#B3500D",
            "Blue": "#1A3EA3", "Green": "#109166"
        }

        self.state = "IDLE"
        self.player_pt = None
        self.show_display = False
        self.last_measured_dists = {c: None for c in self.color_order}

        self.overlay = None
        self.canvas = None
        self._init_overlay()

    def _load_colors_from_config(self):
        """从 config.json 加载 minimap_colors（与 RegionManager 保持一致）"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.colors = config.get("minimap_colors", {})
            except:
                self.colors = {}

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)

        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.overlay.update_idletasks()

        try:
            hwnd = int(self.overlay.frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception as e:
            print(f"[大地图测距] 隐身 API 调用失败: {e}")

        # 一次性强制置顶（与其他模块一致）
        # try:
        #     hwnd = int(self.overlay.frame(), 16)
        #     GWLP_EXSTYLE = -20
        #     WS_EX_TOPMOST = 0x00000008
        #     ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWLP_EXSTYLE)
        #     ctypes.windll.user32.SetWindowLongW(hwnd, GWLP_EXSTYLE, ex_style | WS_EX_TOPMOST)

        #     HWND_TOPMOST = -1
        #     SWP_NOMOVE = 0x0002
        #     SWP_NOSIZE = 0x0001
        #     ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)

        #     ctypes.windll.user32.SetForegroundWindow(hwnd)
        #     ctypes.windll.user32.BringWindowToTop(hwnd)
        #     ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        # except Exception as e:
        #     print(f"[大地图测距] 窗口置顶失败: {e}")

    def set_display(self, show: bool):
        self.show_display = show
        if not show:
            self.canvas.delete("all")
        else:
            if self.state == "WAIT_PLAYER":
                self._update_wait_ui()
            elif self.state == "CALCULATING":
                self._update_calc_ui()
            else:
                self._render_auto_hud()

    def toggle_mode(self):
        if not self.show_display:
            print("[大地图自动测距] 主显示模式未开启，无法触发。")
            return

        # 重新从 RegionManager 加载最新区域和比例尺（支持热更新）
        self.map_rect = self.region_manager.get_real_region("largemap_region")
        self.map_1km_pixels = self.region_manager.get_real_scale("largemap_1km_px") or 540.0

        if not self.map_rect:
            print("[大地图自动测距] 未配置 largemap_region，请先校准")
            return

        if self.state == "IDLE":
            self.state = "WAIT_PLAYER"
            self.player_pt = None
            self._update_wait_ui()
        else:
            self.cancel()

    def cancel(self):
        if self.state != "IDLE":
            self.state = "IDLE"
            self.player_pt = None
            print("[大地图自动测距] 取消本次标定")
            if self.show_display:
                self._render_auto_hud()

    def on_mouse_click(self, x, y, button, pressed):
        if not pressed:
            return
        if button == mouse.Button.right:
            if self.state == "WAIT_PLAYER":
                self.cancel()
            return
        if button == mouse.Button.left and self.state == "WAIT_PLAYER":
            self.player_pt = (x, y)
            self.state = "CALCULATING"
            self._update_calc_ui()
            print(f"[大地图自动测距] 玩家位置确认 {self.player_pt}，开始瞬间快照计算...")
            threading.Thread(target=self._process_single_frame, daemon=True).start()

    # ================= 核心视觉：单次扫描 =================
    def _process_single_frame(self):
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
            try:
                grab_monitor = {
                    "top": int(self.map_rect["top"]),
                    "left": int(self.map_rect["left"]),
                    "width": int(self.map_rect["width"]),
                    "height": int(self.map_rect["height"])
                }
                screenshot = sct.grab(grab_monitor)
                frame_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
                frame_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

                measured_dists = {c: None for c in self.color_order}

                for color_name in self.color_order:
                    if color_name not in self.colors:
                        continue
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

                self.last_measured_dists = measured_dists
                self.state = "IDLE"

                if self.show_display:
                    self.root.after(0, self._render_auto_hud)

            except Exception as e:
                print(f"[大地图快照错误] {e}")
                self.state = "IDLE"
                if self.show_display:
                    self.root.after(0, self._render_auto_hud)

    # ================= UI 渲染 =================
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
        self.canvas.delete("all")
        box_w, box_h = 240, 45
        mortar_total_width = 465
        start_x = self.sw - mortar_total_width - 25
        x1 = start_x + (mortar_total_width - box_w) / 2
        y1 = self.sh * 0.465 - box_h - 15
        self._draw_rounded_rect(x1, y1, x1+box_w, y1+box_h, radius=12, fill="#2980B9", tags="hud")
        self.canvas.create_text(x1 + box_w/2, y1 + box_h/2, text="请左键点击你的当前位置", fill="#FFFFFF", font=("Microsoft YaHei", 12, "bold"), tags="hud")

    def _update_calc_ui(self):
        self.canvas.delete("all")
        box_w, box_h = 240, 45
        mortar_total_width = 465
        start_x = self.sw - mortar_total_width - 25
        x1 = start_x + (mortar_total_width - box_w) / 2
        y1 = self.sh * 0.465 - box_h - 15
        self._draw_rounded_rect(x1, y1, x1+box_w, y1+box_h, radius=12, fill="#E67E22", tags="hud")
        self.canvas.create_text(x1 + box_w/2, y1 + box_h/2, text="正在寻找目标...", fill="#FFFFFF", font=("Microsoft YaHei", 12, "bold"), tags="hud")

    def _render_auto_hud(self):
        self.canvas.delete("all")
        if not self.show_display:
            return

        box_w, box_h, spacing = 105, 50, 15
        total_width = 4 * box_w + 3 * spacing
        start_x = self.sw - total_width - 25
        start_y = self.sh * 0.465 - box_h - 15

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