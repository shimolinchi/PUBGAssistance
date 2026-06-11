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

try:
    from modules.transparent_hud import TransparentHudWindow
except Exception:
    try:
        from transparent_hud import TransparentHudWindow
    except Exception:
        TransparentHudWindow = None

class AutoMapDistanceAssistant:
    """PUBG 大地图半自动测距模块 (单次快照版，集成 RegionManager)"""
    def __init__(self, root, region_manager, config_file="config.json"):
        self.root = root
        self.region_manager = region_manager
        self.config_file = config_file

        # 获取屏幕尺寸
        self.sw = self.region_manager.real_w
        self.sh = self.region_manager.real_h

        # 从 RegionManager 获取大地图区域和比例尺
        self.map_rect = self.region_manager.get_real_region("largemap_region")
        self.map_1km_pixels = self.region_manager.get_real_scale("largemap_1km_px") or 540.0

        # 颜色配置（与小地图共用 pnt_colors）
        self.colors = {
            "Yellow": {"lower": [26, 150, 160], "upper": [30, 255, 255], "hex": "#E9E511"},
            "Orange": {"lower": [10, 160, 160], "upper": [14, 255, 255], "hex": "#DA6226"},
            "Blue": {"lower": [110, 120, 160], "upper": [114, 255, 255], "hex": "#017BC2"},
            "Green": {"lower": [78, 150, 120], "upper": [82, 255, 255], "hex": "#0F9D16"}
        }
        self.color_order = ["Yellow", "Orange", "Blue", "Green"]
        self.base_colors = {
            "Yellow": "#E9E511", "Orange": "#DA6226",
            "Blue": "#017BC2", "Green": "#0F9D16"
        }
        # 替代方案：从 region_manager 内部配置获取，但 region_manager 只提供了 detection_regions 和 map_scales
        # 我们仍从 config.json 读取颜色，或者从 region_manager 中暴露颜色配置。为了简洁，直接从原 config_file 读取颜色部分
        self._load_colors_from_config()

        self.state = "IDLE"
        self.player_pt = None
        self.show_display = False
        self.last_measured_dists = {c: None for c in self.color_order}
        self.tpl_list = self._load_pnt_templates("templates/pnt/largemap")

        self.overlay = None
        self.canvas = None
        self.alpha_hud = TransparentHudWindow() if TransparentHudWindow else None
        self.y_spacer = 30
        self._init_overlay()

    def _load_colors_from_config(self):
        """从 config.json 加载 pnt_colors（与 RegionManager 保持一致）"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.colors = config.get("pnt_colors", self.colors)
                    self.base_colors = {name: data.get("hex", "#FFFFFF") for name, data in self.colors.items()}
            except:
                pass

    def set_pnt_colors(self, colors):
        self.colors = colors
        self.base_colors = {name: data.get("hex", "#FFFFFF") for name, data in colors.items()}
        for color_name in self.color_order:
            self.last_measured_dists.setdefault(color_name, None)
        if self.show_display:
            if self.state == "WAIT_PLAYER":
                self._update_wait_ui()
            elif self.state == "CALCULATING":
                self._update_calc_ui()
            else:
                self._render_auto_hud()

    def _load_pnt_templates(self, preferred_dir):
        for tpl_dir in [preferred_dir, "templates/pnt"]:
            tpl_list = []
            if not os.path.isdir(tpl_dir):
                continue
            for filename in os.listdir(tpl_dir):
                if not filename.lower().endswith('.png'):
                    continue
                img_bgra = cv2.imread(os.path.join(tpl_dir, filename), cv2.IMREAD_UNCHANGED)
                if img_bgra is not None and len(img_bgra.shape) == 3 and img_bgra.shape[2] == 4:
                    alpha = img_bgra[:, :, 3]
                    _, binary_tpl = cv2.threshold(alpha, 128, 255, cv2.THRESH_BINARY)
                    tpl_list.append({"img": binary_tpl, "w": binary_tpl.shape[1], "h": binary_tpl.shape[0]})
            if tpl_list:
                print(f"[大地图测距] 加载标点模板 {tpl_dir}: {len(tpl_list)} 个")
                return tpl_list
        print("[大地图测距] 未找到标点模板")
        return []

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)

        # 强制设置窗口大小为物理分辨率，防止仅显示 1920×1080 区域
        self.overlay.geometry(f"{self.region_manager.real_w}x{self.region_manager.real_h}+0+0")

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
            if self.alpha_hud:
                self.alpha_hud.clear()
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
                    for tpl in self.tpl_list:
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

    def _get_panel_layout(self):
        minimap_rect = self.region_manager.get_real_region("minimap_region")
        panel_height = 25
        if minimap_rect:
            spacing = 10
            panel_width = int(minimap_rect["width"] * 0.82)
            total_spacing = 3 * spacing
            box_width = (panel_width - total_spacing) // 4
            total_width = 4 * box_width + total_spacing
            start_x = minimap_rect["left"] + minimap_rect["width"] - total_width
            start_y = minimap_rect["top"] - panel_height - spacing - panel_height - self.y_spacer
            if start_y < 0:
                start_y = 0
        else:
            box_width, spacing = 90, 15
            total_width = 4 * box_width + 3 * spacing
            start_x = self.sw - total_width - 25
            start_y = self.sh * 0.465
        return start_x, start_y, box_width, panel_height, spacing, total_width

    def _render_prompt_card(self, text, color_name):
        self.canvas.delete("all")
        start_x, start_y, _, panel_height, _, total_width = self._get_panel_layout()
        base_hex = self.base_colors[color_name]
        if self.alpha_hud:
            self.alpha_hud.render_cards([{
                "x1": start_x,
                "y1": start_y,
                "x2": start_x + total_width,
                "y2": start_y + panel_height,
                "radius": 10,
                "fill": base_hex,
                "alpha": 51,
                "outline": base_hex,
                "outline_alpha": 204,
                "outline_width": 2,
                "text": text,
                "text_fill": "#FFFFFF",
                "font_size": 12,
            }])
            return

        self._draw_rounded_rect(start_x, start_y, start_x + total_width, start_y + panel_height, radius=10,
                                fill=self._dim_color(base_hex, 0.2), outline=base_hex, width=2, tags="hud")
        self.canvas.create_text(start_x + total_width / 2, start_y + panel_height / 2, text=text,
                                fill="#FFFFFF", font=("Microsoft YaHei", 12, "bold"), tags="hud")

    def _update_wait_ui(self):
        self._render_prompt_card("请左键点击你的当前位置", "Blue")

    def _update_calc_ui(self):
        self._render_prompt_card("正在测距...", "Orange")

    def _render_auto_hud(self):
        self.canvas.delete("all")
        if not self.show_display:
            return

        start_x, start_y, box_width, panel_height, spacing, _ = self._get_panel_layout()

        for i, color_name in enumerate(self.color_order):
            dist = self.last_measured_dists.get(color_name)
            base_hex = self.base_colors[color_name]

            if dist is not None:
                bg_color = base_hex
                text = f"{dist:.0f}m"
            else:
                bg_color = self._dim_color(base_hex, 0.2)
                text = "---"

            x1 = start_x + i * (box_width + spacing)
            y1 = start_y
            x2 = x1 + box_width
            y2 = y1 + panel_height

            if self.alpha_hud:
                continue

            self._draw_rounded_rect(x1, y1, x2, y2, radius=10, fill=bg_color, outline=base_hex, width=2, tags="hud")
            font_size = 14 if dist is not None else 13
            text_color = "#FFFFFF" if dist is not None else "#7F8C8D"
            self.canvas.create_text(x1 + box_width/2, y1 + panel_height / 2, text=text, fill=text_color, font=("Microsoft YaHei", font_size, "bold"), tags="hud")

        if self.alpha_hud:
            cards = []
            for i, color_name in enumerate(self.color_order):
                dist = self.last_measured_dists.get(color_name)
                base_hex = self.base_colors[color_name]
                if dist is not None:
                    bg_color = base_hex
                    text = f"{dist:.0f}m"
                    alpha = 179
                    text_color = "#FFFFFF"
                    font_size = 14
                else:
                    bg_color = self._dim_color(base_hex, 0.2)
                    text = "---"
                    alpha = 51
                    text_color = "#FFFFFF"
                    font_size = 13

                x1 = start_x + i * (box_width + spacing)
                y1 = start_y
                x2 = x1 + box_width
                y2 = y1 + panel_height
                cards.append({
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "radius": 10,
                    "fill": base_hex,
                    "alpha": alpha,
                    "outline": base_hex,
                    "outline_alpha": 204,
                    "outline_width": 2,
                    "text": text,
                    "text_fill": text_color,
                    "font_size": font_size,
                })
            self.alpha_hud.render_cards(cards)

    def shutdown(self):
        if self.alpha_hud:
            self.alpha_hud.destroy()
