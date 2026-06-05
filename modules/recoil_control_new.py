import ctypes
import time
import threading
import json
import os
from pynput import mouse, keyboard

# Windows API 常量
MOUSEEVENTF_MOVE = 0x0001

class RecoilControlModule:
    """
    增强版压枪模块，支持倍镜、握把、枪口、枪托、姿势系数
    """

    def __init__(self, config_file="config.json"):
        self.config_file = config_file

        # 核心状态
        self.is_enabled = False
        self.recoil_delay = 0.02
        self.fire_key_str = "end"
        self.fire_key = keyboard.Key.end

        # 武器信息
        self.current_weapon = None          # 当前枪械名称
        self.base_recoil = 0.0              # 基础力度
        self.auto_fire_enabled = False      # 是否连发

        # 配件系数（默认均为1.0）
        self.scope = "hip"                  # 当前倍镜标识
        self.grip = None
        self.muzzle = None
        self.stock = None
        self.current_stance = "stand"       # 姿势

        # 配置字典
        self.weapon_configs = {}             # 武器基础数据 {"M416": {"base":10.0, "auto_fire":false}}
        self.scope_multipliers = {}          # 倍镜系数 {"red_dot":1.2, "x3":3.0, ...}
        self.grip_multipliers = {}           # 握把系数 {"vertical":0.9, "half":1.0, ...}
        self.muzzle_multipliers = {}         # 枪口系数 {"compensator":0.85, "flash_hider":0.95, ...}
        self.stock_multipliers = {}          # 枪托系数 {"tactical":0.9, ...}
        self.stance_multipliers = {"stand":1.0, "squat":0.8, "lie":0.6}

        self._load_config()

        # 最终力度
        self.current_recoil_strength = 0

        # 鼠标左键状态
        self.is_firing = False
        self._thread_running = True
        self.kb = keyboard.Controller()

        # 启动工作线程和监听器
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
                    self.stance_multipliers = rc.get("stance_multipliers", self.stance_multipliers)
                    self.scope_multipliers = rc.get("scope_multipliers", {})
                    self.grip_multipliers = rc.get("grip_multipliers", {})
                    self.muzzle_multipliers = rc.get("muzzle_multipliers", {})
                    self.stock_multipliers = rc.get("stock_multipliers", {})
            except Exception as e:
                print(f"[压枪模块] 配置加载失败: {e}")

    def _init_default_config(self):
        """生成默认配置示例"""
        self.weapon_configs = {"M416": {"base": 10.0, "auto_fire": False}}
        self.scope_multipliers = {"red_dot": 1.2, "holo": 1.2, "x2": 2.0, "x3": 3.0, "x4": 4.0, "x6": 6.0}
        self.grip_multipliers = {"vertical": 0.9, "half": 1.0, "light": 1.0}
        self.muzzle_multipliers = {"compensator": 0.85, "flash_hider": 0.95}
        self.stock_multipliers = {"tactical": 0.9}
        # 不自动保存，由外部配置管理

    def save_config(self):
        """保存当前配置到文件"""
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
        """更新当前手持武器（由武器检测模块调用）"""
        if weapon_name == self.current_weapon:
            return
        self.current_weapon = weapon_name
        wp_data = self.weapon_configs.get(weapon_name, {})
        self.base_recoil = wp_data.get("base", 0.0)
        self.auto_fire_enabled = wp_data.get("auto_fire", False)
        self._recalculate_strength()

    def update_attachments(self, attachments: dict):
        """
        更新配件信息（由装备栏检测模块调用）
        attachments = {"scope": "red_dot", "grip": "vertical", "muzzle": "compensator", "stock": "tactical"}
        只传入有配件的键，未传入的键保持不变（或设为 None）
        """
        if "scope" in attachments:
            self.scope = attachments["scope"]
        if "grip" in attachments:
            self.grip = attachments["grip"]
        if "muzzle" in attachments:
            self.muzzle = attachments["muzzle"]
        if "stock" in attachments:
            self.stock = attachments["stock"]
        self._recalculate_strength()

    def update_stance(self, stance: str):
        """更新姿势（由姿势识别模块调用）"""
        if stance in self.stance_multipliers and stance != self.current_stance:
            self.current_stance = stance
            self._recalculate_strength()

    def _recalculate_strength(self):
        """核心计算：基础力度 * 所有系数"""
        if not self.current_weapon or self.base_recoil == 0:
            self.current_recoil_strength = 0
            return

        # 倍镜系数
        scope_mult = self.scope_multipliers.get(self.scope, 1.0)
        # 握把系数
        grip_mult = self.grip_multipliers.get(self.grip, 1.0) if self.grip else 1.0
        # 枪口系数
        muzzle_mult = self.muzzle_multipliers.get(self.muzzle, 1.0) if self.muzzle else 1.0
        # 枪托系数
        stock_mult = self.stock_multipliers.get(self.stock, 1.0) if self.stock else 1.0
        # 姿势系数
        stance_mult = self.stance_multipliers.get(self.current_stance, 1.0)

        raw = self.base_recoil * scope_mult * grip_mult * muzzle_mult * stock_mult * stance_mult
        self.current_recoil_strength = int(round(raw))
        print(f"[压枪计算] {self.current_weapon} | 姿势:{self.current_stance} | 倍镜:{self.scope} | 握把:{self.grip} | 枪口:{self.muzzle} | 枪托:{self.stock} -> 力度: {self.current_recoil_strength}px/tick")

    # ================= 事件处理 =================
    def _on_mouse_click(self, x, y, button, pressed):
        if button == mouse.Button.left:
            self.is_firing = pressed
            if pressed:
                is_auto_clicking = (self.is_enabled and self.current_weapon and self.auto_fire_enabled)
                if not is_auto_clicking:
                    self.kb.press(self.fire_key)
            else:
                self.kb.release(self.fire_key)

    def _recoil_worker_loop(self):
        while self._thread_running:
            if self.is_enabled and self.is_firing and self.current_weapon:
                if self.auto_fire_enabled:
                    self.kb.press(self.fire_key)
                    self.kb.release(self.fire_key)
                if self.current_recoil_strength > 0:
                    ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, 0, self.current_recoil_strength, 0, 0)
                time.sleep(self.recoil_delay)
            else:
                time.sleep(0.01)

    def shutdown(self):
        self._thread_running = False
        if hasattr(self, 'mouse_listener'):
            self.mouse_listener.stop()