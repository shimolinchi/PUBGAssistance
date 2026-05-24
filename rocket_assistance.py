import threading
import time
import numpy as np
import tkinter as tk
import ctypes

class RocketAssistance:
    """
    火箭筒/榴弹发射器 战术标尺辅助模块
    读取小地图距离，通过三次多项式自动拟合数据，在屏幕中心下方渲染动态刻度线。
    """
    def __init__(self, root, screen_width, screen_height, minimap_module, fps=30):
        self.root = root
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.fps = fps
        
        self.minimap = minimap_module
        self.is_enabled = False
        self._thread_running = False
        self.hud_thread = None
        
        self.color_map = {
            "Yellow": "#FBED21", 
            "Orange": "#B3500D", 
            "Blue": "#1A3EA3", 
            "Green": "#109166"
        }
        
        raw_ratios = [0.0648, 0.0532, 0.0856, 0.0949, 0.1157, 0.1319, 0.1435, 0.1667, 0.1852, 0.1968, 0.2054, 0.2361, 0.2523, 0.2894, 0.3333, 0.3819, 0.4190, 0.4907, 0.5301, 0.5972, 0.7222]
        raw_dists = [21.6, 16.4, 31.0, 38.8, 43.3, 51.1, 57.2, 63.3, 69.5, 77.1, 77.1, 84.7, 92.4, 101.7, 110.7, 120.0, 129.1, 138.3, 146.0, 155.2, 164.4]
        
        # 核心：将距离和比例打包，并严格按照距离从小到大排序 (插值法的必须要求)
        sorted_pairs = sorted(zip(raw_dists, raw_ratios))
        self.calib_dists = [p[0] for p in sorted_pairs]
        self.calib_ratios = [p[1] for p in sorted_pairs]

        # # ================= 弹道散点数据与自动拟合 =================
        # # Y轴：映射比例 (0~1)
        # self.calib_ratios = [0.0648, 0.0532, 0.0856, 0.0949, 0.1157, 0.1319, 0.1435, 0.1667, 0.1852, 0.1968, 0.2054, 0.2361, 0.2523, 0.2894, 0.3333, 0.3819, 0.4190, 0.4907, 0.5301, 0.5972, 0.7222]
        # # X轴：真实距离 (将前两个 0.0 替换为了推断出的 21.6 和 16.4)
        # self.calib_dists = [21.6, 16.4, 31.0, 38.8, 43.3, 51.1, 57.2, 63.3, 69.5, 77.1, 77.1, 84.7, 92.4, 101.7, 110.7, 120.0, 129.1, 138.3, 146.0, 155.2, 164.4]
        
        # # 核心：自动生成 3 次多项式系数，无需外部计算！
        # self.poly_coeffs = np.polyfit(self.calib_dists, self.calib_ratios, 5)
        
        # ================= 刻度尺 UI 坐标映射 =================
        self.center_x = self.screen_width / 2
        self.center_y = self.screen_height / 2
        
        # ratio 为 1 时的终点 Y 坐标 (距离屏幕最下方 0.1 倍屏幕高度)
        self.end_y = self.screen_height * 0.9 
        # 标尺的总长度 (像素)
        self.line_length = self.end_y - self.center_y

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
            pass

    def enable_module(self, enable: bool):
        self.is_enabled = enable
        self.minimap.set_enabled(enable)
        
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.hud_thread = threading.Thread(target=self._hud_loop, daemon=True)
            self.hud_thread.start()
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            self.canvas.delete("rocket_hud")

    def _calculate_drop_ratio(self, distance):
        """中值插值法解算 (极其稳定，无越界乱飞风险)"""
        # 如果距离超出你测量的最大值 (164.4m)，它会平滑保持最后一个测算点的斜率，或者截断
        ratio = np.interp(distance, self.calib_dists, self.calib_ratios)
        return max(0.0, min(1.0, ratio))

    def _hud_loop(self):
        while self._thread_running:
            start_time = time.time()
            
            mini_dists = self.minimap.get_measured_distance()
            hud_data = []
            
            for color_name, base_hex in self.color_map.items():
                dist = mini_dists.get(color_name, 0.0)
                
                if dist > 0:
                    ratio = self._calculate_drop_ratio(dist)
                    hud_data.append({
                        "color": base_hex,
                        "ratio": ratio,
                        "distance": dist
                    })
            
            self.root.after(0, self._render_hud, hud_data)
            
            elapsed = time.time() - start_time
            sleep_time = max(0, (1.0 / self.fps) - elapsed)
            time.sleep(sleep_time)

    def _render_hud(self, data):
        if not self._thread_running: return
        self.canvas.delete("rocket_hud")
        
        # 1. 绘制基准白线 (从中心画到 end_y)
        self.canvas.create_line(self.center_x, self.center_y, self.center_x, self.end_y, 
                                fill="white", width=1, tags="rocket_hud")
        
        h_line_width = 30 
        
        # 2. 绘制计算出的每个颜色目标的标识
        for item in data:
            c_hex = item["color"]
            ratio = item["ratio"]
            dist = item["distance"]
            
            # 将 0~1 的 ratio 投射到实际的屏幕坐标上
            target_y = self.center_y + (ratio * self.line_length)
            left_x = self.center_x - h_line_width
            
            # 画横线
            self.canvas.create_line(left_x, target_y, self.center_x, target_y, 
                                    fill=c_hex, width=1, tags="rocket_hud")
            
            # 画左侧指示小三角 (尖角向右)
            tri_w = 8
            tri_h = 10
            pt_tip = (left_x, target_y)
            pt_top = (left_x - tri_w, target_y - tri_h/2)
            pt_bot = (left_x - tri_w, target_y + tri_h/2)
            self.canvas.create_polygon(pt_tip, pt_top, pt_bot, fill=c_hex, outline="black", tags="rocket_hud")
            
            # (可选) 渲染距离数字，如果在视野中心觉得乱，可以删除这一行
            self.canvas.create_text(left_x - tri_w - 5, target_y, text=f"{dist:.0f}m", 
                                    fill=c_hex, font=("Consolas", 12, "bold"), anchor="e", tags="rocket_hud")