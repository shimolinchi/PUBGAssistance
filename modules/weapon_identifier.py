import cv2
import os
import numpy as np
import mss
import time

class WeaponIdentifier:
    def __init__(self, region_manager, templates_dir="templates/weapons", threshold=0.50):
        self.rm = region_manager
        self.templates_dir = templates_dir
        # 线条匹配的得分通常比实心块低，建议从 0.60 开始测试
        self.match_threshold = threshold
        
        self.templates = {}
        self.weapon_names = []
        
        self._load_templates()

    def _preprocess_image(self, img_bgr):
        """
        统一预处理管线：转灰度 -> 高斯模糊(去噪) -> Canny轮廓提取 -> 膨胀(加粗线条)
        """
        # 1. 转为灰度图
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        
        # 2. 稍微模糊一下，过滤掉 UI 上的细小噪点和锯齿
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # 3. Canny 边缘检测提取轮廓
        # 这两个数字(50, 150)是高低阈值。如果提取出的线条太乱，可以提高这两个值(如 80, 200)
        edges = cv2.Canny(blurred, 50, 150)
        
        # 4. (可选增强) 膨胀操作：把 1 像素宽的细线加粗成 2 像素宽
        # 这样在模板匹配时，允许有 1-2 个像素的错位，极大提高容错率
        kernel = np.ones((2, 2), np.uint8)
        edges_dilated = cv2.dilate(edges, kernel, iterations=1)
        
        return edges_dilated

    def _load_templates(self):
        print(f"[武器识别] 正在从 {self.templates_dir} 加载武器轮廓模板...")
        weapon_region = self.rm.get_region("weapon_region")
        if not weapon_region or not os.path.exists(self.templates_dir):
            print("[武器识别] 警告: 标定区域或模板目录不存在！")
            return

        for weapon_name in os.listdir(self.templates_dir):
            weapon_path = os.path.join(self.templates_dir, weapon_name)
            if os.path.isdir(weapon_path):
                self.templates[weapon_name] = []
                self.weapon_names.append(weapon_name)
                
                for filename in os.listdir(weapon_path):
                    if filename.lower().endswith(".png"):
                        file_path = os.path.join(weapon_path, filename)
                        img = cv2.imread(file_path, cv2.IMREAD_COLOR)
                        if img is None: continue
                            
                        h, w = img.shape[:2]
                        if h > weapon_region["height"] and w > weapon_region["width"]:
                            top, left = weapon_region["top"], weapon_region["left"]
                            bottom, right = top + weapon_region["height"], left + weapon_region["width"]
                            if bottom <= h and right <= w:
                                cropped = img[top:bottom, left:right]
                            else:
                                cropped = img 
                        else:
                            cropped = img
                            
                        processed_tpl = self._preprocess_image(cropped)
                        
                        # 因为线条像素少，把非空验证阈值降到 5
                        if cv2.countNonZero(processed_tpl) > 5:
                            self.templates[weapon_name].append(processed_tpl)
                        else:
                            print(f"  [警告] {weapon_name}/{filename} 未提取到有效轮廓，已丢弃！")
                            
                print(f"  - {weapon_name}: 加载了 {len(self.templates[weapon_name])} 个轮廓模板")
        print("[武器识别] 轮廓模板加载完毕。")

    def identify_current_weapon(self, sct: mss.mss):
        weapon_region = self.rm.get_region("weapon_region")
        if not weapon_region or not self.templates:
            return None, 0.0, None

        try:
            screenshot = sct.grab(weapon_region)
            img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
            current_img = self._preprocess_image(img_bgr)
            
            # 防黑洞机制：截图中没有提取到任何线条
            if cv2.countNonZero(current_img) < 5:
                return None, 0.0, current_img
            
            best_match_weapon = None
            best_match_score = 0.0
            
            for weapon_name, tpls in self.templates.items():
                for tpl in tpls:
                    if tpl.shape[0] > current_img.shape[0] or tpl.shape[1] > current_img.shape[1]:
                        continue
                        
                    res = cv2.matchTemplate(current_img, tpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    
                    if max_val > best_match_score:
                        best_match_score = max_val
                        best_match_weapon = weapon_name
            
            if best_match_score >= self.match_threshold:
                return best_match_weapon, best_match_score, current_img
            else:
                return None, best_match_score, current_img
                
        except Exception as e:
            return None, 0.0, None