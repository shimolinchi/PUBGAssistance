import tkinter as tk
import mss
from elevation_radar import ElevationRadarModule

class ElevationTester:
    def __init__(self, root):
        self.root = root
        self.root.title("高低角模块独立测试")
        self.root.geometry("320x250")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 动态获取分辨率
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sw, sh = monitor["width"], monitor["height"]

        # 实例化雷达模块 (FPS默认30)
        self.radar = ElevationRadarModule(self.root, screen_width=sw, screen_height=sh, fps=30)
        
        # 强制设置一个适合测试的居中截取区域
        self.radar.monitor = {
            "top": int(0.15 * sh), 
            "left": int(0.47 * sw), 
            "width": int(0.06 * sw), 
            "height": int(0.51 * sh)
        }
        
        self.is_running = False
        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="垂直高低角 雷达测试台", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=10)
        
        self.lbl_status = tk.Label(self.root, text="状态: 等待启动", fg="#F1C40F", bg="#2C3E50", font=("Microsoft YaHei", 10))
        self.lbl_status.pack(pady=5)

        self.btn_toggle = tk.Button(self.root, text="▶ 启动视觉雷达", command=self.toggle_radar, 
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 11, "bold"))
        self.btn_toggle.pack(fill="x", padx=30, pady=15)
        
        # 实时数据监控面板
        self.lbl_data = tk.Label(self.root, text="黄: None\n橙: None\n蓝: None\n绿: None", 
                                 fg="#00FF00", bg="#111111", font=("Consolas", 10), justify="left")
        self.lbl_data.pack(fill="x", padx=30, pady=5)
        
        self.update_data_loop()

    def toggle_radar(self):
        self.is_running = not self.is_running
        
        # 同步开启模块后台运算和屏幕渲染
        self.radar.set_enabled(self.is_running)
        self.radar.set_display(self.is_running)
        
        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止雷达", bg="#E74C3C")
            self.lbl_status.config(text="状态: 雷达运行中...", fg="#2ECC71")
        else:
            self.btn_toggle.config(text="▶ 启动视觉雷达", bg="#2ECC71")
            self.lbl_status.config(text="状态: 已停止", fg="#F1C40F") 

    def update_data_loop(self):
        """仅用于在测试面板上打印出字典数据"""
        if self.is_running:
            elevs = self.radar.get_measured_elevations()
            text = f"黄 (Yellow) : {elevs['Yellow']}\n" \
                   f"橙 (Orange) : {elevs['Orange']}\n" \
                   f"蓝 (Blue)   : {elevs['Blue']}\n" \
                   f"绿 (Green)  : {elevs['Green']}"
            self.lbl_data.config(text=text)
        
        self.root.after(100, self.update_data_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = ElevationTester(root)
    root.mainloop()