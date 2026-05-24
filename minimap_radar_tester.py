import tkinter as tk
from minimap_radar import MinimapRadarModule

class MinimapTester:
    def __init__(self, root):
        self.root = root
        self.root.title("小地图模块独立测试")
        self.root.geometry("300x250")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 实例化雷达模块
        self.radar = MinimapRadarModule(self.root)
        
        self.is_running = False

        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="小地图模块测试台", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=10)
        
        # 如果没有配置文件，提示需要标定
        status_text = "状态: 已加载配置文件" if self.radar.monitor else "状态: 暂无配置，请先标定"
        self.lbl_status = tk.Label(self.root, text=status_text, fg="#F1C40F", bg="#2C3E50")
        self.lbl_status.pack(pady=5)

        tk.Button(self.root, text="1. 手动标定小地图", command=self.radar.trigger_calibration, 
                  bg="#3498DB", fg="white", font=("Microsoft YaHei", 10)).pack(fill="x", padx=30, pady=5)
                  
        self.btn_toggle = tk.Button(self.root, text="2. 启动雷达 (含显示)", command=self.toggle_radar, 
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_toggle.pack(fill="x", padx=30, pady=15)

    def toggle_radar(self):
        if not self.radar.monitor:
            print("请先标定小地图！")
            self.lbl_status.config(text="错误: 请先标定小地图!", fg="#E74C3C")
            return

        self.is_running = not self.is_running
        
        # 同步开启模块后台运算和屏幕渲染
        self.radar.set_enabled(self.is_running)
        self.radar.set_display(self.is_running)
        
        if self.is_running:
            self.btn_toggle.config(text="停止雷达", bg="#E74C3C")
            self.lbl_status.config(text="状态: 雷达运行中...", fg="#2ECC71")
        else:
            self.btn_toggle.config(text="2. 启动雷达 (含显示)", bg="#2ECC71")
            self.lbl_status.config(text="状态: 已停止", fg="#F1C40F")

if __name__ == "__main__":
    root = tk.Tk()
    app = MinimapTester(root)
    root.mainloop()