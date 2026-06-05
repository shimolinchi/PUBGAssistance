import tkinter as tk
import sys
import os
import cv2

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from region_manager import RegionManager
from minimap_radar import MinimapRadarModule
from crossbow_assistant import CrossbowAssistant

class CrossbowDebugTester:
    def __init__(self, root):
        self.root = root
        self.root.title("十字弩 实战追踪测试台")
        self.root.geometry("320x250")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 1. 初始化区域管理器（加载 config.json）
        self.rm = RegionManager(self.root, config_file="config.json")

        # 2. 获取屏幕分辨率（通过 RegionManager 已有屏幕缩放比，但直接用 root）
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()

        # 3. 实例化小地图雷达，传入 region_manager
        self.minimap = MinimapRadarModule(self.root, self.rm, config_file="config.json")

        # 4. 实例化十字弩助手，传入 region_manager 和 minimap
        self.crossbow_assist = CrossbowAssistant(self.root, self.rm, self.minimap, fps=30, config_file="config.json")

        self.is_running = False
        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="弩/VSS 视觉追踪实测", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=10)
        tk.Label(self.root, text="💡 启动后将自动弹出黑白调试窗口", fg="#F1C40F", bg="#2C3E50", font=("Microsoft YaHei", 9)).pack(pady=2)

        # 显示小地图区域是否已校准
        minimap_rect = self.rm.get_real_region("minimap_region")
        if minimap_rect:
            status_text = f"小地图已校准: {minimap_rect['width']}x{minimap_rect['height']}"
            status_color = "#2ECC71"
        else:
            status_text = "未校准小地图，请先运行 RegionManager 校准"
            status_color = "#E74C3C"
        tk.Label(self.root, text=status_text, fg=status_color, bg="#2C3E50", font=("Arial", 9)).pack(pady=5)

        self.btn_toggle = tk.Button(self.root, text="▶ 启动 十字弩助手", command=self.toggle,
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_toggle.pack(pady=15, fill="x", padx=40)

    def toggle(self):
        self.is_running = not self.is_running

        # 启停小地图雷达（如果小地图未校准，雷达线程会静默失败）
        self.minimap.set_enabled(self.is_running)
        self.crossbow_assist.enable_module(self.is_running)

        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止系统并关闭调试窗", bg="#E74C3C")
        else:
            self.btn_toggle.config(text="▶ 启动 十字弩助手", bg="#2ECC71")
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

    def on_closing(self):
        self.minimap.set_enabled(False)
        self.crossbow_assist.enable_module(False)
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = CrossbowDebugTester(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()