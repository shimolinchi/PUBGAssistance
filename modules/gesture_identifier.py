import cv2
import os
import numpy as np
import mss
import threading
import time
import json
from typing import Optional, Callable

class GestureIdentifier:
    """
    姿势识别模块（站立/蹲下/趴下）
    模板保持原始尺寸，截图根据 region_scaling_settings 中的配置缩放到目标尺寸。
    """
    def __init__(self, region_manager, templates_dir="templates/gestures",
                 fps=30, match_threshold=0.65, debug=False):
        self.rm = region_manager
        self.templates_dir = templates_dir
        self.fps = fps
        self.match_threshold = match_threshold
        self.debug = debug

        # 姿势名称映射（英文 -> 中文，用于回调）
        self.gesture_names = {
            "stand": "站立",
            "squat": "蹲下",
            "lie": "趴下"
        }

        # 读取缩放配置（从 region_scaling_settings 中读取 stance_region 的缩放目标尺寸）
        self.target_width = None
        self.target_height = None
        self._load_target_size()

        # 加载模板（保持原始尺寸）
        self.templates = {}
        self._load_templates()

        # 如果未指定目标尺寸，则使用第一个模板的尺寸作为默认
        if self.target_width is None and self.templates:
            first_tpl = next(iter(self.templates.values()))[0]["tpl"]
            self.target_width = first_tpl.shape[1]
            self.target_height = first_tpl.shape[0]
            print(f"[姿势识别] 使用模板原始尺寸作为目标尺寸: {self.target_width}x{self.target_height}")

        self._enabled = False
        self._thread = None
        self._stop = False
        self._callback = None

        self.current_gesture = None
        self.current_score = 0.0

        self.pending_gesture = None
        self.pending_counter = 0
        self.pending_score = 0.0

    def _load_target_size(self):
        """从 config.json 的 region_scaling_settings 中读取 stance_region 的宽度和高度"""
        config_file = "config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    scaling = config.get("region_scaling_settings", {})
                    if "stance_region" in scaling:
                        self.target_width = scaling["stance_region"].get("width")
                        self.target_height = scaling["stance_region"].get("height")
                        if self.target_width and self.target_height:
                            print(f"[姿势识别] 从配置加载缩放尺寸: {self.target_width}x{self.target_height}")
            except Exception as e:
                print(f"[姿势识别] 读取缩放配置失败: {e}")

    # ================= 模板加载 =================
    def _preprocess_image(self, img_bgr):
        """预处理：灰度 + 高斯模糊 + Canny + 膨胀"""
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = np.ones((2, 2), np.uint8)
        edges_dilated = cv2.dilate(edges, kernel, iterations=1)
        return edges_dilated

    def _load_templates(self):
        """直接加载原始模板图片，不进行缩放，保持原始尺寸"""
        print(f"[姿势识别] 正在从 {self.templates_dir} 加载姿势模板...")
        if not os.path.exists(self.templates_dir):
            print("[姿势识别] 警告: 模板目录不存在！")
            return

        for gesture_name in os.listdir(self.templates_dir):
            gesture_path = os.path.join(self.templates_dir, gesture_name)
            if not os.path.isdir(gesture_path):
                continue
            self.templates[gesture_name] = []
            for filename in os.listdir(gesture_path):
                if not filename.lower().endswith(".png"):
                    continue
                file_path = os.path.join(gesture_path, filename)
                img_full = cv2.imread(file_path, cv2.IMREAD_COLOR)
                if img_full is None:
                    continue
                # 模板保持原始尺寸，不缩放
                processed_tpl = self._preprocess_image(img_full)
                # 创建掩码
                mask_kernel = np.ones((5, 5), np.uint8)
                mask = cv2.dilate(processed_tpl, mask_kernel, iterations=1)
                if cv2.countNonZero(mask) == 0:
                    continue
                self.templates[gesture_name].append({
                    "tpl": processed_tpl,
                    "mask": mask
                })
            print(f"  - {gesture_name}: 加载了 {len(self.templates[gesture_name])} 个模板")
        print("[姿势识别] 模板加载完毕。")

    # ================= 核心识别 =================
    def _identify_gesture(self, sct: mss.mss):
        stance_region_real = self.rm.get_real_region("stance_region")
        if not stance_region_real or not self.templates or self.target_width is None:
            return None, 0.0

        try:
            screenshot = sct.grab(stance_region_real)
            img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)

            # 缩放到目标尺寸
            if img_bgr.shape[1] != self.target_width or img_bgr.shape[0] != self.target_height:
                img_bgr = cv2.resize(img_bgr, (self.target_width, self.target_height))

            current_img = self._preprocess_image(img_bgr)
            if cv2.countNonZero(current_img) < 10:
                return None, 0.0

            best_match_gesture = None
            best_match_score = 0.0

            for gesture_name, tpl_list in self.templates.items():
                for item in tpl_list:
                    tpl = item["tpl"]
                    mask = item["mask"]
                    if tpl.shape[0] > current_img.shape[0] or tpl.shape[1] > current_img.shape[1]:
                        continue
                    res = cv2.matchTemplate(current_img, tpl, cv2.TM_CCORR_NORMED, mask=mask)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    if max_val > best_match_score:
                        best_match_score = max_val
                        best_match_gesture = gesture_name

            if best_match_gesture is not None and best_match_score >= self.match_threshold:
                return best_match_gesture, best_match_score
            else:
                return None, best_match_score
        except Exception as e:
            print(f"[姿势识别错误] {e}")
            return None, 0.0

    # ================= 主循环与接口 =================
    def _run(self):
        with mss.mss() as sct:
            while not self._stop and self._enabled:
                start = time.time()
                gesture, score = self._identify_gesture(sct)

                # 防抖：连续两帧一致才更新
                if gesture is not None and score >= self.match_threshold:
                    if self.pending_gesture == gesture:
                        self.pending_counter += 1
                        if self.pending_counter >= 2:
                            if self.current_gesture != gesture:
                                self.current_gesture = gesture
                                self.current_score = score
                                gesture_display = self.gesture_names.get(gesture, gesture)
                                if self._callback:
                                    self._callback(gesture_display, score)
                    else:
                        self.pending_gesture = gesture
                        self.pending_score = score
                        self.pending_counter = 1
                else:
                    self.pending_gesture = None
                    self.pending_counter = 0
                    if self.current_gesture is not None:
                        self.current_gesture = None
                        self.current_score = 0.0
                        if self._callback:
                            self._callback(None, 0.0)

                elapsed = time.time() - start
                sleep = max(0, (1.0 / self.fps) - elapsed)
                time.sleep(sleep)

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

    def get_current_gesture(self):
        return self.current_gesture, self.current_score