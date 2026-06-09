import tkinter as tk
from tkinter import ttk
import sys
import os
import threading
import time
import cv2
import numpy as np
import mss

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

        self.rm = RegionManager(self.root, config_file="config.json")
        self.detector = WeaponDetector(self.rm, fps=30, match_threshold=0.55, debug=False)

        self.weapon_list = self._get_available_weapons()
        self.primary1 = tk.StringVar(value="")
        self.primary2 = tk.StringVar(value="")

        self.debug_win_name = "Weapon Detection Debug"
        self.debug_running = False
        self.debug_thread = None

        self.init_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _get_available_weapons(self):
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
        tk.Label(self.root, text="武器检测测试", fg="white", bg="#2C3E50",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        rect = self.rm.get_real_region("weapon_region")
        if rect:
            status = f"武器区域已校准: {rect['width']}x{rect['height']}"
            status_color = "#2ECC71"
        else:
            status = "未校准 weapon_region，请先运行 RegionManager 校准"
            status_color = "#E74C3C"
        tk.Label(self.root, text=status, fg=status_color, bg="#2C3E50", font=("Arial", 9)).pack(pady=5)

        frame1 = tk.LabelFrame(self.root, text="主武器 1", bg="#34495E", fg="white", font=("Arial", 10, "bold"))
        frame1.pack(fill="x", padx=10, pady=5)
        self.weapon1_combo = ttk.Combobox(frame1, textvariable=self.primary1, values=self.weapon_list, state="readonly")
        self.weapon1_combo.pack(fill="x", padx=5, pady=5)

        frame2 = tk.LabelFrame(self.root, text="主武器 2", bg="#34495E", fg="white", font=("Arial", 10, "bold"))
        frame2.pack(fill="x", padx=10, pady=5)
        self.weapon2_combo = ttk.Combobox(frame2, textvariable=self.primary2, values=self.weapon_list, state="readonly")
        self.weapon2_combo.pack(fill="x", padx=5, pady=5)

        self.btn_update = tk.Button(self.root, text="更新主武器", command=self.update_primary_weapons,
                                    bg="#3498DB", fg="white", font=("Microsoft YaHei", 10))
        self.btn_update.pack(pady=5)

        self.btn_toggle = tk.Button(self.root, text="启动检测", command=self.toggle_detection,
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_toggle.pack(pady=10)

        self.result_label = tk.Label(self.root, text="当前武器: 未识别", fg="#F1C40F", bg="#2C3E50",
                                     font=("Microsoft YaHei", 12, "bold"))
        self.result_label.pack(pady=5)
        self.score_label = tk.Label(self.root, text="置信度: --", fg="#BDC3C7", bg="#2C3E50",
                                    font=("Arial", 10))
        self.score_label.pack(pady=5)

        tk.Label(self.root, text="请确保游戏中已装备主武器，并校准好 weapon_region",
                 fg="#95A5A6", bg="#2C3E50", font=("Arial", 8)).pack(pady=10)

        self.detecting = False

    def update_primary_weapons(self):
        w1 = self.primary1.get()
        w2 = self.primary2.get()
        self.detector.update_primary_weapons(w1 if w1 else None, w2 if w2 else None)
        print(f"[测试] 更新主武器: {w1}, {w2}")

    def toggle_detection(self):
        if not self.detecting:
            self.detector.set_enabled(True, self.on_weapon_detected)
            self.detecting = True
            self.btn_toggle.config(text="停止检测", bg="#E74C3C")
            # 启动调试显示线程
            self.debug_running = True
            self.debug_thread = threading.Thread(target=self._debug_loop, daemon=True)
            self.debug_thread.start()
        else:
            self.detector.set_enabled(False)
            self.detecting = False
            self.btn_toggle.config(text="启动检测", bg="#2ECC71")
            self.result_label.config(text="当前武器: 未识别", fg="#F1C40F")
            self.score_label.config(text="置信度: --")
            self.debug_running = False
            if self.debug_thread:
                self.debug_thread.join(timeout=0.5)
            cv2.destroyWindow(self.debug_win_name)

    def on_weapon_detected(self, weapon_name, score):
        def update():
            if weapon_name:
                self.result_label.config(text=f"当前武器: {weapon_name}", fg="#2ECC71")
                self.score_label.config(text=f"置信度: {score:.2f}", fg="#2ECC71")
            else:
                self.result_label.config(text="当前武器: 未识别", fg="#F1C40F")
                self.score_label.config(text=f"置信度: {score:.2f}", fg="#BDC3C7")
        self.root.after(0, update)

    def _debug_loop(self):
        """每隔 0.2 秒截取武器区域，绘制预处理后的图像和匹配框"""
        with mss.MSS() as sct:
            while self.debug_running:
                try:
                    # 获取当前匹配位置
                    loc = self.detector.get_last_match_location()
                    # 获取武器区域原图
                    weapon_region = self.rm.get_real_region("weapon_region")
                    if not weapon_region:
                        time.sleep(0.2)
                        continue
                    screenshot = sct.grab(weapon_region)
                    img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
                    # 缩放到模板基准大小
                    base_region = self.rm.get_templates_region("weapon_region")
                    if base_region:
                        img_bgr = cv2.resize(img_bgr, (base_region["width"], base_region["height"]))
                    # 预处理图像
                    processed = self.detector._preprocess_image(img_bgr)
                    # 转为彩色用于显示
                    processed_color = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
                    # 如果有匹配位置，画矩形
                    if loc is not None:
                        x, y, w, h = loc
                        cv2.rectangle(processed_color, (x, y), (x+w, y+h), (0, 0, 255), 2)
                    # 显示
                    cv2.imshow(self.debug_win_name, processed_color)
                    cv2.waitKey(1)
                except Exception as e:
                    print(f"[调试显示错误] {e}")
                time.sleep(0.2)

    def on_closing(self):
        self.detector.set_enabled(False)
        self.debug_running = False
        cv2.destroyAllWindows()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = WeaponDetectorTester(root)
    root.mainloop()