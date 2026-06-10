import cv2
import os
import numpy as np
import mss
import threading
import time
import json
from typing import Optional, Callable

class WeaponDetector:
    def __init__(self, region_manager, templates_dir="templates/weapons",
                 fps=30, match_threshold=0.55, debug=False):
        self.rm = region_manager
        self.templates_dir = templates_dir
        self.fps = fps
        self.match_threshold = match_threshold
        self.debug = debug

        self.primary_weapons = [None, None]
        self.special_weapons = ["Rocket", "Grenade", "VSS", "Crossbow", "C4"]

        # 先加载模板（获取模板尺寸）
        self.templates = {}
        self._load_templates()

        # 再读取配置（可能会覆盖目标尺寸）
        self.target_width = 160
        self.target_height = 50
        self._load_match_target_size()
        print(f"[武器检测] 使用缩放目标尺寸: {self.target_width}x{self.target_height}")

        self.last_best_score = 0.0
        self.last_best_weapon = None

        self._enabled = False
        self._thread = None
        self._stop = False
        self._callback = None

        self.current_weapon = None
        self.current_score = 0.0
        self.last_match_location = None

        self.pending_weapon = None
        self.pending_counter = 0
        self.pending_score = 0.0

    def _load_match_target_size(self):
        """从 config.json 读取 region_scaling_settings 中 weapon_region 的缩放目标尺寸"""
        config_file = "config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    scaling = config.get("region_scaling_settings", {})
                    if "weapon_region" in scaling:
                        self.target_width = scaling["weapon_region"].get("width", self.target_width)
                        self.target_height = scaling["weapon_region"].get("height", self.target_height)
                        print(f"[武器检测] 从 region_scaling_settings 加载缩放尺寸: {self.target_width}x{self.target_height}")
                        return
                    ws = config.get("weapon_match_settings", {})
                    if "target_width" in ws and "target_height" in ws:
                        self.target_width = ws["target_width"]
                        self.target_height = ws["target_height"]
                        print(f"[武器检测] 从 weapon_match_settings 加载缩放尺寸: {self.target_width}x{self.target_height}")
                        return
            except Exception as e:
                print(f"[武器检测] 读取缩放配置失败: {e}")

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

                if weapon is not None and score >= self.match_threshold:
                    if self.pending_weapon == weapon:
                        self.pending_counter += 1
                        if self.pending_counter >= 2:
                            if self.current_weapon != weapon:
                                self.current_weapon = weapon
                                self.current_score = score
                                if self._callback:
                                    self._callback(weapon, score)
                    else:
                        self.pending_weapon = weapon
                        self.pending_score = score
                        self.pending_counter = 1
                else:
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

    def _preprocess_image(self, img_bgr):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = np.ones((2, 2), np.uint8)
        edges_dilated = cv2.dilate(edges, kernel, iterations=1)
        return edges_dilated

    def _load_templates(self):
        print(f"[武器检测] 正在从 {self.templates_dir} 加载武器模板...")
        if not os.path.exists(self.templates_dir):
            print("[武器检测] 警告: 模板目录不存在！")
            return

        first_template_size_set = False
        for weapon_name in os.listdir(self.templates_dir):
            weapon_path = os.path.join(self.templates_dir, weapon_name)
            if not os.path.isdir(weapon_path):
                continue
            self.templates[weapon_name] = []
            for filename in os.listdir(weapon_path):
                if not filename.lower().endswith(".png"):
                    continue
                file_path = os.path.join(weapon_path, filename)
                img_full = cv2.imread(file_path, cv2.IMREAD_COLOR)
                if img_full is None:
                    continue
                # 模板保持原始尺寸
                processed_tpl = self._preprocess_image(img_full)
                # 记录第一个模板的尺寸作为默认目标尺寸（如果尚未设置）
                if not first_template_size_set:
                    self.target_width = processed_tpl.shape[1]
                    self.target_height = processed_tpl.shape[0]
                    first_template_size_set = True
                    print(f"[武器检测] 根据模板尺寸设置默认目标尺寸: {self.target_width}x{self.target_height}")

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
                self.templates[weapon_name].append({
                    "tpl": processed_tpl,
                    "mask": mask,
                    "inner_mask": inner_mask
                })
            print(f"  - {weapon_name}: 加载了 {len(self.templates[weapon_name])} 个模板")
        print("[武器检测] 模板加载完毕。")

    def _identify_weapon(self, sct):
        weapon_region_real = self.rm.get_real_region("weapon_region")
        if not weapon_region_real or not self.templates:
            return None, 0.0

        try:
            screenshot = sct.grab(weapon_region_real)
            img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)

            # 缩放到目标尺寸
            if img_bgr.shape[1] != self.target_width or img_bgr.shape[0] != self.target_height:
                img_bgr = cv2.resize(img_bgr, (self.target_width, self.target_height))

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
            self.last_match_location = None

            for weapon_name in candidates:
                for item in self.templates[weapon_name]:
                    tpl = item["tpl"]
                    mask = item["mask"]
                    if tpl.shape[0] > current_img.shape[0] or tpl.shape[1] > current_img.shape[1]:
                        continue
                    res = cv2.matchTemplate(current_img, tpl, cv2.TM_CCORR_NORMED, mask=mask)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    if not np.isfinite(max_val):
                        max_val = 0.0
                    if max_val > best_match_score:
                        best_match_score = max_val
                        best_match_weapon = weapon_name
                        self.last_match_location = (max_loc[0], max_loc[1], tpl.shape[1], tpl.shape[0])

            self.last_best_weapon = best_match_weapon
            self.last_best_score = best_match_score

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

    def get_last_best_match(self):
        return self.last_best_weapon, self.last_best_score