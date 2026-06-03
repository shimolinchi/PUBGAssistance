import cv2
import os
import numpy as np
import mss

class ScopeIdentifier:
    """
    倍镜视觉识别中枢 (局部掩码轮廓注意力版)
    核心逻辑：
    1. 提取 1 像素宽的精细边缘轮廓。
    2. 将模板轮廓膨胀为 3 像素宽，作为掩码 (Mask)。
    3. 匹配时，完全无视掩码区域外的任何杂草、纹理线条干扰！
    """
    def __init__(self, region_manager, templates_dir="templates/scopes", threshold=0.55, black_thresh=30):
        self.rm = region_manager
        self.templates_dir = templates_dir
        self.match_threshold = threshold
        self.black_thresh = black_thresh
        self.is_enabled = False
        
        self.templates = {}
        self.scope_names = []
        
        self._load_templates()

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled

    def _preprocess_image(self, cropped_img):
        """
        提取带降噪处理的 2 像素宽轮廓统一管线
        """
        # 1. 压缩到 192x108 (保证物理比例恰到好处)
        resized = cv2.resize(cropped_img, (192, 108))
        
        # 2. 灰度与反向二值化
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        _, binary_inv = cv2.threshold(gray, self.black_thresh, 255, cv2.THRESH_BINARY_INV)
        
        # ================== 新增：强力降噪处理 ==================
        # 3.1 形态学开运算：消除零星的噪点（如远处的树叶、杂草碎片），防止它们干扰轮廓
        # morph_kernel = np.ones((3, 3), np.uint8)
        # binary_clean = cv2.morphologyEx(binary_inv, cv2.MORPH_OPEN, morph_kernel, iterations=1)
        binary_clean = binary_inv
        
        # 3.2 高斯模糊：平滑色块边缘，防止提取出的轮廓带有严重的锯齿
        blurred = cv2.GaussianBlur(binary_clean, (3, 3), 0)
        # ========================================================
        
        # 4. 提取极其干净的 1 像素边缘
        edges = cv2.Canny(blurred, 30, 100)
        
        # ================== 新增：轮廓加粗至 2 像素 ==================
        # 使用 2x2 的核进行膨胀，将 1 像素的细线变成 2 像素宽的粗线
        # 这能极大地吸收人物呼吸、准星轻微晃动带来的像素错位
        dilate_kernel = np.ones((2, 2), np.uint8)
        edges_2px = cv2.dilate(edges, dilate_kernel, iterations=1)
        
        return edges_2px

    def _load_templates(self):
        print(f"[倍镜识别] 正在加载掩码轮廓模板...")
        
        scope_region = self.rm.get_region("scope_region")
        if not scope_region or not os.path.exists(self.templates_dir):
            return

        for scope_name in os.listdir(self.templates_dir):
            scope_path = os.path.join(self.templates_dir, scope_name)
            if os.path.isdir(scope_path):
                self.templates[scope_name] = []
                self.scope_names.append(scope_name)
                
                for filename in os.listdir(scope_path):
                    if filename.lower().endswith(".png"):
                        file_path = os.path.join(scope_path, filename)
                        img = cv2.imread(file_path, cv2.IMREAD_COLOR)
                        if img is None: continue
                        
                        # ================= 步骤 1: 精准区域裁切 =================
                        h, w = img.shape[:2]
                        if h >= scope_region["top"] + scope_region["height"] and w >= scope_region["left"] + scope_region["width"]:
                            top = scope_region["top"]
                            left = scope_region["left"]
                            bottom = top + scope_region["height"]
                            right = left + scope_region["width"]
                            cropped_bgr = img[top:bottom, left:right]
                        else:
                            cropped_bgr = img 
                            
                        # ================= 步骤 2: 提取模板轮廓 =================
                        # 此时 processed_tpl 是一张仅有 1 像素宽线条的图
                        processed_tpl = self._preprocess_image(cropped_bgr)
                        
                        # ================= 步骤 3: 创造 3 像素超强掩码 =================
                        # 核心设计：用 3x3 核将轮廓向外各自延伸 1 个像素
                        mask_kernel = np.ones((3, 3), np.uint8)
                        mask = cv2.dilate(processed_tpl, mask_kernel, iterations=1)
                        
                        # ================= 步骤 4: 边缘裁剪 (产生滑动空间) =================
                        margin = 2
                        if processed_tpl.shape[0] > margin*3 and processed_tpl.shape[1] > margin*3:
                            tpl_cropped = processed_tpl[margin:-margin, margin:-margin]
                            mask_cropped = mask[margin:-margin, margin:-margin]
                        else:
                            tpl_cropped = processed_tpl
                            mask_cropped = mask
                        
                        if cv2.countNonZero(tpl_cropped) > 10:
                            self.templates[scope_name].append({
                                "tpl": tpl_cropped.astype(np.uint8),
                                "mask": mask_cropped.astype(np.uint8)
                            })
                        else:
                            print(f"  [警告] {scope_name}/{filename} 无效轮廓，已丢弃！")
                            
        print(f"[倍镜识别] 加载完毕。")

    def identify_current_scope(self, sct: mss.mss):
        if not self.is_enabled:
            return None, 0.0, None

        scope_region = self.rm.get_region("scope_region")
        if not scope_region or not self.templates:
            return None, 0.0, None

        try:
            screenshot = sct.grab(scope_region)
            img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
            
            # 获取实时画面的 1 像素轮廓图 (此时背景里哪怕有1万根杂草线也没关系)
            current_img = self._preprocess_image(img_bgr)
            
            if cv2.countNonZero(current_img) < 10:
                return None, 0.0, current_img
            
            best_match_scope = None
            best_match_score = 0.0
            
            for scope_name, tpl_list in self.templates.items():
                for item in tpl_list:
                    tpl = item["tpl"]
                    mask = item["mask"]
                    
                    if tpl.shape[0] > current_img.shape[0] or tpl.shape[1] > current_img.shape[1]:
                        continue
                        
                    # ================= 步骤 5: 掩码注意力匹配 =================
                    # current_img: 全屏轮廓，包含倍镜和杂草
                    # tpl: 只有倍镜轮廓 (1 像素宽)
                    # mask: 只有倍镜轮廓 (3 像素宽)
                    # 匹配过程：OpenCV 拿着 3 像素的掩码罩在实时图上，如果掩码外的区域有杂草，直接无视！
                    # 如果掩码内的区域有线条，且刚好能和 tpl 的线条重合，得分飙升！
                    res = cv2.matchTemplate(current_img, tpl, cv2.TM_CCORR_NORMED, mask=mask)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    
                    if max_val > best_match_score:
                        best_match_score = max_val
                        best_match_scope = scope_name
            
            if best_match_score >= self.match_threshold:
                return best_match_scope, best_match_score, current_img
            else:
                return None, best_match_score, current_img
                
        except Exception as e:
            print(f"[倍镜识别错误] {e}")
            return None, 0.0, None