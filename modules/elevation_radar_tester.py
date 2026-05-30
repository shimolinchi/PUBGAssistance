import tkinter as tk
from modules.elevation_radar import ElevationRadarModule
import cv2
import threading
import time

class ElevationDebugTester:
    def __init__(self, root):
        self.root = root
        self.root.title("高低角模块独立测试台")
        self.root.geometry("350x300")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        
        # 实例化高低角模块
        self.elevation = ElevationRadarModule(self.root, sw, sh, fps=30)
        
        self.is_running = False
        self.debug_thread = None
        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="垂直测高视觉调试", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=10)
        
        status_text = "状态: 已加载配置" if self.elevation.monitor else "状态: 请先标定屏幕标尺区域"
        self.lbl_status = tk.Label(self.root, text=status_text, fg="#F1C40F", bg="#2C3E50")
        self.lbl_status.pack(pady=5)
        
        tk.Button(self.root, text="1. 手动框选标定区域", command=self.elevation.trigger_calibration, 
                  bg="#3498DB", fg="white", font=("Microsoft YaHei", 10)).pack(fill="x", padx=30, pady=5)
                  
        self.btn_toggle = tk.Button(self.root, text="2. 启动测高 (含调试预览)", command=self.toggle_system, 
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_toggle.pack(fill="x", padx=30, pady=15)
        
        tk.Button(self.root, text="仅测试黄/蓝色 (模拟过滤)", command=self.test_filter, 
                  bg="#9B59B6", fg="white").pack(pady=5)

    def toggle_system(self):
        if not self.elevation.monitor:
            self.lbl_status.config(text="错误: 请先点击上方按钮标定区域!", fg="#E74C3C")
            return

        self.is_running = not self.is_running
        
        self.elevation.set_enabled(self.is_running)
        self.elevation.set_display(self.is_running)
        
        if self.is_running:
            self.btn_toggle.config(text="停止测高并关闭窗口", bg="#E74C3C")
            self.lbl_status.config(text="状态: 模块运行中...", fg="#2ECC71")
            
            # 启动一个简易调试线程获取底层的Mask数据(仅用于显示)
            self.debug_thread = threading.Thread(target=self._debug_loop, daemon=True)
            self.debug_thread.start()
        else:
            self.btn_toggle.config(text="2. 启动测高 (含调试预览)", bg="#2ECC71")
            self.lbl_status.config(text="状态: 已停止", fg="#F1C40F")

    def test_filter(self):
        """测试 API set_valid_colors 是否正常工作"""
        print("[测试] 限制测高雷达仅检测黄色和蓝色")
        self.elevation.set_valid_colors(["Yellow", "Blue"])

    def _debug_loop(self):
        import mss
        import numpy as np
        with mss.MSS() as sct:
            while self.is_running:
                try:
                    if self.elevation.monitor:
                        screenshot = sct.grab(self.elevation.monitor)
                        frame_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
                        frame_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
                        
                        for color_name in self.elevation.valid_colors:
                            config = self.elevation.colors[color_name]
                            lower = np.array(config["lower"], dtype=np.uint8)
                            upper = np.array(config["upper"], dtype=np.uint8)
                            mask = cv2.inRange(frame_hsv, lower, upper)
                            
                            cv2.imshow(f"Elev Debug: {color_name}", mask)
                        
                        cv2.waitKey(1)
                except: pass
                time.sleep(0.05)
        cv2.destroyAllWindows()

if __name__ == "__main__":
    root = tk.Tk()
    app = ElevationDebugTester(root)
    
    def on_closing():
        app.is_running = False
        app.elevation.set_enabled(False)
        cv2.destroyAllWindows()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()