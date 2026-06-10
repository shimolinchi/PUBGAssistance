import tkinter as tk
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from region_manager import RegionManager
from minimap_radar import MinimapRadarModule
from elevation_radar import ElevationRadarModule
from mortar_assistant import MortarAssistant

class RealMortarTester:
    def __init__(self, root):
        self.root = root
        self.root.title("真机集成测试台 (全链路)")
        self.root.geometry("350x400")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 1. 初始化区域管理器
        self.rm = RegionManager(self.root, config_file="config.json")

        # 2. 获取屏幕分辨率
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()
        print(f"[系统] 检测到屏幕分辨率: {self.sw}x{self.sh}")

        # 3. 创建小地图雷达和仰角雷达（传入 region_manager）
        self.minimap = MinimapRadarModule(self.root, self.rm, config_file="config.json")
        self.elevation = ElevationRadarModule(self.root, self.rm, fps=30, config_file="config.json")

        # 4. 创建迫击炮助手（传入 region_manager）
        self.mortar = MortarAssistant(self.root, self.rm, self.minimap, self.elevation, fps=30, config_file="config.json")

        # 状态控制
        self.is_running = False
        self.show_sensor_debug = True

        self.init_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_ui(self):
        tk.Label(self.root, text="全链路火控系统测试台", fg="white", bg="#2C3E50",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        # 显示标定状态
        minimap_rect = self.rm.get_real_region("minimap_region")
        if minimap_rect:
            minimap_status = f"小地图: {minimap_rect['width']}x{minimap_rect['height']}"
            minimap_color = "#2ECC71"
        else:
            minimap_status = "⚠️ 小地图未标定"
            minimap_color = "#E74C3C"
        tk.Label(self.root, text=minimap_status, fg=minimap_color, bg="#2C3E50", font=("Arial", 9)).pack(pady=2)

        elev_rect = self.rm.get_real_region("elevation_region")
        if elev_rect:
            elev_status = f"仰角区域: {elev_rect['width']}x{elev_rect['height']}"
            elev_color = "#2ECC71"
        else:
            elev_status = "⚠️ 仰角区域未标定"
            elev_color = "#E74C3C"
        tk.Label(self.root, text=elev_status, fg=elev_color, bg="#2C3E50", font=("Arial", 9)).pack(pady=2)

        # 控制按钮区
        self.btn_debug = tk.Button(self.root, text="隐藏传感器识别图层", command=self.toggle_sensor_debug,
                                   bg="#E67E22", fg="white", font=("Microsoft YaHei", 10))
        self.btn_debug.pack(fill="x", padx=30, pady=5)

        self.btn_view = tk.Button(self.root, text="当前视角: 第一人称(FPP)", command=self.toggle_view,
                                  bg="#8E44AD", fg="white", font=("Microsoft YaHei", 10))
        self.btn_view.pack(fill="x", padx=30, pady=5)

        self.btn_toggle = tk.Button(self.root, text="▶ 启动全系统侦测与HUD", command=self.toggle_system,
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 12, "bold"))
        self.btn_toggle.pack(fill="x", padx=20, pady=20)

    def toggle_sensor_debug(self):
        self.show_sensor_debug = not self.show_sensor_debug
        self.minimap.set_display(self.show_sensor_debug)
        self.elevation.set_display(self.show_sensor_debug)
        if self.show_sensor_debug:
            self.btn_debug.config(text="隐藏传感器识别图层", bg="#E67E22")
        else:
            self.btn_debug.config(text="显示传感器识别图层", bg="#7F8C8D")

    def toggle_view(self):
        self.mortar.is_fpp = not self.mortar.is_fpp
        view_text = "第一人称(FPP)" if self.mortar.is_fpp else "第三人称(TPP)"
        self.btn_view.config(text=f"当前视角: {view_text}")

    def toggle_system(self):
        # 检查小地图是否已校准
        if not self.rm.get_real_region("minimap_region"):
            print("请先标定小地图！")
            return

        self.is_running = not self.is_running

        # 启停两个传感器
        self.minimap.set_enabled(self.is_running)
        self.elevation.set_enabled(self.is_running)
        # 启停迫击炮 HUD
        self.mortar.enable_module(self.is_running)

        # 同步传感器显示状态
        self.minimap.set_display(self.show_sensor_debug if self.is_running else False)
        self.elevation.set_display(self.show_sensor_debug if self.is_running else False)

        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止系统", bg="#E74C3C")
        else:
            self.btn_toggle.config(text="▶ 启动全系统侦测与HUD", bg="#2ECC71")

    def on_closing(self):
        self.minimap.set_enabled(False)
        self.elevation.set_enabled(False)
        self.mortar.enable_module(False)
        self.root.destroy()

if __name__ == "__main__":
    # >>> 新增：强制 Windows 启用高 DPI 感知，获取真实物理分辨率 >>>
    import ctypes
    import platform
    
    if platform.system() == "Windows":
        try:
            # 尝试调用 PerMonitorV2 DPI 感知 (Windows 10/11)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                # 兼容旧版本调用
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    # <<< 新增结束 <<<

    root = tk.Tk()
    app = RealMortarTester(root)
    root.mainloop()