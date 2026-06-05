import tkinter as tk
import sys
import os
import ctypes
import threading
import time

# 确保能导入同级模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from region_manager import RegionManager
from hair_tracker import HairTracker  # 假设 hair_tracker.py 在 modules 下

class CrosshairTrackerTest:
    def __init__(self, root):
        self.root = root
        self.root.title("准星跟踪器测试台")
        self.root.geometry("350x300")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 1. 初始化区域管理器
        self.rm = RegionManager(self.root, config_file="config.json")

        # 2. 获取屏幕尺寸
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()

        # 3. 创建准星跟踪器（启用调试窗口，显示二值图和检测圆）
        self.tracker = HairTracker(self.sw, self.sh, self.rm, show_debug=True)

        # 4. 创建透明覆盖层（用于绘制准星位置）
        self.overlay = None
        self.canvas = None
        self._init_overlay()

        # 5. UI 控件
        self.is_running = False
        self.init_ui()

        # 6. 启动 UI 刷新循环（更新 overlay 上的准星位置）
        self.update_overlay_loop()

    def _init_overlay(self):
        """创建全屏透明覆盖层，一次性强制置顶"""
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)

        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.overlay.update_idletasks()

        # 一次性强制最高层（与火箭筒助手一致）
        try:
            hwnd = int(self.overlay.frame(), 16)
            GWLP_EXSTYLE = -20
            WS_EX_TOPMOST = 0x00000008
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWLP_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWLP_EXSTYLE, ex_style | WS_EX_TOPMOST)

            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)

            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.BringWindowToTop(hwnd)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception as e:
            print(f"[准星测试] 窗口置顶失败: {e}")

    def init_ui(self):
        tk.Label(self.root, text="🎯 准星跟踪器测试", fg="white", bg="#2C3E50",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        # 显示 crosshair_region 是否已校准
        region = self.rm.get_real_region("crosshair_region")
        if region:
            status_text = f"准星区域: {region['width']}x{region['height']}"
            status_color = "#2ECC71"
        else:
            status_text = "未校准 crosshair_region，使用默认区域"
            status_color = "#E74C3C"
        tk.Label(self.root, text=status_text, fg=status_color, bg="#2C3E50",
                 font=("Arial", 9)).pack(pady=5)

        self.btn_toggle = tk.Button(self.root, text="▶ 启动跟踪", command=self.toggle_tracker,
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 12, "bold"))
        self.btn_toggle.pack(pady=20, fill="x", padx=40)

        self.btn_quit = tk.Button(self.root, text="退出", command=self.on_closing,
                                  bg="#E74C3C", fg="white", font=("Microsoft YaHei", 10))
        self.btn_quit.pack(pady=5, fill="x", padx=40)

    def toggle_tracker(self):
        """启动/停止准星跟踪器"""
        self.is_running = not self.is_running
        self.tracker.enable_module(self.is_running)

        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止跟踪", bg="#E74C3C")
        else:
            self.btn_toggle.config(text="▶ 启动跟踪", bg="#2ECC71")
            # 清空 overlay 上绘制的标记
            self.canvas.delete("crosshair")

    def update_overlay_loop(self):
        """每隔 50ms 刷新覆盖层，绘制当前准星中心"""
        if self.is_running:
            cx, cy, found = self.tracker.get_dynamic_center()
            self.canvas.delete("crosshair")
            if found:
                # 绘制红色十字线（大小 30 像素）
                self.canvas.create_line(cx - 15, cy, cx + 15, cy, fill="red", width=2, tags="crosshair")
                self.canvas.create_line(cx, cy - 15, cx, cy + 15, fill="red", width=2, tags="crosshair")
                # 中心点加粗
                self.canvas.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill="red", outline="red", tags="crosshair")
        self.root.after(50, self.update_overlay_loop)

    def on_closing(self):
        self.tracker.enable_module(False)
        # 关闭 OpenCV 窗口
        try:
            cv2.destroyAllWindows()
        except:
            pass
        self.root.destroy()

if __name__ == "__main__":
    # 导入 cv2 用于关闭窗口
    import cv2
    root = tk.Tk()
    app = CrosshairTrackerTest(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()