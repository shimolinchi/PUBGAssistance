import threading
import time
import numpy as np
import tkinter as tk
import ctypes
import json
import os

class RocketAssistant:
    """
    火箭筒/榴弹发射器 战术标尺辅助模块
    读取小地图距离，通过三次多项式自动拟合数据，在屏幕中心下方渲染动态刻度线。
    """
    def __init__(self, root, screen_width, screen_height, minimap_module, fps=30, config_file="config.json"):
        self.root = root
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.fps = fps
        self.minimap = minimap_module
        
        self.is_enabled = False
        self._thread_running = False
        self.hud_thread = None
        
        self.color_map = {
            "Yellow": "#E3D43C", "Orange": "#B3500D", 
            "Blue": "#1A3EA3", "Green": "#109166"
        }

        self.calib_dists = []
        self.calib_ratios = []
        self.end_y = self.screen_height * 0.9 # 默认值
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    data = config.get("rocket_config", {})
                    
                    # 排序逻辑保持不变，确保插值准确
                    raw_dists = data.get("calib_dists", [])
                    raw_ratios = data.get("calib_ratios", [])
                    
                    if len(raw_dists) == len(raw_ratios) and len(raw_dists) > 0:
                        sorted_pairs = sorted(zip(raw_dists, raw_ratios))
                        self.calib_dists = [p[0] for p in sorted_pairs]
                        self.calib_ratios = [p[1] for p in sorted_pairs]
                    
                    self.end_y = self.screen_height * data.get("end_y_ratio", 0.9)
            except Exception as e:
                print(f"[火箭筒助手] 配置加载失败: {e}")

        self.center_x = self.screen_width / 2
        self.center_y = self.screen_height / 2
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
        # self.minimap.set_enabled(enable)
        
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
        
        self.canvas.create_line(self.center_x, self.center_y, self.center_x, self.end_y, 
                                fill="white", width=1, tags="rocket_hud")
        
        h_line_width = 30 
        
        for item in data:
            c_hex = item["color"]
            ratio = item["ratio"]
            dist = item["distance"]
            if dist > 160:
                continue
            
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
            
            self.canvas.create_text(left_x - tri_w - 5, target_y, text=f"{dist:.0f}m", 
                                    fill=c_hex, font=("Consolas", 12, "bold"), anchor="e", tags="rocket_hud")