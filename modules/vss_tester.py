import tkinter as tk
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from region_manager import RegionManager
from minimap_radar import MinimapRadarModule
from vss_assistant import VssAssistant

class VSSTester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VSS 实战联动测试台")
        self.root.geometry("320x250")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 1. 初始化区域管理器
        self.rm = RegionManager(self.root, config_file="config.json")

        # 2. 获取屏幕分辨率（通过 root）
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()

        # 3. 创建小地图雷达（传入 region_manager）
        self.minimap = MinimapRadarModule(self.root, self.rm, config_file="config.json")

        # 4. 创建 VSS 助手（传入 region_manager 和 minimap）
        self.vss_assist = VssAssistant(self.root, self.rm, self.minimap, fps=30, config_file="config.json")

        self.is_running = False
        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="VSS 真机实测终端", fg="white", bg="#2C3E50",
                 font=("Microsoft YaHei", 12, "bold")).pack(pady=10)

        # 显示小地图和准星区域是否已校准
        minimap_rect = self.rm.get_real_region("minimap_region")
        crosshair_rect = self.rm.get_real_region("crosshair_region")

        if minimap_rect:
            minimap_status = f"小地图: {minimap_rect['width']}x{minimap_rect['height']}"
            minimap_color = "#2ECC71"
        else:
            minimap_status = "小地图未校准"
            minimap_color = "#E74C3C"
        tk.Label(self.root, text=minimap_status, fg=minimap_color, bg="#2C3E50", font=("Arial", 9)).pack(pady=2)

        if crosshair_rect:
            crosshair_status = f"准星区域: {crosshair_rect['width']}x{crosshair_rect['height']}"
            crosshair_color = "#2ECC71"
        else:
            crosshair_status = "准星区域未校准 (将使用默认)"
            crosshair_color = "#F1C40F"
        tk.Label(self.root, text=crosshair_status, fg=crosshair_color, bg="#2C3E50", font=("Arial", 9)).pack(pady=2)

        self.btn_toggle = tk.Button(self.root, text="▶ 启动 VSS 助手", command=self.toggle,
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10))
        self.btn_toggle.pack(pady=10, fill="x", padx=40)

        tk.Label(self.root, text="(支持 vss_crosshair.png 与 vss_dark.png 模板)", fg="#7F8C8D", bg="#2C3E50", font=("Arial", 8)).pack(pady=5)

    def toggle(self):
        self.is_running = not self.is_running

        # 同时启停小地图雷达和 VSS 助手
        self.minimap.set_enabled(self.is_running)
        self.vss_assist.enable_module(self.is_running)

        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止系统", bg="#E74C3C")
        else:
            self.btn_toggle.config(text="▶ 启动 VSS 助手", bg="#2ECC71")

    def on_closing(self):
        self.minimap.set_enabled(False)
        self.vss_assist.enable_module(False)
        self.root.destroy()

if __name__ == "__main__":
    app = VSSTester()
    app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.root.mainloop()