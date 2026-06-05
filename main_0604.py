import tkinter as tk
from tkinter import ttk
import mss
from pynput import keyboard, mouse
import threading
import time
import json
import os

from modules.region_manager import RegionManager
from modules.minimap_radar import MinimapRadarModule
from modules.elevation_radar import ElevationRadarModule
from modules.mortar_assistant import MortarAssistant
from modules.rocket_assistant import RocketAssistant
from modules.map_assistant import MapPointAssistant
from modules.throwables_assistant import ThrowablesAssistant
from modules.vss_assistant import VssAssistant
from modules.crossbow_assistant import CrossbowAssistant
from modules.largemap_radar import AutoMapDistanceAssistant
from modules.weapon_identifier import WeaponIdentifier
from modules.scope_identifier import ScopeIdentifier
from modules.recoil_control_old import RecoilControlModule
from modules.gesture_identifier import GestureIdentifier

class RoundedButton(tk.Canvas):
    def __init__(self, parent, width, height, radius, text, command, text_size = 10, is_toggle=False, *args, **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, *args, **kwargs)
        self.command = command
        self.is_toggle = is_toggle
        self.is_active = False
        self.color_default = "#FFFFFF"
        self.color_hover = "#F3F4F6"
        self.color_pressed = "#D1D5DB"
        self.color_active = "#E5E7EB"
        self.text_color = "#000000"
        self.radius = radius
        self.text_size = text_size
        self.rect = self._create_rounded_rect(0, 0, width, height, radius, fill=self.color_default, outline="#E5E7EB", width=1)
        self.text_id = self.create_text(width/2, height/2, text=text, fill=self.text_color, font=("Microsoft YaHei", text_size, "bold"))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_hover)
        self.bind("<Leave>", self._on_leave)

    def _create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2, x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_press(self, event):
        self.itemconfig(self.rect, fill=self.color_pressed)
    def _on_release(self, event):
        if self.is_toggle:
            self.is_active = not self.is_active
        self.itemconfig(self.rect, fill=self.color_active if self.is_active else self.color_hover)
        if self.command:
            self.command()
    def _on_hover(self, event):
        if not self.is_active:
            self.itemconfig(self.rect, fill=self.color_hover)
    def _on_leave(self, event):
        if not self.is_active:
            self.itemconfig(self.rect, fill=self.color_default)
    def set_active(self, state):
        self.is_active = state
        self.itemconfig(self.rect, fill=self.color_active if self.is_active else self.color_default)
    def set_text(self, text):
        self.itemconfig(self.text_id, text=text)

