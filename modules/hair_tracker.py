import tkinter as tk
import threading
import time
import cv2
import numpy as np
import mss

class HairTracker:
    """内部组件：十字弩/VSS 圆形瞄准镜追踪器 (线程安全版，集成 RegionManager)"""
    
    def __init__(self, screen_width, screen_height, region_manager, show_debug=False):
        self.sw = screen_width
        self.sh = screen_height
        self.region_manager = region_manager
        self.show_debug = show_debug
        
        # 1. 默认兜底 ROI (兼容任意分辨率，防止未标定)
        self.monitor = {
            "top": int(self.sh * (208 / 1080.0)),
            "left": int(self.sw * (605 / 1920.0)),
            "width": int(self.sw * ((1299 - 605) / 1920.0)),
            "height": int(self.sh * ((878 - 208) / 1080.0))
        }
        
        # 2. 从 RegionManager 读取精准标定数据（crosshair_region）
        self._load_region_from_manager()
        
        # 强力填补黑洞的闭运算核
        self.close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
        # 消除零星白点的开运算核
        self.open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        
        self.cx = self.sw // 2
        self.cy = self.sh // 2
        self.is_found = False
        self.is_enabled = False
        self._thread_running = False

    def _load_region_from_manager(self):
        """从 RegionManager 获取 crosshair_region 的真实区域"""
        if not self.region_manager:
            return
        try:
            region = self.region_manager.get_real_region("crosshair_region")
            if region and region.get("width", 0) > 0 and region.get("height", 0) > 0:
                self.monitor = region
                print(f"[准星追踪] 已加载标定区域: {self.monitor}")
            else:
                print("[准星追踪] 未找到 crosshair_region，使用默认区域")
        except Exception as e:
            print(f"[准星追踪] 加载区域失败: {e}")

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
        
        if self.show_debug:
            cv2.namedWindow(debug_win_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(debug_win_name, 400, 400)

        with mss.mss() as sct:
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
                                
                                # 只有拟合度大于 0.7s，才承认这是一个瞄准镜！
                                if fit_ratio > 0.7:
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
                        cv2.waitKey(1)

                except Exception as e:
                    self.is_found = False
                    print(f"🔴 [VSS 视觉致命报错] {e}")
                    if self.show_debug:
                        cv2.waitKey(1)
                        
                time.sleep(0.015)
                
        if self.show_debug:
            try:
                cv2.destroyWindow(debug_win_name)
            except:
                pass