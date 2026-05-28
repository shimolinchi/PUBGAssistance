import tkinter as tk
import threading
import time
import cv2
import numpy as np
import mss
import json
import os
import math
import ctypes

# ================= 颜色配置 (HSV) =================
# 统一使用经过高精度标定的 HSV 阈值
# COLOR_HSV = {
#     "Yellow": {
#         "lower": [26, 150, 160], 
#         "upper": [30, 255, 255], 
#         "hex": "#E3D43C"
#     },
#     "Orange": {
#         "lower": [10, 160, 160], 
#         "upper": [14, 255, 255], 
#         "hex": "#B3500D"
#     },
#     "Blue": {
#         "lower": [110, 120, 160], 
#         "upper": [114, 255, 255], 
#         "hex": "#1A3EA3"
#     },
#     "Green": {
#         "lower": [78, 150, 120], 
#         "upper": [82, 255, 255], 
#         "hex": "#109166"
#     }
# }

class MinimapRadarModule:
    """
    PUBG 小地图视觉雷达子模块
    负责：独立截屏、识别标点(基于HSV)、换算距离、管理防截图透明画板
    """
    def __init__(self, root, config_file="minimap_config.json"):
        self.root = root  
        self.config_file = config_file
        self.monitor = self.load_config()
        
        self.is_enabled = True     
        self.show_display = True      
        
        self._thread_running = False
        self.radar_thread = None
        self.latest_targets = []      
        
        self.calib_state = "IDLE"
        self.calib_pt1 = None
        
        self.overlay = None
        self.canvas = None
        self._init_overlay()

        self.measured_distance = {
            "Yellow": 0.0,
            "Orange": 0.0,
            "Blue": 0.0,
            "Green": 0.0
        }

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f).get("minimap_rect")
            except: pass
        return None

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump({"minimap_rect": self.monitor}, f)

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)
        
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Button-1>", self._on_canvas_left_click)
        self.canvas.bind("<Button-3>", self._on_canvas_right_click)
        
        self.overlay.update_idletasks()
        try:
            hwnd = int(self.overlay.frame(), 16)
            result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
            if result == 0:
                hwnd_alt = self.overlay.winfo_id()
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd_alt, 17)
        except Exception as e:
            print(f"[雷达模块] 窗口隐身 API 调用失败: {e}")

    def set_enabled(self, enabled: bool):
        # 记录用户的期望状态
        self.is_enabled = enabled
        
        # 如果期望开启，且线程没在跑，则启动
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.radar_thread = threading.Thread(target=self._cv_process_loop, daemon=True)
            self.radar_thread.start()
            print("[雷达模块] 视觉线程已启动")
            
        # 如果期望关闭，且线程正在跑，则停止
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            # 等待一小会儿让线程自然退出，避免暴力关闭
            time.sleep(0.1) 
            self.canvas.delete("marker")
            self.latest_targets = []
            print("[雷达模块] 视觉线程已停止")

    def set_display(self, show: bool):
        self.show_display = show
        if not self.show_display:
            self.canvas.delete("marker")

    def get_latest_targets(self):
        return self.latest_targets

    def get_measured_distance(self):
        return self.measured_distance

    def trigger_calibration(self):
        self.calib_state = "CALIB_1"
        self.overlay.attributes("-transparentcolor", "")
        self.overlay.attributes("-alpha", 0.4)
        self.canvas.config(bg="#111111", cursor="crosshair")
        self.canvas.delete("all")
        print("[雷达模块] 请左键点击小地图左上角...")

    def _on_canvas_left_click(self, event):
        if self.calib_state == "CALIB_1":
            self.calib_pt1 = (event.x, event.y)
            self.calib_state = "CALIB_2"
            self.canvas.create_oval(event.x-3, event.y-3, event.x+3, event.y+3, fill="red", tags="temp_calib")
            print("[雷达模块] 请左键点击小地图右下角...")
            
        elif self.calib_state == "CALIB_2":
            x1, y1 = self.calib_pt1
            x2, y2 = event.x, event.y
            
            side = max(abs(x2 - x1), abs(y2 - y1))
            left, top = min(x1, x2), min(y1, y2)
            
            self.monitor = {"top": top, "left": left, "width": side, "height": side}
            self.save_config()
            
            self._exit_calibration()
            print(f"[雷达模块] 标定完成! 区域: {self.monitor}")

    def _on_canvas_right_click(self, event):
        if self.calib_state != "IDLE":
            self._exit_calibration()
            print("[雷达模块] 校准已取消")

    def _exit_calibration(self):
        self.calib_state = "IDLE"
        self.overlay.attributes("-alpha", 1.0)
        self.overlay.attributes("-transparentcolor", "black")
        self.canvas.config(bg="black", cursor="arrow")
        self.canvas.delete("temp_calib")

    def _draw_markers(self, points):
        if not self._thread_running or not self.show_display: 
            return
        self.canvas.delete("marker")
        
        if self.monitor:
            cx = self.monitor["left"] + (self.monitor["width"] // 2)
            cy = self.monitor["top"] + (self.monitor["height"] // 2)
            self.canvas.create_line(cx-6, cy, cx+6, cy, fill="black", width=4, tags="marker")
            self.canvas.create_line(cx, cy-6, cx, cy+6, fill="black", width=4, tags="marker")
            self.canvas.create_line(cx-6, cy, cx+6, cy, fill="white", width=2, tags="marker")
            self.canvas.create_line(cx, cy-6, cx, cy+6, fill="white", width=2, tags="marker")
        
        for pt in points:
            ax, ay, color = pt['x'], pt['y'], pt['color']
            self.canvas.create_oval(ax-3, ay-3, ax+3, ay+3, fill=color, outline="black", tags="marker")
            self.canvas.create_rectangle(ax-10, ay-20, ax+10, ay, outline=color, width=2, tags="marker")
            self.canvas.create_text(ax, ay+15, text=f"{pt['dist']:.1f}m", fill=color, font=("Arial", 12, "bold"), tags="marker")
    
    def _cv_process_loop(self):
        with mss.MSS() as sct:
            while self._thread_running:
                try:
                    if not self.monitor:
                        time.sleep(0.1)
                        continue
                    
                    screenshot = sct.grab(self.monitor)
                    frame_bgra = np.array(screenshot)
                    frame_bgr = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)
                    
                    frame_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
                    
                    side_len = self.monitor["width"]
                    center_local_x, center_local_y = side_len // 2, side_len // 2
                    
                    current_targets = []
                    current_frame_distances = {
                        "Yellow": 0.0, "Orange": 0.0, "Blue": 0.0, "Green": 0.0
                    }
                    
                    for color_name, config in self.colors.items():
                        lower = np.array(config["lower"], dtype=np.uint8)
                        upper = np.array(config["upper"], dtype=np.uint8)
                        
                        mask = cv2.inRange(frame_hsv, lower, upper)
                        
                        kernel = np.ones((5, 5), np.uint8)
                        mask_closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                        contours, _ = cv2.findContours(mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        
                        for cnt in contours:
                            area = cv2.contourArea(cnt)
                            if 10 < area < 400:
                                x, y, w, h = cv2.boundingRect(cnt)
                                
                                if w == 0: continue
                                aspect_ratio = h / float(w)
                                
                                if aspect_ratio < 1.1 or aspect_ratio > 2.0:
                                    continue
                                
                                pt_local_x = x + (w // 2)
                                pt_local_y = y + h
                                
                                dist_px = math.sqrt((pt_local_x - center_local_x)**2 + (pt_local_y - center_local_y)**2)
                                real_dist = (dist_px / side_len) * 700.0

                                current_frame_distances[color_name] = real_dist
                                
                                abs_x = self.monitor["left"] + pt_local_x
                                abs_y = self.monitor["top"] + pt_local_y
                                
                                current_targets.append({
                                    'x': abs_x, 'y': abs_y, 
                                    'dist': real_dist, 'color': config["hex"]
                                })

                    self.measured_distance = current_frame_distances
                    self.latest_targets = current_targets
                    
                    if self.show_display and self.calib_state == "IDLE":
                        self.root.after(0, self._draw_markers, current_targets)
                        
                except Exception as e:
                    # 在控制台打印具体的错误原因，方便你排查
                    print(f"[雷达模块线程错误] {e}")
                    # break 
                    
                time.sleep(0.03)

class MinimapRadarModule:
    """PUBG 小地图视觉雷达子模块"""
    def __init__(self, root, config_file="config.json"):
        self.root = root  
        self.config_file = config_file
        
        # 将原本在文件顶部的字典转移到这里，作为保底的默认配置
        self.default_colors = {
            "Yellow": {"lower": [26, 150, 160], "upper": [30, 255, 255], "hex": "#E3D43C"},
            "Orange": {"lower": [10, 160, 160], "upper": [14, 255, 255], "hex": "#B3500D"},
            "Blue": {"lower": [110, 120, 160], "upper": [114, 255, 255], "hex": "#1A3EA3"},
            "Green": {"lower": [78, 150, 120], "upper": [82, 255, 255], "hex": "#109166"}
        }
        
        # 同时加载标定框和颜色配置
        self.monitor, self.colors = self.load_config()
        
        self.is_enabled = True     
        self.show_display = True      
        self._thread_running = False
        self.radar_thread = None
        self.latest_targets = []      
        self.calib_state = "IDLE"
        self.calib_pt1 = None
        self.overlay = None
        self.canvas = None
        self._init_overlay()
        self.measured_distance = {"Yellow": 0.0, "Orange": 0.0, "Blue": 0.0, "Green": 0.0}

    def load_config(self):
        monitor = None
        colors = self.default_colors
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    monitor = config_data.get("minimap_rect")
                    # 读取配置文件里的颜色，如果没有则使用默认颜色
                    colors = config_data.get("minimap_colors", self.default_colors)
            except: 
                pass
        return monitor, colors

    def save_config(self):
        config_data = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except:
                pass
        
        # 分别写入框选数据和颜色数据
        config_data["minimap_rect"] = self.monitor
        config_data["minimap_colors"] = self.colors
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)
        
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Button-1>", self._on_canvas_left_click)
        self.canvas.bind("<Button-3>", self._on_canvas_right_click)
        
        self.overlay.update_idletasks()
        try:
            hwnd = int(self.overlay.frame(), 16)
            result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
            if result == 0:
                hwnd_alt = self.overlay.winfo_id()
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd_alt, 17)
        except Exception as e:
            print(f"[雷达模块] 窗口隐身 API 调用失败: {e}")

    def set_enabled(self, enabled: bool):
        # 记录用户的期望状态
        self.is_enabled = enabled
        
        # 如果期望开启，且线程没在跑，则启动
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.radar_thread = threading.Thread(target=self._cv_process_loop, daemon=True)
            self.radar_thread.start()
            print("[雷达模块] 视觉线程已启动")
            
        # 如果期望关闭，且线程正在跑，则停止
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            # 等待一小会儿让线程自然退出，避免暴力关闭
            time.sleep(0.1) 
            self.canvas.delete("marker")
            self.latest_targets = []
            print("[雷达模块] 视觉线程已停止")

    def set_display(self, show: bool):
        self.show_display = show
        if not self.show_display:
            self.canvas.delete("marker")

    def get_latest_targets(self):
        return self.latest_targets

    def get_measured_distance(self):
        return self.measured_distance

    def trigger_calibration(self):
        self.calib_state = "CALIB_1"
        self.overlay.attributes("-transparentcolor", "")
        self.overlay.attributes("-alpha", 0.4)
        self.canvas.config(bg="#111111", cursor="crosshair")
        self.canvas.delete("all")
        print("[雷达模块] 请左键点击小地图左上角...")

    def _on_canvas_left_click(self, event):
        if self.calib_state == "CALIB_1":
            self.calib_pt1 = (event.x, event.y)
            self.calib_state = "CALIB_2"
            self.canvas.create_oval(event.x-3, event.y-3, event.x+3, event.y+3, fill="red", tags="temp_calib")
            print("[雷达模块] 请左键点击小地图右下角...")
            
        elif self.calib_state == "CALIB_2":
            x1, y1 = self.calib_pt1
            x2, y2 = event.x, event.y
            
            side = max(abs(x2 - x1), abs(y2 - y1))
            left, top = min(x1, x2), min(y1, y2)
            
            self.monitor = {"top": top, "left": left, "width": side, "height": side}
            self.save_config()
            
            self._exit_calibration()
            print(f"[雷达模块] 标定完成! 区域: {self.monitor}")

    def _on_canvas_right_click(self, event):
        if self.calib_state != "IDLE":
            self._exit_calibration()
            print("[雷达模块] 校准已取消")

    def _exit_calibration(self):
        self.calib_state = "IDLE"
        self.overlay.attributes("-alpha", 1.0)
        self.overlay.attributes("-transparentcolor", "black")
        self.canvas.config(bg="black", cursor="arrow")
        self.canvas.delete("temp_calib")

    def _draw_markers(self, points):
        if not self._thread_running or not self.show_display: 
            return
        self.canvas.delete("marker")
        
        if self.monitor:
            cx = self.monitor["left"] + (self.monitor["width"] // 2)
            cy = self.monitor["top"] + (self.monitor["height"] // 2)
            self.canvas.create_line(cx-6, cy, cx+6, cy, fill="black", width=4, tags="marker")
            self.canvas.create_line(cx, cy-6, cx, cy+6, fill="black", width=4, tags="marker")
            self.canvas.create_line(cx-6, cy, cx+6, cy, fill="white", width=2, tags="marker")
            self.canvas.create_line(cx, cy-6, cx, cy+6, fill="white", width=2, tags="marker")
        
        for pt in points:
            ax, ay, color = pt['x'], pt['y'], pt['color']
            self.canvas.create_oval(ax-3, ay-3, ax+3, ay+3, fill=color, outline="black", tags="marker")
            self.canvas.create_rectangle(ax-10, ay-20, ax+10, ay, outline=color, width=2, tags="marker")
            self.canvas.create_text(ax, ay+15, text=f"{pt['dist']:.1f}m", fill=color, font=("Arial", 12, "bold"), tags="marker")
    
    def _apply_nms(self, candidates, min_dist):
        final = []
        for c in candidates:
            if not any(math.sqrt((c['x'] - f['x'])**2 + (c['y'] - f['y'])**2) < min_dist for f in final):
                final.append(c)
        return final

    def _cv_process_loop(self):
        # 1. 预先加载所有模板 (从 templates/pnt 文件夹)
        tpl_list = []
        tpl_dir = "templates/pnt"
        if os.path.exists(tpl_dir):
            for f in os.listdir(tpl_dir):
                if f.endswith('.png'):
                    # 读取带有 Alpha 透明通道的图像 (4通道)
                    img_bgra = cv2.imread(os.path.join(tpl_dir, f), cv2.IMREAD_UNCHANGED)
                    if img_bgra is not None and img_bgra.shape[2] == 4:
                        # 提取 Alpha 通道：透明的地方是 0，黑色色块的地方是 >0 的值
                        alpha = img_bgra[:, :, 3]
                        
                        # 强制二值化：将色块部分变成 255 (纯白)，透明背景变成 0 (纯黑)
                        _, binary_tpl = cv2.threshold(alpha, 128, 255, cv2.THRESH_BINARY)
                        
                        tpl_list.append({
                            "img": binary_tpl,
                            "w": binary_tpl.shape[1],
                            "h": binary_tpl.shape[0]
                        })
        
        with mss.MSS() as sct:
            while self._thread_running:
                try:
                    if not self.monitor:
                        time.sleep(0.1)
                        continue
                    
                    screenshot = sct.grab(self.monitor)
                    frame_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
                    frame_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
                    
                    side_len = self.monitor["width"]
                    center_local = side_len // 2
                    
                    candidates = []
                    current_distances = {c: 0.0 for c in self.colors.keys()}
                    
                    # 2. 遍历四个颜色，分别生成二值图并进行模板匹配
                    for color_name, config in self.colors.items():
                        # 获取当前颜色的二值化图 (匹配到的颜色为 255，其余为 0)
                        lower = np.array(config["lower"], dtype=np.uint8)
                        upper = np.array(config["upper"], dtype=np.uint8)
                        color_mask = cv2.inRange(frame_hsv, lower, upper)
                        
                        # 3. 将当前颜色的二值图与所有模板进行匹配
                        for tpl in tpl_list:
                            # 两个二值图的纯净匹配，使用 TM_CCOEFF_NORMED 最准
                            res = cv2.matchTemplate(color_mask, tpl["img"], cv2.TM_CCOEFF_NORMED)
                            
                            # 匹配阈值 (因为是二值匹配，容错率很高，通常 0.75-0.85 之间即可)
                            threshold = 0.75 
                            loc = np.where(res >= threshold)
                            
                            for pt in zip(*loc[::-1]):
                                candidates.append({
                                    'x': pt[0] + (tpl["w"] // 2), 
                                    'y': pt[1] + tpl["h"], # 锚点要求：对象下方中间
                                    'color_name': color_name,
                                    'hex': config["hex"]
                                })
                    
                    # 4. 去重逻辑 (NMS)：过滤掉同一个标点匹配出的多个相近坐标
                    final_targets = []
                    min_dist = 15 # 判定为同一个标点的最小像素距离
                    
                    for c in candidates:
                        is_duplicate = False
                        for f in final_targets:
                            # 计算与已存在点的距离
                            if math.sqrt((c['x'] - f['x'])**2 + (c['y'] - f['y'])**2) < min_dist:
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            final_targets.append(c)
                            
                    # 5. 更新最终的距离和目标信息
                    current_targets = []
                    for pt in final_targets:
                        dist_px = math.sqrt((pt['x'] - center_local)**2 + (pt['y'] - center_local)**2)
                        real_dist = (dist_px / side_len) * 700.0
                        
                        current_distances[pt['color_name']] = real_dist
                        
                        current_targets.append({
                            'x': self.monitor["left"] + pt['x'], 
                            'y': self.monitor["top"] + pt['y'], 
                            'dist': real_dist, 
                            'color': pt['hex']
                        })
                        
                    self.measured_distance = current_distances
                    self.latest_targets = current_targets
                    
                    # 6. UI渲染
                    if self.show_display and self.calib_state == "IDLE":
                        self.root.after(0, self._draw_markers, current_targets)
                            
                except Exception as e:
                    print(f"[雷达模块线程错误] {e}")
                
                time.sleep(0.03)