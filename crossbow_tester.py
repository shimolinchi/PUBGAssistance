import tkinter as tk
import os
import json
import cv2
from minimap_radar import MinimapRadarModule
from crossbow_assistant import CrossbowAssistant

class CrossbowDebugTester:
    def __init__(self, root):
        self.root = root
        self.root.title("十字弩/VSS 实战追踪测试台")
        self.root.geometry("320x220")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")
        
        # 1. 自动生成基础 config，防止小地图模块因找不到数据报错
        self._ensure_dummy_config()

        # 2. 获取准确的屏幕分辨率 (替代原来复杂的 mss 获取方式)
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()
            
        # 3. 实例化小地图测距雷达
        self.minimap = MinimapRadarModule(self.root)
        
        # 4. 实例化十字弩助手
        # 只要你在 crossbow_assistant.py 里将原有的 MathematicalCrossTracker 
        # 替换为了新的 CrossbowCrosshairTracker，这里就会自动启动带有 Debug 窗口的新追踪器！
        self.crossbow_assist = CrossbowAssistant(self.root, self.sw, self.sh, self.minimap, fps=30)
        
        self.is_running = False
        self.init_ui()

    def _ensure_dummy_config(self):
        """确保目录下有 config.json 让小地图能跑起来"""
        if not os.path.exists("config.json"):
            dummy_config = {
                "minimap_rect": {"top": 100, "left": 100, "width": 300, "height": 300},
                "minimap_100m_pixels": 100
            }
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(dummy_config, f, indent=4)

    def init_ui(self):
        tk.Label(self.root, text="弩/VSS 视觉追踪实测", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=10)
        tk.Label(self.root, text="💡 启动后将自动弹出黑白调试窗口", fg="#F1C40F", bg="#2C3E50", font=("Microsoft YaHei", 9)).pack(pady=2)
        
        # 必须先校准小地图，助手才能拿到有效距离
        self.btn_calib = tk.Button(self.root, text="📏 第一步：校准小地图", command=self.minimap.trigger_calibration, bg="#3498DB", fg="white", font=("Microsoft YaHei", 10))
        self.btn_calib.pack(pady=5, fill="x", padx=40)

        self.btn_toggle = tk.Button(self.root, text="▶ 第二步：启动 十字弩助手", command=self.toggle, bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_toggle.pack(pady=10, fill="x", padx=40)

    def toggle(self):
        self.is_running = not self.is_running
        
        # 同步启停两个核心模块
        self.minimap.set_enabled(self.is_running)
        self.crossbow_assist.enable_module(self.is_running)
        
        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止系统并关闭调试窗", bg="#E74C3C")
        else:
            self.btn_toggle.config(text="▶ 第二步：启动 十字弩助手", bg="#2ECC71")
            # 【关键安全机制】：用户点击停止时，强制向系统发送销毁所有 cv2 窗口的指令，防止残留黑白窗口卡死
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

    def on_closing(self):
        self.minimap.set_enabled(False)
        self.crossbow_assist.enable_module(False)
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = CrossbowDebugTester(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()