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
    增加防抖：连续两帧识别到同一武器才更新。
    """

    def __init__(self, region_manager, templates_dir="templates/weapons",
                 fps=30, match_threshold=0.55, debug=False):
        self.rm = region_manager
        self.templates_dir = templates_dir
        self.fps = fps
        self.match_threshold = match_threshold
        self.debug = debug

        # 主武器列表
        self.primary_weapons = [None, None]
        self.special_weapons = ["Rocket", "Grenade", "VSS", "Crossbow","C4"]

        self.templates = {}
        self._load_templates()

        self._enabled = False
        self._thread = None
        self._stop = False
        self._callback = None

        self.current_weapon = None
        self.current_score = 0.0
        self.last_match_location = None

        # 防抖相关
        self.pending_weapon = None
        self.pending_counter = 0
        self.pending_score = 0.0

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
        self.primary_weapons = [weapon1, weapon2]

    def _run(self):
        with mss.mss() as sct:
            while not self._stop and self._enabled:
                start = time.time()
                weapon, score = self._identify_weapon(sct)

                # 防抖逻辑
                if weapon is not None and score >= self.match_threshold:
                    if self.pending_weapon == weapon:
                        self.pending_counter += 1
                        if self.pending_counter >= 2:
                            # 连续两帧识别到相同武器，确认切换
                            if self.current_weapon != weapon:
                                self.current_weapon = weapon
                                self.current_score = score
                                if self._callback:
                                    self._callback(weapon, score)
                    else:
                        # 新候选，重置计数器
                        self.pending_weapon = weapon
                        self.pending_score = score
                        self.pending_counter = 1
                else:
                    # 未识别到武器，重置防抖状态
                    self.pending_weapon = None
                    self.pending_counter = 0
                    if self.current_weapon is not None:
                        self.current_weapon = None
                        self.current_score = 0.0
                        if self._callback:
                            self._callback(None, 0.0)

                elapsed = time.time() - start
                sleep = max(0, (1.0 / self.fps) - elapsed)
                time.sleep(sleep)

    # ================= 图像预处理 =================
    def _preprocess_image(self, img_bgr):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = np.ones((2, 2), np.uint8)
        edges_dilated = cv2.dilate(edges, kernel, iterations=1)
        return edges_dilated

    # ================= 加载模板 =================
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
                    if not filename.lower().endswith(".png"):
                        continue
                    file_path = os.path.join(weapon_path, filename)
                    img = cv2.imread(file_path, cv2.IMREAD_COLOR)
                    if img is None:
                        continue
                    # 裁切模板
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
                    if cv2.countNonZero(mask) == 0:
                        continue

                    inner_mask = np.zeros_like(processed_tpl, dtype=np.uint8)
                    contours, _ = cv2.findContours(processed_tpl, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    if contours:
                        cnt = max(contours, key=cv2.contourArea)
                        cv2.drawContours(inner_mask, [cnt], -1, 255, -1)
                        inner_mask = cv2.erode(inner_mask, np.ones((2,2), np.uint8), iterations=1)
                    else:
                        inner_mask = np.ones_like(processed_tpl, dtype=np.uint8) * 255

                    if cv2.countNonZero(processed_tpl) > 5:
                        self.templates[weapon_name].append({
                            "tpl": processed_tpl,
                            "mask": mask,
                            "inner_mask": inner_mask
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

            candidates = []
            for w in self.primary_weapons:
                if w and w in self.templates:
                    candidates.append(w)
            for sw in self.special_weapons:
                if sw in self.templates:
                    candidates.append(sw)
            if not candidates:
                return None, 0.0

            best_match_weapon = None
            best_match_score = 0.0
            for weapon_name in candidates:
                for item in self.templates[weapon_name]:
                    tpl = item["tpl"]
                    mask = item["mask"]
                    h_tpl, w_tpl = tpl.shape[:2]
                    if h_tpl > current_img.shape[0] or w_tpl > current_img.shape[1]:
                        continue
                    res = cv2.matchTemplate(current_img, tpl, cv2.TM_CCORR_NORMED, mask=mask)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    if np.isinf(max_val) or np.isnan(max_val):
                        max_val = 0.0
                    if max_val > best_match_score:
                        best_match_score = max_val
                        best_match_weapon = weapon_name

            if best_match_weapon is not None:
                threshold = 0.6 if best_match_weapon == "Grenade" else self.match_threshold
                if best_match_score >= threshold:
                    return best_match_weapon, best_match_score
                else:
                    return None, best_match_score
            else:
                return None, best_match_score
        except Exception as e:
            print(f"[武器检测错误] {e}")
            return None, 0.0

    def get_current_weapon(self):
        return self.current_weapon, self.current_score

    def get_last_match_location(self):
        return self.last_match_location