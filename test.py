import tkinter as tk
import ctypes
import mss  # 仅用于获取真实屏幕分辨率

from minimap_radar import MinimapRadarModule
from compass_radar import CompassRadarModule
from elevation_radar import ElevationRadarModule

# ==================== 屏幕比例配置区 (0.0 ~ 1.0) ====================
# 使用比例配置，完美适配任何分辨率 (1080p, 2K, 4K 或窗口化)

# 1. 顶部罗盘捕捉区域 (极度扁平的长条)
COMPASS_START_Y = 0.00   # 顶端开始
COMPASS_END_Y   = 0.10   # 占屏幕高度前 10%
COMPASS_START_X = 0.00   # 最左侧
COMPASS_END_X   = 1.00   # 最右侧

# 2. 中心高低角捕捉区域 (极度细长的竖条，避开顶部罗盘)
ELEV_START_Y    = 0.15   # 从 15% 开始 (完美避开顶部 10% 的罗盘)
ELEV_END_Y      = 0.66   # 到 66% 结束 (大约屏幕三分之二)
ELEV_START_X    = 0.47   # 中心偏左一点 (宽度占屏幕宽度的 6%)
ELEV_END_X      = 0.53   # 中心偏右一点

# ====================================================================

class MasterTestVisualizer:
    def __init__(self, root):
        self.root = root
        self.root.title("火控传感器综合测试平台 (自适应版)")
        self.root.geometry("380x250")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")
        
        # 自动获取当前主屏幕的真实分辨率
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            self.screen_width = monitor["width"]
            self.screen_height = monitor["height"]
        
        print(f"[系统] 检测到屏幕分辨率: {self.screen_width}x{self.screen_height}")

        # 1. 实例化三大模块
        self.minimap = MinimapRadarModule(self.root)
        self.compass = CompassRadarModule(screen_width=self.screen_width)
        self.elevation = ElevationRadarModule(screen_width=self.screen_width, screen_height=self.screen_height)
        
        # 【动态计算并强行覆盖模块的监控区域】
        self.compass.monitor = self._calc_rect(COMPASS_START_X, COMPASS_END_X, COMPASS_START_Y, COMPASS_END_Y)
        self.elevation.monitor = self._calc_rect(ELEV_START_X, ELEV_END_X, ELEV_START_Y, ELEV_END_Y)

        self.minimap.set_display(False)
        self.is_running = False
        
        self.init_ui()
        self.init_master_overlay()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _calc_rect(self, start_x_ratio, end_x_ratio, start_y_ratio, end_y_ratio):
        """将 0~1 的比例换算为真实的像素监控区域"""
        left = int(start_x_ratio * self.screen_width)
        top = int(start_y_ratio * self.screen_height)
        width = int((end_x_ratio - start_x_ratio) * self.screen_width)
        height = int((end_y_ratio - start_y_ratio) * self.screen_height)
        return {"top": top, "left": left, "width": width, "height": height}

    def init_ui(self):
        tk.Label(self.root, text="传感器融合监控 (相对坐标版)", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=10)
        
        tk.Button(self.root, text="📏 手动标定小地图区域", command=self.minimap.trigger_calibration, 
                  bg="#3498DB", fg="white", font=("Microsoft YaHei", 10)).pack(fill="x", padx=20, pady=5)
                  
        self.btn_toggle = tk.Button(self.root, text="▶ 启动全系统监控", command=self.toggle_system, 
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 12, "bold"))
        self.btn_toggle.pack(fill="x", padx=20, pady=15)

    def init_master_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)
        
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 防截图黑科技
        self.overlay.update_idletasks()
        try:
            hwnd = int(self.overlay.frame(), 16)
            result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
            if result == 0:
                hwnd_alt = self.overlay.winfo_id()
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd_alt, 17)
        except Exception as e:
            print("隐藏画布失败:", e)

    def toggle_system(self):
        self.is_running = not self.is_running
        
        self.minimap.set_enabled(self.is_running)
        self.compass.set_enabled(self.is_running)
        self.elevation.set_enabled(self.is_running)
        
        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止系统", bg="#E74C3C")
            self.draw_loop()
        else:
            self.btn_toggle.config(text="▶ 启动全系统监控", bg="#2ECC71")
            self.canvas.delete("all")

    def draw_loop(self):
        if not self.is_running: return
        self.canvas.delete("all")
        
        # 1. 绘制虚线区域框
        self.draw_zone(self.compass.monitor, "罗盘方位")
        self.draw_zone(self.elevation.monitor, "垂直高低")
        if self.minimap.monitor:
            self.draw_zone(self.minimap.monitor, "雷达测距")

        # 2. 绘制罗盘数据 (橙色)
        h_ratio = self.compass.get_horizontal_ratio()
        if h_ratio is not None:
            abs_x = h_ratio * self.screen_width
            abs_y = self.compass.monitor["top"] + self.compass.monitor["height"] / 2
            self.canvas.create_polygon(abs_x, abs_y, abs_x-10, abs_y-20, abs_x+10, abs_y-20, fill="#FF8C00", outline="black")
            self.canvas.create_text(abs_x, abs_y+15, text=f"X: {h_ratio:.3f}", fill="#FF8C00", font=("Arial", 12, "bold"))

        # 3. 绘制高低角数据 (天蓝)
        v_ratio = self.elevation.get_vertical_ratio()
        if v_ratio is not None:
            abs_x = self.elevation.monitor["left"] + self.elevation.monitor["width"] / 2
            abs_y = v_ratio * self.screen_height
            self.canvas.create_polygon(abs_x, abs_y, abs_x-20, abs_y-10, abs_x-20, abs_y+10, fill="#00BFFF", outline="black")
            self.canvas.create_text(abs_x+35, abs_y, text=f"Y: {v_ratio:.3f}", fill="#00BFFF", font=("Arial", 12, "bold"))

        # 4. 绘制小地图数据 (继承目标自身颜色)
        targets = self.minimap.get_latest_targets()
        for pt in targets:
            ax, ay = pt['x'], pt['y']
            color = pt['color']
            self.canvas.create_rectangle(ax-10, ay-20, ax+10, ay, outline=color, width=2)
            self.canvas.create_text(ax, ay+15, text=f"{pt['dist']:.1f}m", fill=color, font=("Arial", 12, "bold"))

        self.root.after(30, self.draw_loop)

    def draw_zone(self, monitor, label):
        if not monitor: return
        x1, y1 = monitor["left"], monitor["top"]
        x2, y2 = x1 + monitor["width"], y1 + monitor["height"]
        self.canvas.create_rectangle(x1-1, y1-1, x2+1, y2+1, outline="black", width=2)
        self.canvas.create_rectangle(x1, y1, x2, y2, outline="white", width=2, dash=(5, 5))
        self.canvas.create_text(x1+5, y1+5, text=label, fill="black", anchor="nw", font=("Microsoft YaHei", 10, "bold"))
        self.canvas.create_text(x1+4, y1+4, text=label, fill="white", anchor="nw", font=("Microsoft YaHei", 10, "bold"))

    def on_closing(self):
        self.is_running = False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MasterTestVisualizer(root)
    root.mainloop()