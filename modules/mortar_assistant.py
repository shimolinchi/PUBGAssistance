import threading
import time
import numpy as np
import tkinter as tk
import ctypes
import json
import os

class MortarAssistant:
    """
    迫击炮火控解算与 HUD 显示模块
    只负责计算真实距离，并在右侧屏幕悬浮显示四个标点的火控数据。
    """
    def __init__(self, root, region_manager, minimap_module, elevation_module, fps=30, config_file="config.json"):
        self.root = root
        self.region_manager = region_manager
        self.minimap = minimap_module
        self.elevation = elevation_module
        self.fps = fps

        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        self.is_enabled = False
        self._thread_running = False
        self.hud_thread = None
        self.is_fpp = True

        # 加载迫击炮标定参数
        self.a_param = 0.2
        self.b_param = 0.2
        self.fpp_dists = []
        self.fpp_ratios = []
        self.tpp_dists = []
        self.tpp_ratios = []

        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    data = config.get("mortar_config", {})
                    self.a_param = data.get("a_param", 0.2)
                    self.b_param = data.get("b_param", 0.2)
                    # 兼容两种键名
                    self.tpp_dists = data.get("tpp_dists", [])
                    self.tpp_ratios = data.get("tpp_ratios", data.get("tpp_elevations", []))
                    self.fpp_dists = data.get("fpp_dists", [])
                    self.fpp_ratios = data.get("fpp_ratios", data.get("fpp_elevations", []))

                    if len(self.tpp_dists) != len(self.tpp_ratios) or len(self.tpp_dists) == 0:
                        print("[迫击炮] TPP标定数据无效，将禁用高低补偿")
                        self.tpp_dists = []
                        self.tpp_ratios = []
                    if len(self.fpp_dists) != len(self.fpp_ratios):
                        print("[迫击炮] FPP标定数据无效，将禁用高低补偿")
                        self.fpp_dists = []
                        self.fpp_ratios = []
            except Exception as e:
                print(f"[迫击炮助手] 配置读取失败: {e}")

        self.color_map = {
            "Yellow": "#FBED21",
            "Orange": "#B3500D",
            "Blue": "#1A3EA3",
            "Green": "#109166"
        }

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

        self.overlay.update_idletasks()

        # 一次性强制最高层
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
        #     print(f"[迫击炮模块] HUD 置顶失败: {e}")

    def enable_module(self, enable: bool):
        self.is_enabled = enable
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.hud_thread = threading.Thread(target=self._hud_loop, daemon=True)
            self.hud_thread.start()
            print("[迫击炮模块] 数据汇编与 HUD 已启动")
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            self.canvas.delete("hud")
            print("[迫击炮模块] 数据汇编与 HUD 已停止")

    def _calculate_true_dist(self, measured_distance, measured_elevation):
        if self.is_fpp:
            dists = self.fpp_dists
            ratios = self.fpp_ratios
        else:
            dists = self.tpp_dists
            ratios = self.tpp_ratios

        # 无有效标定数据时直接返回原始距离
        if not dists or len(dists) < 2 or not ratios or len(ratios) < 2:
            return measured_distance

        try:
            flat_ground_elevation = np.interp(measured_distance, dists, ratios)
            delta_h = measured_elevation - flat_ground_elevation
            if delta_h > 0:
                true_distance = measured_distance - (self.a_param * delta_h * measured_distance)
            else:
                true_distance = measured_distance - (self.b_param * delta_h * measured_distance)
            return max(0.0, true_distance)
        except Exception as e:
            return measured_distance

    def _dim_color(self, hex_color, factor):
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1+radius, y1, x2-radius, y1,
            x2, y1, x2, y1+radius,
            x2, y2-radius, x2, y2,
            x2-radius, y2, x1+radius, y2,
            x1, y2, x1, y2-radius,
            x1, y1+radius, x1, y1
        ]
        self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _hud_loop(self):
        while self._thread_running:
            start_time = time.time()

            mini_dists = self.minimap.get_measured_distance()
            elev_ratios = self.elevation.get_measured_elevations()

            valid_colors = {color: (dist > 0.0) for color, dist in mini_dists.items()}
            self.elevation.set_valid_colors(valid_colors)


            # 计算 HUD 面板位置（小地图上方）
            minimap_rect = self.region_manager.get_real_region("minimap_region")
            if minimap_rect:
                panel_width = minimap_rect["width"]
                panel_height = 50
                panel_x = minimap_rect["left"]
                panel_y = minimap_rect["top"] - panel_height - 5
                if panel_y < 0:
                    panel_y = 0
                box_width = panel_width // 4
            else:
                # 回退位置
                box_w, box_h, spacing = 105, 50, 15
                total_width = 4 * box_w + 3 * spacing
                panel_x = self.screen_width - total_width - 25
                panel_y = self.screen_height * 0.465
                box_width = box_w

            hud_data = []
            for color_name, base_hex in self.color_map.items():
                m_dist = mini_dists.get(color_name, 0.0)
                e_ratio = elev_ratios.get(color_name, None)

                if m_dist <= 0:
                    text = "无标点"
                    bg_color = self._dim_color(base_hex, 0.3)
                elif m_dist < 121:
                    text = "距离过近"
                    bg_color = self._dim_color(base_hex, 0.3)
                elif e_ratio is None:
                    text = f"{m_dist:.0f}m"
                    bg_color = self._dim_color(base_hex, 0.7)
                else:
                    true_dist = self._calculate_true_dist(m_dist, e_ratio)
                    text = f"{true_dist:.0f}m"
                    bg_color = base_hex

                hud_data.append((text, bg_color))

            # self.root.after(0, self._render_hud, panel_x, panel_y, box_width, panel_height, hud_data)
            self.root.after(0, self._render_hud, hud_data)

            elapsed = time.time() - start_time
            sleep_time = max(0, (1.0 / self.fps) - elapsed)
            time.sleep(sleep_time)

    def _dim_color(self, hex_color, alpha_ratio=0.2):
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"#{int(r*alpha_ratio):02x}{int(g*alpha_ratio):02x}{int(b*alpha_ratio):02x}"

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [x1+radius, y1, x2-radius, y1, x2, y1, x2, y1+radius,
                  x2, y2-radius, x2, y2, x2-radius, y2, x1+radius, y2,
                  x1, y2, x1, y2-radius, x1, y1+radius, x1, y1]
        self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _render_hud(self, data):
        self.canvas.delete("hud")
        if not self._thread_running or not self.is_enabled:
            return

        box_w, box_h, spacing = 105, 50, 15
        total_width = 4 * box_w + 3 * spacing
        
        # X坐标起点，与大地图模块完全一致
        start_x = self.screen_width - total_width - 25
        
        # Y坐标起点，在大地图模块正下方
        # 大地图是 self.sh * 0.465 - box_h - 15，这里刚好衔接
        start_y = self.screen_height * 0.465 

        for i, (text, bg_color) in enumerate(data):
            x1 = start_x + i * (box_w + spacing)
            y1 = start_y
            x2 = x1 + box_w
            y2 = y1 + box_h

            # 绘制完全相同的 15px 圆角矩形
            self._draw_rounded_rect(x1, y1, x2, y2, radius=15, fill=bg_color, tags="hud")
            
            # 判断字体颜色和大小（未获取到距离时灰色，获取到时白色）
            font_size = 14 if text != "---" and "距离过近" not in text else 12
            text_color = "#FFFFFF" if text != "---" else "#7F8C8D"
            
            self.canvas.create_text(x1 + box_w/2, y1 + box_h/2, 
                                    text=text, 
                                    fill=text_color, 
                                    font=("Microsoft YaHei", font_size, "bold"), 
                                    tags="hud")