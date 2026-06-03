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
    PUBG 智能压枪与连发控制中枢
    负责维护状态、计算力度，并在开火时向系统发送底层位移信号。
    """
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        
        # === 核心维护变量 ===
        self.is_enabled = False          # 总开关
        self.recoil_delay = 0.02         # 下压与连发的延迟时间(秒)
        self.fire_key_str = "end"        # 连点按键名称 (写入配置文件)
        self.fire_key = keyboard.Key.end # pynput 对应的按键对象
        
        self.current_weapon = None       # 当前枪械 (如 "M416")
        self.current_stance = "stand"    # 当前姿势 (stand/squat/lie)
        self.current_scope = "hip"       # 当前倍镜 (hip/red_dot/x3/x4...)
        
        self.base_recoil = 0.0           # 枪械基础力度
        self.current_recoil_strength = 0 # 最终计算出的实际下压力度 (像素)
        self.auto_fire_enabled = False   # 当前是否需要连点连发
        
        # === 配置字典 (系数表) ===
        self.weapon_configs = {}
        self.stance_multipliers = {"stand": 1.0, "squat": 0.8, "lie": 0.6}
        self.scope_multipliers = {"hip": 1.0, "red_dot": 1.2, "x3": 3.0, "x4": 4.0, "x6": 6.0}
        
        self._load_config()
        
        # === 线程与监听器状态 ===
        self.is_firing = False           # 鼠标左键是否处于按下状态
        self._thread_running = True
        self.kb = keyboard.Controller()
        
        # 启动后台压枪执行线程
        self.worker_thread = threading.Thread(target=self._recoil_worker_loop, daemon=True)
        self.worker_thread.start()
        
        # 启动鼠标监听器
        self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
        self.mouse_listener.start()

    # ================= 配置读写 =================
    def _load_config(self):
        """读取压枪相关的配置参数"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    rc_config = config.get("recoil_settings", {})
                    
                    if not rc_config:
                        self._init_default_config()
                        return
                        
                    self.fire_key_str = rc_config.get("fire_key", "end")
                    self._parse_fire_key(self.fire_key_str)
                    
                    self.recoil_delay = rc_config.get("recoil_delay", 0.02)
                    self.weapon_configs = rc_config.get("weapons", {})
                    self.stance_multipliers = rc_config.get("stance_multipliers", self.stance_multipliers)
                    self.scope_multipliers = rc_config.get("scope_multipliers", self.scope_multipliers)
            except Exception as e:
                print(f"[压枪模块] 配置文件读取失败: {e}")

    def _init_default_config(self):
        """如果没配置，生成一份默认数据（方便测试）"""
        self.weapon_configs = {
            "M416": {"base": 10.0, "auto_fire": False},
            "AKM": {"base": 12.0, "auto_fire": False},
            "M16A4": {"base": 11.0, "auto_fire": True}, # 必须连发
            "SKS": {"base": 15.0, "auto_fire": True}
        }
        self.save_config()

    def save_config(self):
        """将当前的压枪参数写入统一配置文件"""
        config = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except: pass
            
        config["recoil_settings"] = {
            "fire_key": self.fire_key_str,
            "recoil_delay": self.recoil_delay,
            "weapons": self.weapon_configs,
            "stance_multipliers": self.stance_multipliers,
            "scope_multipliers": self.scope_multipliers
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    def _parse_fire_key(self, key_str):
        """将字符串如 'end' 转换为 pynput 按键对象"""
        key_str = key_str.lower()
        if hasattr(keyboard.Key, key_str):
            self.fire_key = getattr(keyboard.Key, key_str)
        else:
            # 如果是普通字母按键，如 'k'
            self.fire_key = keyboard.KeyCode.from_char(key_str)

    # ================= 状态更新接口 =================
    
    def set_enabled(self, enabled: bool):
        """总开关"""
        self.is_enabled = enabled
        print(f"[压枪模块] 状态: {'开启' if enabled else '关闭'}")

    def update_weapon(self, weapon_name):
        """更新枪械"""
        if weapon_name == self.current_weapon:
            return
        self.current_weapon = weapon_name
        
        # 查找枪械配置
        wp_data = self.weapon_configs.get(weapon_name, {})
        self.base_recoil = wp_data.get("base", 0.0)
        self.auto_fire_enabled = wp_data.get("auto_fire", False)
        
        self._recalculate_strength()

    def update_stance(self, stance):
        """更新姿势: stand, squat, lie"""
        if stance in self.stance_multipliers and stance != self.current_stance:
            self.current_stance = stance
            self._recalculate_strength()

    def update_scope(self, scope):
        """更新倍镜: hip, red_dot, x3, x4..."""
        if scope in self.scope_multipliers and scope != self.current_scope:
            self.current_scope = scope
            self._recalculate_strength()

    def _recalculate_strength(self):
        """核心计算公式：基础力度 * 姿势系数 * 倍镜系数"""
        if not self.current_weapon or self.base_recoil == 0:
            self.current_recoil_strength = 0
            return
            
        st_mult = self.stance_multipliers.get(self.current_stance, 1.0)
        sc_mult = self.scope_multipliers.get(self.current_scope, 1.0)
        
        # 计算并四舍五入为整数像素
        raw_strength = self.base_recoil * st_mult * sc_mult
        self.current_recoil_strength = int(round(raw_strength))
        
        # 调试输出
        print(f"[压枪计算] {self.current_weapon} | 姿势:{self.current_stance} | 镜:{self.current_scope} -> 力度: {self.current_recoil_strength}px/tick")

    # ================= 事件监听与执行线程 =================

    def _on_mouse_click(self, x, y, button, pressed):
        """pynput 鼠标点击回调"""
        if button == mouse.Button.left:
            self.is_firing = pressed
            
            if pressed:
                is_auto_clicking = (self.is_enabled and self.current_weapon and self.auto_fire_enabled)
                if not is_auto_clicking:
                    self.kb.press(self.fire_key)
            else:
                self.kb.release(self.fire_key)

    def _recoil_worker_loop(self):
        """后台高频执行线程 (取代了 Sleep 阻塞)"""
        while self._thread_running:
            # 只有当：总开关开启 + 左键按下 + 拿着有效的枪
            if self.is_enabled and self.is_firing and self.current_weapon:
                
                # 1. 连发逻辑 (反复敲击副开火键)
                if self.auto_fire_enabled:
                    self.kb.press(self.fire_key)
                    self.kb.release(self.fire_key)
                
                # 2. 压枪位移逻辑 (调用底层 Ctypes)
                if self.current_recoil_strength > 0:
                    ctypes.windll.user32.mouse_event(
                        MOUSEEVENTF_MOVE, 
                        0, 
                        self.current_recoil_strength, 
                        0, 0
                    )
                
                # 极短的延迟，保证平滑下压和连点间隔
                time.sleep(self.recoil_delay)
            else:
                # 未开火时休眠，极大降低 CPU 占用
                time.sleep(0.01)

    def shutdown(self):
        """安全清理退出"""
        self._thread_running = False
        self.mouse_listener.stop()