import tkinter as tk
from region_manager import RegionManager

class RegionTester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PUBG 检测区域标定工具")
        self.root.geometry("350x300")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")
        
        # 实例化我们的区域管理器
        self.rm = RegionManager(self.root)
        
        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="👁️ 视觉截取 ROI 标定控制台", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=10)
        
        # 标定按钮
        tk.Button(self.root, text="📐 标定 1：倍镜识别区 (大屏)", command=lambda: self.rm.calibrate_region("scope_region"), bg="#3498DB", fg="white", font=("Microsoft YaHei", 10)).pack(pady=5, fill="x", padx=40)
        
        tk.Button(self.root, text="🔫 标定 2：主武器 UI 槽 (中等)", command=lambda: self.rm.calibrate_region("weapon_region"), bg="#E67E22", fg="white", font=("Microsoft YaHei", 10)).pack(pady=5, fill="x", padx=40)
        
        tk.Button(self.root, text="🧍 标定 3：姿势小人 (微小)", command=lambda: self.rm.calibrate_region("stance_region"), bg="#9B59B6", fg="white", font=("Microsoft YaHei", 10)).pack(pady=5, fill="x", padx=40)
        
        tk.Frame(self.root, height=2, bg="#34495E").pack(fill="x", pady=10)
        
        # 调试显示控制
        self.btn_debug = tk.Button(self.root, text="👀 显示调试边框 (OFF)", command=self.toggle_debug, bg="#7F8C8D", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_debug.pack(pady=5, fill="x", padx=40)

    def toggle_debug(self):
        # 获取当前状态并取反
        new_state = not self.rm.show_debug
        self.rm.set_debug_mode(new_state)
        
        if new_state:
            self.btn_debug.config(text="👀 隐藏调试边框 (ON)", bg="#2ECC71")
        else:
            self.btn_debug.config(text="👀 显示调试边框 (OFF)", bg="#7F8C8D")

    def on_closing(self):
        self.root.destroy()

if __name__ == "__main__":
    app = RegionTester()
    app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.root.mainloop()