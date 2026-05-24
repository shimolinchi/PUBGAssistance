import tkinter as tk
import queue
import math
import json
import os
from pynput import keyboard, mouse

# ================= 1. 地图点位数据配置 =================
MAP_DATA = {
    "艾伦格 (Erangel)": {
        "vehicles": [(-0.757, 0.594), (-0.609, 0.62), (-0.344, 0.674), (-0.07, 0.681), (0.126, 0.757), (0.365, 0.891), (0.654, 0.765), (-0.583, 0.45), (-0.369, 0.383), (0.376, 0.674), (0.639, 0.574), (0.319, 0.417), (0.489, 0.357), (0.689, 0.193), (0.719, -0.133), (-0.656, 0.287), (-0.081, 0.257), (0.098, 0.235), (-0.002, 0.152), (-0.224, 0.183), (-0.591, 0.154), (-0.75, -0.281), (-0.578, -0.124), (-0.483, 0.041), (-0.337, -0.052), (-0.094, -0.017), (0.063, -0.146), (0.261, -0.124), (0.431, -0.161), (-0.633, -0.481), (-0.078, -0.465), (0.111, -0.656), (0.078, -0.735), (0.359, -0.469), (0.476, -0.513)],
        "rooms": [(-0.663, 0.554), (-0.639, 0.126), (-0.363, 0.457), (-0.689, -0.356), (-0.261, 0.08), (-0.33, -0.265), (0.141, -0.083), (0.341, 0.161), (0.589, 0.491), (0.657, -0.2), (-0.193, -0.641), (0.08, -0.452), (0.391, -0.65)],
        "planes": [(-0.778, 0.611), (-0.6, 0.622), (-0.581, 0.519), (-0.406, 0.656), (-0.294, 0.696), (-0.137, 0.606), (-0.135, 0.719), (-0.189, 0.393), (0.337, 0.881), (0.541, 0.872), (0.617, 0.667), (0.569, 0.572), (0.694, 0.541), (0.669, 0.448), (0.689, 0.32), (0.669, -0.009), (0.711, -0.165), (0.667, -0.233), (0.83, 0.006), (0.859, -0.124), (-0.333, 0.256), (-0.611, 0.174), (-0.739, 0.2), (-0.739, 0.096), (-0.774, -0.217), (-0.691, -0.398), (-0.528, -0.396), (-0.502, -0.298), (-0.352, -0.411), (-0.302, -0.346), (-0.228, -0.667), (-0.126, -0.578), (0.033, -0.615), (0.019, -0.72), (0.209, -0.617), (0.3, -0.648), (0.346, -0.537), (0.402, -0.517)]
    },
    "米拉玛 (Miramar)": {
        "vehicles": [(-0.765, -0.756), (-0.102, -0.843), (0.12, -0.752), (-0.12, -0.644), (-0.406, -0.531), (-0.635, -0.463), (-0.772, -0.228), (-0.581, -0.167), (-0.331, -0.283), (-0.174, -0.344), (0.269, -0.574), (0.535, -0.496), (0.209, -0.394), (0.139, -0.324), (-0.487, -0.002), (-0.87, 0.202), (-0.615, 0.252), (-0.239, 0.115), (-0.113, -0.035), (0.235, -0.011), (0.522, -0.15), (-0.776, 0.461), (-0.717, 0.524), (-0.319, 0.496), (-0.033, 0.261), (0.081, 0.315), (0.389, 0.294), (0.585, 0.376), (0.75, 0.174), (-0.38, 0.654), (-0.244, 0.854), (-0.08, 0.861), (-0.026, 0.706), (0.137, 0.8), (0.354, 0.656), (0.437, 0.794), (0.624, 0.709), (0.702, 0.607)],
        "rooms":[(-0.559, 0.589), (-0.2, 0.733), (-0.659, 0.194), (-0.313, 0.387), (0.13, 0.648), (-0.678, -0.304), (-0.339, -0.224), (-0.065, 0.043), (0.261, 0.217), (0.546, 0.524), (-0.657, -0.778), (-0.2, -0.63), (0.078, -0.276), (0.519, -0.041), (0.281, -0.537)],
        "planes": [(0.556, 0.867), (0.22, 0.839), (0.022, 0.87), (-0.12, 0.661), (-0.191, 0.857), (-0.587, 0.617), (-0.704, 0.487), (-0.869, 0.302), (-0.631, 0.189), (-0.711, -0.039), (-0.576, -0.133), (-0.737, -0.363), (-0.77, -0.517), (-0.461, -0.45), (-0.307, -0.581), (-0.62, -0.644), (-0.748, -0.826), (-0.537, -0.894), (0.022, -0.737), (0.172, -0.756), (0.27, -0.665), (0.378, -0.52), (0.572, -0.404), (0.806, -0.17)]
    },
    "泰戈 (Taego)": {
        "vehicles":[(-0.319, 0.793), (-0.6, 0.617), (-0.689, 0.383), (-0.511, 0.261), (-0.419, 0.419), (-0.367, 0.4), (-0.302, 0.498), (-0.057, 0.756), (-0.411, 0.046), (-0.133, 0.296), (0.081, 0.428), (0.144, 0.394), (0.27, 0.644), (0.537, 0.633), (0.604, 0.539), (0.717, 0.596), (0.77, 0.261), (0.783, 0.226), (0.754, 0.161), (0.144, 0.109), (0.293, 0.041), (0.435, -0.043), (0.587, -0.111), (0.602, -0.465), (0.478, -0.385), (0.435, -0.45), (0.27, -0.291), (0.033, -0.189), (-0.148, -0.219), (-0.181, -0.267), (-0.394, -0.169), (-0.626, 0.043), (-0.837, -0.117), (-0.637, -0.157), (-0.28, -0.343), (-0.481, -0.417), (-0.554, -0.435), (-0.504, -0.639), (-0.202, -0.563), (-0.019, -0.685), (0.083, -0.617), (0.169, -0.483), (0.352, -0.678), (0.448, -0.844), (0.433, 0.357), (0.706, -0.126)],
        "rooms":[(-0.657, 0.709), (-0.369, 0.67), (-0.691, 0.339), (-0.75, 0.165), (-0.761, -0.285), (-0.406, -0.581), (0.085, -0.219), (-0.122, 0.515), (0.183, 0.58), (0.696, 0.491), (0.741, 0.174), (0.481, 0.052), (0.207, -0.576), (0.574, -0.367), (0.557, -0.763)],
        "planes": [(-0.569, 0.511), (-0.089, 0.331), (-0.683, -0.015), (-0.27, -0.719), (-0.015, -0.17), (0.224, 0.102), (0.554, 0.296), (0.87, 0.428), (0.574, -0.591)]
    },
    "荣都 (Rondo)": {
        "vehicles": [(-0.689, 0.561), (-0.711, -0.28), (-0.672, -0.748), (-0.374, 0.322), (-0.274, -0.059), (-0.333, -0.319), (-0.378, -0.693), (-0.267, 0.93), (-0.091, 0.467), (0.087, 0.12), (0.235, -0.254), (0.211, -0.619), (0.244, -0.737), (0.137, 0.744), (0.683, 0.648), (0.548, 0.515), (0.594, 0.174), (0.606, -0.193), (0.817, -0.461), (0.685, -0.554)],
        "rooms": [(-0.639, 0.669), (-0.652, 0.206), (-0.643, -0.174), (-0.68, -0.594), (-0.256, 0.772), (-0.259, -0.261), (-0.17, -0.717), (-0.072, 0.35), (0.235, 0.498), (0.144, -0.078), (0.213, -0.811), (0.43, 0.772), (0.4, -0.493), (0.628, -0.05), (0.728, 0.324)],
        "planes": [(0.909, 0.078), (0.906, 0.439), (0.848, 0.754), (0.448, 0.941), (-0.196, 0.92), (-0.63, 0.67), (-0.869, 0.47), (-0.785, -0.513), (-0.459, -0.783), (-0.037, -0.746)]
    },
    "维寒迪 (Vikendi)": {
        "vehicles":[(-0.702, 0.557), (-0.589, 0.513), (-0.38, 0.576), (-0.091, 0.696), (0.078, 0.77), (-0.072, 0.519), (-0.744, 0.113), (-0.506, 0.194), (-0.302, 0.265), (-0.163, 0.319), (0.009, 0.428), (0.256, 0.559), (0.483, 0.672), (0.111, 0.233), (0.283, 0.391), (0.563, 0.474), (-0.744, -0.196), (-0.569, -0.109), (-0.581, -0.091), (-0.339, -0.083), (-0.072, -0.03), (0.248, 0.006), (0.328, 0.154), (0.446, 0.107), (0.591, 0.23), (0.685, 0.23), (-0.672, -0.476), (-0.537, -0.55), (-0.261, -0.289), (-0.091, -0.359), (-0.069, -0.335), (0.343, -0.252), (0.644, -0.317), (0.706, -0.122), (0.502, -0.035), (-0.378, -0.78), (-0.22, -0.596), (0.033, -0.65), (0.313, -0.781), (0.48, -0.591)],
        "rooms": [(-0.657, 0.056), (-0.324, 0.611), (-0.417, -0.383), (0.007, 0.211), (0.328, 0.674), (-0.03, -0.607), (0.159, -0.217), (0.537, 0.396), (0.683, 0.046), (0.493, -0.444)],
        "bear_caves": [(-0.296, 0.669), (0.293, 0.661), (0.491, 0.569), (0.402, 0.28), (0.157, 0.126), (0.633, 0.048), (0.53, -0.448), (0.289, -0.446), (-0.065, -0.502), (-0.074, -0.594)],
        "planes": [(-0.607, 0.643), (-0.576, 0.013), (-0.111, 0.439), (-0.683, -0.424), (-0.43, -0.743), (0.044, -0.08), (0.339, 0.248), (0.457, 0.504), (0.209, -0.698), (0.624, -0.394)],
        "crowbar_rooms":[(-0.652, 0.656), (-0.243, 0.687), (-0.528, 0.246), (-0.207, 0.285), (-0.106, 0.465), (-0.561, -0.094), (-0.748, -0.206), (0.115, 0.128), (0.285, 0.354), (0.309, 0.104), (-0.28, -0.298), (-0.215, -0.476), (-0.011, -0.352), (-0.113, -0.702), (0.061, -0.646), (0.304, -0.52), (0.487, -0.211), (0.622, -0.435), (0.681, -0.135)],
        "lab_camps":[(-0.506, 0.341), (-0.443, 0.463), (-0.209, 0.524), (-0.194, 0.741)]
    },
    "帝斯顿 (Deston)": {
        "vehicles": [(-0.354, 0.869), (-0.815, 0.624), (-0.526, 0.613), (-0.293, 0.672), (0.28, 0.763), (-0.924, 0.363), (-0.396, 0.424), (-0.174, 0.583), (-0.911, -0.065), (-0.554, 0.181), (-0.337, 0.25), (-0.124, 0.335), (0.148, 0.328), (0.361, 0.485), (0.693, 0.533), (0.813, 0.461), (0.481, 0.317), (-0.152, 0.113), (-0.448, -0.152), (-0.581, -0.152), (-0.644, -0.541), (-0.52, -0.289), (-0.191, -0.057), (-0.178, -0.596), (-0.102, -0.4), (-0.076, -0.183), (0.154, -0.487), (0.157, -0.767), (0.291, -0.065), (0.348, -0.565), (0.491, -0.08), (0.559, -0.333), (0.835, 0.096)],
        "safty_doors": [(-0.322, 0.87), (-0.543, 0.646), (-0.53, 0.637), (-0.524, 0.556), (-0.572, 0.17), (-0.23, 0.339), (-0.598, -0.119), (-0.437, -0.157), (-0.194, 0.119), (0.111, 0.33), (0.248, 0.519), (0.269, 0.78), (0.644, 0.541), (-0.717, -0.544), (-0.065, -0.394), (-0.061, -0.111), (0.122, 0.0), (0.396, -0.574), (0.802, 0.226), (0.456, -0.161), (0.476, -0.152), (0.502, -0.156), (0.563, -0.128), (0.606, -0.141), (0.596, -0.152), (0.619, -0.122), (0.644, -0.128), (0.661, -0.113), (0.598, -0.061), (0.617, -0.015), (0.585, 0.0), (0.543, -0.017), (0.496, -0.031), (0.517, -0.039), (0.517, -0.024)],
        "planes": [(-0.702, 0.77), (-0.83, -0.293), (-0.844, -0.124), (-0.33, 0.259), (-0.243, 0.43), (0.078, -0.485), (0.019, -0.161), (0.157, 0.196), (0.331, 0.478), (0.606, -0.494)],
    }
}

