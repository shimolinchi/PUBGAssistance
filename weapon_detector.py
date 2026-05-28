# import cv2
# import numpy as np
# import mss
# import time
# import threading
# class AutoWeaponDetector:
#     """全局状态监控：武器栏视觉识别自动调度器 (自适应任意分辨率)"""
#     def __init__(self, screen_width, screen_height, templates_config, on_switch_callback):
#         self.sw = screen_width
#         self.sh = screen_height
#         self.callback = on_switch_callback
        
#         # =========================================================
#         # 【核心改进：基于 1920x1080 的相对比例映射】
#         # 无论玩家是 2K 还是 4K，截图区域都会精准锁定在那块相对位置
#         # =========================================================
#         ref_w, ref_h = 1920.0, 1080.0
        
#         box_left = int(self.sw * (880 / ref_w))
#         box_top = int(self.sh * (925 / ref_h))
#         box_width = int(self.sw * ((1040 - 880) / ref_w))
#         box_height = int(self.sh * ((984 - 925) / ref_h))
        
#         self.monitor = {
#             "top": box_top,
#             "left": box_left,
#             "width": box_width,
#             "height": box_height
#         }
        
#         # 加载纯白模板 (兼容你的透明 PNG)
#         self.templates = {}
#         for weapon_name, path in templates_config.items():
#             try:
#                 # 保留透明通道读取
#                 img_bgra = cv2.imread(path, cv2.IMREAD_UNCHANGED)
#                 if img_bgra is not None:
#                     # 如果图是带透明通道的，提取 Alpha 通道作为纯白形状
#                     if len(img_bgra.shape) == 3 and img_bgra.shape[2] == 4:
#                         img_shape = img_bgra[:, :, 3]
#                     else:
#                         # 如果图是黑底白字，直接灰度读取
#                         img_shape = cv2.cvtColor(img_bgra, cv2.COLOR_BGR2GRAY)
                    
#                     # 确保模板是绝对的二值化黑白图 (纯白值为 255)
#                     _, img_bin = cv2.threshold(img_shape, 128, 255, cv2.THRESH_BINARY)
                    
#                     # 【重要】：如果用户的显示器不是 1080P，模板的尺寸也必须等比例缩放！
#                     # 否则 2K 屏幕截出来的武器比 1080P 的模板大，会导致匹配失败
#                     if self.sw != 1920 or self.sh != 1080:
#                         scale_factor_x = self.sw / ref_w
#                         scale_factor_y = self.sh / ref_h
#                         new_size = (int(img_bin.shape[1] * scale_factor_x), int(img_bin.shape[0] * scale_factor_y))
#                         img_bin = cv2.resize(img_bin, new_size, interpolation=cv2.INTER_NEAREST)
                        
#                     self.templates[weapon_name] = img_bin
#             except Exception as e:
#                 print(f"[自动切枪] 模板 {path} 加载失败: {e}")

#         self.current_weapon = None
#         self.is_running = False

#     def start(self):
#         if not self.is_running:
#             self.is_running = True
#             threading.Thread(target=self._detection_loop, daemon=True).start()
#             print("[自动切枪] 武器状态监控已启动，侦测区域映射完毕。")

#     def stop(self):
#         self.is_running = False

#     def _detection_loop(self):
#         with mss.MSS() as sct:
#             while self.is_running:
#                 try:
#                     screenshot = sct.grab(self.monitor)
#                     frame = np.array(screenshot)
#                     gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                    
#                     # PUBG 武器 UI 是明亮的，将暗色背景剥离 (阈值可根据实际效果在 150-180 间微调)
#                     _, live_thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

#                     best_match = None
#                     best_score = 0.0

#                     # 轮询比对所有武器模板
#                     for weapon_name, tpl in self.templates.items():
#                         res = cv2.matchTemplate(live_thresh, tpl, cv2.TM_CCOEFF_NORMED)
#                         _, max_val, _, _ = cv2.minMaxLoc(res)
                        
#                         if max_val > best_score:
#                             best_score = max_val
#                             best_match = weapon_name

