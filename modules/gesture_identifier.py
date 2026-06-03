import cv2
import os
import numpy as np
import mss

class GestureIdentifier:
    """
    姿势识别中枢 (掩码遮罩匹配版)
    通过识别左下角姿态图标的线条轮廓，判断玩家姿势。
    """
    def __init__(self, region_manager, templates_dir="templates/gestures", threshold=0.50):
        self.rm = region_manager
        self.templates_dir = templates_dir
        self.match_threshold = threshold
        self.templates = {}  # 结构: {name: [{"tpl": img, "mask": mask}, ...]}
        self.gesture_names = []
        self._load_templates()

    def _preprocess_image(self, img_bgr):
        """统一预处理管线：转灰度 -> 高斯模糊 -> Canny -> 膨胀加粗线条"""
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = np.ones((2, 2), np.uint8)
        return cv2.dilate(edges, kernel, iterations=1)

    def _load_templates(self):
        print(f"[姿势识别] 正在加载模板 (Mask模式)...")
        stance_region = self.rm.get_region("stance_region")
        if not stance_region or not os.path.exists(self.templates_dir):
            return

        for gesture_name in os.listdir(self.templates_dir):
            path = os.path.join(self.templates_dir, gesture_name)
            if os.path.isdir(path):
                self.templates[gesture_name] = []
                self.gesture_names.append(gesture_name)
                
                for filename in os.listdir(path):
                    if filename.lower().endswith(".png"):
                        img = cv2.imread(os.path.join(path, filename))
                        if img is None: continue
                        
                        # 裁剪模板
                        top, left = stance_region["top"], stance_region["left"]
                        h, w = stance_region["height"], stance_region["width"]
                        cropped = img[top:top+h, left:left+w] if img.shape[0] > h else img
                        
                        processed = self._preprocess_image(cropped)
                        
                        # 【核心优化】：生成遮罩 (Mask)
                        # 只有线条部分(>0)是有效区域
                        _, mask = cv2.threshold(processed, 1, 255, cv2.THRESH_BINARY)
                        
                        if cv2.countNonZero(processed) > 5:
                            self.templates[gesture_name].append({
                                "tpl": processed.astype(np.uint8),
                                "mask": mask.astype(np.uint8)
                            })
        print(f"[姿势识别] 加载完毕: {self.gesture_names}")

    def identify_current_gesture(self, sct: mss.mss):
        stance_region = self.rm.get_region("stance_region")
        if not stance_region or not self.templates:
            return None, 0.0, None

        try:
            screenshot = sct.grab(stance_region)
            img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
            current_img = self._preprocess_image(img_bgr).astype(np.uint8)
            
            if cv2.countNonZero(current_img) < 5:
                return None, 0.0, current_img
            
            best_gesture = None
            best_score = 0.0
            
            for name, tpls in self.templates.items():
                for item in tpls:
                    tpl = item["tpl"]
                    mask = item["mask"]
                    
                    # 【核心优化】：使用 TM_CCORR_NORMED + Mask
                    # 匹配仅计算模板中白色线条部分，彻底忽略背景噪音
                    res = cv2.matchTemplate(current_img, tpl, cv2.TM_CCORR_NORMED, mask=mask)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    
                    if max_val > best_score:
                        best_score = max_val
                        best_gesture = name
            
            if best_score >= self.match_threshold:
                return best_gesture, best_score, current_img
            return None, best_score, current_img
        except Exception as e:
            return None, 0.0, None