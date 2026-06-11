import cv2
import os
import numpy as np
import mss
import threading
import time
import json
from typing import Optional, Callable, Dict

class EquipmentDetector:
    """
    装备栏识别模块（武器名灰度匹配，配件彩色+掩码匹配，编号检测作为开关）
    - 武器名称区域：根据 region_scaling_settings 中的配置缩放
    - 配件区域（倍镜/握把/枪口/枪托）：截图固定缩放到 50x50，模板保持原始尺寸（模板本身应为 50x50）
    - 编号区域：固定缩放到 28x28（模板尺寸）
    """

    def __init__(self, region_manager, templates_dir="templates/equipments",
                 fps=15, idle_timeout=10.0,
                 thresholds: Dict[str, float] = None, debug=False, on_status_change: Optional[Callable] = None):
        self.rm = region_manager
        self.templates_dir = templates_dir
        self.fps = fps
        self.idle_timeout = idle_timeout
        self.debug = debug
        self.on_status_change = on_status_change

        # 默认阈值
        self.thresholds = {
            "names": 0.55,
            "scopes": 0.65,
            "grips": 0.4,
            "muzzles": 0.4,
            "stocks": 0.4
        }
        if thresholds:
            self.thresholds.update(thresholds)

        # 加载模板
        self.templates = {
            "names": {},
            "scopes": {},
            "grips": {},
            "muzzles": {},
            "stocks": {}
        }
        self._load_all_templates()

        # 加载编号模板
        self.number_templates = {}  # {1: template, 2: template}
        self._load_number_templates()

        # 读取武器名称区域的缩放配置
        self.scaling_config = self._load_scaling_config()

        self._enabled = False
        self._active = False
        self._thread = None
        self._stop = False
        self._last_detected_time = 0
        self._callback = None
        self.clear_confirm_frames = 2

        self.current_weapons = {
            1: {"name": None, "name_score": 0.0, "scope": None, "scope_score": 0.0,
                "grip": None, "grip_score": 0.0, "muzzle": None, "muzzle_score": 0.0,
                "stock": None, "stock_score": 0.0},
            2: {"name": None, "name_score": 0.0, "scope": None, "scope_score": 0.0,
                "grip": None, "grip_score": 0.0, "muzzle": None, "muzzle_score": 0.0,
                "stock": None, "stock_score": 0.0}
        }
        self._missing_part_counts = {
            slot: {key: 0 for key in ["scope", "grip", "muzzle", "stock"]}
            for slot in [1, 2]
        }

    def _load_scaling_config(self) -> Dict[str, Dict[str, int]]:
        """从 config.json 读取 region_scaling_settings（仅用于武器名称）"""
        config_file = "config.json"
        scaling = {}
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    scaling = config.get("region_scaling_settings", {})
                    print(f"[装备栏] 加载缩放配置: {list(scaling.keys())}")
            except Exception as e:
                print(f"[装备栏] 读取缩放配置失败: {e}")
        return scaling

    def _get_name_target_size(self, region_key: str) -> tuple:
        """获取武器名称区域的目标缩放尺寸，若无配置则使用模板原始尺寸"""
        # 获取第一个名称模板的尺寸作为基准
        if not self.templates["names"]:
            return 237, 36  # 后备默认值
        first_name = next(iter(self.templates["names"]))
        if self.templates["names"][first_name]:
            tpl = self.templates["names"][first_name][0]
            base_w, base_h = tpl.shape[1], tpl.shape[0]
        else:
            base_w, base_h = 237, 36
        if region_key in self.scaling_config:
            w = self.scaling_config[region_key].get("width", base_w)
            h = self.scaling_config[region_key].get("height", base_h)
            return w, h
        return base_w, base_h

    # ================= 模板加载 =================
    def _load_templates(self, category: str, region_name: str):
        category_path = os.path.join(self.templates_dir, category)
        if not os.path.exists(category_path):
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

                if category == "names":
                    # 名称：灰度图，保持原始尺寸
                    processed = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
                    self.templates[category][item_name].append(processed)
                else:
                    # 配件：保持原始尺寸（不缩放），使用 BGR 和掩码
                    # 假设模板图片已经是合适大小（例如 50x50），但不再强制缩放
                    if img.shape[2] == 4:
                        bgr = img[:, :, :3]
                        alpha = img[:, :, 3]
                        _, mask = cv2.threshold(alpha, 1, 255, cv2.THRESH_BINARY)
                    else:
                        bgr = img
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

    def _load_number_templates(self):
        numbers_dir = os.path.join(self.templates_dir, "numbers")
        if not os.path.exists(numbers_dir):
            return
        for num in [1, 2]:
            num_dir = os.path.join(numbers_dir, str(num))
            if not os.path.isdir(num_dir):
                continue
            for filename in os.listdir(num_dir):
                if not filename.lower().endswith(".png"):
                    continue
                img = cv2.imread(os.path.join(num_dir, filename), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                # 统一缩放到 28x28
                img_resized = cv2.resize(img, (28, 28))
                self.number_templates[num] = img_resized
                break
        if self.debug:
            print(f"[装备栏] 加载编号模板: {list(self.number_templates.keys())}")

    # ================= 图像缩放辅助函数 =================
    def _resize_name_to_target(self, img_bgr, region_key: str):
        """将武器名称截图缩放到配置的目标尺寸"""
        target_w, target_h = self._get_name_target_size(region_key)
        if img_bgr.shape[1] != target_w or img_bgr.shape[0] != target_h:
            img_bgr = cv2.resize(img_bgr, (target_w, target_h))
        return img_bgr

    def _resize_accessory_to_fixed(self, img_bgr):
        """将配件截图缩放到 50x50"""
        if img_bgr.shape[1] != 50 or img_bgr.shape[0] != 50:
            img_bgr = cv2.resize(img_bgr, (50, 50))
        return img_bgr

    def _resize_number_to_fixed(self, img_bgr):
        """将编号截图缩放到 28x28"""
        if img_bgr.shape[1] != 32 or img_bgr.shape[0] != 32:
            img_bgr = cv2.resize(img_bgr, (32, 32))
        return img_bgr

    # ================= 编号检测 =================
    def _detect_any_number(self) -> bool:
        return self._detect_weapon_number(1) or self._detect_weapon_number(2)

    def _detect_weapon_number(self, weapon_slot: int) -> bool:
        region_key = f"weapon{weapon_slot}_number_region"
        rect = self.rm.get_real_region(region_key)
        if not rect or not self.number_templates:
            return False
        with mss.mss() as sct:
            img = sct.grab(rect)
            img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
            roi = self._resize_number_to_fixed(img_bgr)
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            for tpl in self.number_templates.values():
                res = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                if max_val >= 0.5:
                    return True
        return False

    # ================= 武器名和配件识别 =================
    def _match_item(self, roi_bgr, templates_dict, category: str, region_key: str = None):
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

        # 配件匹配
        best_name = None
        best_score = 0.0
        best_loc = None
        best_tpl_item = None
        for name, tpl_list in templates_dict.items():
            for item in tpl_list:
                tpl_bgr = item["bgr"]
                mask = item["mask"]
                # 注意：此时 roi_bgr 已经是 50x50，模板可能是任意大小（但应该也是 50x50）
                if tpl_bgr.shape[0] > roi_bgr.shape[0] or tpl_bgr.shape[1] > roi_bgr.shape[1]:
                    # 如果模板大于 50x50，则跳过（需要调整模板）
                    if self.debug:
                        print(f"[警告] 模板 {name} 尺寸 {tpl_bgr.shape} 大于截图 {roi_bgr.shape}")
                    continue
                res = cv2.matchTemplate(roi_bgr, tpl_bgr, cv2.TM_CCOEFF_NORMED, mask=mask)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val > best_score:
                    best_score = max_val
                    best_name = name
                    best_loc = max_loc
                    best_tpl_item = item
        if best_score >= threshold and best_name is not None:
            return best_name, best_score
        return None, best_score

    def _detect_weapon(self, weapon_slot: int):
        slot_regions = {
            1: ("weapon1_name_region", "weapon1_scope_region", "weapon1_grip_region",
                "weapon1_muzzle_region", "weapon1_stock_region"),
            2: ("weapon2_name_region", "weapon2_scope_region", "weapon2_grip_region",
                "weapon2_muzzle_region", "weapon2_stock_region")
        }
        name_region, scope_region, grip_region, muzzle_region, stock_region = slot_regions[weapon_slot]

        result = {}
        with mss.mss() as sct:
            # 名称
            name_rect = self.rm.get_real_region(name_region)
            if name_rect:
                img = sct.grab(name_rect)
                img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
                img_resized = self._resize_name_to_target(img_bgr, name_region)
                name, score = self._match_item(img_resized, self.templates["names"], "names", name_region)
                result["name"] = name
                result["name_score"] = score
                if self.debug:
                    live_disp = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
                    cv2.imshow(f"Weapon{weapon_slot}_name_live", live_disp)
                    cv2.waitKey(1)
            else:
                result["name"] = None
                result["name_score"] = 0.0

            # 配件（仅当武器名称识别成功时才识别配件，减少误报）
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
                    # 配件截图固定缩放到 50x50
                    img_resized = self._resize_accessory_to_fixed(img_bgr)
                    match, score = self._match_item(img_resized, self.templates[templates_key], templates_key, region_key)
                    result[key] = match
                    result[f"{key}_score"] = score
                else:
                    result[key] = None
                    result[f"{key}_score"] = 0.0
        return result

    # ================= 主循环与接口 =================
    def _detection_loop(self):
        consecutive_no_numbers = 0
        with mss.mss() as sct:
            while not self._stop and self._enabled:
                if not self._active:
                    time.sleep(1 / self.fps)
                    continue

                any_number = self._detect_any_number()
                if not any_number:
                    consecutive_no_numbers += 1
                    if consecutive_no_numbers >= 4:
                        self._active = False
                        if self._callback:
                            self._callback(False, self.current_weapons)
                        if self.on_status_change:
                            self.on_status_change("closed")
                        consecutive_no_numbers = 0
                    continue
                else:
                    consecutive_no_numbers = 0
                    self._last_detected_time = time.time()

                new_weapons = {}
                for slot in [1, 2]:
                    new_weapons[slot] = self._detect_weapon(slot)

                changed = False
                for slot in [1, 2]:
                    cur = self.current_weapons[slot]
                    new = new_weapons[slot]
                    if new.get("name") is not None and new["name"] != cur.get("name"):
                        cur["name"] = new["name"]
                        cur["name_score"] = new["name_score"]
                        for key in ["scope", "grip", "muzzle", "stock"]:
                            self._missing_part_counts[slot][key] = 0
                        changed = True
                    for key in ["scope", "grip", "muzzle", "stock"]:
                        new_val = new.get(key)
                        new_score = new.get(f"{key}_score", 0.0)
                        threshold = self.thresholds.get(key+"s", 0.65)
                        if new_val is not None and new_score >= threshold:
                            self._missing_part_counts[slot][key] = 0
                            if cur.get(key) != new_val:
                                cur[key] = new_val
                                cur[f"{key}_score"] = new_score
                                changed = True
                        elif new.get("name") is not None and new.get("name") == cur.get("name"):
                            if cur.get(key) is not None:
                                self._missing_part_counts[slot][key] += 1
                                if self._missing_part_counts[slot][key] >= self.clear_confirm_frames:
                                    cur[key] = None
                                    cur[f"{key}_score"] = new_score
                                    self._missing_part_counts[slot][key] = 0
                                    changed = True
                            else:
                                self._missing_part_counts[slot][key] = 0
                        else:
                            self._missing_part_counts[slot][key] = 0
                if changed and self._callback:
                    self._callback(True, self.current_weapons)

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
        if not self._enabled:
            return
        if self._active:
            self._active = False
            if self._callback:
                self._callback(False, self.current_weapons)
            if self.on_status_change:
                self.on_status_change("closed")
        else:
            if self.on_status_change:
                self.on_status_change("confirming")
            success = False
            for _ in range(2):
                if self._detect_any_number():
                    success = True
                    break
                time.sleep(0.02)
            if success:
                self._active = True
                self._last_detected_time = time.time()
                if self._callback:
                    self._callback(True, self.current_weapons)
                if self.on_status_change:
                    self.on_status_change("opened")
                for slot in [1, 2]:
                    self.current_weapons[slot] = self._detect_weapon(slot)
                if self._callback:
                    self._callback(True, self.current_weapons)
            else:
                if self.on_status_change:
                    self.on_status_change("closed")

    def get_current_weapons(self):
        return self.current_weapons
