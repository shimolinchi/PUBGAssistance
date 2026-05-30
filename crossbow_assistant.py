import tkinter as tk
import threading
import time
import cv2
import numpy as np
import mss
import json
import os
from hair_tracker import HairTracker

class CrossbowAssistant:
    """PUBG 弩 专属战术助手 (对外主类)"""
    def __init__(self, root, screen_width, screen_height, minimap_module, fps=30, config_file="config.json"):
        self.root = root
        self.sw = screen_width
        self.sh = screen_height
        self.minimap = minimap_module
        self.fps = fps
        self.center_x = self.sw / 2
        self.center_y = self.sh / 2
        
        self.tracker = HairTracker(screen_width, screen_height, show_debug=True)
        self.is_enabled = False
        self._thread_running = False
        self.hud_thread = None
        
        # 加载配置
        self.calib_dists = []
        self.calib_drops_ratio = []
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    cfg = config.get("crossbow_config", {})
                    self.calib_dists = cfg.get("calib_dists", [])
                    self.calib_drops_ratio = cfg.get("calib_drops_ratio", [])
            except: pass
        
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
            import ctypes
            hwnd = int(self.overlay.frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception: pass

    def enable_module(self, enabled: bool):
        self.is_enabled = enabled
        self.tracker.enable_module(enabled)
        
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.hud_thread = threading.Thread(target=self._hud_loop, daemon=True)
            self.hud_thread.start()
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            self.canvas.delete("crossbow_hud")

    def _draw_hud(self, valid_targets):
        self.canvas.delete("crossbow_hud")
        if not self.is_enabled: return

        cx, cy, is_found = self.tracker.get_dynamic_center()

        if not is_found:
            warn_y = self.sh * 0.75
            self.canvas.create_text(self.sw/2, warn_y, text="[ 未检测到弩/VSS准星，图层已隐藏 ]", 
                                    fill="#E74C3C", font=("Microsoft YaHei", 12, "bold"), tags="crossbow_hud")
            return
        
        h_line_width = 30 

        for target in valid_targets:
            dist = target['dist']
            color = target['color']
            
            if dist <= 30.0 or dist > self.calib_dists[-1]:
                continue
                
            drop_ratio = np.interp(dist, self.calib_dists, self.calib_drops_ratio)
            drop_px = drop_ratio * self.sh
            target_y = cy + drop_px
            
            self.canvas.create_line(self.center_x - h_line_width, cy, self.center_x, cy, fill=color, width=1, tags="crossbow_hud")
            self.canvas.create_line(self.center_x - h_line_width, target_y, self.center_x, target_y, fill=color, width=1, tags="crossbow_hud")
            self.canvas.create_text(self.center_x - h_line_width - 5, target_y, text=f"{dist:.0f}m", fill=color, 
                                    font=("Consolas", 12, "bold"), anchor="e", tags="crossbow_hud")
            
    def _hud_loop(self):
        color_hex_map = {
            "Yellow": "#E3D43C", "Orange": "#B3500D", 
            "Blue": "#1A3EA3", "Green": "#109166"
        }
        while self._thread_running:
            mini_dists = self.minimap.get_measured_distance()
            valid_targets = []
            
            for color, dist in mini_dists.items():
                if dist > 0.0:
                    valid_targets.append({
                        "dist": dist,
                        "color": color_hex_map[color]
                    })
                    
            self.root.after(0, self._draw_hud, valid_targets)
            time.sleep(1.0 / self.fps)