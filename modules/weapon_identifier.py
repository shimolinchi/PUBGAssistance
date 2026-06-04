import cv2
import os
import numpy as np
import mss
import time

class WeaponIdentifier:
    def __init__(self, region_manager, templates_dir="templates/weapons", threshold=0.55):
        self.rm = region_manager
        self.templates_dir = templates_dir
        # 因为带了精准掩码，排除了背景干扰，分数会更纯净，建议 0.55 或 0.60 左右
        self.match_threshold = threshold
        
        self.templates = {}
        self.weapon_names = []
        
        self._load_templates()

    def _preprocess_image(self, img_bgr):
        """
        统一预处理管线：转灰度 -> 高斯模糊(去噪) -> Canny轮廓提取 -> 膨胀(加粗线条至2像素)
        """
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        
        # 把 1 像素宽的细线加粗成 2 像素宽，增加轻微错位的容错率
        kernel = np.ones((2, 2), np.uint8)
        edges_dilated = cv2.dilate(edges, kernel, iterations=1)
        
        return edges_dilated

    def _load_templates(self):
        print(f"[武器识别] 正在从 {self.templates_dir} 加载带掩码的武器模板...")
        weapon_region = self.rm.get_templates_region("weapon_region")
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
                            
                        # === 精准裁切模板 ===
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
                            
                        # 1. 获取基础 2px 武器轮廓
                        processed_tpl = self._preprocess_image(cropped)
                        
                        # 2. 【核心修改：生成 3 层掩码 Mask】
                        # 使用 5x5 的核进行膨胀，相当于把线条向外上下左右各扩充 2 个像素
                        # 这样就完美地保留了“轮廓本体 + 附近约 3 层像素”作为有效匹配区！
                        mask_kernel = np.ones((5, 5), np.uint8)
                        mask = cv2.dilate(processed_tpl, mask_kernel, iterations=1)
                        
                        # 因为线条像素少，把非空验证阈值降到 5
                        if cv2.countNonZero(processed_tpl) > 5:
                            # 存储为一个字典，同时包含模板和掩码
                            self.templates[weapon_name].append({
                                "tpl": processed_tpl,
                                "mask": mask
                            })
                        else:
                            print(f"  [警告] {weapon_name}/{filename} 未提取到有效轮廓，已丢弃！")
                            
                print(f"  - {weapon_name}: 加载了 {len(self.templates[weapon_name])} 个掩码模板")
        print("[武器识别] 掩码轮廓模板加载完毕。")

    def identify_current_weapon(self, sct: mss.mss):
        weapon_region_real = self.rm.get_real_region("weapon_region")
        weapon_region_base = self.rm.get_templates_region("weapon_region")
        
        if not weapon_region_real or not self.templates:
            return None, 0.0, None

        try:
            # 1. 用当前真实分辨率截图
            screenshot = sct.grab(weapon_region_real)
            img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
            
            # 2. 【重要修复】：强制压缩回 1080P 基准大小！保证能和模板完全重合！
            img_bgr = cv2.resize(img_bgr, (weapon_region_base["width"], weapon_region_base["height"]))
            
            # 3. 提取实时画面的轮廓 (当前图里面有武器、有杂草背景的轮廓)
            current_img = self._preprocess_image(img_bgr)
            
            if cv2.countNonZero(current_img) < 5:
                return None, 0.0, current_img
            
            best_match_weapon = None
            best_match_score = 0.0
            
            for weapon_name, tpls in self.templates.items():
                for item in tpls:
                    tpl = item["tpl"]
                    mask = item["mask"]
                    
                    if tpl.shape[0] > current_img.shape[0] or tpl.shape[1] > current_img.shape[1]:
                        continue
                        
                    # 【核心修改：使用带 Mask 的匹配算法】
                    # 注意：OpenCV 中只有 TM_CCORR_NORMED (和 SQDIFF) 完美支持 mask。
                    # 它会完全无视 mask 为纯黑(0)的地方的任何背景杂线！
                    res = cv2.matchTemplate(current_img, tpl, cv2.TM_CCORR_NORMED, mask=mask)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    
                    if max_val > best_match_score:
                        best_match_score = max_val
                        best_match_weapon = weapon_name
            
            if best_match_score >= self.match_threshold:
                return best_match_weapon, best_match_score, current_img
            else:
                return None, best_match_score, current_img
                
        except Exception as e:
            print(f"[武器识别模块错误] {e}")
            return None, 0.0, None