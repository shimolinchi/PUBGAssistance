import tkinter as tk
import queue
from pynput import keyboard, mouse

# --- 1. 测试点位数据 (坐标 -1 到 1) ---
MAP_DATA = {
    "艾伦格 (Erangel)": {
        "vehicles": [(-0.757, 0.594), (-0.609, 0.62), (-0.344, 0.674), (-0.07, 0.681), (0.126, 0.757), (0.365, 0.891), (0.654, 0.765), (-0.583, 0.45), (-0.369, 0.383), (0.376, 0.674), (0.639, 0.574), (0.319, 0.417), (0.489, 0.357), (0.689, 0.193), (0.719, -0.133), (-0.656, 0.287), (-0.081, 0.257), (0.098, 0.235), (-0.002, 0.152), (-0.224, 0.183), (-0.591, 0.154), (-0.75, -0.281), (-0.578, -0.124), (-0.483, 0.041), (-0.337, -0.052), (-0.094, -0.017), (0.063, -0.146), (0.261, -0.124), (0.431, -0.161), (-0.633, -0.481), (-0.078, -0.465), (0.111, -0.656), (0.078, -0.735), (0.359, -0.469), (0.476, -0.513)],
        "rooms": [(-0.663, 0.554), (-0.639, 0.126), (-0.363, 0.457), (-0.689, -0.356), (-0.261, 0.08), (-0.33, -0.265), (0.141, -0.083), (0.341, 0.161), (0.589, 0.491), (0.657, -0.2), (-0.193, -0.641), (0.08, -0.452), (0.391, -0.65)],                 # 红色
        "planes": [(-0.778, 0.611), (-0.6, 0.622), (-0.581, 0.519), (-0.406, 0.656), (-0.294, 0.696), (-0.137, 0.606), (-0.135, 0.719), (-0.189, 0.393), (0.337, 0.881), (0.541, 0.872), (0.617, 0.667), (0.569, 0.572), (0.694, 0.541), (0.669, 0.448), (0.689, 0.32), (0.669, -0.009), (0.711, -0.165), (0.667, -0.233), (0.83, 0.006), (0.859, -0.124), (-0.333, 0.256), (-0.611, 0.174), (-0.739, 0.2), (-0.739, 0.096), (-0.774, -0.217), (-0.691, -0.398), (-0.528, -0.396), (-0.502, -0.298), (-0.352, -0.411), (-0.302, -0.346), (-0.228, -0.667), (-0.126, -0.578), (0.033, -0.615), (0.019, -0.72), (0.209, -0.617), (0.3, -0.648), (0.346, -0.537), (0.402, -0.517)]                             # 橘黄色
    },
    "米拉玛 (Miramar)": {
        "vehicles": [(-0.765, -0.756), (-0.102, -0.843), (0.12, -0.752), (-0.12, -0.644), (-0.406, -0.531), (-0.635, -0.463), (-0.772, -0.228), (-0.581, -0.167), (-0.331, -0.283), (-0.174, -0.344), (0.269, -0.574), (0.535, -0.496), (0.209, -0.394), (0.139, -0.324), (-0.487, -0.002), (-0.87, 0.202), (-0.615, 0.252), (-0.239, 0.115), (-0.113, -0.035), (0.235, -0.011), (0.522, -0.15), (-0.776, 0.461), (-0.717, 0.524), (-0.319, 0.496), (-0.033, 0.261), (0.081, 0.315), (0.389, 0.294), (0.585, 0.376), (0.75, 0.174), (-0.38, 0.654), (-0.244, 0.854), (-0.08, 0.861), (-0.026, 0.706), (0.137, 0.8), (0.354, 0.656), (0.437, 0.794), (0.624, 0.709), (0.702, 0.607)],
        "rooms":[(-0.559, 0.589), (-0.2, 0.733), (-0.659, 0.194), (-0.313, 0.387), (0.13, 0.648), (-0.678, -0.304), (-0.339, -0.224), (-0.065, 0.043), (0.261, 0.217), (0.546, 0.524), (-0.657, -0.778), (-0.2, -0.63), (0.078, -0.276), (0.519, -0.041), (0.281, -0.537)],
        "planes": [(0.556, 0.867), (0.22, 0.839), (0.022, 0.87), (-0.12, 0.661), (-0.191, 0.857), (-0.587, 0.617), (-0.704, 0.487), (-0.869, 0.302), (-0.631, 0.189), (-0.711, -0.039), (-0.576, -0.133), (-0.737, -0.363), (-0.77, -0.517), (-0.461, -0.45), (-0.307, -0.581), (-0.62, -0.644), (-0.748, -0.826), (-0.537, -0.894), (0.022, -0.737), (0.172, -0.756), (0.27, -0.665), (0.378, -0.52), (0.572, -0.404), (0.806, -0.17)]
    },
    "泰戈 (Taego)": {
        "vehicles":[(-0.319, 0.793), (-0.6, 0.617), (-0.689, 0.383), (-0.511, 0.261), (-0.419, 0.419), (-0.367, 0.4), (-0.302, 0.498), (-0.057, 0.756), (-0.411, 0.046), (-0.133, 0.296), (0.081, 0.428), (0.144, 0.394), (0.27, 0.644), (0.537, 0.633), (0.604, 0.539), (0.717, 0.596), (0.77, 0.261), (0.783, 0.226), (0.754, 0.161), (0.144, 0.109), (0.293, 0.041), (0.435, -0.043), (0.587, -0.111), (0.602, -0.465), (0.478, -0.385), (0.435, -0.45), (0.27, -0.291), (0.033, -0.189), (-0.148, -0.219), (-0.181, -0.267), (-0.394, -0.169), (-0.626, 0.043), (-0.837, -0.117), (-0.637, -0.157), (-0.28, -0.343), (-0.481, -0.417), (-0.554, -0.435), (-0.504, -0.639), (-0.202, -0.563), (-0.019, -0.685), (0.083, -0.617), (0.169, -0.483), (0.352, -0.678), (0.448, -0.844)],
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

# --- 自定义平滑圆角按钮 ---
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

    def _on_press(self, event):
        pass

    def _on_release(self, event):
        if self.command:
            self.command()

# --- 主程序逻辑 ---
class PUBGMapAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("PUBG 地图助手")
        self.root.geometry("420x280")  # 稍微加高了窗口以容纳新增的排版
        self.root.attributes("-topmost", True)
        
        self.bg_color = "#F5F7FA"
        self.root.configure(bg=self.bg_color)
        
        self.cmd_queue = queue.Queue()
        self.is_overlay_active = False
        self.current_map = "艾伦格 (Erangel)"
        self.map_buttons = {}
        
        self.screen_w = tk.StringVar(value="1920")
        self.screen_h = tk.StringVar(value="1080")

        # 【新增】点位大小配置
        self.size_configs = {
            "小": {"radius": 3, "width": 1},
            "中": {"radius": 3, "width": 2},
            "大": {"radius": 5, "width": 4}
        }
        self.current_size = "小"
        self.size_buttons = {}

        # 记录鼠标按键的实时状态
        self.mouse_states = {
            mouse.Button.left: False,
            mouse.Button.middle: False,
            mouse.Button.right: False
        }

        self.init_ui()
        self.init_overlay()

        # 启动鼠标监听
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.mouse_listener.start()

        self.process_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_ui(self):
        # 1. 分辨率设置区
        frame_res = tk.Frame(self.root, bg=self.bg_color)
        frame_res.pack(pady=(15, 5))
        tk.Label(frame_res, text="屏幕分辨率:", bg=self.bg_color, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
        tk.Entry(frame_res, textvariable=self.screen_w, width=6, relief="flat", highlightbackground="#ccc", highlightthickness=1).pack(side=tk.LEFT, padx=5)
        tk.Label(frame_res, text="x", bg=self.bg_color).pack(side=tk.LEFT)
        tk.Entry(frame_res, textvariable=self.screen_h, width=6, relief="flat", highlightbackground="#ccc", highlightthickness=1).pack(side=tk.LEFT, padx=5)

        # 2. 【新增】点位大小设置区
        frame_size = tk.Frame(self.root, bg=self.bg_color)
        frame_size.pack(pady=5)
        tk.Label(frame_size, text="点位大小:", bg=self.bg_color, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        for size in ["小", "中", "大"]:
            # 使用较小的 RoundButton 作为尺寸选择按键
            btn = RoundButton(frame_size, text=size, width=46, height=28, radius=12,
                              command=lambda s=size: self.select_size(s))
            btn.pack(side=tk.LEFT, padx=4)
            self.size_buttons[size] = btn
        self.update_size_button_styles()

        # 3. 状态提示区
        self.status_label = tk.Label(self.root, text="状态: 关闭 (同时按 左+中键 显示)", fg="#E53935", bg=self.bg_color, font=("Microsoft YaHei", 11, "bold"))
        self.status_label.pack(pady=(10, 5))
        tk.Label(self.root, text="仅按右键: 标记游戏地图并自动隐藏", fg="#7F8C8D", bg=self.bg_color, font=("Microsoft YaHei", 9)).pack(pady=0)

        # 4. 地图选择按钮区
        frame_btns = tk.Frame(self.root, bg=self.bg_color)
        frame_btns.pack(pady=15)
        
        maps = list(MAP_DATA.keys())
        for i, map_name in enumerate(maps[:6]):
            btn = RoundButton(frame_btns, text=map_name, width=110, height=36, radius=16,
                              command=lambda m=map_name: self.select_map(m))
            btn.grid(row=i // 3, column=i % 3, padx=6, pady=6)
            self.map_buttons[map_name] = btn
            
        self.update_button_styles()

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
        if self.is_overlay_active:
            self.draw_points()

    def update_button_styles(self):
        for name, btn in self.map_buttons.items():
            btn.set_active(name == self.current_map)

    # 【新增】尺寸选择控制逻辑
    def select_size(self, size_name):
        self.current_size = size_name
        self.update_size_button_styles()
        if self.is_overlay_active:
            self.draw_points()

    def update_size_button_styles(self):
        for name, btn in self.size_buttons.items():
            btn.set_active(name == self.current_size)

    def on_mouse_click(self, x, y, button, pressed):
        if button in self.mouse_states:
            self.mouse_states[button] = pressed

        if self.mouse_states[mouse.Button.left] and self.mouse_states[mouse.Button.middle] and pressed:
            if button in (mouse.Button.left, mouse.Button.middle):
                self.cmd_queue.put("toggle")
                return 

        if button == mouse.Button.right and pressed:
            if not self.mouse_states[mouse.Button.left] and not self.mouse_states[mouse.Button.middle]:
                if self.is_overlay_active:
                    self.cmd_queue.put("hide")

    def process_queue(self):
        try:
            while True:
                cmd = self.cmd_queue.get_nowait()
                if cmd == "toggle":
                    self.toggle_overlay()
                elif cmd == "hide":
                    self.hide_overlay()
        except queue.Empty:
            pass
        self.root.after(50, self.process_queue)

    def toggle_overlay(self):
        if self.is_overlay_active:
            self.hide_overlay()
        else:
            self.show_overlay()

    def show_overlay(self):
        self.is_overlay_active = True
        self.status_label.config(text="状态: 开启 (右键 关闭)", fg="#43A047")
        self.draw_points()
        self.overlay.deiconify()

    def hide_overlay(self):
        self.is_overlay_active = False
        self.status_label.config(text="状态: 关闭 (同时按 左+中键 显示)", fg="#E53935")
        self.overlay.withdraw()

    def draw_points(self):
        self.canvas.delete("all")
        
        try:
            w = int(self.screen_w.get())
            h = int(self.screen_h.get())
        except ValueError:
            w, h = 1920, 1080

        data = MAP_DATA.get(self.current_map, {})
        narrow_edge = min(w, h)
        cx, cy = w / 2, h / 2

        font_style = ("Microsoft YaHei", 20, "bold")
        legend_start_y = 100 

        # 【核心修改】读取当前选择的点位大小配置
        current_radius = self.size_configs[self.current_size]["radius"]
        current_width = self.size_configs[self.current_size]["width"]

        for key, config in POINT_CONFIG.items():
            points = data.get(key, [])
            
            if points:
                self.canvas.create_text(30, legend_start_y, text=config["name"], 
                                        fill=config["color"], font=font_style, anchor="nw")
                legend_start_y += 40 
                
                color_hex = config["color"]
                for nx, ny in points:
                    px = cx + (nx * narrow_edge / 2)
                    py = cy - (ny * narrow_edge / 2)
                    # 替换为你调整好的粗细和半径
                    self.canvas.create_oval(px - current_radius, py - current_radius, 
                                            px + current_radius, py + current_radius,
                                            outline=color_hex, width=current_width)

    def on_closing(self):
        self.mouse_listener.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PUBGMapAssistant(root)
    root.mainloop()