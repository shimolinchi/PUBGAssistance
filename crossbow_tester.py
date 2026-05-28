import tkinter as tk
import mss

# 导入真实的小地图模块 和 我们刚写好的 弩 助手
from minimap_radar import MinimapRadarModule
from crossbow_assistant import CrossbowAssistant

class CrossbowTester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("弩 实战联动测试台")
        self.root.geometry("300x200")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")
        
        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            sw, sh = monitor["width"], monitor["height"]
            
        # 1. 实例化真实的小地图测距雷达
        self.minimap = MinimapRadarModule(self.root)
        
        # 2. 实例化 弩 助手，并将真实的小地图对象喂给它！
        self.crossbow_assist = CrossbowAssistant(self.root, sw, sh, self.minimap, fps=30)
        
        self.is_running = False
        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="弩 真机实测终端", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=10)
        
        # 必须先校准小地图，VSS 助手才能拿到有效距离
        self.btn_calib = tk.Button(self.root, text="📏 第一步：校准小地图", command=self.minimap.trigger_calibration, bg="#3498DB", fg="white", font=("Microsoft YaHei", 10))
        self.btn_calib.pack(pady=5, fill="x", padx=40)

        self.btn_toggle = tk.Button(self.root, text="▶ 第二步：启动 弩 助手", command=self.toggle, bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10))
        self.btn_toggle.pack(pady=5, fill="x", padx=40)

    def toggle(self):
        self.is_running = not self.is_running
        
        # 同时启停两个模块
        self.minimap.set_enabled(self.is_running)
        self.crossbow_assist.enable_module(self.is_running)
        
        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止系统", bg="#E74C3C")
        else:
            self.btn_toggle.config(text="▶ 第二步：启动 弩 助手", bg="#2ECC71")

    def on_closing(self):
        self.minimap.set_enabled(False)
        self.crossbow_assist.enable_module(False)
        self.root.destroy()

if __name__ == "__main__":
    app = CrossbowTester()
    app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.root.mainloop()