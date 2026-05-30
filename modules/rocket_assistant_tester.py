import tkinter as tk
import mss

# 导入真正的物理传感器与火箭筒解算模块
from modules.minimap_radar import MinimapRadarModule
from modules.rocket_assistant import RocketAssistant

class RealRocketTester:
    def __init__(self, root):
        self.root = root
        self.root.title("火箭筒真机集成测试台")
        self.root.geometry("350x300")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 动态获取屏幕分辨率
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            self.sw = monitor["width"]
            self.sh = monitor["height"]
            
        print(f"[系统] 检测到屏幕分辨率: {self.sw}x{self.sh}")

        # ================= 实例化真实的视觉模块 =================
        # 1. 实例化真实的小地图视觉雷达模块
        self.minimap = MinimapRadarModule(self.root)
        
        # 2. 实例化火箭筒 HUD 模块，并将真实的小地图实例传进去
        self.rocket = RocketAssistant(self.root, self.sw, self.sh, self.minimap, fps=30)

        # 状态控制
        self.is_running = False
        self.show_sensor_debug = True # 是否在屏幕上显示小地图的带距离的方框

        self.init_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_ui(self):
        tk.Label(self.root, text="全链路火箭筒系统测试台", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 14, "bold")).pack(pady=10)
        
        # 状态检查
        if not self.minimap.monitor:
            tk.Label(self.root, text="⚠️ 小地图未标定，请先标定！", fg="#E74C3C", bg="#2C3E50", font=("Arial", 10, "bold")).pack(pady=5)
        
        # 控制按钮区
        tk.Button(self.root, text="📏 手动标定小地图", command=self.minimap.trigger_calibration, 
                  bg="#3498DB", fg="white", font=("Microsoft YaHei", 10)).pack(fill="x", padx=30, pady=5)
                  
        self.btn_debug = tk.Button(self.root, text="隐藏小地图识别图层", command=self.toggle_sensor_debug, 
                                   bg="#E67E22", fg="white", font=("Microsoft YaHei", 10))
        self.btn_debug.pack(fill="x", padx=30, pady=5)

        self.btn_toggle = tk.Button(self.root, text="▶ 启动侦测与动态标尺", command=self.toggle_system, 
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 16, "bold"))
        self.btn_toggle.pack(fill="x", padx=20, pady=20)

    def toggle_sensor_debug(self):
        """控制底层传感器（小地图方框）的显示与隐藏"""
        self.show_sensor_debug = not self.show_sensor_debug
        
        # 下发显示指令给底层传感器
        self.minimap.set_display(self.show_sensor_debug)
        
        if self.show_sensor_debug:
            self.btn_debug.config(text="隐藏小地图识别图层", bg="#E67E22")
        else:
            self.btn_debug.config(text="显示小地图识别图层", bg="#7F8C8D")

    def toggle_system(self):
        """主系统的启停控制"""
        if not self.minimap.monitor:
            print("请先标定小地图！")
            return

        self.is_running = not self.is_running
        
        # 启停核心标尺模块
        self.rocket.enable_module(self.is_running)
        
        # 同步应用传感器的显示状态 (停止时自动关掉小地图画图)
        self.minimap.set_display(self.show_sensor_debug if self.is_running else False)
        
        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止侦测与动态标尺", bg="#E74C3C")
        else:
            self.btn_toggle.config(text="▶ 启动侦测与动态标尺", bg="#2ECC71")

    def on_closing(self):
        """清理线程资源"""
        self.rocket.enable_module(False)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = RealRocketTester(root)
    root.mainloop()