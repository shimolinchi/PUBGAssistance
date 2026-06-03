import cv2
import os
import numpy as np
import mss

class WeaponIdentifier:
    def __init__(self, region_manager, templates_dir="templates/weapons", threshold=0.50):
        self.rm = region_manager
        self.templates_dir = templates_dir
        # 将匹配成功阈值下调至 50% (0.50)
        self.match_threshold = threshold
        
        self.templates = {}
        self.weapon_names = []
        
        self._load_templates()

    def _preprocess_image(self, img_bgr):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        
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