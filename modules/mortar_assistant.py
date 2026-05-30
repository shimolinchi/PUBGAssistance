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
    def __init__(self, root, screen_width, screen_height, minimap_module, elevation_module, fps=30, config_file="config.json"):
        self.root = root
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.fps = fps
        
        self.minimap = minimap_module
        self.elevation = elevation_module
        
        self.is_enabled = False
        self._thread_running = False
        self.hud_thread = None
        self.is_fpp = True
        
        self.a_param = 0.2
        self.b_param = 0.2
        self.tpp_dists = []
        self.tpp_elevations = []

        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    data = config.get("mortar_config", {})
                    
                    self.a_param = data.get("a_param", 0.2)
                    self.b_param = data.get("b_param", 0.2)
                    self.tpp_dists = data.get("tpp_dists", [])
                    self.tpp_elevations = data.get("tpp_elevations", [])
            except Exception as e:
                print(f"[迫击炮助手] 配置读取失败: {e}")

        # UI 颜色配置
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
        try:
            hwnd = int(self.overlay.frame(), 16)
            result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
            if result == 0:
                hwnd_alt = self.overlay.winfo_id()
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd_alt, 17)
        except Exception as e:
            print(f"[迫击炮模块] HUD 隐身 API 调用失败: {e}")

    def enable_module(self, enable: bool):
        """主开关：联动传感器启停与 HUD 渲染"""
        self.is_enabled = enable
        # self.minimap.set_enabled(enable)
        # self.elevation.set_enabled(enable)
        
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
        """核心解算函数"""
        dists = self.fpp_dists if self.is_fpp else self.tpp_dists
        ratios = self.fpp_ratios if self.is_fpp else self.tpp_ratios
        flat_ground_elevation = np.interp(measured_distance, dists, ratios)
        delta_h = measured_elevation - flat_ground_elevation
        if delta_h > 0:
            true_distance = measured_distance - (self.a_param * delta_h * measured_distance)
        else:
            true_distance = measured_distance - (self.b_param * delta_h * measured_distance)
        return true_distance

    def _dim_color(self, hex_color, factor):
        """模拟透明度：通过降低颜色亮度实现 (Factor: 0.0~1.0)"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Canvas 画圆角矩形的黑科技"""
        points = [x1+radius, y1, x2-radius, y1, x2, y1, x2, y1+radius,
                  x2, y2-radius, x2, y2, x2-radius, y2, x1+radius, y2,
                  x1, y2, x1, y2-radius, x1, y1+radius, x1, y1]
        self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _hud_loop(self):
        """数据读取与渲染线程"""
        while self._thread_running:
            start_time = time.time()
            
            # 读取最新数据
            mini_dists = self.minimap.get_measured_distance()
            elev_ratios = self.elevation.get_measured_elevations()

            valid_colors_for_elevation = {}
            for color_name, dist in mini_dists.items():
                # 距离大于0说明小地图上确实存在这个标点
                valid_colors_for_elevation[color_name] = (dist > 0.0) 
            
            # 把状态推给测高模块
            self.elevation.set_valid_colors(valid_colors_for_elevation)
            
            # 定位 HUD (右侧，偏下，位于小地图上方区域)
            # 你可以通过修改这两个值来自由调整面板在屏幕上的绝对位置
            box_w, box_h, spacing = 105, 50, 15
            total_width = 4 * box_w + 3 * spacing
            start_x = self.screen_width - total_width - 25 # 靠右 40 像素
            start_y = self.screen_height * 0.465             # 高度
            
            hud_data = []
            
            # 状态机判断
            for color_name, base_hex in self.color_map.items():
                m_dist = mini_dists.get(color_name, 0.0)
                e_ratio = elev_ratios.get(color_name, None)
                
                if m_dist <= 0:
                    text = "无标点"
                    bg_color = self._dim_color(base_hex, 0.3)  # 30% 不透明度
                elif m_dist < 121:
                    text = "距离过近"
                    bg_color = self._dim_color(base_hex, 0.3)  # 30% 不透明度
                elif e_ratio is None:
                    text = f"{m_dist:.0f}m"
                    bg_color = self._dim_color(base_hex, 0.7)  # 70% 不透明度
                else:
                    true_dist = self._calculate_true_dist(m_dist, e_ratio)
                    text = f"{true_dist:.0f}m"
                    bg_color = base_hex                        # 100% 不透明度
                    
                hud_data.append((text, bg_color))
            
            # 渲染到屏幕
            self.root.after(0, self._render_hud, start_x, start_y, box_w, box_h, spacing, hud_data)
            
            # 帧率控制
            elapsed = time.time() - start_time
            sleep_time = max(0, (1.0 / self.fps) - elapsed)
            time.sleep(sleep_time)

    def _render_hud(self, sx, sy, bw, bh, sp, data):
        if not self._thread_running: return
        self.canvas.delete("hud")
        
        text_color = "#CCCCCC"  # 模拟 80% 不透明度的白色字体
        
        for i, (text, bg_color) in enumerate(data):
            x1 = sx + i * (bw + sp)
            y1 = sy
            x2 = x1 + bw
            y2 = y1 + bh
            
            # 画圆角背景
            self._draw_rounded_rect(x1, y1, x2, y2, radius=15, fill=bg_color, tags="hud")
            
            # 画居中文本
            cx = x1 + bw / 2
            cy = y1 + bh / 2
            font_size = 14 if "m" in text else 12 # 纯数字字体大一点
            self.canvas.create_text(cx, cy, text=text, fill=text_color, font=("Microsoft YaHei", font_size, "bold"), tags="hud")