import tkinter as tk
from region_manager import RegionManager

class RegionTester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PUBG 全局校准中枢")
        self.root.geometry("420x680")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")
        
        # 实例化核心全局管理器
        self.rm = RegionManager(self.root)
        self.init_ui()

    def init_ui(self):
        # 标题
        tk.Label(self.root, text="⚙️ 战术枢纽全局标定台", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 14, "bold")).pack(pady=10)
        
        # ================= 压枪与特种武器 =================
        tk.Label(self.root, text="--- 🔫 枪械、姿态与特种武器 ---", fg="#BDC3C7", bg="#2C3E50", font=("Microsoft YaHei", 10)).pack(pady=(5,2))
        
        tk.Button(self.root, text="标定：主武器 UI 槽 (连发识别)", command=lambda: self.rm.calibrate_region("weapon_region"), bg="#E74C3C", fg="white", font=("Microsoft YaHei", 9)).pack(pady=3, fill="x", padx=40)
        tk.Button(self.root, text="标定：姿势小人 (蹲/趴识别)", command=lambda: self.rm.calibrate_region("stance_region"), bg="#E74C3C", fg="white", font=("Microsoft YaHei", 9)).pack(pady=3, fill="x", padx=40)
        tk.Button(self.root, text="标定：倍镜/准星 识别全屏区", command=lambda: self.rm.calibrate_region("scope_region"), bg="#C0392B", fg="white", font=("Microsoft YaHei", 9)).pack(pady=3, fill="x", padx=40)

        # ================= 小地图系统 =================
        tk.Label(self.root, text="--- 🗺️ 实时小地图雷达 ---", fg="#BDC3C7", bg="#2C3E50", font=("Microsoft YaHei", 10)).pack(pady=(15,2))
        
        tk.Button(self.root, text="区域：框选小地图显示范围", command=lambda: self.rm.calibrate_region("minimap_region"), bg="#3498DB", fg="white", font=("Microsoft YaHei", 9)).pack(pady=3, fill="x", padx=40)
        tk.Button(self.root, text="比例尺：画线标定 100m 网格", command=lambda: self.rm.calibrate_scale("minimap_100m_px"), bg="#2980B9", fg="white", font=("Microsoft YaHei", 9)).pack(pady=3, fill="x", padx=40)
        
        # ================= 大地图系统 =================
        tk.Label(self.root, text="--- 🌍 战术大地图系统 ---", fg="#BDC3C7", bg="#2C3E50", font=("Microsoft YaHei", 10)).pack(pady=(15,2))
        
        tk.Button(self.root, text="区域：框选大地图有效范围", command=lambda: self.rm.calibrate_region("largemap_region"), bg="#9B59B6", fg="white", font=("Microsoft YaHei", 9)).pack(pady=3, fill="x", padx=40)
        tk.Button(self.root, text="比例尺：画线标定 1km 网格", command=lambda: self.rm.calibrate_scale("largemap_1km_px"), bg="#8E44AD", fg="white", font=("Microsoft YaHei", 9)).pack(pady=3, fill="x", padx=40)

        # ================= 其他辅助模块 =================
        tk.Label(self.root, text="--- 🏔️ 辅助功能模块 ---", fg="#BDC3C7", bg="#2C3E50", font=("Microsoft YaHei", 10)).pack(pady=(15,2))
        
        tk.Button(self.root, text="标定：迫击炮垂直测高仪区", command=lambda: self.rm.calibrate_region("elevation_region"), bg="#E67E22", fg="white", font=("Microsoft YaHei", 9)).pack(pady=3, fill="x", padx=40)
        tk.Button(self.root, text="标定：顶部方位罗盘区", command=lambda: self.rm.calibrate_region("compass_region"), bg="#F1C40F", fg="black", font=("Microsoft YaHei", 9)).pack(pady=3, fill="x", padx=40)
        tk.Button(self.root, text="标定：准星内框识别区", command=lambda: self.rm.calibrate_region("crosshair_region"), bg="#C1C40F", fg="black", font=("Microsoft YaHei", 9)).pack(pady=3, fill="x", padx=40)

        # 分割线
        tk.Frame(self.root, height=2, bg="#34495E").pack(fill="x", pady=15)
        
        # 调试显示控制按钮
        self.btn_debug = tk.Button(self.root, text="👀 开启全局透视调试层 (OFF)", command=self.toggle_debug, bg="#7F8C8D", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_debug.pack(pady=5, fill="x", padx=40)

    def toggle_debug(self):
        new_state = not self.rm.show_debug
        self.rm.set_debug_mode(new_state)
        if new_state:
            self.btn_debug.config(text="👀 关闭全局透视调试层 (ON)", bg="#2ECC71")
        else:
            self.btn_debug.config(text="👀 开启全局透视调试层 (OFF)", bg="#7F8C8D")

    def on_closing(self):
        # 退出前确保清理内存
        self.root.destroy()

if __name__ == "__main__":
    app = RegionTester()
    app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.root.mainloop()