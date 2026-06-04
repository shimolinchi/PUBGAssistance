import tkinter as tk
import threading
import time
import cv2
import numpy as np
import mss

# 导入我们的全局区域管理器
from region_manager import RegionManager

# ================= 颜色配置 (HSV) =================
COLORS_HSV = {
    "Yellow": {"lower": [26, 150, 160], "upper": [30, 255, 255], "hex": "#E3D43C"},
    "Orange": {"lower": [10, 160, 160], "upper": [14, 255, 255], "hex": "#B3500D"},
    "Blue":   {"lower": [110, 120, 160], "upper": [114, 255, 255], "hex": "#1A3EA3"},
    "Green":  {"lower": [78, 150, 120], "upper": [82, 255, 255], "hex": "#109166"}
}

class ColorMaskTester:
    def __init__(self, root):
        self.root = root
        self.root.title("雷达视觉验证台 (接入RegionManager)")
        self.root.geometry("380x280")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        self.is_running = False
        self._thread_running = False
        
        # 【核心修改】：初始化 RM
        print("[验证台] 正在连接 RegionManager...")
        self.rm = RegionManager(self.root)

        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="👁️ 小地图掩码(Mask)验证台", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=10)
        
        self.lbl_status = tk.Label(self.root, text="状态: 待机中", fg="#F1C40F", bg="#2C3E50")
        self.lbl_status.pack(pady=5)
        
        # 显示动态区域信息
        self.lbl_region = tk.Label(self.root, text="获取坐标中...", fg="#BDC3C7", bg="#2C3E50", font=("Consolas", 9))
        self.lbl_region.pack(pady=5)

        self.btn_toggle = tk.Button(self.root, text="▶ 启动实时多窗口预览", command=self.toggle_system, 
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_toggle.pack(fill="x", padx=40, pady=15)
        
        tk.Label(self.root, text="提示: 若 OpenCV 窗口卡死，请点击上方停止按钮", fg="#95A5A6", bg="#2C3E50", font=("Microsoft YaHei", 8)).pack(pady=5)

    def toggle_system(self):
        self.is_running = not self.is_running
        
        if self.is_running:
            self._thread_running = True
            threading.Thread(target=self._capture_loop, daemon=True).start()
            
            self.btn_toggle.config(text="⏹ 停止预览并关闭窗口", bg="#E74C3C")
            self.lbl_status.config(text="状态: 正在实时渲染 4 个二值图", fg="#2ECC71")
        else:
            self._thread_running = False
            self.btn_toggle.config(text="▶ 启动实时多窗口预览", bg="#2ECC71")
            self.lbl_status.config(text="状态: 已停止", fg="#F1C40F")

    def _capture_loop(self):
        with mss.mss() as sct:
            while self._thread_running:
                try:
                    # 【核心修改】：从 RegionManager 动态拉取小地图区域
                    monitor = self.rm.get_real_region("minimap_region")
                    
                    if not monitor:
                        self.root.after(0, lambda: self.lbl_region.config(text="❌ 未找到小地图区域，请先使用全局中枢标定!"))
                        time.sleep(0.5)
                        continue
                        
                    # 更新 UI 提示文本 (要在主线程中执行)
                    self.root.after(0, lambda m=monitor: self.lbl_region.config(
                        text=f"当前锁定区域: {m['width']}x{m['height']}  (Left:{m['left']}, Top:{m['top']})"))

                    # 1. 抓取屏幕并转换颜色空间
                    screenshot = sct.grab(monitor)
                    frame_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
                    frame_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
                    
                    # 额外显示一个原图，方便对比
                    cv2.imshow("Debug: Original View", frame_bgr)
                    
                    # 2. 分别提取 4 个颜色的二值图 (Mask)
                    for color_name, config in COLORS_HSV.items():
                        lower = np.array(config["lower"], dtype=np.uint8)
                        upper = np.array(config["upper"], dtype=np.uint8)
                        
                        color_mask = cv2.inRange(frame_hsv, lower, upper)
                        cv2.imshow(f"Mask: {color_name}", color_mask)
                    
                    cv2.waitKey(1)
                    
                except Exception as e:
                    print(f"[验证台错误] {e}")
                
                time.sleep(0.03) # 约 30 帧刷新率
                
        # 退出循环时，销毁所有 OpenCV 窗口
        cv2.destroyAllWindows()

if __name__ == "__main__":
    root = tk.Tk()
    app = ColorMaskTester(root)
    
    # 绑定窗口关闭事件，确保安全退出
    def on_closing():
        app._thread_running = False
        cv2.destroyAllWindows()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()