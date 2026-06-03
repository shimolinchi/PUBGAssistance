import tkinter as tk
import threading
import time
import cv2
import numpy as np
import mss

class HairTracker:
    """内部组件：十字弩/VSS 圆形瞄准镜追踪器 (线程安全版)"""
    
    def __init__(self, screen_width, screen_height, show_debug=False, config_file="config.json"):
        self.sw = screen_width
        self.sh = screen_height
        self.show_debug = show_debug
        self.config_file = config_file
        
        # 1. 默认兜底 ROI (兼容任意分辨率，防止 config 丢失)
        self.monitor = {
            "top": int(self.sh * (208 / 1080.0)),
            "left": int(self.sw * (605 / 1920.0)),
            "width": int(self.sw * ((1299 - 605) / 1920.0)),
            "height": int(self.sh * ((878 - 208) / 1080.0))
        }
        
        # 2. 尝试从全局配置读取精准标定数据
        self._load_config()
        
        # 强力填补黑洞的闭运算核
        self.close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
        # 消除零星白点的开运算核
        self.open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        
        self.cx = self.sw // 2
        self.cy = self.sh // 2
        self.is_found = False
        self.is_enabled = False
        self._thread_running = False

    def _load_config(self):
        """从 config.json 读取视觉管理器的标定区域"""
        import os, json
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    regions = config.get("detection_regions", {})
                    
                    # 尝试读取我们在 RegionManager 中对应的名称
                    if "crosshair_region" in regions:
                        self.monitor = regions["crosshair_region"]
            except:
                pass

    def enable_module(self, enabled: bool):
        self.is_enabled = enabled
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            threading.Thread(target=self._tracking_loop, daemon=True).start()
        elif not self.is_enabled:
            self._thread_running = False

    def get_dynamic_center(self):
        return self.cx, self.cy, self.is_found

    def _tracking_loop(self):
        debug_win_name = "Crossbow/VSS Vision Debug"
        
        # 核心修复：在子线程内部独立创建和管理 OpenCV 窗口，绝不和主程序冲突
        if self.show_debug:
            cv2.namedWindow(debug_win_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(debug_win_name, 400, 400)

        with mss.MSS() as sct:
            while self._thread_running:
                try:
                    screenshot = sct.grab(self.monitor)
                    frame = np.array(screenshot)
                    
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                    
                    # 1. 阈值分割：游戏画面变白，黑框(通常极黑)变黑
                    _, thresh = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
                    
                    # 2. 形态学清理
                    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, self.open_kernel)
                    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, self.close_kernel)
                    
                    # 3. 提取轮廓 (仅提取最外层)
                    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    best_circle = None
                    
                    if contours:
                        largest_c = max(contours, key=cv2.contourArea)
                        area = cv2.contourArea(largest_c)
                        roi_area = self.monitor["width"] * self.monitor["height"]
                        
                        # 只要白区占据超过 8% 的面积就认为是开镜
                        if roi_area * 0.08 < area < roi_area * 0.85:
                            (x, y), radius = cv2.minEnclosingCircle(largest_c)
                            circle_area = np.pi * (radius ** 2)
                            
                            if circle_area > 0:
                                fit_ratio = area / circle_area
                                
                                # 只有拟合度大于 0.82，才承认这是一个瞄准镜！
                                if fit_ratio > 0.82:
                                    self.cx = self.monitor["left"] + int(x)
                                    self.cy = self.monitor["top"] + int(y)
                                    self.is_found = True
                                    best_circle = (int(x), int(y), int(radius))
                        else:
                            self.is_found = False
                    else:
                        self.is_found = False
                        
                    # 4. 线程内安全渲染调试窗口
                    if self.show_debug:
                        debug_frame = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
                        
                        if self.is_found and best_circle:
                            bx, by, br = best_circle
                            cv2.circle(debug_frame, (bx, by), br, (0, 0, 255), 3)
                            cv2.drawMarker(debug_frame, (bx, by), (0, 255, 0), cv2.MARKER_CROSS, 20, 2)
                            
                        status = "LOCKED" if self.is_found else "SEARCHING"
                        color = (0, 255, 0) if self.is_found else (0, 0, 255)
                        cv2.putText(debug_frame, status, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                        
                        cv2.imshow(debug_win_name, debug_frame)
                        cv2.waitKey(1)  # 保持窗口响应的关键

                except Exception as e:
                    self.is_found = False
                    print(f"🔴 [VSS 视觉致命报错] {e}")  # 如果出错，控制台必定打印
                    # 即使出错也要刷新窗口防止卡死
                    if self.show_debug:
                        cv2.waitKey(1)
                        
                time.sleep(0.015)
                
        # 退出循环后安全销毁窗口
        if self.show_debug:
            try:
                cv2.destroyWindow(debug_win_name)
            except: pass