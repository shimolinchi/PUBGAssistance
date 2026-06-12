import tkinter as tk
from tkinter import ttk
import mss
from pynput import keyboard, mouse
import threading
import time
import ctypes
import json
import os

try:
    import cv2
    import numpy as np
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from modules.transparent_hud import TransparentHudWindow
except ImportError:
    TransparentHudWindow = None

from modules.region_manager import RegionManager
from modules.minimap_radar import MinimapRadarModule
from modules.elevation_radar import ElevationRadarModule
from modules.mortar_assistant import MortarAssistant
from modules.rocket_assistant import RocketAssistant
from modules.map_assistant import MapPointAssistant
from modules.throwables_assistant import ThrowablesAssistant
from modules.vss_assistant import VssAssistant
from modules.crossbow_assistant import CrossbowAssistant
from modules.c4_assistant import C4Assistant
from modules.largemap_radar import AutoMapDistanceAssistant
from modules.gesture_identifier import GestureIdentifier
from modules.weapon_detector import WeaponDetector
from modules.equipment_detector import EquipmentDetector
from modules.recoil_control import RecoilControlModule as RecoilControlModuleNew

try:
    from modules.region_calibrator_auto import open_region_scaling_auto_calibrator
except Exception:
    open_region_scaling_auto_calibrator = None

try:
    from modules.recoil_debugger import open_recoil_debugger
except Exception:
    open_recoil_debugger = None

try:
    from modules.special_weapon_debugger import open_special_weapon_debugger
except Exception:
    open_special_weapon_debugger = None