class TacticalHub:
    def __init__(self, root):
        self.root = root
        self.root.title("PUBG 战术助手")
        self.root.geometry("250x400")
        self.root.configure(bg="#F9FAFB")
        self.root.attributes("-topmost", True)
        # self.root.withdraw()  # 初始隐藏

        self.config_file = "config.json"
        self.region_manager = RegionManager(self.root, config_file=self.config_file)

        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            self.sw, self.sh = monitor["width"], monitor["height"]

        # 模块初始化
        self.minimap = MinimapRadarModule(self.root, self.region_manager, config_file=self.config_file)
        self.elevation = ElevationRadarModule(self.root, self.region_manager, fps=30, config_file=self.config_file)
        self.map_assist = MapPointAssistant(self.root, self.region_manager, config_file=self.config_file)
        self.largemap_radar = AutoMapDistanceAssistant(self.root, self.region_manager, config_file=self.config_file)

        self.rocket = RocketAssistant(self.root, self.region_manager, self.minimap, fps=30, config_file=self.config_file)
        self.mortar = MortarAssistant(self.root, self.region_manager, self.minimap, self.elevation, fps=30, config_file=self.config_file)
        self.throwables = ThrowablesAssistant(self.root, self.region_manager, self.minimap, self.elevation, fps=30, config_file=self.config_file)
        self.vss_assist = VssAssistant(self.root, self.region_manager, self.minimap, fps=30, config_file=self.config_file)
        self.crossbow_assist = CrossbowAssistant(self.root, self.region_manager, self.minimap, fps=30, config_file=self.config_file)

        self.weapon_id = WeaponIdentifier(self.region_manager, threshold=0.5)
        self.scope_id = ScopeIdentifier(self.region_manager, threshold=0.55)
        self.scope_id.set_enabled(True)      # 启用倍镜识别
        self.gesture_id = GestureIdentifier(region_manager=self.region_manager)
        self.recoil = RecoilControlModule(config_file=self.config_file)

        self.weapon_detection_enabled = False
        self.display_enabled = False
        self.recoil_enabled = False
        self.current_weapon = None
        self._stop_detection = False
        self.detection_thread = None
        self.left_pressed = False
        self.middle_pressed = False
        self.alt_pressed = False
        self.current_scope = None
        self.current_gesture = None
        self.scope_update_after_id = None
        self.scope_update_delay = 500  # 毫秒
        self._is_capturing = False  
        self.status_overlay = None
        self.status_canvas = None
        self._init_status_overlay()

        def on_weapon_identified(weapon, score):
            if weapon and score >= 0.5:
                self.current_weapon = weapon
                self.update_weapon_ui(weapon)
            else:
                self.current_weapon = None
                self.update_weapon_ui(None)
            self.update_status_full()
            self.update_status_display()

        # 姿势识别回调
        def on_gesture_identified(gesture, score):
            if gesture and score >= 0.7:
                self.current_gesture = gesture
                if self.recoil_enabled:
                    self.recoil.update_stance(gesture)
            else:
                self.current_gesture = None
            self.update_status_full()
            self.update_status_display()

        # 设置回调
        self.weapon_id.set_enabled(False, on_weapon_identified)
        self.gesture_id.set_enabled(False, on_gesture_identified)

        # 快捷键配置
        self.hotkeys = {
            "throw": "v",
            "toggle_display": "<ctrl>+<shift>+<space>",
            "measure_map": "<f1>",
            "toggle_recoil": "<ctrl>+<shift>+<tab>",
            "toggle_weapon_detection": "<f2>"
        }
        self.load_hotkey_config()

        self.init_ui()
        self.start_listeners()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # 地图选项卡
        self.map_tab = tk.Frame(self.notebook, bg="#F9FAFB")
        self.notebook.add(self.map_tab, text="地图点位")
        self.map_tab.columnconfigure(0, weight=1)         
        self.build_map_tab()

        # 启动选项卡
        self.launch_tab = tk.Frame(self.notebook, bg="#F9FAFB")
        self.notebook.add(self.launch_tab, text="启动助手")
        self.build_launch_tab()

        # 校准选项卡
        self.calib_tab = tk.Frame(self.notebook, bg="#F9FAFB")
        self.notebook.add(self.calib_tab, text="校准区域")
        self.build_calib_tab()

        # 按键选项卡
        self.key_tab = tk.Frame(self.notebook, bg="#F9FAFB")
        self.notebook.add(self.key_tab, text="按键设置")
        self.build_key_tab()

        self.status_var = tk.StringVar(value="就绪")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN,
                                anchor=tk.CENTER, bg="#3498DB", fg="#FFFFFF", font=("Microsoft YaHei", 10, "bold"))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _init_status_overlay(self):
        self.status_overlay = tk.Toplevel(self.root)
        self.status_overlay.attributes("-topmost", True)
        self.status_overlay.attributes("-transparentcolor", "black")
        self.status_overlay.overrideredirect(True)
        x = 10
        y = self.sh - 60
        self.status_overlay.geometry(f"300x40+{x}+{y}")
        self.status_canvas = tk.Canvas(self.status_overlay, bg="black", highlightthickness=0, width=300, height=40)
        self.status_canvas.pack()
        self.status_overlay.withdraw() 

    def set_status(self, status_text, status_type="info"):
        """设置状态栏文本和背景色
        status_type: 'info' (蓝色), 'success' (绿色), 'error' (红色), 'warning' (橙色)
        """
        self.status_var.set(status_text)
        colors = {
            "info": "#3498DB",     # 天蓝
            "success": "#2ECC71",  # 绿
            "error": "#E74C3C",    # 红
            "warning": "#F39C12",  # 橙
            "default": "#3498DB"
        }
        self.status_bar.config(bg=colors.get(status_type, colors["default"]))

    def select_map(self, idx):
        for i, btn in enumerate(self.map_buttons):
            btn.set_active(i == idx)
        map_name = self.map_names[idx]
        self.map_assist.set_map(map_name)

    def select_size(self, idx):
        for i, btn in enumerate(self.size_buttons):
            btn.set_active(i == idx)
        size_key = ["small", "medium", "large"][idx]
        self.map_assist.set_marker_size(size_key)

    def build_map_tab(self):
        self.map_names = [
            "艾伦格 (Erangel)", "米拉玛 (Miramar)", "泰戈 (Taego)",
            "荣都 (Rondo)", "帝斯顿 (Deston)", "维寒迪 (Vikendi)"
        ]
        self.map_buttons = []

        # 地图按钮（单列居中）
        for i, map_name in enumerate(self.map_names):
            short_name = map_name.split()[0]
            # 创建容器 Frame，使按钮能够居中
            container = tk.Frame(self.map_tab, bg="#F9FAFB")
            container.grid(row=i, column=0, sticky="ew", padx=10, pady=5)
            container.columnconfigure(0, weight=1)   # 容器内水平扩展
            btn = RoundedButton(container, 220, 34, 25, map_name,
                                command=lambda idx=i: self.select_map(idx), is_toggle=True)
            btn.pack(anchor="center")               # 按钮在容器内水平居中
            self.map_buttons.append(btn)

        # 标点尺寸标签
        tk.Label(self.map_tab, text="--标点尺寸--", bg="#F9FAFB", fg="#6B7280").grid(
            row=len(self.map_names), column=0, pady=5
        )
        # 标点尺寸按钮（水平排列）
        size_frame = tk.Frame(self.map_tab, bg="#F9FAFB")
        size_frame.grid(row=len(self.map_names)+1, column=0, pady=5)
        self.size_buttons = []
        sizes = [("小", "small"), ("中", "medium"), ("大", "large")]
        for i, (name, val) in enumerate(sizes):
            btn = RoundedButton(size_frame, 66, 35, 25, name,
                                command=lambda idx=i: self.select_size(idx), is_toggle=True)
            btn.grid(row=0, column=i, padx=4)
            self.size_buttons.append(btn)

        self.select_map(0)
        self.select_size(1)

    def build_launch_tab(self):
        self.btn_weapon_detect = RoundedButton(self.launch_tab, 220, 45, 25, "开启武器检测", command=self.toggle_weapon_detection, is_toggle=True, text_size=12)
        self.btn_weapon_detect.pack(pady=6)
        self.btn_display = RoundedButton(self.launch_tab, 220, 45, 25, "开启瞄准辅助", command=self.toggle_display, is_toggle=True, text_size=12)
        self.btn_display.pack(pady=6)
        self.btn_recoil = RoundedButton(self.launch_tab, 220, 45, 25, "开启辅助压枪", command=self.toggle_recoil, is_toggle=True, text_size=12)
        self.btn_recoil.pack(pady=6)

        tk.Label(self.launch_tab, text="--启用特殊武器助手--", bg="#F9FAFB", fg="#6B7280").pack(pady=5)

        assistants = [
            ("迫击炮", "mortar"),
            ("火箭筒", "rocket"),
            ("投掷物", "throwables"),
            ("VSS", "vss"),
            ("十字弩", "crossbow")
        ]
        self.assistant_btns = {}
        frame = tk.Frame(self.launch_tab, bg="#F9FAFB")
        frame.pack(pady=10)  # frame 本身用 pack，内部用 grid 没问题
        for i, (name, key) in enumerate(assistants):
            btn = RoundedButton(frame, 107, 30, 25, name, command=lambda k=key: self.toggle_assistant(k), is_toggle=True)
            btn.grid(row=i//2, column=i%2, padx=3, pady=5)
            self.assistant_btns[key] = btn


    def build_calib_tab(self):
        self.btn_debug = RoundedButton(self.calib_tab, 220, 32, 25, "显示所有区域框", command=self.toggle_debug, is_toggle=True)
        self.btn_debug.pack(pady=5)

        btn_calib_largemap_scale = RoundedButton(self.calib_tab, 220, 36, 25, "校准大地图 1km 比例尺",
                                                command=lambda: self.region_manager.calibrate_scale("largemap_1km_px"))
        btn_calib_largemap_scale.pack(pady=3)

        regions = [
            ("小地图区域", "minimap_region"),
            ("大地图区域", "largemap_region"),
            ("垂直测高区域", "elevation_region"),
            ("准星区域", "crosshair_region"),
            ("倍镜检测区域", "scope_region"),
            ("武器栏区域", "weapon_region")
        ]
        for name, key in regions:
            btn = RoundedButton(self.calib_tab, 220, 36, 25, f"校准{name}",
                                command=lambda k=key: self.region_manager.calibrate_region(k))
            btn.pack(pady=3)

    def build_key_tab(self):
        self.key_frame = tk.Frame(self.key_tab, bg="#F9FAFB")
        self.key_frame.pack(fill="both", expand=True, padx=5, pady=5)

        key_configs = [
            ("手雷瞬爆", "throw"),
            ("显示层开关", "toggle_display"),
            ("大地图测距", "measure_map"),
            ("压枪开关", "toggle_recoil"),
            ("武器检测开关", "toggle_weapon_detection"),
        ]
        self.key_labels = {}

        for label, action in key_configs:
            # 每个功能使用一个容器 Frame
            func_frame = tk.Frame(self.key_frame, bg="#F9FAFB")
            func_frame.pack(fill="x", pady=2)

            left_frame = tk.Frame(func_frame, bg="#F9FAFB")
            left_frame.pack(side="left", fill="both", expand=True)

            # 描述标签
            desc_label = tk.Label(left_frame, text=label, bg="#F9FAFB", fg="#333333", font=("Microsoft YaHei", 10, "bold"))
            desc_label.pack(anchor="w")

            # 快捷键显示
            current_key = self.format_hotkey(self.hotkeys[action])
            key_label = tk.Label(left_frame, text=current_key, bg="#F9FAFB", fg="#2563EB", font=("Consolas", 10, "bold"))
            key_label.pack(anchor="w", pady=(1, 0))
            self.key_labels[action] = key_label

            # 右侧：录制按钮
            record_btn = RoundedButton(func_frame, 60, 30, 25, "录制", 
                                    command=lambda a=action, lbl=key_label: self.capture_hotkey(a, lbl), 
                                    is_toggle=False)
            record_btn.pack(side="right", padx=2)

        # 保存快捷键按钮
        save_btn = RoundedButton(self.key_frame, 220, 30, 25, "保存快捷键", 
                                command=self.save_hotkey_config, is_toggle=False)
        save_btn.pack(pady=5)

        # 恢复默认按钮
        default_btn = RoundedButton(self.key_frame, 220, 30, 25, "恢复默认", 
                                    command=self.reset_default_hotkeys, is_toggle=False)
        default_btn.pack(pady=5)

    def toggle_assistant(self, key):
        # 仅当显示层开启且当前武器匹配时才允许手动切换
        weapon_map = {"rocket": "Rocket", "throwables": "Grenade", "vss": "VSS", "crossbow": "Crossbow"}
        if key == "mortar":
            # 迫击炮独立控制，不依赖武器
            self.mortar.enable_module(not self.mortar.is_enabled)
            self.assistant_btns["mortar"].set_active(self.mortar.is_enabled)
        else:
            required_weapon = weapon_map.get(key)
            if self.display_enabled and self.current_weapon == required_weapon:
                module = getattr(self, key)
                module.enable_module(not module.is_enabled)
                self.assistant_btns[key].set_active(module.is_enabled)

    def format_hotkey(self, combo):
        """将组合键字符串转换为便于显示的格式（去除尖括号，大写）"""
        return combo.replace("<", "").replace(">", "").upper()

    def capture_hotkey(self, action_key, key_label):
        if self._is_capturing:
            return
        self._is_capturing = True

        # 停止所有现有监听器
        if hasattr(self, 'hotkey_listener') and self.hotkey_listener:
            self.hotkey_listener.stop()
        if hasattr(self, 'keyboard_listener') and self.keyboard_listener:
            self.keyboard_listener.stop()
        if hasattr(self, 'mouse_listener') and self.mouse_listener:
            self.mouse_listener.stop()

        key_label.config(text="请按下...")
        self.root.update()

        modifiers = []

        def on_press(key):
            name = ""
            if hasattr(key, 'name') and key.name:
                name = f"<{key.name}>"
                if name in ["<ctrl_l>", "<ctrl_r>"]:
                    name = "<ctrl>"
                elif name in ["<shift_l>", "<shift_r>"]:
                    name = "<shift>"
                elif name in ["<alt_l>", "<alt_r>", "<alt_gr>"]:
                    name = "<alt>"
                elif name == "<space>":
                    name = "<space>"
                if name in ["<ctrl>", "<shift>", "<alt>"]:
                    if name not in modifiers:
                        modifiers.append(name)
                    return True
                else:
                    finish_capture(name)
                    return False

            char = None
            if hasattr(key, 'char') and key.char:
                char = key.char
                if 1 <= ord(char) <= 26:
                    char = chr(ord(char) + 96)
            elif hasattr(key, 'vk') and key.vk is not None:
                if 65 <= key.vk <= 90:
                    char = chr(key.vk).lower()
                elif 48 <= key.vk <= 57:
                    char = chr(key.vk)

            if char:
                finish_capture(char.lower())
                return False

        def finish_capture(main_key):
            combo_str = "+".join(modifiers + [main_key])
            # 手雷瞬爆只允许单键，不允许带修饰键
            if action_key == "throw" and modifiers:
                # 如果用户按了修饰键，则忽略并提示
                key_label.config(text="仅允许单键")
                self.root.after(1000, lambda: key_label.config(text=self.format_hotkey(self.hotkeys[action_key])))
                self._is_capturing = False
                self.restart_listeners()
                return

            self.hotkeys[action_key] = combo_str
            self._is_capturing = False
            key_label.config(text=self.format_hotkey(combo_str))
            self.root.after(100, self.restart_listeners)

        self.temp_listener = keyboard.Listener(on_press=on_press)
        self.temp_listener.start()

    def load_hotkey_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    if "hotkeys" in data:
                        self.hotkeys.update(data["hotkeys"])
            except: pass

    def save_hotkey_config(self):
        data = {}
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                try: data = json.load(f)
                except: pass
        data["hotkeys"] = self.hotkeys
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=4)

    def toggle_weapon_detection(self):
        self.weapon_detection_enabled = not self.weapon_detection_enabled
        self.btn_weapon_detect.set_active(self.weapon_detection_enabled)
        self.btn_weapon_detect.set_text(f"{'关闭' if self.weapon_detection_enabled else '开启'}武器检测")
        # 异步执行耗时的关闭操作，避免阻塞按钮响应
        self.root.after(10, lambda: self._do_weapon_detection_state_change())

    def _do_weapon_detection_state_change(self):
        self.weapon_id.set_enabled(self.weapon_detection_enabled)
        self.gesture_id.set_enabled(self.weapon_detection_enabled)
        if not self.weapon_detection_enabled:
            self.current_weapon = None
            self.update_weapon_ui(None)
        self.update_status_display()

    def update_status_display(self):
        if not self.weapon_detection_enabled:
            if self.status_overlay:
                self.status_overlay.withdraw()
            return
        if not self.status_overlay:
            return
        scope_map = {
            "red_dot": "红点",
            "holographic": "全息",
            "x2": "二倍镜",
            "x3": "三倍镜",
            "x4": "四倍镜",
            "x6": "六倍镜",
            "x8": "八倍镜",
            "iron": "机瞄",
            "hip": "腰射"
        }
        # 姿势映射
        gesture_map = {"stand": "站立", "squat": "蹲下", "lie": "趴下"}

        parts = []
        if self.current_weapon:
            parts.append(self.current_weapon)
        if self.current_scope:
            # 映射为中文
            scope_display = scope_map.get(self.current_scope, self.current_scope)
            parts.append(scope_display)
        if self.current_gesture:
            gesture_display = gesture_map.get(self.current_gesture, self.current_gesture)
            parts.append(gesture_display)

        # 使用空格分隔，去掉竖线
        text = "  ".join(parts) if parts else ""
        self.status_canvas.delete("status_text")
        if text:
            self.status_canvas.create_text(10, 20, anchor="w", text=text,
                                        fill="white",
                                        font=("Microsoft YaHei", 15, "bold"),
                                        tags="status_text")
            self.status_overlay.deiconify()
        else:
            self.status_overlay.withdraw()

    def update_status_full(self):
        # 倍镜映射（根据模板文件夹名称）
        scope_map = {
            "red_dot": "红点",
            "holographic": "全息",
            "x2": "二倍镜",
            "x3": "三倍镜",
            "x4": "四倍镜",
            "x6": "六倍镜",
            "x8": "八倍镜",
            "iron": "机瞄"
        }
        # 姿势映射
        gesture_map = {"stand": "站立", "squat": "蹲下", "lie": "趴下"}

        parts = []
        if self.current_weapon:
            parts.append(self.current_weapon)
        if self.current_scope:
            # 尝试映射，若找不到则保留原值（可能直接是数字或简称）
            scope_display = scope_map.get(self.current_scope, self.current_scope)
            parts.append(scope_display)
        if self.current_gesture:
            gesture_display = gesture_map.get(self.current_gesture, self.current_gesture)
            parts.append(gesture_display)

        status_text = " | ".join(parts) if parts else "就绪"
        # 根据武器识别状态设置背景色
        if self.current_weapon:
            self.set_status(status_text, "success")
        else:
            self.set_status(status_text, "info")

    def _update_scope_from_screenshot(self):
        """延迟执行的倍镜识别，在右键按下一段时间后调用"""
        self.scope_update_after_id = None   # 清除ID
        try:
            with mss.MSS() as sct:
                scope, score, _ = self.scope_id.identify_current_scope(sct)
                if scope and score >= 0.55:
                    self.current_scope = scope
                    if self.recoil_enabled:
                        self.recoil.update_scope(scope)
                else:
                    # 未识别到倍镜，重置为机瞄（腰射）状态
                    self.current_scope = None
                    if self.recoil_enabled:
                        self.recoil.update_scope("hip")
                # 刷新状态栏显示
                self.root.after(0, self.update_status_full)
                self.update_status_display()
        except Exception as e:
            print(f"[倍镜识别延迟错误] {e}")

    def update_weapon_ui(self, weapon_name):

        # 特殊武器列表
        special = {
            "Rocket": self.rocket,
            "Grenade": self.throwables,
            "VSS": self.vss_assist,
            "Crossbow": self.crossbow_assist
        }
        # 先将所有特殊助手关闭，再根据当前武器开启对应的助手
        for name, mod in special.items():
            if self.display_enabled and weapon_name == name:
                mod.enable_module(True)
            else:
                mod.enable_module(False)

        # 更新按钮状态
        for btn_key, mod in [("rocket", self.rocket), ("throwables", self.throwables),
                            ("vss", self.vss_assist), ("crossbow", self.crossbow_assist)]:
            if btn_key in self.assistant_btns:
                self.assistant_btns[btn_key].set_active(mod.is_enabled)

        if weapon_name and weapon_name not in special:
            if self.recoil_enabled:
                self.recoil.update_weapon(weapon_name)
                self.recoil.set_enabled(True)
            else:
                self.recoil.set_enabled(False)
        else:
            # 如果没有武器或是特殊武器，且压枪开关开启，也需要禁用
            if self.recoil_enabled:
                self.recoil.set_enabled(False)

    def toggle_display(self):
        self.display_enabled = not self.display_enabled
        self.btn_display.set_active(self.display_enabled)
        self.btn_display.set_text(f"{'关闭' if self.display_enabled else '开启'}瞄准辅助")
        # 迫击炮始终随显示层开启
        self.mortar.enable_module(self.display_enabled)
        self.assistant_btns["mortar"].set_active(self.display_enabled and self.mortar.is_enabled)
        # 重新评估特殊助手状态
        if self.current_weapon:
            self.update_weapon_ui(self.current_weapon)
        # 同步雷达显示
        self.minimap.set_enabled(self.display_enabled)
        self.elevation.set_enabled(self.display_enabled)
        self.minimap.set_display(self.display_enabled)
        self.elevation.set_display(self.display_enabled)
        self.largemap_radar.set_display(self.display_enabled)


    def toggle_recoil(self):
        self.recoil_enabled = not self.recoil_enabled
        self.btn_recoil.set_active(self.recoil_enabled)
        self.btn_recoil.set_text(f"{'关闭' if self.recoil_enabled else '开启'}辅助压枪")
        self.recoil.set_enabled(self.recoil_enabled)
        if self.recoil_enabled:
            # 立即同步当前武器、姿势、倍镜
            if self.current_weapon and self.current_weapon not in ["Rocket", "Grenade", "VSS", "Crossbow"]:
                self.recoil.update_weapon(self.current_weapon)
            if self.current_gesture:
                self.recoil.update_stance(self.current_gesture)
            if self.current_scope:
                self.recoil.update_scope(self.current_scope)

    def toggle_debug(self):
        self.region_manager.set_debug_mode(not self.region_manager.show_debug)
        self.btn_debug.set_active(self.region_manager.show_debug)
        self.btn_debug.set_text(f"{'关闭' if self.region_manager.show_debug else '开启'}显示所有区域框")

    def restart_listeners(self):
        """停止并重新启动所有监听器（应用新快捷键）"""
        if hasattr(self, 'keyboard_listener') and self.keyboard_listener:
            self.keyboard_listener.stop()
        if hasattr(self, 'mouse_listener') and self.mouse_listener:
            self.mouse_listener.stop()
        if hasattr(self, 'hotkey_listener') and self.hotkey_listener:
            self.hotkey_listener.stop()
        self.start_listeners()

    def start_listeners(self):
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.keyboard_listener.start()
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.mouse_listener.start()
        hotkey_mapping = {
            self.hotkeys['toggle_display']: self.toggle_display,
            self.hotkeys['measure_map']: self.largemap_radar.toggle_mode,
            self.hotkeys['toggle_recoil']: self.toggle_recoil,
            self.hotkeys['toggle_weapon_detection']: self.toggle_weapon_detection,
        }
        self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_mapping)
        self.hotkey_listener.start()

    def on_throw_hotkey(self):
        """手雷瞬爆热键的回调（检查条件）"""
        if self.display_enabled and self.current_weapon == "Grenade":
            self.throwables.toggle_auto_throw()

    def on_key_press(self, key):
        try:
            if key == keyboard.Key.home:
                if self.root.state() == 'normal':
                    self.root.withdraw()
                else:
                    self.root.deiconify()
                    self.root.lift()
                    self.root.focus_force()
                return
        except:
            pass
        if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt_pressed = True

        throw_key = self.hotkeys['throw']
        # 将组合键字符串解析成一组按键名和主键
        parts = throw_key.split('+')
        main_key = parts[-1]

        # 检测当前按下的键是否匹配
        current_mods = set()
        if self.alt_pressed:
            current_mods.add('<alt>')
        if hasattr(key, 'char') and key.char == main_key:
            if self.display_enabled and self.current_weapon == "Grenade":
                self.throwables.toggle_auto_throw()

    def on_key_release(self, key):
        if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt_pressed = False

    def on_mouse_click(self, x, y, button, pressed):
        # 更新左键和中键状态
        if button == mouse.Button.left:
            self.left_pressed = pressed
        elif button == mouse.Button.middle:
            self.middle_pressed = pressed

        # 左键 + 中键同时按下 -> 启用地图点位助手
        if self.left_pressed and self.middle_pressed:
            if not self.map_assist.is_enabled:   # 避免重复启用
                self.map_assist.set_enabled(True)
        else:
            # 右键按下（且未按住 Alt）-> 关闭地图点位助手
            if button == mouse.Button.right and pressed:
                if not self.alt_pressed:
                    if self.map_assist.is_enabled:
                        self.map_assist.set_enabled(False)

        if button == mouse.Button.right and pressed and self.weapon_detection_enabled:
            # 取消之前的延迟任务，避免重复执行
            if self.scope_update_after_id:
                self.root.after_cancel(self.scope_update_after_id)
            # 启动延迟任务
            self.scope_update_after_id = self.root.after(self.scope_update_delay, self._update_scope_from_screenshot)

        # 传递给大地图测距模块
        self.largemap_radar.on_mouse_click(x, y, button, pressed)

    def save_hotkey_config(self):
        import shutil
        data = {}
        # 尝试读取现有配置文件
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"读取配置文件失败: {e}，将备份原文件并创建新文件")
                # 备份损坏的配置文件
                backup = self.config_file + ".bak"
                shutil.copy(self.config_file, backup)
                print(f"已备份至 {backup}")
                data = {}
        # 更新快捷键设置（不覆盖其他字段）
        data["hotkeys"] = self.hotkeys
        # 写回文件
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print("[快捷键] 配置已保存")    
    
    def reset_default_hotkeys(self):
        self.hotkeys = {
            "throw": "v",
            "toggle_display": "<ctrl>+<shift>+<space>",
            "measure_map": "<ctrl>+<shift>+m",
            "toggle_recoil": "<ctrl>+<shift>+<tab>",
            "toggle_weapon_detection": "<f2>"
        }
        self.save_hotkey_config()
        # 刷新UI中的快捷键显示
        for action, label in self.key_labels.items():
            label.config(text=self.format_hotkey(self.hotkeys[action]))

    def load_hotkey_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    if "hotkeys" in data:
                        self.hotkeys.update(data["hotkeys"])
            except:
                pass

    def on_closing(self):
        self._stop_detection = True
        self.weapon_id.set_enabled(False)
        self.recoil.shutdown()
        if self.status_overlay:
            self.status_overlay.destroy()
        self.keyboard_listener.stop()
        self.mouse_listener.stop()
        self.hotkey_listener.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TacticalHub(root)
    root.mainloop()