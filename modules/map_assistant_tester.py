import tkinter as tk
from tkinter import ttk
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from region_manager import RegionManager
from map_assistant import MapPointAssistant, MAP_DATA, POINT_CONFIG
from pynput import mouse, keyboard


class MapPointTester:
    def __init__(self, root):
        self.root = root
        self.root.title("大地图点位助手 测试台 (RegionManager版)")
        self.root.geometry("400x550")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 1. 初始化区域管理器
        self.rm = RegionManager(self.root, config_file="config.json")

        # 2. 创建地图助手实例，传入 region_manager
        self.map_assistant = MapPointAssistant(self.root, self.rm, config_file="config.json")

        self.is_running = False

        # pynput 状态
        self.left_pressed = False
        self.middle_pressed = False
        self.alt_pressed = False

        # UI 变量
        self.map_var = tk.StringVar(value="艾伦格 (Erangel)")
        self.category_vars = {}

        self.init_ui()

        # 启动 pynput 监听
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.kb_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.mouse_listener.start()
        self.kb_listener.start()
        print("[测试台] pynput 键鼠监听已启动！等待指令...")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_ui(self):
        tk.Label(self.root, text="战术点位记录 终端", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        # 显示当前 largemap_region 状态
        rect = self.rm.get_real_region("largemap_region")
        if rect:
            status = f"大地图区域: {rect['width']}x{rect['height']}"
            status_color = "#2ECC71"
        else:
            status = "⚠️ 未校准 largemap_region，请先标定"
            status_color = "#E74C3C"
        tk.Label(self.root, text=status, fg=status_color, bg="#2C3E50", font=("Arial", 9)).pack(pady=2)

        tk.Button(self.root, text="📏 1. 校准大地图边界 (框选正方形)", command=self.map_assistant.trigger_calibration,
                  bg="#3498DB", fg="white", font=("Microsoft YaHei", 10)).pack(fill="x", padx=30, pady=10)

        panel = tk.LabelFrame(self.root, text=" 战术资源分布图层 ", bg="#34495E", fg="white", font=("Microsoft YaHei", 10))
        panel.pack(fill="x", padx=20, pady=5)

        map_frame = tk.Frame(panel, bg="#34495E")
        map_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(map_frame, text="当前地图:", bg="#34495E", fg="white").pack(side="left")
        map_selector = ttk.Combobox(map_frame, textvariable=self.map_var, values=list(MAP_DATA.keys()), state="readonly")
        map_selector.pack(side="right", expand=True, fill="x", padx=5)
        map_selector.bind("<<ComboboxSelected>>", self.on_display_changed)

        for key, config in POINT_CONFIG.items():
            var = tk.BooleanVar(value=False)
            self.category_vars[key] = var
            chk = tk.Checkbutton(panel, text=config["name"], variable=var, bg="#34495E", fg=config["color"],
                                 selectcolor="#2C3E50", activebackground="#34495E", command=self.on_display_changed)
            chk.pack(anchor="w", padx=20)

        self.btn_toggle = tk.Button(self.root, text="▶ 等待鼠标触发 (左键+中键)", state="normal",
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 11, "bold"))
        self.btn_toggle.pack(fill="x", padx=30, pady=15)

        tk.Label(self.root, text="操作说明:\n【左键+中键】绝对开启\n【右键】绝对关闭 (按住Alt例外)",
                 fg="#BDC3C7", bg="#2C3E50", justify="left", font=("Arial", 9)).pack()

    def on_display_changed(self, event=None):
        """更新地图助手参数并重绘"""
        active_cats = {k for k, v in self.category_vars.items() if v.get()}
        self.map_assistant.active_categories = active_cats
        self.map_assistant.current_map_name = self.map_var.get()
        if self.is_running:
            self.map_assistant._render_points()

    # ================= pynput 键盘监听 =================
    def on_key_press(self, key):
        if key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            self.alt_pressed = True

    def on_key_release(self, key):
        if key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            self.alt_pressed = False

    # ================= pynput 鼠标绝对触发 =================
    def on_mouse_click(self, x, y, button, pressed):
        # 记录左键和中键状态
        if button == mouse.Button.left:
            self.left_pressed = pressed
        elif button == mouse.Button.middle:
            self.middle_pressed = pressed

        # 绝对开启：左键和中键同时按下
        if self.left_pressed and self.middle_pressed:
            if not self.is_running:
                print("[触发] 左键+中键 -> 执行【开启】")
                self.is_running = True
                self.root.after(0, self.update_ui_state)

        # 绝对关闭：按下右键（且未按住 Alt）
        if button == mouse.Button.right and pressed:
            if self.is_running and not self.alt_pressed:
                print("[触发] 右键 (未按Alt) -> 执行【关闭】")
                self.is_running = False
                self.root.after(0, self.update_ui_state)

    def update_ui_state(self):
        # 如果未标定大地图区域，禁止开启
        if self.is_running and not self.rm.get_real_region("largemap_region"):
            print("⚠️ 忽略触发：请先标定大地图边界！")
            self.is_running = False
            return

        self.map_assistant.set_enabled(self.is_running)
        if self.is_running:
            self.on_display_changed()
            self.btn_toggle.config(text="⏹ 正在显示 (右键关闭)", bg="#E74C3C")
        else:
            self.btn_toggle.config(text="▶ 等待鼠标触发 (左键+中键)", bg="#2ECC71")

    def on_closing(self):
        print("正在关闭测试台...")
        if hasattr(self, 'mouse_listener'):
            self.mouse_listener.stop()
        if hasattr(self, 'kb_listener'):
            self.kb_listener.stop()
        self.map_assistant.set_enabled(False)
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MapPointTester(root)
    root.mainloop()