POINT_CONFIG = {
    "planes": {"name": "飞机点位", "color": "#FFA500"},
    "rooms": {"name": "密室位置", "color": "#FF0000"},
    "vehicles": {"name": "固定刷车", "color": "#00FFFF"},
    "bear_caves": {"name": "熊洞位置", "color": "#8B4513"},
    "crowbar_rooms": {"name": "撬棍房", "color": "#FF69B4"},
    "lab_camps": {"name": "实验营地", "color": "#32CD32"},
    "safty_doors": {"name": "安全门", "color": "#FF0000"}
}

# ================= 2. UI 组件 =================
class RoundButton(tk.Canvas):
    def __init__(self, master, text, command=None, width=110, height=36, radius=16, 
                 bg_color="#E0E0E0", fg_color="#333333", active_bg="#4CAF50", active_fg="white"):
        super().__init__(master, width=width, height=height, bg=master["bg"], highlightthickness=0)
        self.command = command
        self.text = text
        self.radius = radius
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.active_bg = active_bg
        self.active_fg = active_fg
        self.is_active = False

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        r = self.radius
        color = self.active_bg if self.is_active else self.bg_color
        text_color = self.active_fg if self.is_active else self.fg_color

        points = [
            r, 0, r, 0, w - r, 0, w - r, 0, w, 0, w, r, w, r,
            w, h - r, w, h - r, w, h, w - r, h, w - r, h, r, h,
            r, h, 0, h, 0, h - r, 0, h - r, 0, r, 0, r, 0, 0
        ]
        self.create_polygon(points, smooth=True, fill=color, outline=color, width=1)
        self.create_text(w/2, h/2, text=self.text, fill=text_color, font=("Microsoft YaHei", 9, "bold"))

    def set_active(self, active):
        self.is_active = active
        self._draw()

    def _on_press(self, event): pass
    def _on_release(self, event):
        if self.command: self.command()

