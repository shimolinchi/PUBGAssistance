import tkinter as tk
import sys
import os
from pynput import keyboard

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from region_manager import RegionManager
from minimap_radar import MinimapRadarModule
from c4_assistant import C4Assistant

class C4Tester:
    def __init__(self, root):
        self.root = root
        self.root.title("C4助手测试台 (真实小地图)")
        self.root.geometry("500x500")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        self.rm = RegionManager(self.root, config_file="config.json")
        self.minimap = MinimapRadarModule(self.root, self.rm, config_file="config.json")
        self.minimap.set_enabled(True)
        self.minimap.set_display(True)

        self.c4 = C4Assistant(self.root, self.rm, self.minimap,
                              fps=30, explosion_margin=2.0, target_speed=70.0)
        self.c4.set_enabled(True)
        self.c4.c4_equipped = True

        self.init_ui()
        self.update_ui_loop()
        self.start_global_listener()

    def start_global_listener(self):
        """使用 pynput 全局监听键盘"""
        def on_press(key):
            try:
                # 直接调用 C4 助手的按键处理方法
                self.root.after(0, lambda: self.c4.on_key_press(key))
            except Exception as e:
                print(f"按键处理错误: {e}")
        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.start()

    def init_ui(self):
        tk.Label(self.root, text="C4助手测试台 (真实小地图)", fg="white", bg="#2C3E50",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        minimap_rect = self.rm.get_real_region("minimap_region")
        if minimap_rect:
            status = f"小地图已校准: {minimap_rect['width']}x{minimap_rect['height']}"
            status_color = "#2ECC71"
        else:
            status = "⚠️ 小地图未校准，请先运行 RegionManager 校准"
            status_color = "#E74C3C"
        tk.Label(self.root, text=status, fg=status_color, bg="#2C3E50", font=("Arial", 9)).pack(pady=2)

        frame_info = tk.LabelFrame(self.root, text="标点信息", bg="#34495E", fg="white")
        frame_info.pack(fill="x", padx=10, pady=5)
        self.color_label = tk.Label(frame_info, text=f"当前标点颜色: {self.c4.selected_color}", fg="#3498DB", bg="#34495E", font=("Arial", 10, "bold"))
        self.color_label.pack(pady=2)
        self.dist_label = tk.Label(frame_info, text="距离: -- m", fg="#F39C12", bg="#34495E", font=("Arial", 10))
        self.dist_label.pack(pady=2)

        frame_btn = tk.Frame(self.root, bg="#2C3E50")
        frame_btn.pack(pady=10)
        btn_install = tk.Button(frame_btn, text="模拟安装 C4 (鼠标左键)", command=self.simulate_install,
                                bg="#E67E22", fg="white", font=("Microsoft YaHei", 10, "bold"))
        btn_install.pack(side="left", padx=5)
        btn_reset = tk.Button(frame_btn, text="重置助手状态", command=self.reset_state,
                              bg="#E74C3C", fg="white", font=("Microsoft YaHei", 10))
        btn_reset.pack(side="left", padx=5)

        tip = ("使用说明:\n1. 确保游戏中小地图已校准，且已在地图上放置标点（建议黄色）。\n"
               "2. 按 Q/E 切换标点颜色（全局监听，安装前有效）。\n"
               "3. 点击「模拟安装 C4」按钮开始安装流程（4秒安装，之后倒计时）。\n"
               "4. 当建议车速低于 50 km/h 时，会显示起步倒计时。")
        tk.Label(self.root, text=tip, fg="#BDC3C7", bg="#2C3E50", justify="left", font=("Arial", 9)).pack(pady=10)

    def update_ui_loop(self):
        # 从 C4 助手获取当前颜色
        self.color_label.config(text=f"当前标点颜色: {self.c4.selected_color}")
        dist_dict = self.minimap.get_measured_distance()
        dist = dist_dict.get(self.c4.selected_color, 0.0)
        self.dist_label.config(text=f"距离: {dist:.1f} m")
        self.root.after(100, self.update_ui_loop)

    def simulate_install(self):
        if not self.c4.is_enabled:
            print("C4助手未启用")
            return
        if not self.c4.c4_equipped:
            print("未装备 C4，请先通过武器检测设置（测试中已强制为 True）")
            return
        self.c4.on_mouse_left_press()

    def reset_state(self):
        self.c4._reset()
        self.c4.is_installing = False
        self.c4.is_active = False
        self.c4.c4_equipped = True
        self.c4._clear_display()
        print("助手状态已重置")

    def on_closing(self):
        if hasattr(self, 'listener') and self.listener:
            self.listener.stop()
        self.minimap.set_enabled(False)
        self.c4.shutdown()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = C4Tester(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()