import ctypes
import time
import threading
import json
import os
from pynput import mouse, keyboard

MOUSEEVENTF_MOVE = 0x0001

class RecoilControlModule:
    """
    增强版压枪模块，支持倍镜、握把、枪口、枪托、姿势系数，动态压枪力度随时间线性增加
    """

    def __init__(self, config_file="config.json"):
        self.config_file = config_file

        # 核心状态
        self.is_enabled = False
        self.recoil_delay = 0.02
        self.fire_key_str = "end"
        self.fire_key = keyboard.Key.end

        # 武器原始参数（未乘系数）
        self.current_weapon = None
        self.base_recoil = 0.0              # 基础力度（原始）
        self.auto_fire_enabled = False
        self.dynamic_increment = 0.0        # 动态增量（像素/秒，原始）

        # 配件/姿势系数
        self.total_multiplier = 1.0         # 所有系数的乘积（用于动态计算）
        self.scope = "hip"
        self.grip = None
        self.muzzle = None
        self.stock = None
        self.current_stance = "stand"
        self.current_stance_multipliers = {"stand": 1.0, "squat": 0.8, "lie": 0.6}   # 临时默认

        # 配置字典
        self.weapon_configs = {}
        self.weapon_type_map = {}
        self.stance_multipliers = {}        # 嵌套字典 {"rifle": {...}, "lmg": {...}}
        self.scope_multipliers = {}
        self.grip_multipliers = {}
        self.muzzle_multipliers = {}
        self.stock_multipliers = {}

        self._load_config()

        # 最终力度（用于外部查询）
        self.current_recoil_strength = 0

        # 鼠标状态
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
                    self.weapon_configs = rc.get("weapons", {})
                    self.weapon_type_map = rc.get("weapon_types", {})
                    self.stance_multipliers = rc.get("stance_multipliers", {})     # 嵌套字典
                    self.scope_multipliers = rc.get("scope_multipliers", {})
                    self.grip_multipliers = rc.get("grip_multipliers", {})
                    self.muzzle_multipliers = rc.get("muzzle_multipliers", {})
                    self.stock_multipliers = rc.get("stock_multipliers", {})
            except Exception as e:
                print(f"[压枪模块] 配置加载失败: {e}")

    def _init_default_config(self):
        self.weapon_configs = {
            "M416": {"base": 10.0, "auto_fire": False, "dynamic_increment_per_second": 6.0},
            "AKM": {"base": 12.0, "auto_fire": False, "dynamic_increment_per_second": 8.0}
        }
        self.weapon_type_map = {"M416": "rifle", "AKM": "rifle"}
        self.stance_multipliers = {
            "rifle": {"stand": 1.0, "squat": 0.8, "lie": 0.6},
            "lmg":   {"stand": 1.0, "squat": 0.4, "lie": 0.2},
            "smg":   {"stand": 1.0, "squat": 0.8, "lie": 0.7}
        }
        self.scope_multipliers = {"red_dot": 1.2, "holo": 1.2, "x2": 2.0, "x3": 3.0, "x4": 4.0, "x6": 6.0}
        self.grip_multipliers = {"vertical": 0.9, "half": 1.0, "light": 1.0}
        self.muzzle_multipliers = {"compensator": 0.85, "flash_hider": 0.95}
        self.stock_multipliers = {"tactical": 0.9}

    def save_config(self):
        config = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        config["recoil_settings"] = {
            "fire_key": self.fire_key_str,
            "recoil_delay": self.recoil_delay,
            "weapons": self.weapon_configs,
            "weapon_types": self.weapon_type_map,
            "stance_multipliers": self.stance_multipliers,
            "scope_multipliers": self.scope_multipliers,
            "grip_multipliers": self.grip_multipliers,
            "muzzle_multipliers": self.muzzle_multipliers,
            "stock_multipliers": self.stock_multipliers
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    def _parse_fire_key(self, key_str):
        key_str = key_str.lower()
        if hasattr(keyboard.Key, key_str):
            self.fire_key = getattr(keyboard.Key, key_str)
        else:
            self.fire_key = keyboard.KeyCode.from_char(key_str)

    # ================= 外部接口 =================
    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled

    def update_current_weapon(self, weapon_name: str):
        if weapon_name == self.current_weapon:
            return
        self.current_weapon = weapon_name
        wp_data = self.weapon_configs.get(weapon_name, {})
        self.base_recoil = wp_data.get("base", 0.0)
        self.auto_fire_enabled = wp_data.get("auto_fire", False)
        self.dynamic_increment = wp_data.get("dynamic_increment_per_second", 0.0)

        # 根据武器类型获取姿势系数表
        weapon_type = self.weapon_type_map.get(weapon_name, "rifle")
        self.current_stance_multipliers = self.stance_multipliers.get(weapon_type,
                                                                     {"stand": 1.0, "squat": 0.8, "lie": 0.6})
        # 更新总系数
        self._recalculate_multiplier()

    def update_attachments(self, attachments: dict):
        if "scope" in attachments:
            self.scope = attachments["scope"]
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
        """计算静态总系数（不含时间增量），用于动态压枪公式中的乘数"""
        if not self.current_weapon or self.base_recoil == 0:
            self.total_multiplier = 1.0
            return

        scope_mult = self.scope_multipliers.get(self.scope, 1.0)
        grip_mult = self.grip_multipliers.get(self.grip, 1.0) if self.grip else 1.0
        muzzle_mult = self.muzzle_multipliers.get(self.muzzle, 1.0) if self.muzzle else 1.0
        stock_mult = self.stock_multipliers.get(self.stock, 1.0) if self.stock else 1.0
        stance_mult = self.current_stance_multipliers.get(self.current_stance, 1.0)

        self.total_multiplier = scope_mult * grip_mult * muzzle_mult * stock_mult * stance_mult
        # 立即更新 current_recoil_strength 用于外部显示（静态部分，不含时间增量）
        self.current_recoil_strength = int(round(self.base_recoil * self.total_multiplier))
        print(f"[压枪静态] {self.current_weapon} | 姿势:{self.current_stance} | 倍镜:{self.scope} | 握把:{self.grip} | 枪口:{self.muzzle} | 枪托:{self.stock} -> 总系数: {self.total_multiplier:.3f}")

    # ================= 事件处理 =================
    def _on_mouse_click(self, x, y, button, pressed):
        if button == mouse.Button.left:
            self.is_firing = pressed
            if pressed:
                self.fire_start_time = time.time()
                if not (self.is_enabled and self.current_weapon and self.auto_fire_enabled):
                    self.kb.press(self.fire_key)
            else:
                self.fire_start_time = 0
                self.kb.release(self.fire_key)

    def _recoil_worker_loop(self):
        while self._thread_running:
            if self.is_enabled and self.is_firing and self.current_weapon:
                # 动态压枪力度 = (基础力度 + 时间×动态增量) × 总系数
                elapsed = max(0, time.time() - self.fire_start_time)
                raw_strength = self.base_recoil + elapsed * self.dynamic_increment
                total = raw_strength * self.total_multiplier
                strength = int(round(total))
                self.current_recoil_strength = strength   # 实时更新供外部显示

                # 连发模拟（自动武器）
                if self.auto_fire_enabled:
                    self.kb.press(self.fire_key)
                    self.kb.release(self.fire_key)

                # 压枪位移
                if strength > 0:
                    ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, 0, strength, 0, 0)

                time.sleep(self.recoil_delay)
            else:
                time.sleep(0.01)

    def shutdown(self):
        self._thread_running = False
        if hasattr(self, 'mouse_listener'):
            self.mouse_listener.stop()