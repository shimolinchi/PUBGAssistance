import tkinter as tk
import mss

from modules.minimap_radar import MinimapRadarModule
from modules.elevation_radar import ElevationRadarModule
from modules.mortar_assistant import MortarAssistant

# ================= 传感器区域配置 =================
ELEV_START_Y    = 0.11   # 从 11% 开始
ELEV_END_Y      = 0.66   # 到 66% 结束
ELEV_START_X    = 0.47   # 中心偏左
ELEV_END_X      = 0.53   # 中心偏右

class RealMortarTester:
    def __init__(self, root):
        self.root = root
        self.root.title("真机集成测试台 (全链路)")
        self.root.geometry("350x380")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 动态获取屏幕分辨率
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            self.sw = monitor["width"]
            self.sh = monitor["height"]
            
        print(f"[系统] 检测到屏幕分辨率: {self.sw}x{self.sh}")

        # ================= 实例化真实核心模块 =================
        self.minimap = MinimapRadarModule(self.root)
        self.elevation = ElevationRadarModule(self.root, screen_width=self.sw, screen_height=self.sh, fps=30)
        
        # 写入垂直高度模块的监控区域
        self.elevation.monitor = self._calc_rect(ELEV_START_X, ELEV_END_X, ELEV_START_Y, ELEV_END_Y)
        
        # 实例化火控 HUD 模块
        self.mortar = MortarAssistant(self.root, self.sw, self.sh, self.minimap, self.elevation, fps=30)

        # 状态控制
        self.is_running = False
        self.show_sensor_debug = True # 是否显示底层传感器的识别框

        self.init_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _calc_rect(self, start_x, end_x, start_y, end_y):
        left = int(start_x * self.sw)
        top = int(start_y * self.sh)
        width = int((end_x - start_x) * self.sw)
        height = int((end_y - start_y) * self.sh)
        return {"top": top, "left": left, "width": width, "height": height}

    def init_ui(self):
        tk.Label(self.root, text="全链路火控系统测试台", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 14, "bold")).pack(pady=10)
        
        # 小地图状态检查
        if not self.minimap.monitor:
            tk.Label(self.root, text="⚠️ 小地图未标定，请先标定！", fg="#E74C3C", bg="#2C3E50", font=("Arial", 10, "bold")).pack(pady=5)
        
        # 控制按钮区
        tk.Button(self.root, text="📏 手动标定小地图", command=self.minimap.trigger_calibration, 
                  bg="#3498DB", fg="white", font=("Microsoft YaHei", 10)).pack(fill="x", padx=30, pady=5)
                  
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
        
        # 动态将显示状态下发给底层传感器
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
        if not self.minimap.monitor:
            print("请先标定小地图！")
            return

        self.is_running = not self.is_running
        
        # 启停核心模块
        self.mortar.enable_module(self.is_running)
        
        # 同步应用传感器的显示状态
        self.minimap.set_display(self.show_sensor_debug if self.is_running else False)
        self.elevation.set_display(self.show_sensor_debug if self.is_running else False)
        
        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止系统", bg="#E74C3C")
        else:
            self.btn_toggle.config(text="▶ 启动全系统侦测与HUD", bg="#2ECC71")

    def on_closing(self):
        self.mortar.enable_module(False)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = RealMortarTester(root)
    root.mainloop()