#                     if best_score > 0.28:
#                         if best_match != self.current_weapon:
#                             self.current_weapon = best_match
#                             if self.callback:
#                                 self.callback(self.current_weapon)
#                     else:
#                         # 分数太低，说明切成了空手、平底锅，或者 UI 消失了
#                         if self.current_weapon is not None:
#                             self.current_weapon = None
#                             if self.callback:
#                                 self.callback(None) # 发送 None，触发界面的"未识别到武器"

#                 except Exception:
#                     pass
                
#                 # 0.3秒扫描一次，极低性能开销
#                 time.sleep(0.3)



import cv2
import numpy as np
import mss
import time
import threading
import os

class AutoWeaponDetector:
    """全局状态监控：武器栏视觉识别自动调度器 (正式版)"""
    def __init__(self, screen_width, screen_height, templates_config, on_switch_callback):
        self.sw = screen_width
        self.sh = screen_height
        self.callback = on_switch_callback
        
        # 坐标自适应换算 (基于测试程序的精准坐标)
        ref_w, ref_h = 1920.0, 1080.0
        box_left = int(self.sw * (890 / ref_w))
        box_top = int(self.sh * (925 / ref_h))
        box_width = int(self.sw * ((1030 - 890) / ref_w))
        box_height = int(self.sh * ((984 - 925) / ref_h))
        
        self.monitor = {
            "top": box_top,
            "left": box_left,
            "width": box_width,
            "height": box_height
        }
        
        # 加载并生成完美线框模板
        self.templates = {}
        for weapon_name, path in templates_config.items():
            if not os.path.exists(path):
                print(f"[武器探测] ⚠️ 找不到模板文件: {path}")
                continue
                
            try:
                img_gray = cv2.imread(path, 0)
                if img_gray is not None:
                    # 动态缩放
                    if self.sw != 1920 or self.sh != 1080:
                        scale_factor_x = self.sw / ref_w
                        scale_factor_y = self.sh / ref_h
                        new_size = (int(img_gray.shape[1] * scale_factor_x), int(img_gray.shape[0] * scale_factor_y))
                        img_gray = cv2.resize(img_gray, new_size, interpolation=cv2.INTER_LINEAR)
                    
                    # 自动拉伸对比度 + Canny 边缘提取
                    img_gray = cv2.normalize(img_gray, None, 0, 255, cv2.NORM_MINMAX)
                    img_edges = cv2.Canny(img_gray, 50, 150)
                    
                    # 防呆检查
                    if cv2.countNonZero(img_edges) == 0:
                        print(f"[致命错误] ⚠️ {weapon_name} 模板全是黑的！请重新截图！")
                        continue
                        
                    self.templates[weapon_name] = img_edges
            except Exception as e:
                print(f"[武器探测] 加载失败 {path}: {e}")

        self.current_weapon = None
        self.is_running = False

    def start(self):
        if not self.is_running:
            self.is_running = True
            threading.Thread(target=self._detection_loop, daemon=True).start()

    def stop(self):
        self.is_running = False

    def _detection_loop(self):
        with mss.MSS() as sct:
            while self.is_running:
                try:
                    screenshot = sct.grab(self.monitor)
                    frame = np.array(screenshot)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                    
                    # 实时边缘提取
                    live_edges = cv2.Canny(gray, 50, 150)
                    
                    best_match = None
                    best_score = 0.0

                    for weapon_name, tpl in self.templates.items():
                        res = cv2.matchTemplate(live_edges, tpl, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(res)
                        
                        if max_val > best_score:
                            best_score = max_val
                            best_match = weapon_name

                    # 判定逻辑：及格线为 0.28（线框匹配的极高置信度）
                    if best_score > 0.28: 
                        if best_match != self.current_weapon:
                            self.current_weapon = best_match
                            if self.callback:
                                self.callback(self.current_weapon)
                    else:
                        # 核心修复：分数太低说明没切出武器或 UI 消失了，发送 None 信号！
                        if self.current_weapon is not None:
                            self.current_weapon = None
                            if self.callback:
                                self.callback(None)

                except Exception as e:
                    pass
                
                time.sleep(0.3)