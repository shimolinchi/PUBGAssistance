import ctypes
import ctypes.wintypes
import time
import threading
import json
import os
from pynput import mouse, keyboard

MOUSEEVENTF_MOVE = 0x0001

class RecoilControlModule:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file

        # 核心状态
        self.is_enabled = False
        self.recoil_delay = 0.02
        self.fire_key_str = "end"
        self.fire_key = keyboard.Key.end

        # 武器原始参数
        self.current_weapon = None
        self.weapon_type = "ar"          # 武器类型：ar, smg, lmg, dmr
        self.base_recoil = 0.0
        self.recoil_curve = []
        self.recoil_curve_step = 0.4
        self.auto_fire_enabled = False

        # 配件/姿势系数
        self.total_multiplier = 1.0
        self.scope = "hip"
        self.grip = None
        self.muzzle = None
        self.stock = None
        self.current_stance = "stand"
        self.current_stance_multipliers = {"stand": 1.0, "squat": 0.8, "lie": 0.6}

        # 配置字典
        self.weapon_configs = {}
        self.stance_multipliers = {}      # 由武器类型索引的姿势系数
        self.scope_multiplier_curves = {}
        self.grip_multiplier_curves = {}
        self.muzzle_multiplier_curves = {}
        self.stock_multiplier_curves = {}
        self.scope_multipliers = {}
        self.grip_multipliers = {}
        self.muzzle_multipliers = {}
        self.stock_multipliers = {}

        self._load_config()

        self.current_recoil_strength = 0
        self.is_firing = False
        self.fire_start_time = 0
        self._thread_running = True
        self.kb = keyboard.Controller()

        self.worker_thread = threading.Thread(target=self._recoil_worker_loop, daemon=True)
        self.worker_thread.start()
        self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
        self.mouse_listener.start()

    # ================= 配置读写 =================
    def _load_config(self):
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        rc = config.get("recoil_settings", {})
                        if not rc:
                            self._init_default_config()
                            return

                        self.fire_key_str = rc.get("fire_key", "end")
                        self._parse_fire_key(self.fire_key_str)
                        self.recoil_delay = rc.get("recoil_delay", 0.02)
                        self.recoil_curve_step = rc.get("recoil_curve_step", 0.4)
                        self.weapon_configs = rc.get("weapons", {})
                        # 读取姿势系数（嵌套字典）
                        self.stance_multipliers = rc.get("stance_multipliers", {})
                        # 若配置文件缺少某些武器类型的姿势系数，使用默认值
                        default_stance = {
                            "ar": {"stand": 1.0, "squat": 0.8, "lie": 0.6},
                            "smg": {"stand": 1.0, "squat": 0.8, "lie": 0.7},
                            "lmg": {"stand": 1.0, "squat": 0.4, "lie": 0.2},
                            "dmr": {"stand": 1.0, "squat": 0.8, "lie": 0.6}
                        }
                        for wtype, vals in default_stance.items():
                            if wtype not in self.stance_multipliers:
                                self.stance_multipliers[wtype] = vals
                        # 配件系数曲线，公开的 *_multipliers 保留 0 秒值，兼容测试工具。
                        self.scope_multiplier_curves = self._normalize_multiplier_curves(rc.get("scope_multipliers", {}))
                        self.grip_multiplier_curves = self._normalize_multiplier_curves(rc.get("grip_multipliers", {}))
                        self.muzzle_multiplier_curves = self._normalize_multiplier_curves(rc.get("muzzle_multipliers", {}))
                        self.stock_multiplier_curves = self._normalize_multiplier_curves(rc.get("stock_multipliers", {}))
                        self.scope_multipliers = self._first_values(self.scope_multiplier_curves)
                        self.grip_multipliers = self._first_values(self.grip_multiplier_curves)
                        self.muzzle_multipliers = self._first_values(self.muzzle_multiplier_curves)
                        self.stock_multipliers = self._first_values(self.stock_multiplier_curves)
                except Exception as e:
                    print(f"[压枪模块] 配置加载失败: {e}")

    def _init_default_config(self):
        self.weapon_configs = {
            "M416": {"recoil_curve": [10.0, 12.0, 14.0], "auto_fire": False, "type": "ar"},
            "AKM": {"recoil_curve": [12.0, 14.0, 16.0], "auto_fire": False, "type": "ar"},
            "MP5K": {"recoil_curve": [8.0, 10.0, 12.0], "auto_fire": False, "type": "smg"},
            "SKS": {"recoil_curve": [15.0], "auto_fire": False, "type": "dmr"}
        }
        self.stance_multipliers = {
            "ar": {"stand": 1.0, "squat": 0.8, "lie": 0.6},
            "smg": {"stand": 1.0, "squat": 0.8, "lie": 0.7},
            "lmg": {"stand": 1.0, "squat": 0.4, "lie": 0.2},
            "dmr": {"stand": 1.0, "squat": 0.8, "lie": 0.6}
        }
        self.scope_multiplier_curves = {"red_dot": [1.2], "holo": [1.2], "x2": [2.0], "x3": [3.0], "x4": [4.0], "x6": [6.0]}
        self.grip_multiplier_curves = {"vertical": [0.9], "half": [1.0], "light": [1.0]}
        self.muzzle_multiplier_curves = {"compensator": [0.85], "flash_hider": [0.95]}
        self.stock_multiplier_curves = {"tactical": [0.9]}
        self.scope_multipliers = self._first_values(self.scope_multiplier_curves)
        self.grip_multipliers = self._first_values(self.grip_multiplier_curves)
        self.muzzle_multipliers = self._first_values(self.muzzle_multiplier_curves)
        self.stock_multipliers = self._first_values(self.stock_multiplier_curves)

    def _normalize_curve(self, value, default=1.0):
        if isinstance(value, list):
            curve = value
        elif value is None:
            curve = [default]
        else:
            curve = [value]
        normalized = []
        for item in curve:
            try:
                normalized.append(float(item))
            except (TypeError, ValueError):
                pass
        return normalized or [float(default)]

    def _normalize_multiplier_curves(self, multiplier_config):
        return {key: self._normalize_curve(value, 1.0) for key, value in multiplier_config.items()}

    def _first_values(self, curve_config):
        return {key: values[0] for key, values in curve_config.items() if values}

    def _sample_curve(self, curve, elapsed_time):
        curve = self._normalize_curve(curve, 0.0)
        if len(curve) == 1:
            return curve[0]

        step = max(float(self.recoil_curve_step), 0.001)
        position = max(0.0, elapsed_time) / step
        left_index = int(position)
        if left_index >= len(curve) - 1:
            return curve[-1]

        ratio = position - left_index
        return curve[left_index] + (curve[left_index + 1] - curve[left_index]) * ratio

    def _get_multiplier(self, curve_config, key, elapsed_time):
        if not key:
            return 1.0
        return self._sample_curve(curve_config.get(key, [1.0]), elapsed_time)

    def _calculate_recoil_strength(self, elapsed_time):
        if not self.current_weapon or not self.recoil_curve:
            return 0.0

        weapon_recoil = self._sample_curve(self.recoil_curve, elapsed_time)
        scope_mult = self._get_multiplier(self.scope_multiplier_curves, self.scope, elapsed_time)
        grip_mult = self._get_multiplier(self.grip_multiplier_curves, self.grip, elapsed_time)
        muzzle_mult = self._get_multiplier(self.muzzle_multiplier_curves, self.muzzle, elapsed_time)
        stock_mult = self._get_multiplier(self.stock_multiplier_curves, self.stock, elapsed_time)
        stance_mult = self.current_stance_multipliers.get(self.current_stance, 1.0)
        self.total_multiplier = scope_mult * grip_mult * muzzle_mult * stock_mult * stance_mult
        return weapon_recoil * self.total_multiplier

    # def save_config(self):
    #     config = {}
    #     if os.path.exists(self.config_file):
    #         try:
    #             with open(self.config_file, 'r', encoding='utf-8') as f:
    #                 config = json.load(f)
    #         except:
    #             pass
    #     config["recoil_settings"] = {
    #         "fire_key": self.fire_key_str,
    #         "recoil_delay": self.recoil_delay,
    #         "weapons": self.weapon_configs,
    #         "stance_multipliers": self.stance_multipliers,
    #         "scope_multipliers": self.scope_multipliers,
    #         "grip_multipliers": self.grip_multipliers,
    #         "muzzle_multipliers": self.muzzle_multipliers,
    #         "stock_multipliers": self.stock_multipliers
    #     }
    #     with open(self.config_file, 'w', encoding='utf-8') as f:
    #         json.dump(config, f, indent=4, ensure_ascii=False)

    def _parse_fire_key(self, key_str):
        key_str = key_str.lower()
        if hasattr(keyboard.Key, key_str):
            self.fire_key = getattr(keyboard.Key, key_str)
        else:
            self.fire_key = keyboard.KeyCode.from_char(key_str)

    # ================= 外部接口 =================
    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled
        if not enabled:
            self.is_firing = False
            self.fire_start_time = 0
            try:
                self.kb.release(self.fire_key)
            except Exception:
                pass

    def save_config(self):
        config = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                config = {}

        config["recoil_settings"] = {
            "fire_key": self.fire_key_str,
            "recoil_delay": self.recoil_delay,
            "recoil_curve_step": self.recoil_curve_step,
            "weapons": self.weapon_configs,
            "stance_multipliers": self.stance_multipliers,
            "scope_multipliers": self.scope_multiplier_curves,
            "grip_multipliers": self.grip_multiplier_curves,
            "muzzle_multipliers": self.muzzle_multiplier_curves,
            "stock_multipliers": self.stock_multiplier_curves,
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        print("[压枪模块] 配置已保存")

    def update_current_weapon(self, weapon_name: str):
        if weapon_name == self.current_weapon:
            return
        self.is_firing = False
        self.fire_start_time = 0
        self.kb.release(self.fire_key)
        self.current_weapon = weapon_name
        wp_data = self.weapon_configs.get(weapon_name, {})
        self.recoil_curve = self._normalize_curve(wp_data.get("recoil_curve", wp_data.get("base", 0.0)), 0.0)
        self.base_recoil = self.recoil_curve[0] if self.recoil_curve else 0.0
        self.auto_fire_enabled = wp_data.get("auto_fire", False)
        self.weapon_type = wp_data.get("type", "ar")

        self.current_stance_multipliers = self.stance_multipliers.get(self.weapon_type,
                                                                      {"stand": 1.0, "squat": 0.8, "lie": 0.6})
        self._recalculate_multiplier()

    def update_attachments(self, attachments: dict):
        if "scope" in attachments:
            self.scope = attachments["scope"] or "hip"
        if "grip" in attachments:
            self.grip = attachments["grip"]
        if "muzzle" in attachments:
            self.muzzle = attachments["muzzle"]
        if "stock" in attachments:
            self.stock = attachments["stock"]
        self._recalculate_multiplier()

    def update_stance(self, stance: str):
        if stance in self.current_stance_multipliers and stance != self.current_stance:
            self.current_stance = stance
            self._recalculate_multiplier()

    def _recalculate_multiplier(self):
        if not self.current_weapon or not self.recoil_curve or self.base_recoil == 0:
            self.total_multiplier = 1.0
            self.current_recoil_strength = 0
            return
        static_strength = self._calculate_recoil_strength(0.0)
        self.current_recoil_strength = int(round(static_strength))

    # ================= 事件处理 =================
    def _on_mouse_click(self, x, y, button, pressed):
        if button != mouse.Button.left:
            return
        # 无论压枪是否开启，左键按下/释放必须同步 fire_key
        if pressed:
            # 按下左键：始终按下 fire_key
            self.kb.press(self.fire_key)
        else:
            # 释放左键：始终释放 fire_key，并重置压枪状态
            self.is_firing = False
            self.fire_start_time = 0
            self.kb.release(self.fire_key)
            return

        # 以下仅处理压枪位移（仅在压枪开关开启且有武器时）
        if not self.is_enabled or not self.current_weapon:
            return

        if self.weapon_type == "dmr":
            # DMR：单次压枪，不启动状态机
            strength = int(round(self._calculate_recoil_strength(0.0)))
            if strength > 0:
                threading.Thread(
                    target=lambda: ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, 0, strength, 0, 0),
                    daemon=True
                ).start()
        else:
            # 自动/半自动武器：启动持续压枪状态机
            self.is_firing = True
            self.fire_start_time = time.time()

    def _is_left_button_pressed(self):
        """通过 Windows API 实时获取鼠标左键物理状态"""
        return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)

    def _recoil_worker_loop(self):
        while self._thread_running:
            # 硬件状态修正（防止事件丢失导致的卡键）
            if self.is_firing and not self._is_left_button_pressed():
                self.is_firing = False
                self.fire_start_time = 0
                self.kb.release(self.fire_key)  # 保险
                time.sleep(0.01)
                continue

            if self.is_enabled and self.is_firing and self.current_weapon and self.weapon_type != "dmr":
                t = max(0, time.time() - self.fire_start_time)
                total = self._calculate_recoil_strength(t)
                strength = int(round(total))
                self.current_recoil_strength = strength

                if self.auto_fire_enabled:
                    self.kb.press(self.fire_key)
                    time.sleep(0.001)
                    self.kb.release(self.fire_key)

                # 不再模拟 fire_key，只做压枪位移
                if strength > 0:
                    ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, 0, strength, 0, 0)

                time.sleep(self.recoil_delay)
            else:
                time.sleep(0.01)

    def reload_config(self):
        self._load_config()
        if self.current_weapon:
            wp_data = self.weapon_configs.get(self.current_weapon, {})
            self.recoil_curve = self._normalize_curve(wp_data.get("recoil_curve", wp_data.get("base", 0.0)), 0.0)
            self.base_recoil = self.recoil_curve[0] if self.recoil_curve else 0.0
            self.auto_fire_enabled = wp_data.get("auto_fire", False)
            self.weapon_type = wp_data.get("type", "ar")
            self.current_stance_multipliers = self.stance_multipliers.get(self.weapon_type,
                                                                          {"stand": 1.0, "squat": 0.8, "lie": 0.6})
            self._recalculate_multiplier()
        print("[压枪模块] 配置已重新加载")

    def shutdown(self):
        self._thread_running = False
        if hasattr(self, 'mouse_listener'):
            self.mouse_listener.stop()
