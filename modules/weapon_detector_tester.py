import tkinter as tk
from tkinter import ttk
import sys
import os
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from region_manager import RegionManager
from weapon_detector import WeaponDetector

class WeaponDetectorTester:
    def __init__(self, root):
        self.root = root
        self.root.title("武器检测测试台")
        self.root.geometry("400x350")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 初始化区域管理器
        self.rm = RegionManager(self.root, config_file="config.json")

        # 创建武器检测器（先不启用）
        self.detector = WeaponDetector(self.rm, fps=30, match_threshold=0.55, debug=False)

        # 获取所有可用武器模板名
        self.weapon_list = self._get_available_weapons()
        self.primary1 = tk.StringVar(value="")
        self.primary2 = tk.StringVar(value="")

        self.init_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _get_available_weapons(self):
        """扫描 templates/weapons 目录，获取所有武器名称"""
        templates_dir = "templates/weapons"
        if not os.path.exists(templates_dir):
            return []
        weapons = []
        for name in os.listdir(templates_dir):
            path = os.path.join(templates_dir, name)
            if os.path.isdir(path):
                weapons.append(name)
        return weapons

    def init_ui(self):
        # 标题
        tk.Label(self.root, text="武器检测测试", fg="white", bg="#2C3E50",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        # 显示 weapon_region 校准状态
        rect = self.rm.get_real_region("weapon_region")
        if rect:
            status = f"武器区域已校准: {rect['width']}x{rect['height']}"
            status_color = "#2ECC71"
        else:
            status = "未校准 weapon_region，请先运行 RegionManager 校准"
            status_color = "#E74C3C"
        tk.Label(self.root, text=status, fg=status_color, bg="#2C3E50", font=("Arial", 9)).pack(pady=5)

        # 选择主武器1
        frame1 = tk.LabelFrame(self.root, text="主武器 1", bg="#34495E", fg="white", font=("Arial", 10, "bold"))
        frame1.pack(fill="x", padx=10, pady=5)
        self.weapon1_combo = ttk.Combobox(frame1, textvariable=self.primary1, values=self.weapon_list, state="readonly")
        self.weapon1_combo.pack(fill="x", padx=5, pady=5)

        # 选择主武器2
        frame2 = tk.LabelFrame(self.root, text="主武器 2", bg="#34495E", fg="white", font=("Arial", 10, "bold"))
        frame2.pack(fill="x", padx=10, pady=5)
        self.weapon2_combo = ttk.Combobox(frame2, textvariable=self.primary2, values=self.weapon_list, state="readonly")
        self.weapon2_combo.pack(fill="x", padx=5, pady=5)

        # 更新主武器按钮
        self.btn_update = tk.Button(self.root, text="更新主武器", command=self.update_primary_weapons,
                                    bg="#3498DB", fg="white", font=("Microsoft YaHei", 10))
        self.btn_update.pack(pady=5)

        # 启停控制
        self.btn_toggle = tk.Button(self.root, text="启动检测", command=self.toggle_detection,
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_toggle.pack(pady=10)

        # 结果显示
        self.result_label = tk.Label(self.root, text="当前武器: 未识别", fg="#F1C40F", bg="#2C3E50",
                                     font=("Microsoft YaHei", 12, "bold"))
        self.result_label.pack(pady=5)
        self.score_label = tk.Label(self.root, text="置信度: --", fg="#BDC3C7", bg="#2C3E50",
                                    font=("Arial", 10))
        self.score_label.pack(pady=5)

        # 提示
        tk.Label(self.root, text="请确保游戏中已装备主武器，并校准好 weapon_region",
                 fg="#95A5A6", bg="#2C3E50", font=("Arial", 8)).pack(pady=10)

        self.detecting = False

    def update_primary_weapons(self):
        """将选择的武器传入检测器"""
        w1 = self.primary1.get()
        w2 = self.primary2.get()
        self.detector.update_primary_weapons(w1 if w1 else None, w2 if w2 else None)
        print(f"[测试] 更新主武器: {w1}, {w2}")

    def toggle_detection(self):
        if not self.detecting:
            # 启动检测
            self.detector.set_enabled(True, self.on_weapon_detected)
            self.detecting = True
            self.btn_toggle.config(text="停止检测", bg="#E74C3C")
        else:
            self.detector.set_enabled(False)
            self.detecting = False
            self.btn_toggle.config(text="启动检测", bg="#2ECC71")
            self.result_label.config(text="当前武器: 未识别", fg="#F1C40F")
            self.score_label.config(text="置信度: --")

    def on_weapon_detected(self, weapon_name, score):
        """检测回调，更新UI"""
        def update():
            if weapon_name:
                self.result_label.config(text=f"当前武器: {weapon_name}", fg="#2ECC71")
                self.score_label.config(text=f"置信度: {score:.2f}", fg="#2ECC71")
            else:
                self.result_label.config(text="当前武器: 未识别", fg="#F1C40F")
                self.score_label.config(text=f"置信度: {score:.2f}", fg="#BDC3C7")
        self.root.after(0, update)

    def on_closing(self):
        self.detector.set_enabled(False)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = WeaponDetectorTester(root)
    root.mainloop()