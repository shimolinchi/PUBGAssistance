import tkinter as tk
from elevation_radar import ElevationRadarModule

class ElevationTester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("垂直测高模块 - 独立测试台")
        self.root.geometry("350x450")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")
        
        # 获取当前屏幕分辨率
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()
        
        # 实例化我们刚清理干净的测高模块
        self.elevation = ElevationRadarModule(self.root, self.sw, self.sh)
        
        self.init_ui()
        
        # 启动 UI 刷新循环
        self.update_data_loop()

    def init_ui(self):
        tk.Label(self.root, text="🏔️ 垂直测高雷达测试", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 14, "bold")).pack(pady=15)
        
        # ================= 控制面板 =================
        self.frame_controls = tk.Frame(self.root, bg="#2C3E50")
        self.frame_controls.pack(fill="x", padx=20, pady=10)
        
        self.btn_enable = tk.Button(self.frame_controls, text="▶️ 启动检测引擎 (OFF)", command=self.toggle_enable, bg="#E74C3C", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_enable.pack(fill="x", pady=5)
        
        self.btn_display = tk.Button(self.frame_controls, text="👀 显示屏幕标尺 (OFF)", command=self.toggle_display, bg="#7F8C8D", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_display.pack(fill="x", pady=5)
        
        tk.Frame(self.root, height=2, bg="#34495E").pack(fill="x", pady=15)
        
        # ================= 数据展示面板 =================
        tk.Label(self.root, text="实时高度比率数据 (0.0 ~ 1.0)", fg="#BDC3C7", bg="#2C3E50", font=("Microsoft YaHei", 10)).pack()
        
        self.labels = {}
        # UI 颜色映射
        colors = {"Yellow": "#F1C40F", "Orange": "#E67E22", "Blue": "#3498DB", "Green": "#2ECC71"}
        
        for color_name, hex_code in colors.items():
            frame = tk.Frame(self.root, bg="#2C3E50")
            frame.pack(fill="x", padx=40, pady=5)
            
            # 颜色名称标签
            tk.Label(frame, text=f"{color_name}:", fg=hex_code, bg="#2C3E50", font=("Consolas", 12, "bold"), width=8, anchor="w").pack(side="left")
            
            # 数值显示标签
            self.labels[color_name] = tk.Label(frame, text="None", fg="white", bg="#2C3E50", font=("Consolas", 12))
            self.labels[color_name].pack(side="left", padx=10)

    def toggle_enable(self):
        """切换后台识别线程的状态"""
        is_active = not self.elevation.is_enabled
        self.elevation.set_enabled(is_active)
        
        if is_active:
            self.btn_enable.config(text="⏹️ 停止检测引擎 (ON)", bg="#2ECC71")
        else:
            self.btn_enable.config(text="▶️ 启动检测引擎 (OFF)", bg="#E74C3C")

    def toggle_display(self):
        """切换游戏屏幕上标尺横线的显示状态"""
        is_showing = not self.elevation.show_display
        self.elevation.set_display(is_showing)
        
        if is_showing:
            self.btn_display.config(text="👀 隐藏屏幕标尺 (ON)", bg="#3498DB")
        else:
            self.btn_display.config(text="👀 显示屏幕标尺 (OFF)", bg="#7F8C8D")

    def update_data_loop(self):
        """高频读取后台数据并刷新 UI"""
        if self.elevation.is_enabled:
            data = self.elevation.get_measured_elevations()
            
            for color_name, label in self.labels.items():
                val = data.get(color_name)
                if val is not None:
                    # 识别到目标，显示绿色四位小数
                    label.config(text=f"{val:.4f}", fg="#2ECC71")
                else:
                    # 未识别到目标，显示灰色 None
                    label.config(text="None", fg="#7F8C8D")
        else:
            for label in self.labels.values():
                label.config(text="None", fg="#7F8C8D")
                
        # 每 100 毫秒刷新一次 UI
        self.root.after(100, self.update_data_loop)

    def on_closing(self):
        """安全退出"""
        self.elevation.set_enabled(False)
        self.root.destroy()

if __name__ == "__main__":
    app = ElevationTester()
    app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.root.mainloop()