# ================= 3. 全局统一状态机程序 =================
class PUBGComprehensiveAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("PUBG 综合战术助手")
        self.root.geometry("400x550")
        self.root.attributes("-topmost", True)
        self.bg_color = "#F5F7FA"
        self.root.configure(bg=self.bg_color)
        
        self.config_file = "mortar_config.json"
        self.config_data = self.load_config()
        self.zoom_level = min(3, max(1, self.config_data.get("current_zoom", 1)))
        self.scales = self.config_data.get("scales_1km", {"1": 850.0, "2": 850.0, "3": 850.0})

        self.state = "IDLE"
        self.cmd_queue = queue.Queue()
        self.current_map = "艾伦格 (Erangel)"
        self.map_buttons = {}
        
        self.manual_points = []
        self.calib_pt1 = None
        self.calib_mode = 1000 

        self.screen_w = tk.StringVar(value="1920")
        self.screen_h = tk.StringVar(value="1080")

        self.size_configs = {
            "小": {"radius": 3, "width": 1},
            "中": {"radius": 4, "width": 3},
            "大": {"radius": 7, "width": 3}
        }
        self.current_size = "小"
        self.size_buttons = {}

        self.mouse_states = {mouse.Button.left: False, mouse.Button.middle: False, mouse.Button.right: False}
        self.keys_pressed = set()
        self.combo_triggered = False

        self.init_ui()
        self.init_overlay()

        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.mouse_listener.start()
        self.keyboard_listener.start()

        self.process_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f: return json.load(f)
            except: pass
        return {"current_zoom": 1, "scales_1km": {"1": 850.0, "2": 850.0, "3": 850.0}}

    def save_config(self):
        self.config_data["current_zoom"] = self.zoom_level
        self.config_data["scales_1km"] = self.scales
        with open(self.config_file, 'w') as f: json.dump(self.config_data, f)

    def get_current_scale(self):
        return self.scales.get(str(self.zoom_level), 850.0)

    def get_state_desc(self):
        desc_map = {
            "IDLE": ("待命", "#7F8C8D"),
            "MAP_SHOWING": ("点位显示中", "#27AE60"),
            "DIST_PT1": ("测距中 - 请按左键选【起点】", "#E67E22"),
            "DIST_PT2": ("测距中 - 请按左键选【终点】", "#E67E22"),
            "DIST_RESULT": ("测距结果展示 (右键返回)", "#2980B9"),
            "CALIB_PT1": (f"标定中 ({self.calib_mode}m) - 选起点", "#8E44AD"),
            "CALIB_PT2": (f"标定中 ({self.calib_mode}m) - 选交点", "#8E44AD")
        }
        return desc_map.get(self.state, ("未知", "#7F8C8D"))

    def init_ui(self):
        frame_res = tk.Frame(self.root, bg=self.bg_color)
        frame_res.pack(pady=(15, 5))
        tk.Label(frame_res, text="屏幕分辨率:", bg=self.bg_color, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
        tk.Entry(frame_res, textvariable=self.screen_w, width=6, relief="flat", highlightbackground="#ccc", highlightthickness=1).pack(side=tk.LEFT, padx=5)
        tk.Label(frame_res, text="x", bg=self.bg_color).pack(side=tk.LEFT)
        tk.Entry(frame_res, textvariable=self.screen_h, width=6, relief="flat", highlightbackground="#ccc", highlightthickness=1).pack(side=tk.LEFT, padx=5)

        frame_size = tk.Frame(self.root, bg=self.bg_color)
        frame_size.pack(pady=5)
        tk.Label(frame_size, text="点位大小:", bg=self.bg_color, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(0, 10))
        for size in ["小", "中", "大"]:
            btn = RoundButton(frame_size, text=size, width=75, height=36, radius=18, command=lambda s=size: self.select_size(s))
            btn.pack(side=tk.LEFT, padx=4)
            self.size_buttons[size] = btn
        self.update_size_button_styles()

        frame_btns = tk.Frame(self.root, bg=self.bg_color)
        frame_btns.pack(pady=5)
        maps = list(MAP_DATA.keys())
        for i, map_name in enumerate(maps[:6]):
            btn = RoundButton(frame_btns, text=map_name, width=110, height=36, radius=18, command=lambda m=map_name: self.select_map(m))
            btn.grid(row=i // 3, column=i % 3, padx=6, pady=6)
            self.map_buttons[map_name] = btn
        self.update_button_styles()

        tk.Frame(self.root, height=2, bg="#CCCCCC").pack(fill="x", padx=30, pady=10)

        self.global_status_lbl = tk.Label(self.root, text="系统状态: 待命", fg="#7F8C8D", bg=self.bg_color, font=("Microsoft YaHei", 14, "bold"))
        self.global_status_lbl.pack(pady=(0, 5))

        frame_mortar = tk.Frame(self.root, bg=self.bg_color)
        frame_mortar.pack(pady=2)
        
        self.zoom_lbl = tk.Label(frame_mortar, text=f"当前预设标尺号: {self.zoom_level} / 3", fg="#E67E22", bg=self.bg_color, font=("Microsoft YaHei", 11, "bold"))
        self.zoom_lbl.pack()
        self.scale_lbl = tk.Label(frame_mortar, text=f"当前标尺(1km): {self.get_current_scale():.1f} 像素", fg="#2980B9", bg=self.bg_color, font=("Microsoft YaHei", 10))
        self.scale_lbl.pack(pady=(0, 5))

        frame_calib = tk.Frame(frame_mortar, bg=self.bg_color)
        frame_calib.pack()
        RoundButton(frame_calib, "标定 1km", width=110, height=36, radius=18, command=lambda: self.cmd_queue.put(("trigger_calib", 1000))).pack(side=tk.LEFT, padx=10)
        RoundButton(frame_calib, "标定 200m", width=110, height=36, radius=18, command=lambda: self.cmd_queue.put(("trigger_calib", 200))).pack(side=tk.LEFT, padx=10)
        RoundButton(frame_calib, "标定 100m", width=110, height=36, radius=18, command=lambda: self.cmd_queue.put(("trigger_calib", 100))).pack(side=tk.LEFT, padx=10)
        
        help_text = (
            "【操作说明】\n\n"
            " 开启地图点位 : 同时按【左键+中键】 \n"
            " 启动迫击炮测距 : 同时按【Tab+Caps+Shift+Ctrl】 \n"
            " 切换预设标尺 :  【+/-】  (锁定3档)\n"
            " 快捷切换大地图 : 【Alt + (+/-)】\n"
            " 测距/标定操作 : 【左键】选点，【右键】直接返回\n"
            " 关闭点位显示 : 【右键】 (按住 【Alt】 标路线不关闭)\n"
            " 紧急状态复位 :  【中键】"
        )
        tk.Label(self.root, text=help_text, justify="left", bg=self.bg_color, fg="#555555", font=("Microsoft YaHei", 9)).pack(pady=10)

    def init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)
        self.overlay.withdraw()
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def select_map(self, map_name):
        self.current_map = map_name
        self.update_button_styles()
        self.sync_ui()

    def update_button_styles(self):
        for name, btn in self.map_buttons.items(): btn.set_active(name == self.current_map)

    def select_size(self, size_name):
        self.current_size = size_name
        self.update_size_button_styles()
        self.sync_ui()

    def update_size_button_styles(self):
        for name, btn in self.size_buttons.items(): btn.set_active(name == self.current_size)

    def on_key_press(self, key):
        self.keys_pressed.add(key)
        has_tab = keyboard.Key.tab in self.keys_pressed
        has_caps = keyboard.Key.caps_lock in self.keys_pressed
        has_shift = any(k in self.keys_pressed for k in [keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r])
        has_ctrl = any(k in self.keys_pressed for k in [keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r])
        has_alt = any(k in self.keys_pressed for k in [keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r])
        
        current_combo = has_tab and has_caps and has_shift and has_ctrl
        if current_combo and not self.combo_triggered:
            self.combo_triggered = True
            self.cmd_queue.put(("trigger_dist", None))

        try:
            if key.char in ['+', '=']: 
                if has_alt:
                    self.cmd_queue.put(("switch_map", 1))
                else:
                    self.cmd_queue.put(("zoom", 1))
            elif key.char in ['-', '_']: 
                if has_alt:
                    self.cmd_queue.put(("switch_map", -1))
                else:
                    self.cmd_queue.put(("zoom", -1))
        except AttributeError: pass

    def on_key_release(self, key):
        if key in self.keys_pressed: self.keys_pressed.remove(key)
        has_tab = keyboard.Key.tab in self.keys_pressed
        has_caps = keyboard.Key.caps_lock in self.keys_pressed
        has_shift = any(k in self.keys_pressed for k in [keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r])
        has_ctrl = any(k in self.keys_pressed for k in [keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r])
        if not (has_tab and has_caps and has_shift and has_ctrl): self.combo_triggered = False

    def on_mouse_click(self, x, y, button, pressed):
        if button in self.mouse_states: self.mouse_states[button] = pressed
        has_alt = any(k in self.keys_pressed for k in [keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r])

        if pressed:
            if button in (mouse.Button.left, mouse.Button.middle) and self.mouse_states[mouse.Button.left] and self.mouse_states[mouse.Button.middle]:
                self.cmd_queue.put(("combo_map", None))
                return 

            if button == mouse.Button.left and not self.mouse_states[mouse.Button.middle]:
                self.cmd_queue.put(("left_click", (x, y)))

            elif button == mouse.Button.right and not self.mouse_states[mouse.Button.left] and not self.mouse_states[mouse.Button.middle]:
                self.cmd_queue.put(("right_click", (x, y, has_alt)))

            elif button == mouse.Button.middle and not self.mouse_states[mouse.Button.left]:
                self.cmd_queue.put(("middle_click", None))

    def process_queue(self):
        try:
            while True:
                cmd, data = self.cmd_queue.get_nowait()
                
                if cmd == "combo_map":
                    self.state = "IDLE" if self.state == "MAP_SHOWING" else "MAP_SHOWING"
                
                elif cmd == "trigger_dist":
                    self.state = "DIST_PT1"
                    self.manual_points = []
                    
                elif cmd == "trigger_calib":
                    self.calib_mode = data
                    self.state = "CALIB_PT1"
                    self.calib_pt1 = None

                elif cmd == "left_click":
                    if self.state == "DIST_PT1":
                        self.manual_points.append(data)
                        self.state = "DIST_PT2"
                    elif self.state == "DIST_PT2":
                        self.manual_points.append(data)
                        self.state = "DIST_RESULT"
                    elif self.state == "CALIB_PT1":
                        self.calib_pt1 = data
                        self.state = "CALIB_PT2"
                    elif self.state == "CALIB_PT2":
                        self.finish_calibration(data)

                elif cmd == "right_click":
                    x, y, has_alt = data
                    if self.state == "MAP_SHOWING":
                        if not has_alt:
                            self.state = "IDLE"
                    elif self.state != "IDLE":
                        self.state = "IDLE"

                elif cmd == "middle_click":
                    if self.state != "IDLE":
                        self.state = "IDLE"

                elif cmd == "zoom":
                    self.zoom_level = min(3, max(1, self.zoom_level + data))
                    self.save_config()
                    self.zoom_lbl.config(text=f"当前预设标尺号: {self.zoom_level} / 3")
                    self.scale_lbl.config(text=f"当前标尺(1km): {self.get_current_scale():.1f} 像素")

                elif cmd == "switch_map":
                    maps = list(MAP_DATA.keys())
                    idx = maps.index(self.current_map)
                    new_idx = (idx + data) % len(maps)
                    self.current_map = maps[new_idx]
                    self.update_button_styles()

                self.sync_ui()
        except queue.Empty:
            pass
        self.root.after(30, self.process_queue)

    def finish_calibration(self, pt2):
        # 修复了原来丢失的平方符号 `**2`
        dist = math.sqrt((pt2[0] - self.calib_pt1[0])**2 + (pt2[1] - self.calib_pt1[1])**2)
        if dist > 5: 
            if self.calib_mode == 100:
                scale_1km = dist * 10.0
            elif self.calib_mode == 1000:
                scale_1km = dist
            elif self.calib_mode == 200:
                scale_1km = dist * 5.0
            elif self.calib_mode == 500:
                scale_1km = dist * 2.0
            else:
                scale_1km = dist

            self.scales[str(self.zoom_level)] = scale_1km
            self.save_config()
            self.scale_lbl.config(text=f"当前标尺(1km): {scale_1km:.1f} 像素")
            
        self.state = "IDLE"

    def sync_ui(self):
        desc, color = self.get_state_desc()
        self.global_status_lbl.config(text=f"系统状态: {desc}", fg=color)

        if self.state == "IDLE":
            self.overlay.withdraw()
            self.canvas.delete("all")
        else:
            self.overlay.deiconify()
            self.canvas.delete("all")
            
            if self.state == "MAP_SHOWING":
                self.draw_map()
            else:
                self.draw_mortar()
                
            # 不论是地图还是迫击炮状态，都绘制左下角 HUD
            self.draw_bottom_left_hud()

    def create_shadow_text(self, x, y, text, fill, font, anchor="center"):
        self.canvas.create_text(x+2, y+2, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    # --- 新增的通用左下角 HUD 绘制函数 ---
    def draw_bottom_left_hud(self):
        try:
            w, h = int(self.screen_w.get()), int(self.screen_h.get())
        except ValueError:
            w, h = 1920, 1080
            
        # 设置 HUD 位置：左侧边距30，底部偏上约120像素，避开血条栏
        hud_x = 30
        hud_y = h - 250 
        font_hud = ("Microsoft YaHei", 16, "bold")
        
        text_zoom = f"预设标尺: 档位 {self.zoom_level} / 3"
        text_scale = f"1km 像素: {self.get_current_scale():.1f} px"
        
        # 橙色显示档位，亮蓝色显示标尺数值
        self.create_shadow_text(hud_x, hud_y, text_zoom, "#FFA500", font_hud, anchor="nw")
        self.create_shadow_text(hud_x, hud_y + 35, text_scale, "#00FFFF", font_hud, anchor="nw")

    def draw_map(self):
        try:
            w, h = int(self.screen_w.get()), int(self.screen_h.get())
        except ValueError:
            w, h = 1920, 1080

        font_title = ("Microsoft YaHei", 24, "bold")
        self.create_shadow_text(30, 40, f"{self.current_map}", "#FFFFFF", font_title, anchor="nw")

        data = MAP_DATA.get(self.current_map, {})
        narrow_edge = min(w, h)
        cx, cy = w / 2, h / 2
        font_style = ("Microsoft YaHei", 20, "bold")
        legend_start_y = 100 
        current_radius = self.size_configs[self.current_size]["radius"]
        current_width = self.size_configs[self.current_size]["width"]

        for key, config in POINT_CONFIG.items():
            points = data.get(key, [])
            if points:
                self.create_shadow_text(30, legend_start_y, text=config["name"], fill=config["color"], font=font_style, anchor="nw")
                legend_start_y += 40 
                color_hex = config["color"]
                for nx, ny in points:
                    px = cx + (nx * narrow_edge / 2)
                    py = cy - (ny * narrow_edge / 2)
                    self.canvas.create_oval(px - current_radius, py - current_radius, 
                                            px + current_radius, py + current_radius,
                                            outline=color_hex, width=current_width)

    def draw_mortar(self):
        try:
            w, h = int(self.screen_w.get()), int(self.screen_h.get())
        except ValueError:
            w, h = 1920, 1080
            
        font_h1 = ("Microsoft YaHei", 24, "bold")
        text_color = "#FFFFFF" 
        
        if self.state == "CALIB_PT1":
            self.create_shadow_text(w/2, 150, f"【标定 {self.calib_mode}m】请左键点击 起点 (右键退出)", text_color, font_h1)
        elif self.state == "CALIB_PT2":
            self.create_shadow_text(w/2, 150, f"【标定 {self.calib_mode}m】请左键点击 交点 (右键退出)", text_color, font_h1)
            x, y = self.calib_pt1
            self.canvas.create_line(x-6, y-6, x+6, y+6, fill="#FFD700", width=2)
            self.canvas.create_line(x-6, y+6, x+6, y-6, fill="#FFD700", width=2)
            
        elif self.state == "DIST_PT1":
            self.create_shadow_text(w/2, 150, "【测距】请左键点击迫击炮 起点 (右键退出)", text_color, font_h1)
        elif self.state == "DIST_PT2":
            self.create_shadow_text(w/2, 150, "【测距】请左键点击迫击炮 终点 (右键退出)", text_color, font_h1)
            for pt in self.manual_points:
                x, y = pt
                self.canvas.create_line(x-6, y-6, x+6, y+6, fill="#FFD700", width=2)
                self.canvas.create_line(x-6, y+6, x+6, y-6, fill="#FFD700", width=2)
                
        elif self.state == "DIST_RESULT":
            p1, p2 = self.manual_points[0], self.manual_points[1]
            self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#FFFFFF", dash=(5, 5), width=2)
            
            # 修复了原来丢失的平方符号 `**2`
            pixel_dist = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
            
            real_dist = (pixel_dist / self.get_current_scale()) * 1000
            
            self.create_shadow_text(w/2, 150, f"距离: {real_dist:.1f} 米", "#00FF00", ("Arial", 45, "bold"))
            self.create_shadow_text(w/2, 210, "(右键返回)", "#CCCCCC", ("Microsoft YaHei", 14))

    def on_closing(self):
        self.mouse_listener.stop()
        self.keyboard_listener.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PUBGComprehensiveAssistant(root)
    root.mainloop()