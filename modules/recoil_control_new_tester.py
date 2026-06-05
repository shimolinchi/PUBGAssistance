import tkinter as tk
from tkinter import ttk
import sys
import os
import json
import threading
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from recoil_control_new import RecoilControlModule
from pynput.mouse import Button

class RecoilTester:
    def __init__(self, root):
        self.root = root
        self.root.title("压枪模块测试台 (增强版)")
        self.root.geometry("520x700")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 创建压枪模块实例
        self.recoil = RecoilControlModule(config_file="config.json")

        # 获取可用列表（如果配置为空则使用硬编码示例）
        self.weapon_list = list(self.recoil.weapon_configs.keys())
        if not self.weapon_list:
            self.weapon_list = ["M416", "AKM", "SCAR-L", "M16A4"]
            # 临时设置默认武器配置，方便测试
            for w in self.weapon_list:
                if w not in self.recoil.weapon_configs:
                    self.recoil.weapon_configs[w] = {"base": 10.0, "auto_fire": False}
            self.recoil.weapon_configs["M416"]["base"] = 10.0
            self.recoil.weapon_configs["AKM"]["base"] = 12.0
            self.recoil.weapon_configs["SCAR-L"]["base"] = 10.5
            self.recoil.weapon_configs["M16A4"]["base"] = 11.0
            self.recoil.weapon_configs["M16A4"]["auto_fire"] = True

        self.scope_list = list(self.recoil.scope_multipliers.keys()) or ["hip", "red_dot", "x3", "x4", "x6"]
        self.grip_list = list(self.recoil.grip_multipliers.keys()) or ["vertical", "half", "light"]
        self.muzzle_list = list(self.recoil.muzzle_multipliers.keys()) or ["compensator", "flash_hider"]
        self.stock_list = list(self.recoil.stock_multipliers.keys()) or ["tactical"]
        self.stance_list = ["stand", "squat", "lie"]

        # 当前选择变量
        self.weapon_var = tk.StringVar(value=self.weapon_list[0] if self.weapon_list else "")
        self.scope_var = tk.StringVar(value=self.scope_list[0] if self.scope_list else "hip")
        self.grip_var = tk.StringVar(value="无")
        self.muzzle_var = tk.StringVar(value="无")
        self.stock_var = tk.StringVar(value="无")
        self.stance_var = tk.StringVar(value="stand")

        self.init_ui()
        self.on_weapon_change()
        self.on_attachment_change()

    def init_ui(self):
        # 标题
        tk.Label(self.root, text="压枪模块测试 (增强版)", fg="white", bg="#2C3E50",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        # 总开关
        self.enable_var = tk.BooleanVar(value=False)
        self.enable_check = tk.Checkbutton(self.root, text="启用压枪", variable=self.enable_var,
                                           command=self.toggle_enable, bg="#2C3E50", fg="white",
                                           selectcolor="#2C3E50", activebackground="#2C3E50")
        self.enable_check.pack(pady=5)

        # 主武器选择
        self._add_combo("武器", self.weapon_var, self.weapon_list, self.on_weapon_change)

        # 配件选择
        self._add_combo("倍镜", self.scope_var, self.scope_list, self.on_attachment_change)
        self._add_combo("握把", self.grip_var, self.grip_list, self.on_attachment_change, include_none=True)
        self._add_combo("枪口", self.muzzle_var, self.muzzle_list, self.on_attachment_change, include_none=True)
        self._add_combo("枪托", self.stock_var, self.stock_list, self.on_attachment_change, include_none=True)
        self._add_combo("姿势", self.stance_var, self.stance_list, self.on_attachment_change)

        # 当前力度显示
        frame_strength = tk.LabelFrame(self.root, text="当前压枪力度 (像素/次)", bg="#34495E", fg="white", font=("Arial", 10, "bold"))
        frame_strength.pack(fill="x", padx=10, pady=10)
        self.strength_label = tk.Label(frame_strength, text="0", fg="#F1C40F", bg="#34495E",
                                       font=("Consolas", 28, "bold"))
        self.strength_label.pack(pady=10)

        # 详细计算过程
        frame_detail = tk.LabelFrame(self.root, text="计算详情", bg="#34495E", fg="white", font=("Arial", 10, "bold"))
        frame_detail.pack(fill="both", expand=True, padx=10, pady=5)
        self.detail_text = tk.Text(frame_detail, height=10, width=60, bg="#2C3E50", fg="#BDC3C7",
                                   font=("Consolas", 9))
        self.detail_text.pack(fill="both", expand=True, padx=5, pady=5)

        # 模拟控制
        btn_frame = tk.Frame(self.root, bg="#2C3E50")
        btn_frame.pack(pady=10)
        self.simulate_btn = tk.Button(btn_frame, text="模拟开火 (左键按下3秒)", command=self.simulate_fire,
                                      bg="#E67E22", fg="white", font=("Microsoft YaHei", 10))
        self.simulate_btn.pack(side="left", padx=5)
        self.stop_btn = tk.Button(btn_frame, text="停止模拟", command=self.simulate_stop,
                                  bg="#E74C3C", fg="white", font=("Microsoft YaHei", 10))
        self.stop_btn.pack(side="left", padx=5)

        self.simulating = False
        self.simulate_timer = None

    def _add_combo(self, label, var, values, command, include_none=False):
        frame = tk.Frame(self.root, bg="#2C3E50")
        frame.pack(fill="x", padx=20, pady=5)
        tk.Label(frame, text=f"{label}:", width=8, anchor="w", bg="#2C3E50", fg="white").pack(side="left")
        if include_none:
            vals = ["无"] + values
        else:
            vals = values
        combo = ttk.Combobox(frame, textvariable=var, values=vals, state="readonly")
        combo.pack(side="left", fill="x", expand=True, padx=5)
        if include_none and var.get() == "":
            var.set("无")
        combo.bind("<<ComboboxSelected>>", lambda e: command())

    def on_weapon_change(self):
        weapon = self.weapon_var.get()
        self.recoil.update_current_weapon(weapon)
        self.update_display()

    def on_attachment_change(self):
        # 构建配件字典，忽略 "无"
        attachments = {}
        scope = self.scope_var.get()
        if scope != "hip" and scope != "无":
            attachments["scope"] = scope
        grip = self.grip_var.get()
        if grip and grip != "无":
            attachments["grip"] = grip
        muzzle = self.muzzle_var.get()
        if muzzle and muzzle != "无":
            attachments["muzzle"] = muzzle
        stock = self.stock_var.get()
        if stock and stock != "无":
            attachments["stock"] = stock
        self.recoil.update_attachments(attachments)
        stance = self.stance_var.get()
        self.recoil.update_stance(stance)
        self.update_display()

    def update_display(self):
        # 更新力度显示
        self.strength_label.config(text=str(self.recoil.current_recoil_strength))

        # 更新详细计算文本
        self.detail_text.delete(1.0, tk.END)
        weapon = self.recoil.current_weapon
        base = self.recoil.base_recoil
        scope = self.recoil.scope
        scope_mult = self.recoil.scope_multipliers.get(scope, 1.0)
        grip = self.recoil.grip
        grip_mult = self.recoil.grip_multipliers.get(grip, 1.0) if grip else 1.0
        muzzle = self.recoil.muzzle
        muzzle_mult = self.recoil.muzzle_multipliers.get(muzzle, 1.0) if muzzle else 1.0
        stock = self.recoil.stock
        stock_mult = self.recoil.stock_multipliers.get(stock, 1.0) if stock else 1.0
        stance = self.recoil.current_stance
        stance_mult = self.recoil.stance_multipliers.get(stance, 1.0)

        self.detail_text.insert(tk.END, f"武器: {weapon}\n")
        self.detail_text.insert(tk.END, f"基础力度: {base:.2f}\n\n")
        self.detail_text.insert(tk.END, f"倍镜系数 ({scope}): {scope_mult:.3f}\n")
        self.detail_text.insert(tk.END, f"握把系数 ({grip}): {grip_mult:.3f}\n")
        self.detail_text.insert(tk.END, f"枪口系数 ({muzzle}): {muzzle_mult:.3f}\n")
        self.detail_text.insert(tk.END, f"枪托系数 ({stock}): {stock_mult:.3f}\n")
        self.detail_text.insert(tk.END, f"姿势系数 ({stance}): {stance_mult:.3f}\n\n")
        raw = base * scope_mult * grip_mult * muzzle_mult * stock_mult * stance_mult
        self.detail_text.insert(tk.END, f"原始计算: {raw:.4f}\n")
        self.detail_text.insert(tk.END, f"取整后: {self.recoil.current_recoil_strength} 像素/次")

    def toggle_enable(self):
        self.recoil.set_enabled(self.enable_var.get())

    def simulate_fire(self):
        if self.simulating:
            return
        self.simulating = True
        self.simulate_btn.config(state=tk.DISABLED)
        # 模拟按下左键
        self.recoil._on_mouse_click(0, 0, Button.left, True)
        # 3秒后自动释放
        self.simulate_timer = threading.Timer(3.0, self.simulate_stop)
        self.simulate_timer.start()

    def simulate_stop(self):
        if not self.simulating:
            return
        if self.simulate_timer:
            self.simulate_timer.cancel()
            self.simulate_timer = None
        self.simulating = False
        # 释放左键
        self.recoil._on_mouse_click(0, 0, Button.left, False)
        self.simulate_btn.config(state=tk.NORMAL)

    def on_closing(self):
        self.simulate_stop()
        self.recoil.shutdown()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = RecoilTester(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()