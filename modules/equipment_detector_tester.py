import tkinter as tk
from tkinter import ttk
import sys
import os
import cv2
import numpy as np
import mss
import threading
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from pynput import keyboard
from region_manager import RegionManager
from equipment_detector import EquipmentDetector

class EquipmentDetectorTester:
    def __init__(self, root):
        self.root = root
        self.root.title("装备栏识别测试台（调试版）")
        self.root.geometry("600x700")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        self.rm = RegionManager(self.root, config_file="config.json")
        self.detector = EquipmentDetector(
            self.rm, fps=5, idle_timeout=2.0,
            debug=True,
            on_status_change=self.on_status_change
        )
        self.detector.set_enabled(True, self.on_equipment_update)

        self.is_open = False
        self.weapons_data = {1: {}, 2: {}}
        self.listener_running = False

        self.debug_win_name = "Equipment Debug"
        self.debug_running = False
        self.debug_thread = None

        self.init_ui()
        self.start_keyboard_listener()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_ui(self):
        tk.Label(self.root, text="装备栏识别测试台（调试版）", fg="white", bg="#2C3E50",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=10)
        self.status_label = tk.Label(self.root, text="状态: 未打开装备栏", fg="#F1C40F", bg="#2C3E50",
                                     font=("Arial", 10))
        self.status_label.pack(pady=5)

        # 阈值调节框架
        thresh_frame = tk.LabelFrame(self.root, text="匹配阈值调节", bg="#34495E", fg="white", font=("Arial", 10, "bold"))
        thresh_frame.pack(fill="x", padx=10, pady=5)
        frame_name = tk.Frame(thresh_frame, bg="#34495E")
        frame_name.pack(fill="x", padx=5, pady=2)
        tk.Label(frame_name, text="武器名阈值:", bg="#34495E", fg="white").pack(side="left")
        self.name_thresh_var = tk.DoubleVar(value=0.55)
        self.name_thresh_slider = tk.Scale(frame_name, from_=0.3, to=0.9, resolution=0.01,
                                           orient=tk.HORIZONTAL, variable=self.name_thresh_var,
                                           command=self.on_thresh_change, length=200)
        self.name_thresh_slider.pack(side="left", padx=10)
        frame_attach = tk.Frame(thresh_frame, bg="#34495E")
        frame_attach.pack(fill="x", padx=5, pady=2)
        tk.Label(frame_attach, text="配件阈值:", bg="#34495E", fg="white").pack(side="left")
        self.attach_thresh_var = tk.DoubleVar(value=0.85)
        self.attach_thresh_slider = tk.Scale(frame_attach, from_=0.5, to=0.95, resolution=0.01,
                                             orient=tk.HORIZONTAL, variable=self.attach_thresh_var,
                                             command=self.on_thresh_change, length=200)
        self.attach_thresh_slider.pack(side="left", padx=10)

        # 武器1/2显示区域
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

        # 控制按钮
        btn_frame = tk.Frame(self.root, bg="#2C3E50")
        btn_frame.pack(pady=10)
        self.btn_enable = tk.Button(btn_frame, text="禁用识别", command=self.toggle_detector,
                                    bg="#E74C3C", fg="white", font=("Microsoft YaHei", 10))
        self.btn_enable.pack(side="left", padx=5)
        self.btn_test = tk.Button(btn_frame, text="模拟 Tab 按下", command=self.simulate_tab,
                                  bg="#3498DB", fg="white", font=("Microsoft YaHei", 10))
        self.btn_test.pack(side="left", padx=5)
        self.btn_debug = tk.Button(btn_frame, text="开启调试窗口", command=self.toggle_debug_window,
                                   bg="#8E44AD", fg="white", font=("Microsoft YaHei", 10))
        self.btn_debug.pack(side="left", padx=5)
        # 显示匹配分数按钮（使用 TM_CCOEFF_NORMED）
        self.btn_scores = tk.Button(btn_frame, text="显示匹配分数 (CCOEFF)", command=self.show_match_scores,
                                    bg="#27AE60", fg="white", font=("Microsoft YaHei", 10))
        self.btn_scores.pack(side="left", padx=5)

        tk.Label(self.root, text="快捷键: Tab (全局监听) | 调试窗口按 'q' 关闭",
                 fg="#BDC3C7", bg="#2C3E50", font=("Arial", 9)).pack(pady=10)

    def on_thresh_change(self, val):
        self.detector.thresholds["names"] = self.name_thresh_var.get()
        self.detector.thresholds["scopes"] = self.attach_thresh_var.get()
        self.detector.thresholds["grips"] = self.attach_thresh_var.get()
        self.detector.thresholds["muzzles"] = self.attach_thresh_var.get()
        self.detector.thresholds["stocks"] = self.attach_thresh_var.get()

    def toggle_debug_window(self):
        if not self.debug_running:
            self.debug_running = True
            self.debug_thread = threading.Thread(target=self._debug_display_loop, daemon=True)
            self.debug_thread.start()
            self.btn_debug.config(text="关闭调试窗口", bg="#E74C3C")
        else:
            self.debug_running = False
            cv2.destroyWindow(self.debug_win_name)
            self.btn_debug.config(text="开启调试窗口", bg="#8E44AD")

    def _debug_display_loop(self):
        with mss.mss() as sct:
            categories = {
                "weapon1_name": "weapon1_name_region",
                "weapon1_scope": "weapon1_scope_region",
                "weapon1_grip": "weapon1_grip_region",
                "weapon1_stock": "weapon1_stock_region",   # 新增
                "weapon2_name": "weapon2_name_region",
                "weapon2_scope": "weapon2_scope_region",
                "weapon2_grip": "weapon2_grip_region",
                "weapon2_stock": "weapon2_stock_region",   # 新增
            }
            while self.debug_running:
                for name, region_key in categories.items():
                    rect = self.rm.get_real_region(region_key)
                    if not rect:
                        continue
                    img = sct.grab(rect)
                    img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
                    base_region = self.rm.get_templates_region(region_key)
                    if base_region:
                        img_resized = cv2.resize(img_bgr, (base_region["width"], base_region["height"]))
                    else:
                        img_resized = img_bgr
                    cv2.imshow(f"Debug: {name}", img_resized)
                cv2.waitKey(1)
                time.sleep(0.1)
            cv2.destroyAllWindows()

    def show_match_scores(self):
        """计算当前所有配件槽与所有模板的匹配分数（使用 TM_CCOEFF_NORMED）并显示在新窗口"""
        win = tk.Toplevel(self.root)
        win.title("模板匹配分数详情 (TM_CCOEFF_NORMED)")
        win.geometry("600x500")
        win.attributes("-topmost", True)
        text = tk.Text(win, wrap=tk.WORD, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True)

        with mss.mss() as sct:
            slots = [
                (1, "scope", "weapon1_scope_region", self.detector.templates["scopes"]),
                (1, "grip", "weapon1_grip_region", self.detector.templates["grips"]),
                (1, "muzzle", "weapon1_muzzle_region", self.detector.templates["muzzles"]),
                (1, "stock", "weapon1_stock_region", self.detector.templates["stocks"]),
                (2, "scope", "weapon2_scope_region", self.detector.templates["scopes"]),
                (2, "grip", "weapon2_grip_region", self.detector.templates["grips"]),
                (2, "muzzle", "weapon2_muzzle_region", self.detector.templates["muzzles"]),
                (2, "stock", "weapon2_stock_region", self.detector.templates["stocks"]),
            ]

            for weapon_slot, part_name, region_key, templates_dict in slots:
                rect = self.rm.get_real_region(region_key)
                if not rect or not templates_dict:
                    continue
                img = sct.grab(rect)
                img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
                img_resized = self.detector._resize_to_base(img_bgr, region_key)
                if img_resized is None:
                    continue
                text.insert(tk.END, f"\n=== 武器{weapon_slot} {part_name} ===\n")
                for name, tpl_list in templates_dict.items():
                    for item in tpl_list:
                        tpl_bgr = item["bgr"]
                        mask = item["mask"]
                        if tpl_bgr.shape[0] > img_resized.shape[0] or tpl_bgr.shape[1] > img_resized.shape[1]:
                            continue
                        # 使用 TM_CCOEFF_NORMED
                        res = cv2.matchTemplate(img_resized, tpl_bgr, cv2.TM_CCOEFF_NORMED, mask=mask)
                        _, max_val, _, _ = cv2.minMaxLoc(res)
                        text.insert(tk.END, f"{name}: {max_val:.3f}\n")
                text.insert(tk.END, "-"*50 + "\n")
            text.insert(tk.END, "\n说明：分数为 TM_CCOEFF_NORMED 匹配结果，越接近1越相似。")

    def on_equipment_update(self, is_open, weapons):
        self.is_open = is_open
        self.weapons_data = weapons
        self.root.after(0, self.update_ui)

    def on_status_change(self, status):
        self.root.after(0, lambda: self.status_label.config(text=f"状态: {status}", fg="#F39C12"))

    def update_ui(self):
        if self.is_open:
            self.status_label.config(text="状态: 装备栏已打开", fg="#2ECC71")
        else:
            self.status_label.config(text="状态: 装备栏未打开", fg="#E74C3C")

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
                if key == keyboard.Key.f5:
                    self.save_debug_screenshots()
            except:
                pass
        self.keyboard_listener = keyboard.Listener(on_press=on_press)
        self.keyboard_listener.start()
        self.listener_running = True

    def save_debug_screenshots(self):
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        save_dir = "debug_screenshots"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        regions = [
            "weapon1_name_region", "weapon1_scope_region", "weapon1_grip_region",
            "weapon1_muzzle_region", "weapon1_stock_region",
            "weapon2_name_region", "weapon2_scope_region", "weapon2_grip_region",
            "weapon2_muzzle_region", "weapon2_stock_region"
        ]
        with mss.mss() as sct:
            for reg in regions:
                rect = self.rm.get_real_region(reg)
                if rect:
                    img = sct.grab(rect)
                    img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
                    cv2.imwrite(os.path.join(save_dir, f"{reg}_{timestamp}.png"), img_bgr)
        print(f"已保存截图到 {save_dir}")

    def on_closing(self):
        if self.listener_running:
            self.keyboard_listener.stop()
        self.detector.set_enabled(False)
        self.debug_running = False
        cv2.destroyAllWindows()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = EquipmentDetectorTester(root)
    root.mainloop()