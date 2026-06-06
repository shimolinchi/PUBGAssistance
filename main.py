import tkinter as tk
from tkinter import ttk
import mss
from pynput import keyboard, mouse
import threading
import time
import ctypes
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
from modules.gesture_identifier import GestureIdentifier
from modules.weapon_detector import WeaponDetector
from modules.equipment_detector import EquipmentDetector
from modules.recoil_control import RecoilControlModule as RecoilControlModuleNew

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

        self.config_file = "config.json"
        self._set_app_icon('icon.ico')
        self.region_manager = RegionManager(self.root, config_file=self.config_file)

        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            self.sw, self.sh = monitor["width"], monitor["height"]

        # 基础模块
        self.minimap = MinimapRadarModule(self.root, self.region_manager, config_file=self.config_file)
        self.elevation = ElevationRadarModule(self.root, self.region_manager, fps=30, config_file=self.config_file)
        self.map_assist = MapPointAssistant(self.root, self.region_manager, config_file=self.config_file)
        self.largemap_radar = AutoMapDistanceAssistant(self.root, self.region_manager, config_file=self.config_file)
        self.rocket = RocketAssistant(self.root, self.region_manager, self.minimap, fps=30, config_file=self.config_file)
        self.mortar = MortarAssistant(self.root, self.region_manager, self.minimap, self.elevation, fps=30, config_file=self.config_file)
        self.throwables = ThrowablesAssistant(self.root, self.region_manager, self.minimap, self.elevation, fps=30, config_file=self.config_file)
        self.vss_assist = VssAssistant(self.root, self.region_manager, self.minimap, fps=30, config_file=self.config_file)
        self.crossbow_assist = CrossbowAssistant(self.root, self.region_manager, self.minimap, fps=30, config_file=self.config_file)
        self.weapon_detector = WeaponDetector(self.region_manager, fps=30, match_threshold=0.55)
        self.recoil = RecoilControlModuleNew(config_file=self.config_file)
        self.gesture_id = GestureIdentifier(region_manager=self.region_manager)

        self.equipment_detector = EquipmentDetector(
            self.region_manager, fps=20, idle_timeout=2.0, debug=False,
            on_status_change=self.on_equipment_status   # 新增
        )
        # self.equipment_detector = EquipmentDetector(self.region_manager, fps=20, idle_timeout=2.0, debug=False)

        # 状态变量
        self.weapon_detection_enabled = True
        self.display_enabled = False
        self.recoil_enabled = False
        self.current_weapon = None
        self.current_gesture = None
        self.equipment_status = "closed"
        self.current_weapons_attachments = {1: {}, 2: {}}   # 存储装备栏识别的两个武器配件

        self.left_pressed = False
        self.middle_pressed = False
        self.alt_pressed = False
        self._is_capturing = False

        # 状态覆盖层
        self.status_overlay = None
        self.status_canvas = None
        self._init_status_overlay()

        # 回调函数
        def on_equipment_update(is_open, weapons):
            if is_open:
                self.current_weapons_attachments = weapons
                w1 = weapons[1].get("name") if weapons[1] else None
                w2 = weapons[2].get("name") if weapons[2] else None
                self.weapon_detector.update_primary_weapons(w1, w2)
                # 更新压枪模块的配件
                attachments = {}
                if weapons[1]:
                    attachments["scope"] = weapons[1].get("scope")
                    attachments["grip"] = weapons[1].get("grip")
                    attachments["muzzle"] = weapons[1].get("muzzle")
                    attachments["stock"] = weapons[1].get("stock")
                self.recoil.update_attachments(attachments)
            self.update_status_display()   # 刷新状态栏

        def on_weapon_detected(weapon_name, score):
            if weapon_name and score >= 0.5:
                self.current_weapon = weapon_name
                if self.recoil_enabled and weapon_name not in ["Rocket", "Grenade", "VSS", "Crossbow"]:
                    self.recoil.update_current_weapon(weapon_name)
            else:
                self.current_weapon = None
                if self.recoil_enabled:
                    self.recoil.update_current_weapon(None)
            self.update_weapon_ui(self.current_weapon)
            self.update_status_full()
            self.update_status_display()

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

        self.equipment_detector.set_enabled(True, on_equipment_update)
        self.weapon_detector.set_enabled(True, on_weapon_detected)
        self.gesture_id.set_enabled(True, on_gesture_identified)

        # 快捷键配置
        self.hotkeys = {
            "throw": "v",
            "toggle_display": "<ctrl>+<shift>+<space>",
            "measure_map": "<f1>",
            "toggle_recoil": "<ctrl>+<shift>+<tab>",
            "toggle_weapon_detection": "<f2>",
            "toggle_equipment": "tab"
        }
        self.load_hotkey_config()

        self.init_ui()
        self.start_listeners()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _set_app_icon(self, icon_name):
        """
        获取资源路径并设置窗口图标，兼容 Nuitka 单文件打包与本地调试环境。
        """
        # 判断是否被 Nuitka 编译
        if "__compiled__" in globals():
            base_path = os.path.dirname(__file__)
        else:
            base_path = os.path.abspath(os.path.dirname(__file__))
        
        icon_path = os.path.join(base_path, icon_name)
        
        try:
            self.root.iconbitmap(icon_path)
        except Exception as e:
            # 防止在某些没有界面的无头环境或图标丢失时程序直接崩溃
            print(f"警告: 无法加载图标 - {e}")

    def on_equipment_status(self, status):
        self.equipment_status = status
        self.update_status_display()

    def init_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self.map_tab = tk.Frame(self.notebook, bg="#F9FAFB")
        self.notebook.add(self.map_tab, text="地图点位")
        self.map_tab.columnconfigure(0, weight=1)
        self.build_map_tab()

        self.launch_tab = tk.Frame(self.notebook, bg="#F9FAFB")
        self.notebook.add(self.launch_tab, text="启动助手")
        self.build_launch_tab()
        self.btn_weapon_detect.set_active(True)
        self.btn_weapon_detect.set_text("关闭武器检测")

        self.calib_tab = tk.Frame(self.notebook, bg="#F9FAFB")
        self.notebook.add(self.calib_tab, text="校准区域")
        self.build_calib_tab()

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
        x = 5
        y = self.sh - 109   # 底部对齐
        self.status_overlay.geometry(f"450x120+{x}+{y}")
        self.status_canvas = tk.Canvas(self.status_overlay, bg="black", highlightthickness=0, width=450, height=120)
        self.status_canvas.pack()
        try:
            hwnd = int(self.status_overlay.frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception as e:
            print(f"[状态栏] 防截图 API 调用失败: {e}")
            # self.status_overlay.withdraw()

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
        self.btn_weapon_detect = RoundedButton(self.launch_tab, 220, 35, 25, "开启武器检测", command=self.toggle_weapon_detection, is_toggle=True, text_size=12)
        self.btn_weapon_detect.pack(pady=4)
        self.btn_display = RoundedButton(self.launch_tab, 220, 35, 25, "开启瞄准辅助", command=self.toggle_display, is_toggle=True, text_size=12)
        self.btn_display.pack(pady=4)
        self.btn_recoil = RoundedButton(self.launch_tab, 220, 35, 25, "开启辅助压枪", command=self.toggle_recoil, is_toggle=True, text_size=12)
        self.btn_recoil.pack(pady=4)
        self.btn_reload_recoil = RoundedButton(self.launch_tab, 220, 35, 25, "重新加载压枪配置", command=self.reload_recoil_config, text_size=12, is_toggle=False)
        self.btn_reload_recoil.pack(pady=4)

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
        frame.pack(pady=6) 
        for i, (name, key) in enumerate(assistants):
            btn = RoundedButton(frame, 107, 30, 25, name, command=lambda k=key: self.toggle_assistant(k), is_toggle=True)
            btn.grid(row=i//2, column=i%2, padx=3, pady=5)
            self.assistant_btns[key] = btn


    def build_calib_tab(self):
        # 第0行：调试按钮（占两列）
        self.btn_debug = RoundedButton(self.calib_tab, 220, 32, 25, "显示所有区域框", command=self.toggle_debug, is_toggle=True)
        self.btn_debug.grid(row=0, column=0, columnspan=2, pady=5)

        # 原有六个区域按钮列表（名称和区域键）
        existing_items = [
            ("小地图", "minimap_region"),
            ("大地图", "largemap_region"),
            ("垂直测高", "elevation_region"),
            ("准星区域", "crosshair_region"),
            ("武器栏", "weapon_region"),
            ("1km长度", "largemap_1km_px")   
        ]

        row = 1
        for i in range(0, len(existing_items), 2):
            # 左列按钮
            name1, key1 = existing_items[i]
            if key1 == "largemap_1km_px":
                btn1 = RoundedButton(self.calib_tab, 107, 30, 25, f"校准{name1}",
                                    command=lambda: self.region_manager.calibrate_scale("largemap_1km_px"))
            else:
                btn1 = RoundedButton(self.calib_tab, 107, 30, 25, f"校准{name1}",
                                    command=lambda k=key1: self.region_manager.calibrate_region(k))
            btn1.grid(row=row, column=0, padx=5, pady=3, sticky="ew")

            # 右列按钮
            if i+1 < len(existing_items):
                name2, key2 = existing_items[i+1]
                if key2 == "largemap_1km_px":
                    btn2 = RoundedButton(self.calib_tab, 107, 30, 25, f"校准{name2}",
                                        command=lambda: self.region_manager.calibrate_scale("largemap_1km_px"))
                else:
                    btn2 = RoundedButton(self.calib_tab, 107, 30, 25, f"校准{name2}",
                                        command=lambda k=key2: self.region_manager.calibrate_region(k))
                btn2.grid(row=row, column=1, padx=5, pady=3, sticky="ew")
            row += 1

        weapon1_items = [
            ("武器1名称", "weapon1_name_region"),
            ("武器1倍镜", "weapon1_scope_region"),
            ("武器1握把", "weapon1_grip_region"),
            ("武器1枪口", "weapon1_muzzle_region"),
            ("武器1枪托", "weapon1_stock_region"),
        ]
        weapon2_items = [
            ("武器2名称", "weapon2_name_region"),
            ("武器2倍镜", "weapon2_scope_region"),
            ("武器2握把", "weapon2_grip_region"),
            ("武器2枪口", "weapon2_muzzle_region"),
            ("武器2枪托", "weapon2_stock_region"),
        ]

        for i in range(5):
            # 武器1按钮
            name1, key1 = weapon1_items[i]
            btn1 = RoundedButton(self.calib_tab, 107, 30, 25, f"校准{name1}",
                                command=lambda k=key1: self.region_manager.calibrate_region(k))
            btn1.grid(row=row, column=0, padx=5, pady=3, sticky="ew")
            # 武器2按钮
            name2, key2 = weapon2_items[i]
            btn2 = RoundedButton(self.calib_tab, 107, 30, 25, f"校准{name2}",
                                command=lambda k=key2: self.region_manager.calibrate_region(k))
            btn2.grid(row=row, column=1, padx=5, pady=3, sticky="ew")
            row += 1
            
    def build_key_tab(self):
        self.key_frame = tk.Frame(self.key_tab, bg="#F9FAFB")
        self.key_frame.pack(fill="both", expand=True, padx=5, pady=1)

        key_configs = [
            ("手雷瞬爆", "throw"),
            ("辅助显示开关", "toggle_display"),
            ("大地图测距", "measure_map"),
            ("辅助压枪开关", "toggle_recoil"),
            ("武器检测开关", "toggle_weapon_detection"),
            ("打开装备栏", "toggle_equipment"),
        ]
        self.key_labels = {}

        for label, action in key_configs:
            # 每个功能使用一个容器 Frame
            func_frame = tk.Frame(self.key_frame, bg="#F9FAFB")
            func_frame.pack(fill="x", pady=1)

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
        btn_frame = tk.Frame(self.key_frame, bg="#F9FAFB")
        btn_frame.pack(pady=3)
        save_btn = RoundedButton(btn_frame, 107, 30, 25, "保存快捷键", 
                                command=self.save_hotkey_config, is_toggle=False)
        save_btn.pack(side=tk.LEFT, padx=5)
        default_btn = RoundedButton(btn_frame, 107, 30, 25, "恢复默认", 
                                    command=self.reset_default_hotkeys, is_toggle=False)
        default_btn.pack(side=tk.LEFT, padx=5)
        default_btn.pack(pady=1)
    
    def reload_recoil_config(self):
        self.recoil.reload_config()

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
            if action_key in ("throw", "toggle_equipment") and modifiers:
                # 手雷瞬爆和打开装备栏只允许单键，不允许带修饰键
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
        self.weapon_detector.set_enabled(self.weapon_detection_enabled)
        self.gesture_id.set_enabled(self.weapon_detection_enabled)
        self.equipment_detector.set_enabled(self.weapon_detection_enabled) 
        if not self.weapon_detection_enabled:
            self.current_weapon = None
            self.update_weapon_ui(None)
        self.update_status_display()

    def _do_weapon_detection_state_change(self):
        self.weapon_id.set_enabled(self.weapon_detection_enabled)
        self.gesture_id.set_enabled(self.weapon_detection_enabled)
        if not self.weapon_detection_enabled:
            self.current_weapon = None
            self.update_weapon_ui(None)
        self.update_status_display()

    def update_status_display(self):
        # if not self.weapon_detection_enabled:
        #     if self.status_overlay:
        #         self.status_overlay.withdraw()
        #     return
        if not self.status_overlay:
            return

        # 映射表
        grip_map = {
            "vertical": "垂直", "half": "半截", "tilted": "斜握",
            "light": "轻握", "laser": "激光", "thumb": "拇指"
        }
        stock_map = {
            "tactical": "战术", "heavy": "重型", "uzi": "微托"
        }
        scope_map = {
            "red_dot": "红点", "holographic": "全息", "2": "二倍", "3": "三倍",
            "4": "四倍", "6": "六倍", "8": "八倍", "multiple": "蛤蟆"
        }
        muzzle_map = {
            "rifle_compensator": "步枪补偿", "rifle_suppressor": "步枪消焰", "rifle_silencer": "步枪消音", "rifle_braker": "制退",
            "smg_compensator": "冲锋补偿", "smg_suppressor": "冲锋消焰", "smg_silencer": "冲锋消音",
        }
        gesture_map = {"stand": "站立", "squat": "蹲下", "lie": "趴下"}
        status_map = {
            "opened": ("武器识别中", "#2ECC71"),    # 绿
            "closed": ("装备栏关闭", "#3498DB"),      # 蓝
            "confirming": ("正在确认中", "#F39C12")     # 橙黄
        }
        status_text, status_color = status_map.get(self.equipment_status, ("装备栏关闭", "#3498DB"))

        # 清空画布
        self.status_canvas.delete("status_text")

        # 第一行：装备栏状态（y=5）
        # status_indicator = f"识别: {'ON' if self.weapon_detection_enabled else 'OFF'}  测距: {'ON' if self.display_enabled else 'OFF'}  压枪: {'ON' if self.recoil_enabled else 'OFF'}"

        x_start = 10
        y_offset = 5
        # 识别
        color_detect = "#2ECC71" if self.weapon_detection_enabled else "#E74C3C"
        self.status_canvas.create_text(x_start, y_offset, anchor="nw", text="识别", fill=color_detect,
                                    font=("Microsoft YaHei", 10, "bold"), tags="status_text")
        
        x_start += 35
        # 测距
        color_display = "#2ECC71" if self.display_enabled else "#E74C3C"
        self.status_canvas.create_text(x_start, y_offset, anchor="nw", text="测距", fill=color_display,
                                    font=("Microsoft YaHei", 10, "bold"), tags="status_text")
        x_start += 35
        # 压枪
        if self.recoil_enabled:
            if self.current_weapon is None:
                color_recoil = "#F39C12"   # 黄色：没有武器但压枪开启
            else:
                color_recoil = "#2ECC71"   # 绿色：有武器且压枪开启
        else:
            color_recoil = "#E74C3C"       # 红色：压枪关闭
        self.status_canvas.create_text(x_start, y_offset, anchor="nw", text="压枪", fill=color_recoil,
                                    font=("Microsoft YaHei", 10, "bold"), tags="status_text")
        
        
        x_start += 35
        # 装备栏状态
        self.status_canvas.create_text(x_start, y_offset, anchor="nw", text=status_text, fill=status_color,
                                    font=("Microsoft YaHei", 10, "bold"), tags="status_text")

        w1 = self.current_weapons_attachments.get(1, {})
        w2 = self.current_weapons_attachments.get(2, {})

        def format_weapon(weapon_data):
            name = weapon_data.get("name") or "无"
            parts = [name]
            scope = weapon_data.get("scope")
            if scope:
                parts.append(scope_map.get(scope, scope))
            grip = weapon_data.get("grip")
            if grip:
                parts.append(grip_map.get(grip, grip))
            muzzle = weapon_data.get("muzzle")
            if muzzle:
                parts.append(muzzle_map.get(muzzle, muzzle))
            stock = weapon_data.get("stock")
            if stock:
                parts.append(stock_map.get(stock, stock))
            return " | ".join(parts)

        line2 = f"武器1: {format_weapon(w1)}"
        line3 = f"武器2: {format_weapon(w2)}"
        curr = self.current_weapon if self.current_weapon else "无"
        pose = gesture_map.get(self.current_gesture, "未知姿势") if self.current_gesture else "未知姿势"
        line4 = f"当前: {curr} | 姿势: {pose}"

        y_offset += 25 
        for line in [line2, line3, line4]:
            self.status_canvas.create_text(10, y_offset, anchor="nw", text=line, fill="white",
                                        font=("Microsoft YaHei", 10, "bold"), tags="status_text")
            y_offset += 25
        self.status_overlay.deiconify()

    def update_status_full(self):
        parts = []
        if self.current_weapon:
            parts.append(self.current_weapon)
        if self.current_gesture:
            gesture_map = {"stand": "站立", "squat": "蹲下", "lie": "趴下"}
            gesture_display = gesture_map.get(self.current_gesture, self.current_gesture)
            parts.append(gesture_display)
        status_text = " | ".join(parts) if parts else "就绪"
        if self.current_weapon:
            self.set_status(status_text, "success")
        else:
            self.set_status(status_text, "info")

    def update_weapon_ui(self, weapon_name):
        special = {
            "Rocket": self.rocket,
            "Grenade": self.throwables,
            "VSS": self.vss_assist,
            "Crossbow": self.crossbow_assist
        }
        for name, mod in special.items():
            if self.display_enabled and weapon_name == name:
                mod.enable_module(True)
            else:
                mod.enable_module(False)
        for btn_key, mod in [("rocket", self.rocket), ("throwables", self.throwables),
                             ("vss", self.vss_assist), ("crossbow", self.crossbow_assist)]:
            if btn_key in self.assistant_btns:
                self.assistant_btns[btn_key].set_active(mod.is_enabled)

    def toggle_display(self):
        self.display_enabled = not self.display_enabled
        self.btn_display.set_active(self.display_enabled)
        self.btn_display.set_text(f"{'关闭' if self.display_enabled else '开启'}瞄准辅助")
        self.mortar.enable_module(self.display_enabled)
        self.assistant_btns["mortar"].set_active(self.display_enabled and self.mortar.is_enabled)
        if self.current_weapon:
            self.update_weapon_ui(self.current_weapon)
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
            if self.current_weapon and self.current_weapon not in ["Rocket", "Grenade", "VSS", "Crossbow"]:
                self.recoil.update_current_weapon(self.current_weapon)
            if self.current_gesture:
                self.recoil.update_stance(self.current_gesture)
        else:
            self.recoil.update_current_weapon(None)   # 关闭压枪时清除武器

    def toggle_debug(self):
        self.region_manager.set_debug_mode(not self.region_manager.show_debug)
        self.btn_debug.set_active(self.region_manager.show_debug)
        self.btn_debug.set_text(f"{'关闭' if self.region_manager.show_debug else '开启'}显示所有区域框")

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

        equip_key = self.hotkeys['toggle_equipment']
        equip_parts = equip_key.split('+')
        equip_main = equip_parts[-1]  
        # 检查普通字符键
        if hasattr(key, 'char') and key.char == equip_main:
            self.root.after(0, self.equipment_detector.on_tab_press)
            return
        # 检查特殊键（如 tab, f1, space 等）
        elif hasattr(key, 'name') and key.name == equip_main:
            self.root.after(0, self.equipment_detector.on_tab_press)
            return

        # 手雷瞬爆
        throw_key = self.hotkeys['throw'].split('+')[-1]
        if hasattr(key, 'char') and key.char == throw_key:
            if self.display_enabled and self.current_weapon == "Grenade":
                self.throwables.toggle_auto_throw()

    def on_key_release(self, key):
        if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt_pressed = False

    def on_mouse_click(self, x, y, button, pressed):
        # 左键+中键 地图点位助手
        if button == mouse.Button.left:
            self.left_pressed = pressed
        elif button == mouse.Button.middle:
            self.middle_pressed = pressed

        if self.left_pressed and self.middle_pressed:
            if not self.map_assist.is_enabled:
                self.map_assist.set_enabled(True)
        else:
            if button == mouse.Button.right and pressed:
                if not self.alt_pressed:
                    if self.map_assist.is_enabled:
                        self.map_assist.set_enabled(False)

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
            "toggle_weapon_detection": "<f2>",
            "toggle_equipment": "tab"
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
        self.equipment_detector.set_enabled(False)
        self.weapon_detector.set_enabled(False)
        self.gesture_id.set_enabled(False)
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