class RoundedButton(tk.Canvas):
    def __init__(self, parent, width, height, radius, text, command, text_size = -10, is_toggle=False, *args, **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, *args, **kwargs)
        self.command = command
        self.is_toggle = is_toggle
        self.is_active = False
        self.color_default = "#FFFFFF"
        self.color_hover = "#F4F7FB"
        self.color_pressed = "#D7DEE8"
        self.color_active = "#E8EEF6"
        self.text_color = "#111827"
        self.radius = radius
        self.text_size = text_size
        self.rect = self._create_rounded_rect(1, 1, width - 1, height - 1, radius, fill=self.color_default, outline="#FFFFFF", width=1)
        self.text_id = self.create_text(width/2, height/2, text=text, fill=self.text_color, font=("Microsoft YaHei", text_size, "bold"))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_hover)
        self.bind("<Leave>", self._on_leave)

    def _create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
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
        # 启用 DPI 感知，使 GetSystemMetrics 返回物理分辨率
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass
        # 获取系统 DPI 缩放因子
        try:
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)   # LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, hdc)
            factor = dpi / 96.0
        except:
            factor = 1.0
        # 设置 tkinter 内部缩放因子，使所有控件（字体、窗口尺寸）按比例放大
        self.root.tk.call('tk', 'scaling', factor)
        
        self.root.title("PUBG 战术助手")
        self.window_width = 280
        self.window_height = 372
        self.window_radius = 18
        self.root.geometry(f"{self.window_width}x{self.window_height}")
        self.root.minsize(self.window_width, self.window_height)
        self.root.configure(bg="#DDE6F0")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.6)
        self.root.overrideredirect(True)
        self.root.after(0, self._schedule_window_rounding)

        self.config_file = "config.json"
        self._set_app_icon('icon.ico')
        self.region_manager = RegionManager(self.root, config_file=self.config_file)

        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            self.sw, self.sh = monitor["width"], monitor["height"]

        # 主窗口和按钮使用固定像素尺寸，字体也使用固定像素字号，避免不同分辨率下文字与按钮比例不一致。
        self.font_status = -13
        self.font_small = -14
        self.font_large = -16

        # 特殊武器名称映射（英文 -> 中文）
        self.special_weapon_map = {
            "Rocket": "火箭筒",
            "Grenade": "投掷物",
            "VSS": "VSS",
            "Crossbow": "十字弩",
            "C4": "C4",
            "Mortar": "迫击炮"
        }

        # 基础模块
        self.minimap = MinimapRadarModule(self.root, self.region_manager, config_file=self.config_file, fps = 60)
        self.elevation = ElevationRadarModule(self.root, self.region_manager, fps=30, config_file=self.config_file)
        self.map_assist = MapPointAssistant(self.root, self.region_manager, config_file=self.config_file)
        self.largemap_radar = AutoMapDistanceAssistant(self.root, self.region_manager, config_file=self.config_file)
        self.rocket = RocketAssistant(self.root, self.region_manager, self.minimap, fps=30, config_file=self.config_file)
        self.mortar = MortarAssistant(self.root, self.region_manager, self.minimap, self.elevation, fps=30, config_file=self.config_file)
        self.throwables = ThrowablesAssistant(self.root, self.region_manager, self.minimap, self.elevation, fps=30, config_file=self.config_file)
        self.vss_assist = VssAssistant(self.root, self.region_manager, self.minimap, fps=30, config_file=self.config_file)
        self.crossbow_assist = CrossbowAssistant(self.root, self.region_manager, self.minimap, fps=30, config_file=self.config_file)
        self.weapon_detector = WeaponDetector(self.region_manager, fps=30, match_threshold=0.65)
        self.recoil = RecoilControlModuleNew(
            config_file=self.config_file,
            region_manager=self.region_manager,
            screen_width=self.sw,
            screen_height=self.sh
        )
        self.gesture_id = GestureIdentifier(region_manager=self.region_manager, match_threshold=0.65, fps=30)
        self.equipment_detector = EquipmentDetector(self.region_manager, fps=30, idle_timeout=10.0, on_status_change=self.on_equipment_status)
        self.c4_assistant = C4Assistant(self.root, self.region_manager, self.minimap, fps=30, explosion_margin=2.0, target_speed=50.0,  jump_distance_threshold=20.0)

        self.special_assistant_modules = {
            "mortar": self.mortar,
            "rocket": self.rocket,
            "throwables": self.throwables,
            "vss": self.vss_assist,
            "crossbow": self.crossbow_assist,
            "c4": self.c4_assistant
        }
        self.weapon_assistant_map = {
            "Rocket": "rocket",
            "Grenade": "throwables",
            "VSS": "vss",
            "Crossbow": "crossbow",
            "C4": "c4"
        }
        self.manual_assistant_keys = set()
        self.map_point_groups = {"vehicles": True, "planes": True, "rooms": True, "other": True}
        self.marker_color_order = ["Yellow", "Orange", "Blue", "Green"]
        self.current_marker_color = "Yellow"
        self.pnt_color_modes = self._default_pnt_color_modes()
        self.current_pnt_color_mode = "normal"
        self.load_pnt_color_config()
        self.marker_color_hex = self._pnt_hex_map(self.pnt_color_modes[self.current_pnt_color_mode])
        self.status_text_opacity = 0.7
        self.marker_color_bgr = {name: self._hex_to_bgr(hex_color) for name, hex_color in self.marker_color_hex.items()}
        self.marker_icon_img = None
        self.current_marker_icon = None
        self._load_marker_icon()
        self._sync_marker_color_to_assistants()
        self._sync_pnt_colors_to_modules()

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
        self.auto_calibrator_windows = []
        self.recoil_debugger_windows = []
        self.special_weapon_debugger_windows = []

        # 状态覆盖层
        self.assistant_btns = {}          # 关键！
        self.status_var = tk.StringVar(value="就绪")
        self.status_overlay = None
        self.status_canvas = None
        self._init_status_overlay()

        # 回调函数
        def on_equipment_update(is_open, weapons):
            # print(f"[回调] is_open={is_open}, weapons1={weapons[1]}, weapons2={weapons[2]}")
            if is_open:
                self.weapon_slot_map = {}
                for slot, data in weapons.items():
                    name = data.get("name")
                    if name:
                        self.weapon_slot_map[name] = slot
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
            # 传递给 C4 助手
            self.c4_assistant.on_weapon_detected(weapon_name, score)

            if getattr(self.recoil, "is_firing", False):
                return

            if weapon_name and score >= 0.5:
                self.current_weapon = weapon_name
                if self.recoil_enabled and weapon_name not in ["Rocket", "Grenade", "VSS", "Crossbow"]:
                    self.recoil.update_current_weapon(weapon_name)
                    # 获取当前武器的配件
                    slot = self.weapon_slot_map.get(weapon_name)
                    if slot:
                        attachments = {}
                        w = self.current_weapons_attachments.get(slot, {})
                        attachments["scope"] = w.get("scope")
                        attachments["grip"] = w.get("grip")
                        attachments["muzzle"] = w.get("muzzle")
                        attachments["stock"] = w.get("stock")
                        self.recoil.update_attachments(attachments)
            else:
                self.current_weapon = None
                if self.recoil_enabled:
                    self.recoil.update_current_weapon(None)
            if self.current_weapon is not None and self.map_assist.is_enabled:
                self.map_assist.set_enabled(False)
            self.update_weapon_ui(self.current_weapon)
            self.update_status_full()
            self.update_status_display()

        def on_gesture_identified(gesture, score):
            if gesture:
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
            "toggle_weapon_detection": "<f1>",
            "toggle_display": "<f2>",
            "toggle_recoil": "<f3>",
            "measure_map": "<f4>",
            "marker_prev": "q",
            "marker_next": "e",
            "toggle_equipment": "tab",
            "fire_key": "end"
        }
        self.load_hotkey_config()
        self.migrate_legacy_default_hotkeys()

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
            print(f"警告: 无法加载图标 - {e}")

    def _default_pnt_color_modes(self):
        return {
            "normal": {
                "Yellow": {"lower": [28, 150, 160], "upper": [32, 255, 255], "hex": "#ABA809"},
                "Orange": {"lower": [8, 160, 160], "upper": [12, 255, 255], "hex": "#A04619"},
                "Blue": {"lower": [99, 120, 160], "upper": [103, 255, 255], "hex": "#28749F"},
                "Green": {"lower": [60, 150, 120], "upper": [64, 255, 255], "hex": "#2F8433"},
            },
            "deuteranopia": {
                "Yellow": {"lower": [26, 150, 160], "upper": [30, 255, 255], "hex": "#B9AE15"},
                "Orange": {"lower": [11, 160, 160], "upper": [15, 255, 255], "hex": "#A15519"},
                "Blue": {"lower": [107, 120, 160], "upper": [111, 255, 255], "hex": "#0046BC"},
                "Green": {"lower": [78, 150, 120], "upper": [82, 255, 255], "hex": "#01B377"},
            },
            "protanopia": {
                "Yellow": {"lower": [26, 150, 160], "upper": [30, 255, 255], "hex": "#B9AE15"},
                "Orange": {"lower": [10, 160, 160], "upper": [14, 255, 255], "hex": "#B3500D"},
                "Blue": {"lower": [110, 120, 160], "upper": [114, 255, 255], "hex": "#1A3FA4"},
                "Green": {"lower": [78, 150, 120], "upper": [82, 255, 255], "hex": "#109166"},
            },
            "tritanopia": {
                "Yellow": {"lower": [26, 150, 160], "upper": [30, 255, 255], "hex": "#E3D43C"},
                "Orange": {"lower": [3, 160, 160], "upper": [7, 255, 255], "hex": "#B14732"},
                "Blue": {"lower": [105, 120, 160], "upper": [109, 255, 255], "hex": "#2E5689"},
                "Green": {"lower": [87, 150, 120], "upper": [91, 255, 255], "hex": "#009995"},
            },
        }

    def _pnt_hex_map(self, colors):
        return {name: data.get("hex", "#FFFFFF") for name, data in colors.items()}

    def _hex_to_bgr(self, hex_color):
        hex_color = hex_color.lstrip("#")
        return (int(hex_color[4:6], 16), int(hex_color[2:4], 16), int(hex_color[0:2], 16))

    def load_pnt_color_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.pnt_color_modes.update(data.get("pnt_color_modes", {}))
                    mode = data.get("pnt_color_mode", self.current_pnt_color_mode)
                    if mode in self.pnt_color_modes:
                        self.current_pnt_color_mode = mode
            except Exception:
                pass

    def save_pnt_color_config(self):
        data = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["pnt_color_mode"] = self.current_pnt_color_mode
        data["pnt_color_modes"] = self.pnt_color_modes
        data["pnt_colors"] = self.pnt_color_modes[self.current_pnt_color_mode]
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _sync_pnt_colors_to_modules(self):
        colors = self.pnt_color_modes[self.current_pnt_color_mode]
        for module in [
            self.minimap, self.elevation, self.largemap_radar, self.mortar,
            self.rocket, self.throwables, self.vss_assist, self.crossbow_assist,
            self.c4_assistant,
        ]:
            if hasattr(module, "set_pnt_colors"):
                module.set_pnt_colors(colors)

    def select_pnt_color_mode(self, mode):
        if mode not in self.pnt_color_modes:
            return
        self.current_pnt_color_mode = mode
        self.marker_color_hex = self._pnt_hex_map(self.pnt_color_modes[mode])
        self.marker_color_bgr = {name: self._hex_to_bgr(hex_color) for name, hex_color in self.marker_color_hex.items()}
        self.save_pnt_color_config()
        self._sync_pnt_colors_to_modules()
        for mode_key, button in getattr(self, "pnt_mode_buttons", {}).items():
            button.set_active(mode_key == mode)
        self.update_status_display()

    def _load_marker_icon(self):
        if not PIL_AVAILABLE:
            return
        icon_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "templates", "pnt", "0.png")
        if os.path.exists(icon_path):
            img = cv2.imread(icon_path, cv2.IMREAD_UNCHANGED)
            if img is not None and len(img.shape) == 3 and img.shape[2] == 4:
                self.marker_icon_img = img

    def _get_colored_marker_icon(self, color_name):
        if not PIL_AVAILABLE or self.marker_icon_img is None:
            return None
        bgr = self.marker_color_bgr.get(color_name, (255, 255, 255))
        bgr_img = self.marker_icon_img[:, :, :3]
        alpha = self.marker_icon_img[:, :, 3]
        color_layer = np.full_like(bgr_img, bgr, dtype=np.uint8)
        alpha_norm = alpha / 255.0
        result = (color_layer * alpha_norm[..., np.newaxis] + bgr_img * (1 - alpha_norm[..., np.newaxis])).astype(np.uint8)
        result = cv2.cvtColor(result, cv2.COLOR_BGR2RGBA)
        result[:, :, 3] = alpha
        return Image.fromarray(result)

    def _sync_marker_color_to_assistants(self):
        for assistant in [getattr(self, "mortar", None), getattr(self, "throwables", None), getattr(self, "c4_assistant", None)]:
            if assistant and hasattr(assistant, "selected_color"):
                assistant.selected_color = self.current_marker_color

    def _should_show_marker_indicator(self):
        if not self.display_enabled:
            return False
        return any(
            key in self.manual_assistant_keys or self.special_assistant_modules.get(key, None).is_enabled
            for key in ["mortar", "throwables", "c4"]
            if self.special_assistant_modules.get(key, None)
        )

    def cycle_marker_color(self, direction):
        idx = self.marker_color_order.index(self.current_marker_color)
        self.current_marker_color = self.marker_color_order[(idx + direction) % len(self.marker_color_order)]
        self._sync_marker_color_to_assistants()
        self.update_status_display()

    def _cycle_marker_hotkey(self, direction):
        if self._should_show_marker_indicator():
            self.cycle_marker_color(direction)

    def _apply_window_rounding(self):
        try:
            self.root.update_idletasks()
            try:
                hwnd = int(self.root.frame(), 16)
            except Exception:
                hwnd = self.root.winfo_id()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            diameter = self.window_radius * 2
            region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, diameter, diameter)
            if not ctypes.windll.user32.SetWindowRgn(hwnd, region, True):
                ctypes.windll.gdi32.DeleteObject(region)
        except Exception as e:
            print(f"[主窗口] 圆角应用失败: {e}")

    def _schedule_window_rounding(self):
        for delay in (0, 100, 500):
            self.root.after(delay, self._apply_window_rounding)

    def on_equipment_status(self, status):
        self.equipment_status = status
        self.update_status_display()

    def init_ui(self):
        style = ttk.Style(self.root)
        style.configure("TNotebook", background="#DDE6F0", borderwidth=0, tabmargins=(8, 4, 8, 0))
        style.configure("TNotebook.Tab", font=("Microsoft YaHei", self.font_status, "bold"), padding=(12, 6), background="#FFFFFF", borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", "#FFFFFF"), ("!selected", "#EAF0F7")])

        self.window_frame = tk.Frame(self.root, bg="#DDE6F0", bd=0, highlightthickness=1, highlightbackground="#FFFFFF")
        self.window_frame.pack(fill="both", expand=True)
        self._build_title_bar()

        self.tab_bar = tk.Frame(self.window_frame, bg="#DDE6F0")
        self.tab_bar.pack(fill="x", padx=8, pady=(1, 0))
        self.content_frame = tk.Frame(self.window_frame, bg="#DDE6F0")
        self.content_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.tab_buttons = []
        self.tab_frames = []
        self.current_tab_index = 0

        self.map_tab = self._add_tab("地图点位")
        self.map_tab.columnconfigure(0, weight=1)
        self.map_tab.columnconfigure(1, weight=1)
        self.build_map_tab()

        self.launch_tab = self._add_tab("启动助手")
        self.build_launch_tab()
        self.btn_weapon_detect.set_active(True)
        self.btn_weapon_detect.set_text("关闭武器检测")

        self.calib_tab = self._add_tab("校准区域")
        self.build_calib_tab()

        self.key_tab = self._add_tab("按键设置")
        self.build_key_tab()
        self.select_tab(0)

        self.status_var = tk.StringVar(value="就绪")

    def _add_tab(self, text):
        idx = len(self.tab_frames)
        frame = tk.Frame(self.content_frame, bg="#DDE6F0")
        btn = RoundedButton(self.tab_bar, 61, 28, 18, text, command=lambda i=idx: self.select_tab(i), is_toggle=True, text_size=self.font_status)
        btn.pack(side=tk.LEFT, padx=2)
        self.tab_frames.append(frame)
        self.tab_buttons.append(btn)
        return frame

    def select_tab(self, idx):
        if not self.tab_frames:
            return
        idx %= len(self.tab_frames)
        for frame in self.tab_frames:
            frame.pack_forget()
        for button_index, button in enumerate(self.tab_buttons):
            button.set_active(button_index == idx)
        self.tab_frames[idx].pack(fill="both", expand=True)
        self.current_tab_index = idx

    def _build_title_bar(self):
        self.title_bar = tk.Frame(self.window_frame, bg="#DDE6F0", height=30)
        self.title_bar.pack(fill="x", side=tk.TOP)
        self.title_bar.pack_propagate(False)
        self.title_bar.bind("<ButtonPress-1>", self._begin_window_drag)
        self.title_bar.bind("<B1-Motion>", self._drag_window)

        title = tk.Label(self.title_bar, text="PUBG 战术助手", bg="#DDE6F0", fg="#111827", font=("Microsoft YaHei", self.font_status, "bold"))
        title.pack(side=tk.LEFT, padx=10)
        title.bind("<ButtonPress-1>", self._begin_window_drag)
        title.bind("<B1-Motion>", self._drag_window)

        close_btn = tk.Canvas(self.title_bar, width=18, height=18, bg="#DDE6F0", highlightthickness=0, bd=0)
        close_btn.place(x=self.window_width - self.window_radius - 9, y=self.window_radius - 9)
        close_btn.create_oval(4, 4, 14, 14, fill="#FF5F57", outline="#E0473F")
        close_btn.bind("<ButtonRelease-1>", lambda event: self.on_closing())

    def _begin_window_drag(self, event):
        self._drag_start_x = event.x_root - self.root.winfo_x()
        self._drag_start_y = event.y_root - self.root.winfo_y()

    def _drag_window(self, event):
        self.root.geometry(f"+{event.x_root - self._drag_start_x}+{event.y_root - self._drag_start_y}")

    def switch_tab(self, direction):
        if not self.tab_frames:
            return
        self.select_tab(self.current_tab_index + direction)

    def _init_status_overlay(self):
        if TransparentHudWindow:
            self.status_overlay = TransparentHudWindow()
        else:
            self.status_overlay = None
            print("[状态栏] 透明 HUD 不可用，左下角状态覆盖层已禁用")

        # 立即显示状态覆盖层中的四行文字
        self.update_status_display()

    def set_status(self, status_text, status_type="info"):
        """设置状态栏文本和背景色
        status_type: 'info' (蓝色), 'success' (绿色), 'error' (红色), 'warning' (橙色)
        """
        self.status_var.set(status_text)
        colors = {
            "info": "#017BC2",     # 蓝
            "success": "#0F9D16",  # 绿
            "error": "#E74C3C",    # 红
            "warning": "#DA6226",  # 橙
            "default": "#017BC2"
        }
        if hasattr(self, "status_bar"):
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

    def toggle_map_point_group(self, group_key):
        next_state = not self.map_point_groups.get(group_key, True)
        self.map_point_groups[group_key] = next_state
        self.map_assist.set_category_enabled(group_key, next_state)
        if group_key in self.map_point_group_buttons:
            self.map_point_group_buttons[group_key].set_active(next_state)

    def build_map_tab(self):
        self.map_names = [
            "艾伦格 (Erangel)", "米拉玛 (Miramar)", "泰戈 (Taego)",
            "荣都 (Rondo)", "帝斯顿 (Deston)", "维寒迪 (Vikendi)"
        ]
        self.map_tab.rowconfigure(5, weight=0)
        self.map_buttons = []

        # 地图按钮（两列紧凑排列）
        for i, map_name in enumerate(self.map_names):
            short_name = map_name.split()[0]
            btn = RoundedButton(self.map_tab, 126, 30, 30, short_name,
                                command=lambda idx=i: self.select_map(idx), is_toggle=True,text_size=self.font_large)
            btn.grid(row=i//2, column=i%2, padx=2, pady=3, sticky="ew")
            self.map_buttons.append(btn)

        # 标点尺寸标签
        tk.Label(self.map_tab, text="--标点尺寸--", bg="#DDE6F0", fg="#6B7280", font=("Microsoft YaHei", self.font_status, "bold")).grid(
            row=3, column=0, columnspan=2, pady=(4, 3)
        )
        # 标点尺寸按钮（水平排列）
        size_frame = tk.Frame(self.map_tab, bg="#DDE6F0")
        size_frame.grid(row=4, column=0, columnspan=2, pady=(0, 4))
        self.size_buttons = []
        sizes = [("小", "small"), ("中", "medium"), ("大", "large")]
        for i, (name, val) in enumerate(sizes):
            btn = RoundedButton(size_frame, 81, 30, 30, name,
                                command=lambda idx=i: self.select_size(idx), is_toggle=True, text_size=self.font_small)
            btn.grid(row=0, column=i, padx=3)
            self.size_buttons.append(btn)

        tk.Label(self.map_tab, text="--色盲选择--", bg="#DDE6F0", fg="#6B7280", font=("Microsoft YaHei", self.font_status, "bold")).grid(
            row=5, column=0, columnspan=2, pady=(2, 3)
        )
        mode_frame = tk.Frame(self.map_tab, bg="#DDE6F0")
        mode_frame.grid(row=6, column=0, columnspan=2, pady=(0, 0))
        self.pnt_mode_buttons = {}
        modes = [("无色盲", "normal"), ("绿色盲", "deuteranopia"), ("红色盲", "protanopia"), ("蓝色盲", "tritanopia")]
        for i, (name, mode) in enumerate(modes):
            btn = RoundedButton(mode_frame, 61, 30, 30, name,
                                command=lambda m=mode: self.select_pnt_color_mode(m), is_toggle=True, text_size=self.font_status)
            btn.grid(row=0, column=i, padx=2)
            btn.set_active(mode == self.current_pnt_color_mode)
            self.pnt_mode_buttons[mode] = btn

        tk.Label(self.map_tab, text="--点位类型--", bg="#DDE6F0", fg="#6B7280", font=("Microsoft YaHei", self.font_status, "bold")).grid(
            row=7, column=0, columnspan=2, pady=(4, 3)
        )
        group_frame = tk.Frame(self.map_tab, bg="#DDE6F0")
        group_frame.grid(row=8, column=0, columnspan=2, pady=(0, 0))
        self.map_point_group_buttons = {}
        groups = [("载具", "vehicles"), ("飞机", "planes"), ("密室", "rooms"), ("其他", "other")]
        for i, (name, group_key) in enumerate(groups):
            btn = RoundedButton(group_frame, 61, 30, 30, name,
                                command=lambda g=group_key: self.toggle_map_point_group(g), is_toggle=True, text_size=self.font_status)
            btn.grid(row=0, column=i, padx=2)
            btn.set_active(True)
            self.map_point_group_buttons[group_key] = btn

        self.select_map(0)
        self.select_size(1)

    def build_launch_tab(self):
        self.btn_weapon_detect = RoundedButton(self.launch_tab, 256, 34, 30, "开启武器检测", command=self.toggle_weapon_detection, is_toggle=True, text_size=self.font_large)
        self.btn_weapon_detect.pack(pady=3)
        self.btn_display = RoundedButton(self.launch_tab, 256, 34, 30, "开启瞄准辅助", command=self.toggle_display, is_toggle=True, text_size=self.font_large)
        self.btn_display.pack(pady=3)
        self.btn_recoil = RoundedButton(self.launch_tab, 256, 34, 30, "开启辅助压枪", command=self.toggle_recoil, is_toggle=True, text_size=self.font_large)
        self.btn_recoil.pack(pady=3)
        recoil_config_frame = tk.Frame(self.launch_tab, bg="#DDE6F0")
        recoil_config_frame.pack(pady=3)
        self.btn_reload_recoil = RoundedButton(recoil_config_frame, 126, 34, 30, "调试特殊武器", command=self.open_special_weapon_debugger, is_toggle=False, text_size=self.font_small)
        self.btn_reload_recoil.grid(row=0, column=0, padx=2)
        self.btn_debug_recoil = RoundedButton(recoil_config_frame, 126, 34, 30, "调试压枪参数", command=self.open_recoil_debugger, is_toggle=False, text_size=self.font_small)
        self.btn_debug_recoil.grid(row=0, column=1, padx=2)

        tk.Label(self.launch_tab, text="--启用特殊武器助手--", bg="#DDE6F0", fg="#6B7280", font=("Microsoft YaHei", self.font_status, "bold")).pack(pady=4)

        assistants = [
            ("迫击炮", "mortar"),
            ("火箭筒", "rocket"),
            ("投掷物", "throwables"),
            ("VSS", "vss"),
            ("十字弩", "crossbow"),
            ("C4", "c4")
        ]
        self.assistant_btns = {}
        frame = tk.Frame(self.launch_tab, bg="#DDE6F0")
        frame.pack(pady=2) 
        for i, (name, key) in enumerate(assistants):
            btn = RoundedButton(frame, 126, 29, 30, name, command=lambda k=key: self.toggle_assistant(k), is_toggle=True, text_size=self.font_small)
            btn.grid(row=i//2, column=i%2, padx=2, pady=3)
            self.assistant_btns[key] = btn


    def build_calib_tab(self):
        for col in range(3):
            self.calib_tab.columnconfigure(col, weight=1, uniform="calib")

        top_frame = tk.Frame(self.calib_tab, bg="#DDE6F0")
        top_frame.grid(row=0, column=0, columnspan=3, pady=(0, 3))
        self.btn_debug = RoundedButton(top_frame, 125, 36, 30, "显示所有区域框",
                                       command=self.toggle_debug, is_toggle=True, text_size=self.font_large)
        self.btn_debug.grid(row=0, column=0, padx=3)
        self.btn_auto_scale = RoundedButton(top_frame, 125, 36, 30, "调试缩放比例",
                                            command=self.open_auto_scale_calibrator, is_toggle=False,
                                            text_size=self.font_large)
        self.btn_auto_scale.grid(row=0, column=1, padx=3)

        calib_rows = [
            [
                ("大地图", "region", "largemap_region"),
                ("小地图", "region", "minimap_region"),
                ("1km比例尺", "scale", "largemap_1km_px"),
            ],
            [
                ("武器1编号", "region", "weapon1_number_region"),
                ("武器2编号", "region", "weapon2_number_region"),
                ("垂直测高", "region", "elevation_region"),
            ],
            [
                ("武器1名称", "region", "weapon1_name_region"),
                ("武器2名称", "region", "weapon2_name_region"),
                ("武器图标", "region", "weapon_region"),
            ],
            [
                ("武器1倍镜", "region", "weapon1_scope_region"),
                ("武器2倍镜", "region", "weapon2_scope_region"),
                ("姿势区域", "region", "stance_region"),
            ],
            [
                ("武器1枪口", "region", "weapon1_muzzle_region"),
                ("武器2枪口", "region", "weapon2_muzzle_region"),
                ("四倍镜内边", "region", "scope_top_edge_4x_region"),
            ],
            [
                ("武器1握把", "region", "weapon1_grip_region"),
                ("武器2握把", "region", "weapon2_grip_region"),
                ("六倍镜内边", "region", "scope_top_edge_6x_region"),
            ],
            [
                ("武器1枪托", "region", "weapon1_stock_region"),
                ("武器2枪托", "region", "weapon2_stock_region"),
                ("八倍镜内边", "region", "scope_top_edge_8x_region"),
            ],
        ]

        def run_calibration(kind, key):
            if kind == "scale":
                self.region_manager.calibrate_scale(key)
            else:
                self.region_manager.calibrate_region(key)

        for row_index, row_items in enumerate(calib_rows, start=1):
            for col_index, (name, kind, key) in enumerate(row_items):
                btn = RoundedButton(self.calib_tab, 82, 33, 30, name,
                                    command=lambda k=kind, v=key: run_calibration(k, v),
                                    text_size=self.font_status)
                btn.grid(row=row_index, column=col_index, padx=2, pady=2)
            
    def build_key_tab(self):
        self.key_frame = tk.Frame(self.key_tab, bg="#DDE6F0")
        self.key_frame.pack(fill="both", expand=True, padx=0, pady=2)

        key_configs = [
            ("手雷瞬爆", "throw", True),
            ("辅助显示开关", "toggle_display", True),
            ("大地图测距", "measure_map", True),
            ("辅助压枪开关", "toggle_recoil", True),
            ("武器检测开关", "toggle_weapon_detection", True),
            ("打开装备栏", "toggle_equipment", True),
            ("开火按键", "fire_key", True),
            ("标点前后切换", "marker_pair", True),
            ("地图点位显示", "mouse_map_assist", False),
        ]
        self.key_labels = {}

        for label, action, editable in key_configs:
            # 每个功能使用一个容器 Frame
            func_frame = tk.Frame(self.key_frame, bg="#DDE6F0")
            func_frame.pack(fill="x", pady=1)

            left_frame = tk.Frame(func_frame, bg="#DDE6F0")
            left_frame.pack(side="left", fill="both", expand=True)

            # 描述标签
            desc_label = tk.Label(left_frame, text=label, bg="#DDE6F0", fg="#333333", font=("Microsoft YaHei", self.font_status, "bold"))
            desc_label.pack(side=tk.LEFT, anchor="w")

            if action == "marker_pair":
                prev_label = tk.Label(left_frame, text=self.format_hotkey(self.hotkeys["marker_prev"]), bg="#DDE6F0", fg="#2563EB", font=("Consolas", self.font_status, "bold"))
                prev_label.pack(side=tk.LEFT, padx=(6, 0))
                self.key_labels["marker_prev"] = prev_label
                prev_record = RoundedButton(left_frame, 44, 26, 30, "录制",
                                            command=lambda lbl=prev_label: self.capture_hotkey("marker_prev", lbl),
                                            is_toggle=False, text_size=self.font_small)
                prev_record.pack(side=tk.LEFT, padx=(5, 7))
                next_label = tk.Label(left_frame, text=self.format_hotkey(self.hotkeys["marker_next"]), bg="#DDE6F0", fg="#2563EB", font=("Consolas", self.font_status, "bold"))
                next_label.pack(side=tk.LEFT, padx=(0, 0))
                self.key_labels["marker_next"] = next_label
                record_btn = RoundedButton(func_frame, 50, 26, 30, "录制",
                                        command=lambda lbl=next_label: self.capture_hotkey("marker_next", lbl),
                                        is_toggle=False, text_size=self.font_small)
                record_btn.pack(side="right", padx=4)
                continue

            # 快捷键显示
            if action == "fire_key":
                current_key = self.format_hotkey(self.hotkeys["fire_key"])
            else:
                current_key = self.format_hotkey(self.hotkeys[action]) if editable else "鼠标左键 + 中键"
            key_label = tk.Label(left_frame, text=current_key, bg="#DDE6F0", fg="#2563EB", font=("Consolas", self.font_status, "bold"))
            key_label.pack(side=tk.LEFT, padx=(6, 0))
            if editable:
                self.key_labels[action] = key_label

            # 右侧：录制按钮
            if editable:
                record_btn = RoundedButton(func_frame, 50, 26, 30, "录制", 
                                        command=lambda a=action, lbl=key_label: self.capture_hotkey(a, lbl), 
                                        is_toggle=False, text_size=self.font_small)
                record_btn.pack(side="right", padx=4)

        # 保存快捷键按钮
        btn_frame = tk.Frame(self.key_frame, bg="#DDE6F0")
        btn_frame.pack(side=tk.BOTTOM, pady=(2, 2))
        save_btn = RoundedButton(btn_frame, 126, 28, 30, "保存快捷键", 
                                command=self.save_hotkey_config, is_toggle=False, text_size=self.font_small)
        save_btn.pack(side=tk.LEFT, padx=2)
        default_btn = RoundedButton(btn_frame, 126, 28, 30, "恢复默认", 
                                    command=self.reset_default_hotkeys, is_toggle=False, text_size=self.font_small)
        default_btn.pack(side=tk.LEFT, padx=2)
    
    def reload_recoil_config(self):
        self.recoil.reload_config()

    def set_recoil_state_from_debugger(self, enabled):
        self.recoil_enabled = bool(enabled)
        self.btn_recoil.set_active(self.recoil_enabled)
        self.btn_recoil.set_text(f"{'关闭' if self.recoil_enabled else '开启'}辅助压枪")
        if self.recoil_enabled:
            if self.current_weapon and self.current_weapon not in ["Rocket", "Grenade", "VSS", "Crossbow", "C4"]:
                self.recoil.update_current_weapon(self.current_weapon)
                slot = self.weapon_slot_map.get(self.current_weapon)
                if slot:
                    weapon_data = self.current_weapons_attachments.get(slot, {})
                    self.recoil.update_attachments({
                        "scope": weapon_data.get("scope"),
                        "grip": weapon_data.get("grip"),
                        "muzzle": weapon_data.get("muzzle"),
                        "stock": weapon_data.get("stock"),
                    })
            if self.current_gesture:
                self.recoil.update_stance(self.current_gesture)
        self.update_status_display()

    def open_recoil_debugger(self):
        if not open_recoil_debugger:
            print("[压枪调试] recoil_debugger 模块不可用")
            return
        app = open_recoil_debugger(self.root, self.recoil)
        self.recoil_debugger_windows.append(app)

        def on_close():
            if app in self.recoil_debugger_windows:
                self.recoil_debugger_windows.remove(app)
            app.on_closing()

        app.root.protocol("WM_DELETE_WINDOW", on_close)

    def open_special_weapon_debugger(self):
        if not open_special_weapon_debugger:
            print("[特殊武器调试] special_weapon_debugger 模块不可用")
            return
        modules = {
            "rocket": self.rocket,
            "vss": self.vss_assist,
            "crossbow": self.crossbow_assist,
            "mortar": self.mortar,
            "throwables": self.throwables,
            "c4": self.c4_assistant,
        }
        app = open_special_weapon_debugger(self.root, self.config_file, modules)
        self.special_weapon_debugger_windows.append(app)

        def on_close():
            if app in self.special_weapon_debugger_windows:
                self.special_weapon_debugger_windows.remove(app)
            app.on_closing()

        app.root.protocol("WM_DELETE_WINDOW", on_close)

    def open_auto_scale_calibrator(self):
        if not open_region_scaling_auto_calibrator:
            print("[缩放校准] region_calibrator_auto 模块不可用")
            return
        app = open_region_scaling_auto_calibrator(self.root)
        self.auto_calibrator_windows.append(app)

        def on_close():
            if app in self.auto_calibrator_windows:
                self.auto_calibrator_windows.remove(app)
            app.on_closing()

        app.root.protocol("WM_DELETE_WINDOW", on_close)

    def toggle_assistant(self, key):
        module = self.special_assistant_modules.get(key)
        if not module:
            return
        if not self.display_enabled:
            module.enable_module(False)
            self.manual_assistant_keys.discard(key)
            if key in self.assistant_btns:
                self.assistant_btns[key].set_active(False)
            return

        next_state = not module.is_enabled
        module.enable_module(next_state)
        if next_state:
            self.manual_assistant_keys.add(key)
        else:
            self.manual_assistant_keys.discard(key)
        if key in self.assistant_btns:
            self.assistant_btns[key].set_active(module.is_enabled)
        self.update_status_display()

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
            if action_key in ("throw", "toggle_equipment", "fire_key") and modifiers:
                # 手雷瞬爆、打开装备栏和开火按键只允许单键，不允许带修饰键
                key_label.config(text="仅允许单键")
                old_value = self.hotkeys[action_key]
                self.root.after(1000, lambda: key_label.config(text=self.format_hotkey(old_value)))
                self._is_capturing = False
                self.restart_listeners()
                return

            if action_key == "fire_key":
                self.hotkeys["fire_key"] = main_key[1:-1] if main_key.startswith("<") and main_key.endswith(">") else main_key
            else:
                self.hotkeys[action_key] = combo_str
            self._is_capturing = False
            key_label.config(text=self.format_hotkey(self.hotkeys[action_key]))
            self.root.after(100, self.restart_listeners)

        self.temp_listener = keyboard.Listener(on_press=on_press)
        self.temp_listener.start()

    def load_hotkey_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    saved_hotkeys = data.get("hotkeys", {})
                    if saved_hotkeys:
                        self.hotkeys.update(saved_hotkeys)
                    if "fire_key" not in saved_hotkeys:
                        fire_key = data.get("recoil_settings", {}).get("fire_key")
                        if fire_key:
                            self.hotkeys["fire_key"] = self._normalize_fire_key(fire_key)
            except: pass

    def migrate_legacy_default_hotkeys(self):
        legacy_defaults = {
            "toggle_weapon_detection": {"<f2>"},
            "toggle_display": {"<ctrl>+<shift>+<space>"},
            "toggle_recoil": {"<ctrl>+<shift>+<tab>"},
            "measure_map": {"<f1>", "<ctrl>+<shift>+m"}
        }
        new_defaults = {
            "toggle_weapon_detection": "<f1>",
            "toggle_display": "<f2>",
            "toggle_recoil": "<f3>",
            "measure_map": "<f4>"
        }
        changed = False
        for action, old_values in legacy_defaults.items():
            if self.hotkeys.get(action) in old_values:
                self.hotkeys[action] = new_defaults[action]
                changed = True
        if changed:
            self.save_hotkey_config()

    def save_hotkey_config(self):
        data = {}
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                try: data = json.load(f)
                except: pass
        data["hotkeys"] = self.hotkeys
        if "recoil_settings" in data:
            data["recoil_settings"].pop("fire_key", None)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

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
        if not self.status_overlay:
            return

        # 映射表
        grip_map = {
            "vertical": "垂直", "half": "半截", "tilted": "斜握",
            "light": "轻握", "laser": "激光", "thumb": "拇指"
        }
        stock_map = {
            "tactical": "战术", "heavy": "重型", "uzi": "微托", "cheek_pad": "托腮板"
        }
        scope_map = {
            "red_dot": "红点", "holographic": "全息", "2": "二倍", "3": "三倍",
            "4": "四倍", "6": "六倍", "8": "八倍", "multiple": "蛤蟆"
        }
        muzzle_map = {
            "ar_dmr_compensator": "步枪补偿", "ar_dmr_suppressor": "步枪消焰", "ar_dmr_silencer": "步枪消音", "ar_dmr_braker": "制退",
            "dmr_sr_compensator": "狙补偿", "dmr_sr_suppressor": "狙消焰", "dmr_sr_silencer": "狙消音",
            "smg_compensator": "冲锋补偿", "smg_suppressor": "冲锋消焰", "smg_silencer": "冲锋消音",
        }
        gesture_map = {"stand": "站立", "squat": "蹲下", "lie": "趴下"}
        status_colors = {
            "green": self.marker_color_hex["Green"],
            "orange": self.marker_color_hex["Orange"],
            "blue": self.marker_color_hex["Blue"],
            "yellow": self.marker_color_hex["Yellow"],
            "red": "#E74C3C",
            "white": "#FFFFFF"
        }
        status_map = {
            "opened": ("武器识别中", status_colors["green"]),
            "closed": ("装备栏关闭", status_colors["blue"]),
            "confirming": ("正在确认中", status_colors["orange"])
        }
        status_text, status_color = status_map.get(self.equipment_status, ("装备栏关闭", status_colors["blue"]))

        elements = []
        alpha = int(255 * self.status_text_opacity)
        base_x = 35
        top_y = self.sh - 300
        marker_y = 5
        status_y = 33
        detail_y = 58
        if self._should_show_marker_indicator():
            marker_color = self.marker_color_hex.get(self.current_marker_color, "#FFFFFF")
            elements.append({
                "type": "text", "x": base_x, "y": top_y + marker_y,
                "text": "当前使用标点：", "fill": marker_color,
                "alpha": alpha, "font_size": abs(self.font_status), "anchor": "lt"
            })
            marker_icon = self._get_colored_marker_icon(self.current_marker_color)
            if marker_icon:
                elements.append({
                    "type": "image", "x": base_x + 105, "y": top_y + marker_y + 8,
                    "image": marker_icon, "alpha": alpha, "anchor": "mm"
                })
            else:
                elements.append({
                    "type": "text", "x": base_x + 105, "y": top_y + marker_y,
                    "text": self.current_marker_color, "fill": marker_color,
                    "alpha": alpha, "font_size": abs(self.font_status), "anchor": "lt"
                })

        x_start = base_x
        y_offset = top_y + status_y
        # 识别
        color_detect = status_colors["green"] if self.weapon_detection_enabled else status_colors["red"]
        elements.append({"type": "text", "x": x_start, "y": y_offset, "text": "识别", "fill": color_detect, "alpha": alpha, "font_size": abs(self.font_status), "anchor": "lt"})
        
        x_start += 35
        # 测距
        color_display = status_colors["green"] if self.display_enabled else status_colors["red"]
        elements.append({"type": "text", "x": x_start, "y": y_offset, "text": "测距", "fill": color_display, "alpha": alpha, "font_size": abs(self.font_status), "anchor": "lt"})
        x_start += 35
        # 压枪
        if self.recoil_enabled:
            color_recoil = status_colors["green"]   # 绿色：压枪开启
        else:
            color_recoil = status_colors["red"]       # 红色：压枪关闭
        elements.append({"type": "text", "x": x_start, "y": y_offset, "text": "压枪", "fill": color_recoil, "alpha": alpha, "font_size": abs(self.font_status), "anchor": "lt"})
        
        x_start += 35
        # 装备栏状态
        elements.append({"type": "text", "x": x_start, "y": y_offset, "text": status_text, "fill": status_color, "alpha": alpha, "font_size": abs(self.font_status), "anchor": "lt"})

        w1 = self.current_weapons_attachments.get(1, {})
        w2 = self.current_weapons_attachments.get(2, {})

        def format_weapon(weapon_data):
            name = weapon_data.get("name") or "无"
            # 应用特殊武器名称映射
            if name in self.special_weapon_map:
                name = self.special_weapon_map[name]
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
        # 应用特殊武器名称映射
        if curr in self.special_weapon_map:
            curr = self.special_weapon_map[curr]
        pose = gesture_map.get(self.current_gesture, "未知") if self.current_gesture else "未知"
        line4 = f"当前: {curr} | 姿势: {pose}"

        y_offset = top_y + detail_y
        detail_color = status_colors["white"]
        for line in [line2, line3, line4]:
            elements.append({"type": "text", "x": base_x, "y": y_offset, "text": line, "fill": detail_color, "alpha": alpha, "font_size": abs(self.font_status), "anchor": "lt"})
            y_offset += 25
        self.status_overlay.render_elements(elements)

    def update_status_full(self):
        parts = []
        if self.current_weapon:
            # 应用特殊武器名称映射
            weapon_name = self.current_weapon
            if weapon_name in self.special_weapon_map:
                weapon_name = self.special_weapon_map[weapon_name]
            parts.append(weapon_name)
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
        auto_key = self.weapon_assistant_map.get(weapon_name) if self.display_enabled else None
        for key, module in self.special_assistant_modules.items():
            if key == "mortar":
                continue
            if key == "c4" and self.display_enabled and (module.is_installing or module.is_active):
                should_enable = True
                module.enable_module(True)
                if key in self.assistant_btns:
                    self.assistant_btns[key].set_active(module.is_enabled)
                continue
            should_enable = self.display_enabled and (key in self.manual_assistant_keys or key == auto_key)
            module.enable_module(should_enable)
            if key in self.assistant_btns:
                self.assistant_btns[key].set_active(module.is_enabled)

    def toggle_display(self):
        self.display_enabled = not self.display_enabled
        self.btn_display.set_active(self.display_enabled)
        self.btn_display.set_text(f"{'关闭' if self.display_enabled else '开启'}瞄准辅助")
        self.mortar.enable_module(self.display_enabled)
        if not self.display_enabled:
            self.manual_assistant_keys.clear()
        self.assistant_btns["mortar"].set_active(self.display_enabled and self.mortar.is_enabled)
        self.update_weapon_ui(self.current_weapon)
        self.minimap.set_enabled(self.display_enabled)
        self.elevation.set_enabled(self.display_enabled)
        self.minimap.set_display(self.display_enabled)
        self.elevation.set_display(self.display_enabled)
        self.largemap_radar.set_display(self.display_enabled)
        self.update_status_display()


    def toggle_recoil(self):
        self.recoil_enabled = not self.recoil_enabled
        self.btn_recoil.set_active(self.recoil_enabled)
        self.btn_recoil.set_text(f"{'关闭' if self.recoil_enabled else '开启'}辅助压枪")
        self.recoil.set_enabled(self.recoil_enabled)
        if self.recoil_enabled:
            if self.current_weapon and self.current_weapon not in ["Rocket", "Grenade", "VSS", "Crossbow", "C4"]:
                self.recoil.update_current_weapon(self.current_weapon)
                # 获取当前武器的配件
                slot = self.weapon_slot_map.get(self.current_weapon)
                if slot:
                    attachments = {}
                    w = self.current_weapons_attachments.get(slot, {})
                    attachments["scope"] = w.get("scope")
                    attachments["grip"] = w.get("grip")
                    attachments["muzzle"] = w.get("muzzle")
                    attachments["stock"] = w.get("stock")
                    self.recoil.update_attachments(attachments)
            if self.current_gesture:
                self.recoil.update_stance(self.current_gesture)
        else:
            self.recoil.update_current_weapon(None)
        self.update_status_display()

    def toggle_debug(self):
        new_state = not self.region_manager.show_debug
        self.region_manager.set_debug_mode(new_state)
        self.btn_debug.set_active(new_state)
        self.btn_debug.set_text("显示所有区域框")

    def start_listeners(self):
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.keyboard_listener.start()
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.mouse_listener.start()
        hotkey_mapping = {
            self.hotkeys['toggle_display']: lambda: self.root.after(0, self.toggle_display),
            self.hotkeys['measure_map']: lambda: self.root.after(0, self.largemap_radar.toggle_mode),
            self.hotkeys['toggle_recoil']: lambda: self.root.after(0, self.toggle_recoil),
            self.hotkeys['toggle_weapon_detection']: lambda: self.root.after(0, self.toggle_weapon_detection),
            self.hotkeys['marker_prev']: lambda: self.root.after(0, self._cycle_marker_hotkey, -1),
            self.hotkeys['marker_next']: lambda: self.root.after(0, self._cycle_marker_hotkey, 1),
        }
        self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_mapping)
        self.hotkey_listener.start()

    def restart_listeners(self):
        for listener_name in ["hotkey_listener", "keyboard_listener", "mouse_listener"]:
            listener = getattr(self, listener_name, None)
            if listener:
                try:
                    listener.stop()
                except Exception:
                    pass
                setattr(self, listener_name, None)
        self.save_hotkey_config()
        self.start_listeners()

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
                    self._schedule_window_rounding()
                    self.root.lift()
                    self.root.focus_force()
                return
        except:
            pass
        if key in (keyboard.Key.left, keyboard.Key.right) and not self._is_capturing:
            try:
                if self.root.state() == 'normal':
                    self.root.after(0, self.switch_tab, -1 if key == keyboard.Key.left else 1)
                    return
            except Exception:
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
        if hasattr(key, 'char') and key.char and key.char.lower() == 'n':
            self.toggle_display()
            return

    def on_key_release(self, key):
        if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt_pressed = False

    def on_mouse_click(self, x, y, button, pressed):
        # 左键按下时通知 C4 助手（用于安装 C4）
        if button == mouse.Button.left and pressed:
            self.c4_assistant.on_mouse_left_press()
        elif button == mouse.Button.right:
            self.c4_assistant.on_mouse_right_click(pressed)

        # 左键+中键 地图点位助手
        if button == mouse.Button.left:
            self.left_pressed = pressed
        elif button == mouse.Button.middle:
            self.middle_pressed = pressed

        if self.left_pressed and self.middle_pressed and self.current_weapon is None:
            if not self.map_assist.is_enabled:
                self.map_assist.set_enabled(True)
        else:
            if self.current_weapon is not None and self.map_assist.is_enabled:
                self.map_assist.set_enabled(False)
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
        if "recoil_settings" in data:
            data["recoil_settings"].pop("fire_key", None)
        # 写回文件
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        self.recoil.reload_config()
        print("[快捷键] 配置已保存")    
    
    def reset_default_hotkeys(self):
        self.hotkeys = {
            "throw": "b",
            "toggle_weapon_detection": "<f1>",
            "toggle_display": "<f2>",
            "toggle_recoil": "<f3>",
            "measure_map": "<f4>",
            "marker_prev": "q",
            "marker_next": "e",
            "toggle_equipment": "tab",
            "fire_key": "end"
        }
        self.save_hotkey_config()
        self.restart_listeners()
        # 刷新UI中的快捷键显示
        for action, label in self.key_labels.items():
            label.config(text=self.format_hotkey(self.hotkeys[action]))

    def load_hotkey_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    saved_hotkeys = data.get("hotkeys", {})
                    if saved_hotkeys:
                        self.hotkeys.update(saved_hotkeys)
                    if "fire_key" not in saved_hotkeys:
                        fire_key = data.get("recoil_settings", {}).get("fire_key")
                        if fire_key:
                            self.hotkeys["fire_key"] = self._normalize_fire_key(fire_key)
            except:
                pass

    def _normalize_fire_key(self, key):
        fire_key = str(key).strip().lower()
        if fire_key.startswith("<") and fire_key.endswith(">"):
            fire_key = fire_key[1:-1]
        return fire_key or "end"

    def load_fire_key_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return self._normalize_fire_key(data.get("hotkeys", {}).get(
                    "fire_key",
                    data.get("recoil_settings", {}).get("fire_key", "end")
                ))
            except Exception:
                pass
        return "end"

    def on_closing(self):
        self.equipment_detector.set_enabled(False)
        self.weapon_detector.set_enabled(False)
        self.gesture_id.set_enabled(False)
        self.recoil.shutdown()
        if hasattr(self.mortar, "shutdown"):
            self.mortar.shutdown()
        if hasattr(self.largemap_radar, "shutdown"):
            self.largemap_radar.shutdown()
        for assistant in [self.rocket, self.throwables, self.vss_assist, self.crossbow_assist]:
            if hasattr(assistant, "shutdown"):
                assistant.shutdown()
        self.c4_assistant.shutdown()   # 关闭 C4 助手
        for app in list(getattr(self, "recoil_debugger_windows", [])):
            try:
                app.on_closing()
            except Exception:
                pass
        self.recoil_debugger_windows.clear()
        for app in list(getattr(self, "special_weapon_debugger_windows", [])):
            try:
                app.on_closing()
            except Exception:
                pass
        self.special_weapon_debugger_windows.clear()
        if self.status_overlay:
            self.status_overlay.destroy()
        for listener in [getattr(self, "keyboard_listener", None), getattr(self, "mouse_listener", None), getattr(self, "hotkey_listener", None)]:
            if listener:
                try:
                    listener.stop()
                except Exception:
                    pass
        self.root.destroy()

if __name__ == "__main__":
    import ctypes
    import platform

    # 启用高 DPI 感知（Per-Monitor V2），确保 tkinter 使用物理像素
    if platform.system() == "Windows":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    root = tk.Tk()
    app = TacticalHub(root)
    root.mainloop()
