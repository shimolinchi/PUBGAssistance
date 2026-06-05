# weapon_detector.py
import cv2
import os
import numpy as np
import mss
import threading
import time
from typing import Optional, Callable, List

class WeaponDetector:
    """
    当前手持武器检测模块
    维护两个主武器名称（由装备栏模块更新），实时识别手持武器并回调。
    """

    def __init__(self, region_manager, templates_dir="templates/weapons",
                 fps=30, match_threshold=0.55, debug=False):
        self.rm = region_manager
        self.templates_dir = templates_dir
        self.fps = fps
        self.match_threshold = match_threshold
        self.debug = debug

        # 主武器列表：由装备栏模块调用 update_primary_weapons 设置
        self.primary_weapons = [None, None]   # [武器1, 武器2]

        # 特殊武器列表（无需压枪，但需通知主函数启动对应助手）
        self.special_weapons = ["Rocket", "Grenade", "VSS", "Crossbow"]

        self.templates = {}      # 武器名 -> 模板列表（与 weapon_identifier 相同结构）
        self._load_templates()

        self._enabled = False
        self._thread = None
        self._stop = False
        self._callback = None    # 回调函数，参数 (weapon_name, score)

        self.current_weapon = None
        self.current_score = 0.0

    def set_enabled(self, enabled: bool, callback: Optional[Callable] = None):
        self._enabled = enabled
        if callback:
            self._callback = callback
        if enabled and (self._thread is None or not self._thread.is_alive()):
            self._stop = False
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        elif not enabled and self._thread:
            self._stop = True
            if self._thread.is_alive():
                self._thread.join(0.1)
            self._thread = None

    def update_primary_weapons(self, weapon1: Optional[str], weapon2: Optional[str]):
        """由装备栏检测模块调用，更新当前装备的主武器"""
        self.primary_weapons = [weapon1, weapon2]

    def _run(self):
        with mss.mss() as sct:
            while not self._stop and self._enabled:
                start = time.time()
                weapon, score = self._identify_weapon(sct)
                weapon, score = self._identify_weapon(sct)
                if weapon:
                    self.current_weapon = weapon
                    self.current_score = score
                else:
                    self.current_weapon = None
                    self.current_score = 0.0
                if self._callback:
                    self._callback(weapon, score)
                elapsed = time.time() - start
                sleep = max(0, (1.0 / self.fps) - elapsed)
                time.sleep(sleep)

    # ================= 图像预处理（与 weapon_identifier 相同） =================
    def _preprocess_image(self, img_bgr):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = np.ones((2, 2), np.uint8)
        edges_dilated = cv2.dilate(edges, kernel, iterations=1)
        return edges_dilated

    # ================= 加载模板（与 weapon_identifier 相同） =================
    def _load_templates(self):
        print(f"[武器检测] 正在从 {self.templates_dir} 加载武器模板...")
        weapon_region = self.rm.get_templates_region("weapon_region")
        if not weapon_region or not os.path.exists(self.templates_dir):
            print("[武器检测] 警告: 标定区域或模板目录不存在！")
            return

        for weapon_name in os.listdir(self.templates_dir):
            weapon_path = os.path.join(self.templates_dir, weapon_name)
            if os.path.isdir(weapon_path):
                self.templates[weapon_name] = []
                for filename in os.listdir(weapon_path):
                    if filename.lower().endswith(".png"):
                        file_path = os.path.join(weapon_path, filename)
                        img = cv2.imread(file_path, cv2.IMREAD_COLOR)
                        if img is None: continue
                        # 裁切模板（如果有标定区域）
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
                        mask_kernel = np.ones((5, 5), np.uint8)
                        mask = cv2.dilate(processed_tpl, mask_kernel, iterations=1)
                        if cv2.countNonZero(processed_tpl) > 5:
                            self.templates[weapon_name].append({
                                "tpl": processed_tpl,
                                "mask": mask
                            })
                print(f"  - {weapon_name}: 加载了 {len(self.templates[weapon_name])} 个模板")
        print("[武器检测] 模板加载完毕。")

    # ================= 核心识别 =================
    def _identify_weapon(self, sct: mss.mss):
        weapon_region_real = self.rm.get_real_region("weapon_region")
        weapon_region_base = self.rm.get_templates_region("weapon_region")
        if not weapon_region_real or not self.templates:
            return None, 0.0

        try:
            screenshot = sct.grab(weapon_region_real)
            img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
            img_bgr = cv2.resize(img_bgr, (weapon_region_base["width"], weapon_region_base["height"]))
            current_img = self._preprocess_image(img_bgr)
            if cv2.countNonZero(current_img) < 5:
                return None, 0.0

            # 构建待匹配的武器候选列表
            candidates = []
            # 先加入当前两个主武器（非空）
            for w in self.primary_weapons:
                if w and w in self.templates:
                    candidates.append(w)
            # 再加入特殊武器（如果它们在模板库中）
            for sw in self.special_weapons:
                if sw in self.templates:
                    candidates.append(sw)

            # 如果没有候选，直接返回 None
            if not candidates:
                return None, 0.0

            best_match_weapon = None
            best_match_score = 0.0
            for weapon_name in candidates:
                for item in self.templates[weapon_name]:
                    tpl = item["tpl"]
                    mask = item["mask"]
                    if tpl.shape[0] > current_img.shape[0] or tpl.shape[1] > current_img.shape[1]:
                        continue
                    res = cv2.matchTemplate(current_img, tpl, cv2.TM_CCORR_NORMED, mask=mask)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    if max_val > best_match_score:
                        best_match_score = max_val
                        best_match_weapon = weapon_name
            if best_match_score >= self.match_threshold:
                return best_match_weapon, best_match_score
            else:
                return None, best_match_score
        except Exception as e:
            print(f"[武器检测错误] {e}")
            return None, 0.0
        
    def get_current_weapon(self):
        return self.current_weapon, self.current_score