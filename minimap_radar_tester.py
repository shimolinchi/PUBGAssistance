import tkinter as tk
import threading
import time
import cv2
import numpy as np
import mss

# ================= 你的颜色配置 (HSV) =================
COLORS_HSV = {
    "Yellow": {
        "lower": [26, 150, 160], 
        "upper": [30, 255, 255], 
        "hex": "#E3D43C"
    },
    "Orange": {
        "lower": [10, 160, 160], 
        "upper": [14, 255, 255], 
        "hex": "#B3500D"
    },
    "Blue": {
        "lower": [110, 120, 160], 
        "upper": [114, 255, 255], 
        "hex": "#1A3EA3"
    },
    "Green": {
        "lower": [78, 150, 120], 
        "upper": [82, 255, 255], 
        "hex": "#109166"
    }
}

class ColorMaskTester:
    def __init__(self, root):
        self.root = root
        self.root.title("四色二值化视觉测试台")
        self.root.geometry("300x250")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        self.is_running = False
        self._thread_running = False
        
        # 默认截取屏幕中央 400x400 的区域进行测试
        # 你可以根据需要修改这里的大小和位置
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.monitor = {
            "top": sh // 2 - 200, 
            "left": sw // 2 - 200, 
            "width": 400, 
            "height": 400
        }

        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="二值化掩码(Mask)测试", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=10)
        
        self.lbl_status = tk.Label(self.root, text="状态: 待机中", fg="#F1C40F", bg="#2C3E50")
        self.lbl_status.pack(pady=10)
        
        tk.Label(self.root, text=f"当前捕获区域: {self.monitor['width']}x{self.monitor['height']}", 
                 fg="#BDC3C7", bg="#2C3E50", font=("Arial", 9)).pack(pady=5)

        self.btn_toggle = tk.Button(self.root, text="▶ 启动实时多窗口预览", command=self.toggle_system, 
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_toggle.pack(fill="x", padx=30, pady=15)

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
        with mss.MSS() as sct:
            while self._thread_running:
                try:
                    # 1. 抓取屏幕并转换颜色空间
                    screenshot = sct.grab(self.monitor)
                    frame_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
                    frame_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
                    
                    # 额外显示一个原图，方便你对比
                    cv2.imshow("Debug: Original View", frame_bgr)
                    
                    # 2. 分别提取 4 个颜色的二值图 (Mask)
                    for color_name, config in COLORS_HSV.items():
                        lower = np.array(config["lower"], dtype=np.uint8)
                        upper = np.array(config["upper"], dtype=np.uint8)
                        
                        # cv2.inRange 会输出一张 8位单通道图：在范围内的像素变 255(白)，范围外的变 0(黑)
                        color_mask = cv2.inRange(frame_hsv, lower, upper)
                        
                        # 3. 实时显示该颜色的二值图
                        cv2.imshow(f"Mask: {color_name}", color_mask)
                    
                    cv2.waitKey(1)
                    
                except Exception as e:
                    print(f"[测试台错误] {e}")
                
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