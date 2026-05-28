import tkinter as tk
import mss
from pynput import keyboard
import threading
import time

# 导入你的三大模块
from minimap_radar import MinimapRadarModule
from elevation_radar import ElevationRadarModule
from throwables_assistant import ThrowablesAssistant

class ThrowablesTester:
    def __init__(self, root):
        self.root = root
        self.root.title("雷火闪助手 测试台")
        self.root.geometry("380x350")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            sw, sh = monitor["width"], monitor["height"]

        # ================= 1. 实例化核心传感器与助手 =================
        self.minimap = MinimapRadarModule(self.root)
        self.elevation = ElevationRadarModule(self.root, sw, sh, fps=30)
        self.throwables = ThrowablesAssistant(self.root, sw, sh, self.minimap, self.elevation, fps=30)
        
        self.is_running = False
        self.linkage_thread = None
        
        # 键盘监听器，用于测试 V 和 R 键
        self.kb_listener = keyboard.Listener(on_press=self.on_key_press)
        self.kb_listener.start()
        
        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="投掷物瞬爆与火控 终端", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 14, "bold")).pack(pady=10)
        
        # 校准按钮 (复用底层的接口)
        f_calib = tk.Frame(self.root, bg="#2C3E50")
        f_calib.pack(pady=5)
        tk.Button(f_calib, text="📏 校准小地图", command=self.minimap.trigger_calibration, 
                  bg="#3498DB", fg="white", font=("Microsoft YaHei", 10)).grid(row=0, column=0, padx=10)
        
        # 启停控制
        self.btn_toggle = tk.Button(self.root, text="▶ 开启投掷物助手 (全局测试)", command=self.toggle_system, 
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 11, "bold"))
        self.btn_toggle.pack(fill="x", padx=30, pady=20)
                  
        # 提示信息
        info_text = (
            "【测试指南】\n"
            "1. 请先在游戏中按地图原点校准好小地图。\n"
            "2. 开启助手后，按 [V] 键进入自动瞬爆待命状态。\n"
            "3. 捏雷时按下 [R] 键拉环，后台将自动计时。\n"
            "4. 倒计时结束，系统将自动松开 End 键与鼠标左键！"
        )
        tk.Label(self.root, text=info_text, fg="#BDC3C7", bg="#2C3E50", justify="left").pack(pady=10)

    def _sensor_linkage_loop(self):
        """传感器状态联动循环 (模拟主程序的数据泵)"""
        while self.is_running:
            # 获取小地图距离，如果距离大于 0，说明检测到了该颜色标点
            mini_dists = self.minimap.get_measured_distance()
            valid_colors = {color: (dist > 0) for color, dist in mini_dists.items()}
            
            # 告诉测高模块：只去扫那些在小地图上存在的颜色
            self.elevation.set_valid_colors(valid_colors)
            time.sleep(0.1)

    def toggle_system(self):
        self.is_running = not self.is_running
        
        # 启停所有视觉与 HUD 模块
        self.minimap.set_enabled(self.is_running)
        self.elevation.set_enabled(self.is_running)
        self.throwables.enable_module(self.is_running)
        
        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止投掷物助手", bg="#E74C3C")
            # 启动传感器联动线程
            self.linkage_thread = threading.Thread(target=self._sensor_linkage_loop, daemon=True)
            self.linkage_thread.start()
            print("[测试台] 系统已启动，请在游戏中打点测试！")
        else:
            self.btn_toggle.config(text="▶ 开启投掷物助手 (全局测试)", bg="#2ECC71")

    def on_key_press(self, key):
        """全局热键路由"""
        if not self.is_running: return
        try:
            if hasattr(key, 'char') and key.char:
                char = key.char.lower()
                if char == 'v':
                    self.throwables.toggle_auto_throw()
                elif char == 'r':
                    self.throwables.trigger_pull_pin()
        except Exception:
            pass

    def on_closing(self):
        self.is_running = False
        self.kb_listener.stop()
        self.minimap.set_enabled(False)
        self.elevation.set_enabled(False)
        self.throwables.enable_module(False)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ThrowablesTester(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()