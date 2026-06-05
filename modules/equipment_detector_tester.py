import tkinter as tk
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from pynput import keyboard
from region_manager import RegionManager
from equipment_detector import EquipmentDetector

class EquipmentDetectorTester:
    def __init__(self, root):
        self.root = root
        self.root.title("装备栏识别测试台")
        self.root.geometry("500x450")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        self.rm = RegionManager(self.root, config_file="config.json")
        self.detector = EquipmentDetector(self.rm, fps=5, confirm_frames=2, idle_timeout=2.0,
                                  debug=True)
        self.detector.set_enabled(True, self.on_equipment_update)

        self.is_open = False
        self.weapons_data = {1: {}, 2: {}}
        self.listener_running = False

        self.init_ui()
        self.start_keyboard_listener()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_ui(self):
        tk.Label(self.root, text="装备栏识别测试", fg="white", bg="#2C3E50",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        self.status_label = tk.Label(self.root, text="状态: 未打开装备栏", fg="#F1C40F", bg="#2C3E50",
                                     font=("Arial", 10))
        self.status_label.pack(pady=5)

        # 武器1
        frame1 = tk.LabelFrame(self.root, text="武器 1", bg="#34495E", fg="white", font=("Arial", 10, "bold"))
        frame1.pack(fill="x", padx=10, pady=5)
        self.weapon1_vars = {}
        for label in ["名称", "倍镜", "握把", "枪口", "枪托"]:
            row = tk.Frame(frame1, bg="#34495E")
            row.pack(fill="x", padx=5, pady=2)
            tk.Label(row, text=f"{label}:", width=6, anchor="w", bg="#34495E", fg="white").pack(side="left")
            var = tk.StringVar(value="未识别")
            score_var = tk.StringVar(value="")
            tk.Label(row, textvariable=var, bg="#34495E", fg="#2ECC71", anchor="w", width=12).pack(side="left")
            tk.Label(row, textvariable=score_var, bg="#34495E", fg="#F39C12", anchor="w", width=8).pack(side="left")
            self.weapon1_vars[label] = (var, score_var)

        # 武器2
        frame2 = tk.LabelFrame(self.root, text="武器 2", bg="#34495E", fg="white", font=("Arial", 10, "bold"))
        frame2.pack(fill="x", padx=10, pady=5)
        self.weapon2_vars = {}
        for label in ["名称", "倍镜", "握把", "枪口", "枪托"]:
            row = tk.Frame(frame2, bg="#34495E")
            row.pack(fill="x", padx=5, pady=2)
            tk.Label(row, text=f"{label}:", width=6, anchor="w", bg="#34495E", fg="white").pack(side="left")
            var = tk.StringVar(value="未识别")
            score_var = tk.StringVar(value="")
            tk.Label(row, textvariable=var, bg="#34495E", fg="#2ECC71", anchor="w", width=12).pack(side="left")
            tk.Label(row, textvariable=score_var, bg="#34495E", fg="#F39C12", anchor="w", width=8).pack(side="left")
            self.weapon2_vars[label] = (var, score_var)

        btn_frame = tk.Frame(self.root, bg="#2C3E50")
        btn_frame.pack(pady=10)
        self.btn_enable = tk.Button(btn_frame, text="禁用识别", command=self.toggle_detector,
                                    bg="#E74C3C", fg="white", font=("Microsoft YaHei", 10))
        self.btn_enable.pack(side="left", padx=5)
        self.btn_test = tk.Button(btn_frame, text="模拟 Tab 按下", command=self.simulate_tab,
                                  bg="#3498DB", fg="white", font=("Microsoft YaHei", 10))
        self.btn_test.pack(side="left", padx=5)

        tk.Label(self.root, text="快捷键: Tab (全局监听) | 手动点击按钮也可触发",
                 fg="#BDC3C7", bg="#2C3E50", font=("Arial", 9)).pack(pady=10)

    def on_equipment_update(self, is_open, weapons):
        self.is_open = is_open
        self.weapons_data = weapons
        self.root.after(0, self.update_ui)

    def update_ui(self):
        if self.is_open:
            self.status_label.config(text="状态: 装备栏已打开", fg="#2ECC71")
        else:
            self.status_label.config(text="状态: 装备栏未打开", fg="#E74C3C")

        # 更新武器1
        w1 = self.weapons_data.get(1, {})
        for label, key in [("名称", "name"), ("倍镜", "scope"), ("握把", "grip"), ("枪口", "muzzle"), ("枪托", "stock")]:
            value = w1.get(key) or "无"
            score = w1.get(f"{key}_score", 0.0)
            var, score_var = self.weapon1_vars[label]
            var.set(value)
            if score > 0:
                score_var.set(f"{score:.2f}")
            else:
                score_var.set("")

        # 更新武器2
        w2 = self.weapons_data.get(2, {})
        for label, key in [("名称", "name"), ("倍镜", "scope"), ("握把", "grip"), ("枪口", "muzzle"), ("枪托", "stock")]:
            value = w2.get(key) or "无"
            score = w2.get(f"{key}_score", 0.0)
            var, score_var = self.weapon2_vars[label]
            var.set(value)
            if score > 0:
                score_var.set(f"{score:.2f}")
            else:
                score_var.set("")

    def toggle_detector(self):
        if self.detector._enabled:
            self.detector.set_enabled(False)
            self.btn_enable.config(text="启用识别", bg="#2ECC71")
            self.status_label.config(text="状态: 识别模块已禁用", fg="#F39C12")
        else:
            self.detector.set_enabled(True, self.on_equipment_update)
            self.btn_enable.config(text="禁用识别", bg="#E74C3C")
            self.status_label.config(text="状态: 识别模块已启用", fg="#3498DB")

    def simulate_tab(self):
        self.detector.on_tab_press()

    def start_keyboard_listener(self):
        def on_press(key):
            try:
                if key == keyboard.Key.tab:
                    self.root.after(0, self.detector.on_tab_press)
            except:
                pass
        self.keyboard_listener = keyboard.Listener(on_press=on_press)
        self.keyboard_listener.start()
        self.listener_running = True

    def on_closing(self):
        if self.listener_running:
            self.keyboard_listener.stop()
        self.detector.set_enabled(False)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = EquipmentDetectorTester(root)
    root.mainloop()