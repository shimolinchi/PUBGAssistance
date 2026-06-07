import cv2
import os
import numpy as np
import mss
import threading
import time
from typing import Optional, Callable, Dict

class EquipmentDetector:
    """
    装备栏识别模块（武器名灰度匹配，配件彩色+掩码匹配，支持二次验证）
    """

    def __init__(self, region_manager, templates_dir="templates/equipments",
                 fps=15, idle_timeout=2.0,
                 thresholds: Dict[str, float] = None, debug=False, on_status_change: Optional[Callable] = None):
        self.rm = region_manager
        self.templates_dir = templates_dir
        self.fps = fps
        self.idle_timeout = idle_timeout
        self.debug = debug
        self.on_status_change = on_status_change

        # 默认阈值：武器名0.55，配件0.85
        self.thresholds = {
            "names": 0.55,
            "scopes": 0.85,
            "grips": 0.85,
            "muzzles": 0.85,
            "stocks": 0.85
        }
        if thresholds:
            self.thresholds.update(thresholds)

        self.templates = {
            "names": {},
            "scopes": {},
            "grips": {},
            "muzzles": {},
            "stocks": {}
        }
        self._load_all_templates()

        self._enabled = False
        self._active = False
        self._thread = None
        self._stop = False
        self._last_detected_time = 0
        self._callback = None

        self.current_weapons = {
            1: {"name": None, "name_score": 0.0, "scope": None, "scope_score": 0.0,
                "grip": None, "grip_score": 0.0, "muzzle": None, "muzzle_score": 0.0,
                "stock": None, "stock_score": 0.0},
            2: {"name": None, "name_score": 0.0, "scope": None, "scope_score": 0.0,
                "grip": None, "grip_score": 0.0, "muzzle": None, "muzzle_score": 0.0,
                "stock": None, "stock_score": 0.0}
        }

    # ================= 模板加载（不变） =================
    def _load_templates(self, category: str, region_name: str):
        category_path = os.path.join(self.templates_dir, category)
        if not os.path.exists(category_path):
            return

        base_region = self.rm.get_templates_region(region_name)
        if not base_region:
            return

        for item_name in os.listdir(category_path):
            item_path = os.path.join(category_path, item_name)
            if not os.path.isdir(item_path):
                continue
            self.templates[category][item_name] = []
            for filename in os.listdir(item_path):
                if not filename.lower().endswith(".png"):
                    continue
                img = cv2.imread(os.path.join(item_path, filename), cv2.IMREAD_UNCHANGED)
                if img is None:
                    continue

                h, w = img.shape[:2]
                base_w, base_h = base_region["width"], base_region["height"]
                if h > base_h and w > base_w:
                    start_y = (h - base_h) // 2
                    start_x = (w - base_w) // 2
                    cropped = img[start_y:start_y+base_h, start_x:start_x+base_w]
                else:
                    cropped = img

                if category == "names":
                    gray = cv2.cvtColor(cropped, cv2.COLOR_BGRA2GRAY)
                    self.templates[category][item_name].append(gray)
                else:
                    if cropped.shape[2] == 4:
                        bgr = cropped[:, :, :3]
                        alpha = cropped[:, :, 3]
                        _, mask = cv2.threshold(alpha, 1, 255, cv2.THRESH_BINARY)
                    else:
                        bgr = cropped
                        mask = np.ones((bgr.shape[0], bgr.shape[1]), dtype=np.uint8) * 255
                    self.templates[category][item_name].append({
                        "bgr": bgr,
                        "mask": mask
                    })
        if self.debug:
            print(f"[装备栏] 加载 {category} 完成: {list(self.templates[category].keys())}")

    def _load_all_templates(self):
        categories = [
            ("names", "weapon1_name_region"),
            ("scopes", "weapon1_scope_region"),
            ("grips", "weapon1_grip_region"),
            ("muzzles", "weapon1_muzzle_region"),
            ("stocks", "weapon1_stock_region")
        ]
        for cat, region_name in categories:
            self._load_templates(cat, region_name)

    # ================= 图像预处理 =================
    def _resize_to_base(self, img_bgr, region_name: str):
        base_region = self.rm.get_templates_region(region_name)
        if not base_region:
            return None
        target_w, target_h = base_region["width"], base_region["height"]
        if img_bgr.shape[1] != target_w or img_bgr.shape[0] != target_h:
            img_bgr = cv2.resize(img_bgr, (target_w, target_h))
        return img_bgr

    def _match_item(self, roi_bgr, templates_dict, category: str):
        threshold = self.thresholds.get(category, 0.65)
        if category == "names":
            roi_gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
            best_name = None
            best_score = 0.0
            for name, tpl_list in templates_dict.items():
                for tpl in tpl_list:
                    if tpl.shape[0] > roi_gray.shape[0] or tpl.shape[1] > roi_gray.shape[1]:
                        continue
                    res = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    if max_val > best_score:
                        best_score = max_val
                        best_name = name
            if best_score >= threshold:
                return best_name, best_score
            return None, best_score

        # 配件：彩色+掩码匹配 + 二次验证
        best_name = None
        best_score = 0.0
        best_loc = None
        best_tpl_item = None
        for name, tpl_list in templates_dict.items():
            for item in tpl_list:
                tpl_bgr = item["bgr"]
                mask = item["mask"]
                if tpl_bgr.shape[0] > roi_bgr.shape[0] or tpl_bgr.shape[1] > roi_bgr.shape[1]:
                    continue
                res = cv2.matchTemplate(roi_bgr, tpl_bgr, cv2.TM_CCORR_NORMED, mask=mask)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val > best_score:
                    best_score = max_val
                    best_name = name
                    best_loc = max_loc
                    best_tpl_item = item
        if best_score >= threshold and best_name is not None:
            x, y = best_loc
            h, w = best_tpl_item["bgr"].shape[:2]
            matched_region = roi_bgr[y:y+h, x:x+w]
            mask = best_tpl_item["mask"]
            diff = cv2.absdiff(matched_region, best_tpl_item["bgr"])
            diff_gray = np.mean(diff, axis=2)
            masked_diff = diff_gray[mask > 0]
            if len(masked_diff) == 0:
                return None, best_score
            mse = np.mean(masked_diff ** 2)
            if mse > 250:
                if self.debug:
                    pass
                return None, best_score
            return best_name, best_score
        return None, best_score

    # ================= 快速武器名检测（仅名称） =================
    def _detect_weapon_name_only(self, weapon_slot: int):
        """仅检测指定武器槽位的名称，不检测配件"""
        slot_regions = {1: "weapon1_name_region", 2: "weapon2_name_region"}
        name_region = slot_regions.get(weapon_slot)
        if not name_region:
            return None
        name_rect = self.rm.get_real_region(name_region)
        if not name_rect:
            return None
        with mss.mss() as sct:
            img = sct.grab(name_rect)
            img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
            img_resized = self._resize_to_base(img_bgr, name_region)
            if img_resized is None:
                return None
            name, score = self._match_item(img_resized, self.templates["names"], "names")
            if name and score >= self.thresholds["names"]:
                return name
        return None

    def _detect_both_weapon_names(self):
        """快速检测两个武器槽位的名称，返回 (weapon1_name, weapon2_name)"""
        w1 = self._detect_weapon_name_only(1)
        w2 = self._detect_weapon_name_only(2)
        return w1, w2

    # ================= 完整武器检测（含配件） =================
    def _detect_weapon(self, weapon_slot: int):
        slot_regions = {
            1: ("weapon1_name_region", "weapon1_scope_region", "weapon1_grip_region",
                "weapon1_muzzle_region", "weapon1_stock_region"),
            2: ("weapon2_name_region", "weapon2_scope_region", "weapon2_grip_region",
                "weapon2_muzzle_region", "weapon2_stock_region")
        }
        name_region, scope_region, grip_region, muzzle_region, stock_region = slot_regions[weapon_slot]

        result = {}
        with mss.MSS() as sct:
            # 名称
            name_rect = self.rm.get_real_region(name_region)
            if name_rect:
                img = sct.grab(name_rect)
                img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
                img_resized = self._resize_to_base(img_bgr, name_region)
                if img_resized is not None:
                    name, score = self._match_item(img_resized, self.templates["names"], "names")
                    result["name"] = name
                    result["name_score"] = score
                    if self.debug:
                        live_disp = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
                        cv2.imshow(f"Weapon{weapon_slot}_name_live", live_disp)
                        cv2.waitKey(1)
                else:
                    result["name"] = None
                    result["name_score"] = 0.0
            else:
                result["name"] = None
                result["name_score"] = 0.0

            # 配件（仅当武器名称存在时才识别）
            for key, region_key, templates_key in [
                ("scope", scope_region, "scopes"),
                ("grip", grip_region, "grips"),
                ("muzzle", muzzle_region, "muzzles"),
                ("stock", stock_region, "stocks")
            ]:
                if result.get("name") is None:
                    result[key] = None
                    result[f"{key}_score"] = 0.0
                    continue
                rect = self.rm.get_real_region(region_key)
                if rect:
                    img = sct.grab(rect)
                    img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
                    img_resized = self._resize_to_base(img_bgr, region_key)
                    if img_resized is not None:
                        match, score = self._match_item(img_resized, self.templates[templates_key], templates_key)
                        result[key] = match
                        result[f"{key}_score"] = score
                    else:
                        result[key] = None
                        result[f"{key}_score"] = 0.0
                else:
                    result[key] = None
                    result[f"{key}_score"] = 0.0
        return result

    # ================= 主循环与接口 =================
    def _detection_loop(self):
        consecutive_empty = 0
        with mss.mss() as sct:
            while not self._stop and self._enabled:
                if not self._active:
                    time.sleep(1 / self.fps)
                    continue

                new_weapons = {}
                for slot in [1, 2]:
                    new_weapons[slot] = self._detect_weapon(slot)

                has_any_name = any(w.get("name") is not None for w in new_weapons.values())
                if not has_any_name:
                    consecutive_empty += 1
                    # 连续 2 次无武器名，认为装备栏已关闭
                    if consecutive_empty >= 2:
                        self._active = False
                        if self._callback:
                            self._callback(False, self.current_weapons)   # 传递最后成功数据
                        if self.on_status_change:
                            self.on_status_change("closed")
                        consecutive_empty = 0
                    continue   # 无武器名时不更新数据

                # 有武器名，重置计数并更新数据
                consecutive_empty = 0
                self._last_detected_time = time.time()

                changed = False
                for slot in [1, 2]:
                    cur = self.current_weapons[slot]
                    new = new_weapons[slot]
                    # 更新武器名称（如果识别到）
                    if new.get("name") is not None and new["name"] != cur.get("name"):
                        cur["name"] = new["name"]
                        cur["name_score"] = new["name_score"]
                        changed = True
                    # 更新配件：只有当武器名称存在且配件识别分数达到阈值时才更新
                    for key in ["scope", "grip", "muzzle", "stock"]:
                        if new.get(key) is not None and new.get(f"{key}_score", 0) >= self.thresholds.get(key+"s", 0.65):
                            if cur.get(key) != new[key]:
                                cur[key] = new[key]
                                cur[f"{key}_score"] = new[f"{key}_score"]
                                changed = True
                        # 如果新识别中该配件为 None，但武器名存在，则保留原配件值（不置为 None）
                if changed and self._callback:
                    self._callback(True, self.current_weapons)

                # 空闲超时退出（保险）
                if time.time() - self._last_detected_time > self.idle_timeout:
                    self._active = False
                    if self._callback:
                        self._callback(False, self.current_weapons)
                    if self.on_status_change:
                        self.on_status_change("closed")
                    continue

                time.sleep(1.0 / self.fps)

    def set_enabled(self, enabled: bool, callback: Optional[Callable] = None):
        self._enabled = enabled
        if callback:
            self._callback = callback
        if enabled and (self._thread is None or not self._thread.is_alive()):
            self._stop = False
            self._thread = threading.Thread(target=self._detection_loop, daemon=True)
            self._thread.start()
        elif not enabled and self._thread:
            self._stop = True
            if self._thread.is_alive():
                self._thread.join(0.1)
            self._thread = None
            self._active = False
            if self.debug:
                cv2.destroyAllWindows()

    def on_tab_press(self):
        if not self._enabled: return
        if self._active:
            self._active = False
            if self._callback: self._callback(False, self.current_weapons)
            if self.on_status_change: self.on_status_change("closed")
        else:
            if self.on_status_change: self.on_status_change("confirming")
            success_count = 0
            for _ in range(2):
                w1, w2 = self._detect_both_weapon_names()
                if w1 is not None:
                    success_count += 1
                if w2 is not None:
                    success_count += 1
            if success_count >= 2:  # 4次检测中至少2次成功
                self._active = True
                self._last_detected_time = time.time()
                for slot in [1,2]:
                    self.current_weapons[slot] = self._detect_weapon(slot)
                if self._callback: self._callback(True, self.current_weapons)
                if self.on_status_change: self.on_status_change("opened")
            else:
                if self.on_status_change: self.on_status_change("closed")

    def get_current_weapons(self):
        return self.current_weapons