import tkinter as tk
import threading
import time
import cv2
import numpy as np
import mss

class CrossbowCrosshairTracker:
    """内部组件：弩 多模板动态准星追踪器 (支持明暗双模板)"""
    def __init__(self, screen_width, screen_height, template_paths=["template/crossbow_1.png", "template/crossbow_2.png", "template/crossbow_3.png, template/crossbow_4.png, template/crossbow_5.png, template/crossbow_6.png, template/crossbow_7.png, template/crossbow_8.png, template/crossbow_9.png, template/crossbow_10.png, template/crossbow_11.png, template/crossbow_12.png, template/crossbow_13.png, template/crossbow_14.png, template/crossbow_15.png, template/crossbow_16.png, template/crossbow_17.png, template/crossbow_18.png, template/crossbow_19.png, template/crossbow_20.png"]):
        self.sw = screen_width
        self.sh = screen_height


        
        self.roi_w = 80
        self.roi_h = 80
        self.monitor = {
            "top": (self.sh // 2) - (self.roi_h // 2) - 20, 
            "left": (self.sw // 2) - (self.roi_w // 2),
            "width": self.roi_w,
            "height": self.roi_h
        }
        
        # 动态加载传入的多个模板 (明亮环境 + 幽暗环境)
        self.templates = []
        for path in template_paths:
            try:
                # 1. 必须使用 IMREAD_UNCHANGED 读取，保留透明通道 (BGRA)
                img_bgra = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                
                if img_bgra is not None:
                    # 检查图片是否有 4 个通道 (是否真的有透明背景)
                    if img_bgra.shape[2] == 4:
                        # 提取前三个通道 (BGR) 并转为灰度图，作为匹配主体
                        img_bgr = img_bgra[:, :, :3]
                        img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                        
                        # 提取第四个通道 (Alpha) 作为掩膜 Mask！
                        # (透明的地方是 0，有图案的地方是 255)
                        img_mask = img_bgra[:, :, 3]
                    else:
                        print(f"⚠️ 警告: {path} 没有透明通道，请确认是否导出了带 Alpha 的 PNG！")
                        continue # 跳过无效图片
                    
                    # 光学中心微调 (可以沿用之前的对齐逻辑)
                    opt_x = img_gray.shape[1] // 2
                    opt_y = img_gray.shape[0] // 2
                    
                    self.templates.append({
                        "img": img_gray,   # 灰度图主体
                        "mask": img_mask,  # 透明通道掩膜
                        "tw": img_gray.shape[1],
                        "th": img_gray.shape[0],
                        "opt_x": opt_x,
                        "opt_y": opt_y
                    })
            except Exception as e:
                print(f"加载出错: {e}")
            
        if not self.templates:
            print("[弩追踪器] ⚠️ 警告: 未找到任何准星模板图片！请确保同目录下存在截图。")

        self.cx = self.sw // 2
        self.cy = self.sh // 2
        self.is_found = False
        
        self.is_enabled = False
        self._thread_running = False

    def enable_module(self, enabled: bool):
        self.is_enabled = enabled
        if self.is_enabled and not self._thread_running and self.templates:
            self._thread_running = True
            threading.Thread(target=self._tracking_loop, daemon=True).start()
            print("[弩追踪器] 视觉引擎已启动，正在监听准星...")
        elif not self.is_enabled:
            self._thread_running = False

    def get_dynamic_center(self):
        """返回当前的准星绝对坐标，以及是否找到的布尔值"""
        return self.cx, self.cy, self.is_found
    
    def _tracking_loop(self):
        with mss.MSS() as sct:
            while self._thread_running:
                try:
                    screenshot = sct.grab(self.monitor)
                    frame = np.array(screenshot)
                    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                    
                    # 2. 顶帽变换（剥离大面积背景）
                    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
                    tophat_frame = cv2.morphologyEx(gray_frame, cv2.MORPH_TOPHAT, kernel)
                    
                    # =======================================================
                    # 【核心修复 1：二值化过滤】
                    # 把灰度值低于 50 的噪点（云彩边缘、树叶缝隙）全部斩成纯黑 (0)
                    # 只有 UI 层那种极其锐利明亮的线条才能超过 50 变成纯白 (255)
                    # (这里的 50 是经验值，如果你觉得还误报，可以提高到 80 甚至 100)
                    _, enhanced_frame = cv2.threshold(tophat_frame, 50, 255, cv2.THRESH_BINARY)
                    # =======================================================
                    
                    # 因为我们换了算法，现在找的是“最小值”，所以初始值设为无穷大
                    best_val = float('inf') 
                    best_loc = None
                    best_opt_x = 0
                    best_opt_y = 0
                    
                    for tpl in self.templates:
                        # =======================================================
                        # 【核心修复 2：换用极严苛的 SQDIFF_NORMED 算法】
                        res = cv2.matchTemplate(enhanced_frame, tpl["img"], cv2.cv2.TM_SQDIFF_NORMED, mask=tpl["mask"])
                        
                        # 找最小值 (min_val)，越接近 0 说明差异越小，匹配度越高！
                        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                        
                        if min_val < best_val:
                            best_val = min_val
                            best_loc = min_loc  # 注意这里取 min_loc
                            best_opt_x = tpl["opt_x"]
                            best_opt_y = tpl["opt_y"]
                    
                    # =======================================================
                    # 【判定逻辑反转】
                    # best_val 代表差异度。0.0 是完美，我们允许有一点点误差，比如差异小于 0.15 (相当于相似度 > 85%)
                    if best_val < 0.15: 
                        self.is_found = True
                        match_x, match_y = best_loc
                        self.cx = self.monitor["left"] + match_x + best_opt_x
                        self.cy = self.monitor["top"] + match_y + best_opt_y
                        # 调试阶段可以打印一下，看看锁定时真正的差异值是多少
                        # print(f"🎯 锁定! 误差率: {best_val:.3f}") 
                    else:
                        self.is_found = False
                        # print(f"❌ 丢失! 最小误差率: {best_val:.3f}")
                        
                except Exception:
                    self.is_found = False
                    
                time.sleep(0.015) 

class ColorCrosshairTracker:
    """内部组件：基于 HSV 颜色的极简动态准星追踪器 (彻底抛弃模板)"""
    def __init__(self, screen_width, screen_height):
        self.sw = screen_width
        self.sh = screen_height
        
        # 搜索框 100x80，微调向上偏移
        self.roi_w = 80
        self.roi_h = 80
        self.monitor = {
            "top": (self.sh // 2) - (self.roi_h // 2) - 20, 
            "left": (self.sw // 2) - (self.roi_w // 2),
            "width": self.roi_w,
            "height": self.roi_h
        }
        
        # =========================================================
        # 核心参数：天蓝色/青色 (Cyan) 的 HSV 范围
        # 根据你提供的图片，准星颜色在 H=85~100 之间，饱和度和亮度都很高
        # =========================================================
        self.lower_cyan = np.array([88, 100, 150])
        self.upper_cyan = np.array([94, 200, 255])

        self.cx = self.sw // 2
        self.cy = self.sh // 2
        self.is_found = False
        self.is_enabled = False
        self._thread_running = False

    def enable_module(self, enabled: bool):
        self.is_enabled = enabled
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            threading.Thread(target=self._tracking_loop, daemon=True).start()
        elif not self.is_enabled:
            self._thread_running = False

    def get_dynamic_center(self):
        """返回当前的准星绝对坐标，以及是否找到的布尔值"""
        return self.cx, self.cy, self.is_found
    
    def _tracking_loop(self):
        with mss.MSS() as sct:
            while self._thread_running:
                try:
                    # 1. 抓取屏幕中心区域
                    screenshot = sct.grab(self.monitor)
                    frame = np.array(screenshot)
                    
                    # 2. 转换为 HSV 色彩空间 (这一步你小地图模块里用过，非常稳)
                    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR) # 先转 BGR
                    hsv_frame = cv2.cvtColor(hsv_frame, cv2.COLOR_BGR2HSV) # 再转 HSV
                    
                    # 3. 极简魔法：提取天蓝色像素，其他颜色全部抹黑！
                    mask = cv2.inRange(hsv_frame, self.lower_cyan, self.upper_cyan)
                    
                    # 4. 找到天蓝色色块的外轮廓
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    if contours:
                        # 找到面积最大的天蓝色块 (防止极小噪点干扰)
                        largest_contour = max(contours, key=cv2.contourArea)
                        area = cv2.contourArea(largest_contour)
                        
                        # 只要这块天蓝色大于 5 个像素，我们就认定它是准星
                        if area > 5:
                            x, y, w, h = cv2.boundingRect(largest_contour)
                            
                            # 计算这个天蓝色十字的绝对物理中心！
                            self.cx = self.monitor["left"] + x + (w // 2)
                            self.cy = self.monitor["top"] + y + (h // 2)
                            self.is_found = True
                        else:
                            self.is_found = False
                    else:
                        self.is_found = False
                        
                except Exception:
                    self.is_found = False
                    
                time.sleep(0.015)

class UniversalCrossbowTracker:
    """内部组件：全色彩通用的边缘准星追踪器 (支持任何色盲模式)"""
    def __init__(self, screen_width, screen_height, template_paths=["template/crossbow_1.png"]):
        self.sw = screen_width
        self.sh = screen_height
        
        self.roi_w = 100
        self.roi_h = 80
        self.monitor = {
            "top": (self.sh // 2) - (self.roi_h // 2) - 20, 
            "left": (self.sw // 2) - (self.roi_w // 2),
            "width": self.roi_w,
            "height": self.roi_h
        }
        
        self.templates = []
        for path in template_paths:
            try:
                # 1. 保留透明通道读取
                img_bgra = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                if img_bgra is not None and img_bgra.shape[2] == 4:
                    # 2. 提取 Alpha 通道（透明部分是 0，准星部分是 255）
                    mask = img_bgra[:, :, 3]
                    
                    # 3. 【核心魔法】：提取模板的边缘骨架！
                    # 因为 mask 已经是黑白分明的图了，Canny 会完美勾勒出准星的轮廓线
                    template_edges = cv2.Canny(mask, 50, 150)
                    
                    opt_x = template_edges.shape[1] // 2
                    opt_y = template_edges.shape[0] // 2
                    
                    self.templates.append({
                        "edges": template_edges,  # 只存骨架，不存原图
                        "tw": template_edges.shape[1],
                        "th": template_edges.shape[0],
                        "opt_x": opt_x,
                        "opt_y": opt_y
                    })
            except Exception as e: 
                print(f"模板加载失败: {e}")
                
        if not self.templates:
            print("[弩追踪器] ⚠️ 警告: 未找到任何透明准星模板图片！")

        self.cx = self.sw // 2
        self.cy = self.sh // 2
        self.is_found = False
        self.is_enabled = False
        self._thread_running = False

    def enable_module(self, enabled: bool):
        self.is_enabled = enabled
        if self.is_enabled and not self._thread_running and self.templates:
            self._thread_running = True
            threading.Thread(target=self._tracking_loop, daemon=True).start()
        elif not self.is_enabled:
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
                    
                    # 【核心魔法】：对实时游戏画面提取边缘骨架！
                    # 天空会变成纯黑，准星会变成清晰的白色线条
                    live_edges = cv2.Canny(gray_frame, 50, 150)
                    
                    best_val = 0.0
                    best_loc = None
                    best_opt_x = 0
                    best_opt_y = 0
                    
                    for tpl in self.templates:
                        # 拿“实时的骨架”去匹配“模板的骨架”
                        # 对于线条匹配，TM_CCOEFF_NORMED 效果极佳，不需要传 mask 参数
                        res = cv2.matchTemplate(live_edges, tpl["edges"], cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, max_loc = cv2.minMaxLoc(res)
                        
                        if max_val > best_val:
                            best_val = max_val
                            best_loc = max_loc
                            best_opt_x = tpl["opt_x"]
                            best_opt_y = tpl["opt_y"]
                    
                    # 【注意】：边缘匹配的得分特性
                    # 因为骨架图大部分是黑色的，只有细细的线条重合，所以最高分通常不会达到 0.9
                    # 经验值：得分 > 0.45 基本上就是极其精准的命中了
                    if best_val > 0.45:
                        self.is_found = True
                        match_x, match_y = best_loc
                        self.cx = self.monitor["left"] + match_x + best_opt_x
                        self.cy = self.monitor["top"] + match_y + best_opt_y
                    else:
                        self.is_found = False
                        
                except Exception:
                    self.is_found = False
                    
                time.sleep(0.015)

class MathematicalCrossTracker:
    """内部组件：基于纯数学卷积的十字特征追踪器 (无需图片模板，免疫背景变换)"""
    def __init__(self, screen_width, screen_height, cross_size=16, thickness=2):
        self.sw = screen_width
        self.sh = screen_height
        
        self.roi_w = 100
        self.roi_h = 80
        self.monitor = {
            "top": (self.sh // 2) - (self.roi_h // 2) - 20, 
            "left": (self.sw // 2) - (self.roi_w // 2),
            "width": self.roi_w,
            "height": self.roi_h
        }
        
        # =======================================================
        # 【核心魔法：生成数学扣分模板】
        # =======================================================
        self.kernel = np.zeros((cross_size, cross_size), dtype=np.float32)
        c = cross_size // 2
        t = thickness // 2
        
        # 1. 将十字架所在的区域设为 1 (命中则加分)
        self.kernel[c-t:c+t, :] = 1
        self.kernel[:, c-t:c+t] = 1
        
        cross_area = np.sum(self.kernel == 1)
        bg_area = (cross_size * cross_size) - cross_area
        
        # 2. 将那四个背景区域设为负数 (命中亮色则扣分)，保证整个模板的总和为 0
        self.kernel[self.kernel == 0] = - (cross_area / bg_area)
        
        self.cx = self.sw // 2
        self.cy = self.sh // 2
        self.is_found = False
        self.is_enabled = False
        self._thread_running = False

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
        with mss.MSS() as sct:
            while self._thread_running:
                try:
                    screenshot = sct.grab(self.monitor)
                    frame = np.array(screenshot)
                    
                    # 提取灰度图并转为浮点数用于数学计算
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY).astype(np.float32)
                    
                    # =======================================================
                    # 使用我们的“赏罚模板”去扫描整个图像 (底层的模板匹配就是卷积)
                    response = cv2.filter2D(gray, cv2.CV_32F, self.kernel)
                    
                    # 找到全场得分最高的一个点
                    _, max_val, _, max_loc = cv2.minMaxLoc(response)
                    
                    # 设定一个及格线 (满分通常在 3000~5000 左右，设 1000 就能过滤掉所有自然界噪音)
                    if max_val > 1000.0:
                        self.is_found = True
                        # filter2D 算法极其优雅，它的 max_loc 直接就是目标的正中心坐标！
                        self.cx = self.monitor["left"] + max_loc[0]
                        self.cy = self.monitor["top"] + max_loc[1]
                        
                        # 你可以取消这行的注释来观察锁定时的得分
                        # print(f"🎯 锁定准星! 形状得分: {max_val:.1f}")
                    else:
                        self.is_found = False
                        # print(f"❌ 丢失。最高得分仅有: {max_val:.1f}")
                    # =======================================================
                        
                except Exception:
                    self.is_found = False
                    
                time.sleep(0.015)

class CrossbowAssistant:
    """PUBG 弩 专属战术助手 (对外主类)"""
    def __init__(self, root, screen_width, screen_height, minimap_module, fps=30):
        self.root = root
        self.sw = screen_width
        self.sh = screen_height

        self.center_x = self.sw / 2
        self.center_y = self.sh / 2
        
        # 核心：直接引用外部传入的真实小地图模块
        self.minimap = minimap_module
        self.fps = fps
        
        # 内部实例化追踪器，对外部主控程序屏蔽复杂性
        self.tracker = MathematicalCrossTracker(screen_width, screen_height)
        
        self.is_enabled = False
        self._thread_running = False
        self.hud_thread = None
        
        # 完美对齐的 14 个高度映射数据
        self.calib_dists = [29.1, 41.5, 50.5, 62.8, 72.0, 82.7, 91.9, 102.6, 113.3, 122.5, 131.8, 140.9, 151.6, 160.9, 171.6, 182.3, 193.0, 203.7, 214.4, 225.2]
        raw_pixels = [1, 9, 17, 33, 41, 51, 62, 71, 82, 94, 108, 119, 130, 135, 151, 164, 175, 185, 196, 206]
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
            self.canvas.delete("crossbow_hud")

    def _draw_hud(self, valid_targets):
        self.canvas.delete("crossbow_hud")
        if not self.is_enabled: return

        cx, cy, is_found = self.tracker.get_dynamic_center()

        if not is_found:
            warn_y = self.sh * 0.75
            self.canvas.create_text(self.sw/2, warn_y, text="[ 未检测到弩准星，测距图层已隐藏 ]", 
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
            
            self.canvas.create_line(self.center_x - h_line_width, target_y, self.center_x, target_y, fill=color, width=1, tags="crossbow_hud")
            # self.canvas.create_oval(cx - 1, target_y - 1, cx + 1, target_y + 1, fill=color, outline="", tags="crossbow_hud")
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
                # 只有距离大于0（即确实在地图上标了该颜色的点），才加入渲染列表
                if dist > 0.0:
                    valid_targets.append({
                        "dist": dist,
                        "color": color_hex_map[color]
                    })
                    
            self.root.after(0, self._draw_hud, valid_targets)
            time.sleep(1.0 / self.fps)