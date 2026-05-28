import tkinter as tk
import threading
import time
import cv2
import numpy as np
import mss

class VSSCrosshairTracker:
    """内部组件：VSS 透明掩膜模板追踪器 (精准匹配线条)"""
    def __init__(self, screen_width, screen_height, template_paths=["templates/vss_1.png", "templates/vss_2.png", "templates/vss_3.png", "templates/vss_4.png"]):
        self.sw = screen_width
        self.sh = screen_height
        
        # 搜索区域保持 80x80
        self.roi_w = 80
        self.roi_h = 60
        self.monitor = {
            "top": (self.sh // 2) - (self.roi_h // 2) - 12, 
            "left": (self.sw // 2) - (self.roi_w // 2),
            "width": self.roi_w,
            "height": self.roi_h
        }
        
        self.templates = []
        for path in template_paths:
            try:
                # 关键步骤：使用 IMREAD_UNCHANGED 读取带透明通道的 PNG
                img_bgra = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                if img_bgra is not None and img_bgra.shape[2] == 4:
                    # 1. 提取颜色通道和透明通道
                    bgr = img_bgra[:, :, :3]
                    alpha = img_bgra[:, :, 3]
                    gray_tpl = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                    
                    # 2. 制作掩膜 (Mask)：Alpha 值大于 128 的区域才参与匹配
                    _, mask = cv2.threshold(alpha, 128, 255, cv2.THRESH_BINARY)
                    
                    self.templates.append({
                        "img": gray_tpl,
                        "mask": mask,
                        "tw": img_bgra.shape[1],
                        "th": img_bgra.shape[0]
                    })
            except Exception as e:
                print(f"[VSS追踪器] 模板加载失败: {path}, {e}")

        self.cx, self.cy = self.sw // 2, self.sh // 2
        self.is_found = False
        self._thread_running = False

    def enable_module(self, enabled: bool):
        if enabled and not self._thread_running and self.templates:
            self._thread_running = True
            threading.Thread(target=self._tracking_loop, daemon=True).start()
        else:
            self._thread_running = False

    def get_dynamic_center(self):
        return self.cx, self.cy, self.is_found

    def _tracking_loop(self):
        with mss.MSS() as sct:
            while self._thread_running:
                try:
                    screenshot = sct.grab(self.monitor)
                    frame = np.array(screenshot)
                    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                    
                    best_val = 0.0
                    best_loc = None
                    best_tpl_idx = 0
                    
                    # 使用掩膜进行匹配
                    for i, tpl in enumerate(self.templates):
                        # matchTemplate 支持 mask 参数，这是解决透明图匹配的核心！
                        res = cv2.matchTemplate(gray_frame, tpl["img"], cv2.TM_CCORR_NORMED, mask=tpl["mask"])
                        _, max_val, _, max_loc = cv2.minMaxLoc(res)
                        
                        if max_val > best_val:
                            best_val = max_val
                            best_loc = max_loc
                            best_tpl_idx = i
                    
                    # 这里阈值设为 0.60，因为掩膜匹配极其精准，容错率极低
                    if best_val > 0.85:
                        self.is_found = True
                        tpl = self.templates[best_tpl_idx]
                        self.cx = self.monitor["left"] + best_loc[0] + (tpl["tw"] // 2)
                        # self.cy = self.monitor["top"] + best_loc[1] + (tpl["th"] // 2)
                        self.cy = self.monitor["top"] + best_loc[1]
                    else:
                        self.is_found = False
                        
                except Exception:
                    self.is_found = False
                time.sleep(0.015)

class VssAssistant:
    """PUBG VSS 专属战术助手 (对外主类)"""
    def __init__(self, root, screen_width, screen_height, minimap_module, fps=30):
        self.root = root
        self.sw = screen_width
        self.sh = screen_height

        self.center_x = self.sw // 2
        
        # 核心：直接引用外部传入的真实小地图模块
        self.minimap = minimap_module
        self.fps = fps
        
        # 内部实例化追踪器，对外部主控程序屏蔽复杂性
        self.tracker = VSSCrosshairTracker(screen_width, screen_height)
        
        self.is_enabled = False
        self._thread_running = False
        self.hud_thread = None
        
        # 完美对齐的 14 个高度映射数据
        self.calib_dists = [101.1, 122.5, 145.5, 167.0, 196.1, 217.5, 242.0, 258.9, 280.3, 311.0, 333.7, 347.8, 368.9, 406.2]
        raw_pixels = [1, 2, 3, 9, 11, 16, 19, 25, 26, 36, 38, 42, 47, 50]

        self.calib_drops_ratio = [p / 1080.0 for p in raw_pixels]
        
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
            import ctypes
            hwnd = int(self.overlay.frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception: pass

    def enable_module(self, enabled: bool):
        self.is_enabled = enabled
        # 联动启停内部的视觉引擎
        self.tracker.enable_module(enabled)
        
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.hud_thread = threading.Thread(target=self._hud_loop, daemon=True)
            self.hud_thread.start()
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            self.canvas.delete("vss_hud")

    def _draw_hud(self, valid_targets):
        self.canvas.delete("vss_hud")
        if not self.is_enabled: return

        # 1. 尝试获取动态准星坐标
        cx, cy, is_found = self.tracker.get_dynamic_center()

        # 2. 如果视觉引擎未能识别准星，直接拦截显示，并在屏幕下方告警
        if not is_found:
            warn_y = self.sh * 0.75
            self.canvas.create_text(self.sw/2, warn_y, text="[ 未检测到 VSS 准星，测距图层已隐藏 ]", 
                                    fill="#E74C3C", font=("Microsoft YaHei", 12, "bold"), tags="vss_hud")
            return
        
        h_line_width = 30 

        # 3. 正常绘制基于小地图真实距离的 UI
        for target in valid_targets:
            dist = target['dist']
            color = target['color']
            
            # 距离小于等于 100 米时不显示，防止近距离干扰
            if dist <= 100.0:
                continue
                
            # Numpy 中值法(线性插值) 获取下坠像素
            drop_px = np.interp(dist, self.calib_dists, self.calib_drops_ratio) * self.sh
            target_y = cy + drop_px
            
            
            # self.canvas.create_line(self.center_x - h_line_width, cy, self.center_x, cy, fill=color, width=1, tags="vss_hud")


            self.canvas.create_line(self.center_x - h_line_width, target_y, self.center_x, target_y, fill=color, width=1, tags="vss_hud")
            self.canvas.create_text(self.center_x - h_line_width - 5, target_y, text=f"{dist:.0f}m", fill=color, 
                                    font=("Consolas", 12, "bold"), anchor="e", tags="vss_hud")

    def _hud_loop(self):
        color_hex_map = {
            "Yellow": "#E9E39D", "Orange": "#B3500D", 
            "Blue": "#1A3EA3", "Green": "#109166"
        }
        while self._thread_running:
            mini_dists = self.minimap.get_measured_distance()
            valid_targets = []
            
            for color, dist in mini_dists.items():
                # 只有距离大于0（即确实在地图上标了该颜色的点），才加入渲染列表
                if dist > 0.0:
                    valid_targets.append({
                        "dist": dist,
                        "color": color_hex_map[color]
                    })
                    
            self.root.after(0, self._draw_hud, valid_targets)
            time.sleep(1.0 / self.fps)