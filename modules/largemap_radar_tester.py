import tkinter as tk
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from region_manager import RegionManager
from largemap_radar import AutoMapDistanceAssistant
from pynput import mouse, keyboard

class AutoMapDistanceTester:
    def __init__(self, root):
        self.root = root
        self.root.title("自动测距独立测试台 (RegionManager版)")
        self.root.geometry("400x280")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 1. 初始化区域管理器
        self.rm = RegionManager(self.root, config_file="config.json")

        # 2. 创建大地图测距模块，传入 region_manager
        self.assistant = AutoMapDistanceAssistant(self.root, self.rm, config_file="config.json")

        # 3. 关键：开启显示层（允许触发测距和显示HUD）
        self.assistant.set_display(True)

        self.init_ui()
        self.start_listeners()

    def init_ui(self):
        tk.Label(self.root, text="半自动大地图测距测试台", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=10)

        # 显示 largemap_region 和 largemap_1km_px 状态
        rect = self.rm.get_real_region("largemap_region")
        scale = self.rm.get_real_scale("largemap_1km_px")
        if rect and scale:
            status = f"✅ 大地图区域: {rect['width']}x{rect['height']}  |  1km={scale:.1f}px"
            status_color = "#2ECC71"
        else:
            status = "⚠️ 未校准 largemap_region 或 largemap_1km_px，请先运行 RegionManager 校准"
            status_color = "#E74C3C"
        tk.Label(self.root, text=status, fg=status_color, bg="#2C3E50", font=("Arial", 9)).pack(pady=5)

        tk.Button(self.root, text="▶ 手动触发测距 (模拟快捷键)", command=self.assistant.toggle_mode,
                  bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10, "bold")).pack(fill="x", padx=40, pady=10)

        tk.Label(self.root, text="快捷键: Ctrl + Shift + M\n第1步: 左键点击玩家位置\n第2步: 后台自动扫描标点距离\n取消: 任意状态按右键",
                 fg="#BDC3C7", bg="#2C3E50", font=("Microsoft YaHei", 10)).pack(pady=10)

    def start_listeners(self):
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.mouse_listener.start()
        self.hotkey_listener = keyboard.GlobalHotKeys({
            '<ctrl>+<shift>+m': self.assistant.toggle_mode
        })
        self.hotkey_listener.start()

    def on_mouse_click(self, x, y, button, pressed):
        self.root.after(0, self.assistant.on_mouse_click, x, y, button, pressed)

    def on_closing(self):
        self.mouse_listener.stop()
        self.hotkey_listener.stop()
        self.assistant.cancel()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoMapDistanceTester(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()