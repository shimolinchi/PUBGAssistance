import tkinter as tk
import sys
import os
import threading
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from region_manager import RegionManager
from minimap_radar import MinimapRadarModule
from elevation_radar import ElevationRadarModule
from throwables_assistant import ThrowablesAssistant
from pynput import keyboard

class ThrowablesTester:
    def __init__(self, root):
        self.root = root
        self.root.title("雷火闪助手 测试台 (RegionManager版)")
        self.root.geometry("380x400")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 1. 初始化区域管理器
        self.rm = RegionManager(self.root, config_file="config.json")

        # 2. 获取屏幕分辨率
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()

        # 3. 创建小地图雷达和仰角雷达（传入 region_manager）
        self.minimap = MinimapRadarModule(self.root, self.rm, config_file="config.json")
        self.elevation = ElevationRadarModule(self.root, self.rm, fps=30, config_file="config.json")

        # 4. 创建投掷物助手（传入 region_manager）
        self.throwables = ThrowablesAssistant(self.root, self.rm, self.minimap, self.elevation, fps=30, config_file="config.json")

        self.is_running = False
        self.linkage_thread = None

        # 键盘监听器，用于测试 V 键以及 Q/E 切换标点
        self.kb_listener = keyboard.Listener(on_press=self.on_key_press)
        self.kb_listener.start()

        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="投掷物瞬爆与火控 终端", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        # 显示小地图和仰角区域是否校准
        minimap_rect = self.rm.get_real_region("minimap_region")
        if minimap_rect:
            minimap_status = f"小地图: {minimap_rect['width']}x{minimap_rect['height']}"
            minimap_color = "#2ECC71"
        else:
            minimap_status = "⚠️ 小地图未校准"
            minimap_color = "#E74C3C"
        tk.Label(self.root, text=minimap_status, fg=minimap_color, bg="#2C3E50", font=("Arial", 9)).pack(pady=2)

        elev_rect = self.rm.get_real_region("elevation_region")
        if elev_rect:
            elev_status = f"仰角区域: {elev_rect['width']}x{elev_rect['height']}"
            elev_color = "#2ECC71"
        else:
            elev_status = "⚠️ 仰角区域未校准"
            elev_color = "#E74C3C"
        tk.Label(self.root, text=elev_status, fg=elev_color, bg="#2C3E50", font=("Arial", 9)).pack(pady=2)

        # 启停控制
        self.btn_toggle = tk.Button(self.root, text="▶ 开启投掷物助手 (全局测试)", command=self.toggle_system,
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 11, "bold"))
        self.btn_toggle.pack(fill="x", padx=30, pady=20)

        # 提示信息
        info_text = (
            "【测试指南】\n"
            "1. 请先在游戏中校准好小地图和仰角区域。\n"
            "2. 开启助手后，按 [V] 键自动瞬爆拉环并计时。\n"
            "3. 按 [Q]/[E] 键切换当前使用的标点颜色。\n"
            "4. 系统会模拟按 R 拉环，并在对应时间后抛出。\n"
            "5. 注意：请确保游戏为无边框窗口模式。"
        )
        tk.Label(self.root, text=info_text, fg="#BDC3C7", bg="#2C3E50", justify="left").pack(pady=10)

    def _sensor_linkage_loop(self):
        """传感器状态联动循环（确保测高模块只扫描有效颜色）"""
        while self.is_running:
            mini_dists = self.minimap.get_measured_distance()
            valid_colors = {color: (dist > 0) for color, dist in mini_dists.items()}
            self.elevation.set_valid_colors(valid_colors)
            time.sleep(0.1)

    def toggle_system(self):
        self.is_running = not self.is_running

        self.minimap.set_enabled(self.is_running)
        self.elevation.set_enabled(self.is_running)
        self.throwables.enable_module(self.is_running)

        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止投掷物助手", bg="#E74C3C")
            self.linkage_thread = threading.Thread(target=self._sensor_linkage_loop, daemon=True)
            self.linkage_thread.start()
            print("[测试台] 系统已启动，请在游戏中打点测试！")
        else:
            self.btn_toggle.config(text="▶ 开启投掷物助手 (全局测试)", bg="#2ECC71")

    def on_key_press(self, key):
        if not self.is_running:
            return
        try:
            # 处理 Q/E 键切换标点颜色（传递给助手）
            self.throwables.on_key_press(key)

            # 处理 V 键瞬爆
            if hasattr(key, 'char') and key.char:
                if key.char.lower() == 'v':
                    self.throwables.toggle_auto_throw()
        except Exception:
            pass

    def on_closing(self):
        self.is_running = False
        if self.kb_listener:
            self.kb_listener.stop()
        self.minimap.set_enabled(False)
        self.elevation.set_enabled(False)
        self.throwables.enable_module(False)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ThrowablesTester(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()