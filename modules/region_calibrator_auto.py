import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import cv2
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from region_calibrator import RegionScalingCalibrator


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, width=120, height=32, bg="#2563EB", fg="#FFFFFF"):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, bd=0)
        self.command = command
        self.width = width
        self.height = height
        self.bg_color = bg
        self.hover_color = self._adjust_color(bg, 0.9)
        self.fg = fg
        self.enabled = True
        self.rect = self._round_rect(1, 1, width - 1, height - 1, 12, fill=self.bg_color, outline="")
        self.text_id = self.create_text(width / 2, height / 2, text=text, fill=fg, font=("Microsoft YaHei", -14, "bold"))
        self.bind("<ButtonRelease-1>", self._on_click)
        self.bind("<Enter>", lambda _e: self.itemconfig(self.rect, fill=self.hover_color if self.enabled else "#CBD5E1"))
        self.bind("<Leave>", lambda _e: self.itemconfig(self.rect, fill=self.bg_color if self.enabled else "#CBD5E1"))

    def _round_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    @staticmethod
    def _adjust_color(hex_color, factor):
        hex_color = hex_color.lstrip("#")
        r = max(0, min(255, int(int(hex_color[0:2], 16) * factor)))
        g = max(0, min(255, int(int(hex_color[2:4], 16) * factor)))
        b = max(0, min(255, int(int(hex_color[4:6], 16) * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _on_click(self, _event):
        if self.enabled and self.command:
            self.command()

    def config_state(self, enabled, text=None):
        self.enabled = enabled
        self.itemconfig(self.rect, fill=self.bg_color if enabled else "#CBD5E1")
        if text is not None:
            self.itemconfig(self.text_id, text=text)


class RegionScalingAutoCalibrator(RegionScalingCalibrator):
    """Windowed region scaling calibrator with an automatic search button."""

    def build_ui(self):
        self.root.geometry("820x560")
        self.root.minsize(780, 520)
        self.root.configure(bg="#FFFFFF")
        self.canvas_w = 260
        self.canvas_h = 90
        self.canvas_cx = self.canvas_w // 2
        self.canvas_cy = self.canvas_h // 2

        main = tk.Frame(self.root, bg="#FFFFFF")
        main.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)

        left = tk.Frame(main, bg="#FFFFFF", width=360)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        left.pack_propagate(False)

        right = tk.Frame(main, bg="#FFFFFF")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        title = tk.Label(left, text="区域缩放校准", bg="#FFFFFF", fg="#111827", font=("Microsoft YaHei", -20, "bold"))
        title.pack(anchor="w")
        subtitle = tk.Label(left, text="选择区域与模板，可手动调整，也可自动寻找 X/Y 缩放比例。",
                            bg="#FFFFFF", fg="#6B7280", font=("Microsoft YaHei", -12), wraplength=330, justify=tk.LEFT)
        subtitle.pack(anchor="w", pady=(2, 10))

        selector = self._card(left, "1. 选择校准目标")
        region_values = [rk for rk, _, _, _, _ in self.regions]
        self.region_combo = ttk.Combobox(selector, textvariable=self.current_region_key, values=region_values, state="readonly")
        self.region_combo.bind("<<ComboboxSelected>>", self.on_region_selected)
        self.region_combo.pack(fill=tk.X, padx=10, pady=(8, 4))

        self.template_combo = ttk.Combobox(selector, textvariable=self.selected_template, values=[], state="readonly")
        self.template_combo.bind("<<ComboboxSelected>>", lambda _e: self.update_display())
        self.template_combo.pack(fill=tk.X, padx=10, pady=(4, 8))

        self.info_label = tk.Label(selector, text="请选择一个区域", bg="#FFFFFF", fg="#6B7280",
                                   justify=tk.LEFT, font=("Microsoft YaHei", -12), wraplength=320)
        self.info_label.pack(fill=tk.X, padx=10, pady=(0, 8))

        size_card = self._card(left, "2. 手动缩放")
        self._size_row(size_card, "宽度", self.target_width, self.scale_percent_w, self.on_width_scale, "percent_w_label")
        self._size_row(size_card, "高度", self.target_height, self.scale_percent_h, self.on_height_scale, "percent_h_label")

        manual_buttons = tk.Frame(size_card, bg="#FFFFFF")
        manual_buttons.pack(fill=tk.X, padx=10, pady=(6, 10))
        RoundedButton(manual_buttons, "应用刷新", self.apply_custom_size, width=100, height=30, bg="#2563EB").pack(side=tk.LEFT, padx=(0, 7))
        RoundedButton(manual_buttons, "保存配置", self.save_current_config, width=100, height=30, bg="#16A34A").pack(side=tk.LEFT, padx=(0, 7))
        RoundedButton(manual_buttons, "恢复默认", self.reset_to_default, width=100, height=30, bg="#DC2626").pack(side=tk.LEFT)

        auto_frame = self._card(left, "3. 自动校准")
        params_frame = tk.Frame(auto_frame, bg="#FFFFFF")
        params_frame.pack(fill=tk.X, padx=10, pady=(8, 4))

        self.auto_min_percent = tk.DoubleVar(value=50.0)
        self.auto_max_percent = tk.DoubleVar(value=180.0)
        self.auto_coarse_step = tk.DoubleVar(value=5.0)
        self.auto_refine_step = tk.DoubleVar(value=1.0)
        self._small_entry(params_frame, "范围", self.auto_min_percent, "%")
        self._small_entry(params_frame, "至", self.auto_max_percent, "%")
        self._small_entry(params_frame, "粗", self.auto_coarse_step, "%")
        self._small_entry(params_frame, "精", self.auto_refine_step, "%")

        self.auto_btn = RoundedButton(
            auto_frame,
            "自动寻找XY缩放比例",
            self.start_auto_calibration,
            width=320,
            height=36,
            bg="#7C3AED",
        )
        self.auto_btn.pack(padx=10, pady=(6, 8))

        self.auto_result_label = tk.Label(
            auto_frame,
            text="自动校准结果: --",
            bg="#FFFFFF",
            fg="#6D28D9",
            justify=tk.LEFT,
            font=("Microsoft YaHei", -12, "bold"),
            wraplength=320,
        )
        self.auto_result_label.pack(fill=tk.X, padx=10, pady=(0, 8))

        result_card = self._card(left, "4. 匹配分数")
        self.selected_score_label = tk.Label(result_card, text="当前模板分数: --", bg="#FFFFFF", fg="#EA580C",
                                             font=("Microsoft YaHei", -12, "bold"), anchor="w")
        self.selected_score_label.pack(fill=tk.X, padx=10, pady=(8, 2))
        self.best_score_label = tk.Label(result_card, text="全局最佳匹配: --", bg="#FFFFFF", fg="#16A34A",
                                         font=("Microsoft YaHei", -12, "bold"), anchor="w")
        self.best_score_label.pack(fill=tk.X, padx=10, pady=(0, 8))

        guide = tk.Label(
            right,
            text="说明：模板约 160x50，截图区域只需略大于模板。自动校准会搜索 X/Y 缩放比例，完成后请观察预览与分数，再保存配置。",
            bg="#FFFFFF",
            fg="#6B7280",
            font=("Microsoft YaHei", -12),
            wraplength=410,
            justify=tk.LEFT,
        )
        guide.pack(fill=tk.X, pady=(0, 8))

        self.orig_canvas = self._preview_card(right, "原始截图")
        self.scaled_canvas = self._preview_card(right, "缩放后截图")
        self.template_canvas = self._preview_card(right, "当前模板")

    def _card(self, parent, title):
        frame = tk.LabelFrame(parent, text=f" {title} ", bg="#FFFFFF", fg="#111827",
                              font=("Microsoft YaHei", -13, "bold"), bd=1, relief=tk.SOLID,
                              highlightbackground="#E5E7EB")
        frame.pack(fill=tk.X, pady=(0, 8))
        return frame

    def _preview_card(self, parent, title):
        frame = tk.LabelFrame(parent, text=f" {title} ", bg="#FFFFFF", fg="#111827",
                              font=("Microsoft YaHei", -13, "bold"), bd=1, relief=tk.SOLID)
        frame.pack(fill=tk.X, pady=(0, 8))
        canvas = tk.Canvas(frame, bg="#F8FAFC", width=self.canvas_w, height=self.canvas_h,
                           highlightthickness=1, highlightbackground="#E5E7EB")
        canvas.pack(padx=10, pady=8)
        return canvas

    def _size_row(self, parent, label, var, scale_var, command, percent_attr):
        row = tk.Frame(parent, bg="#FFFFFF")
        row.pack(fill=tk.X, padx=10, pady=(8, 0))
        tk.Label(row, text=label, width=4, anchor="w", bg="#FFFFFF", fg="#374151",
                 font=("Microsoft YaHei", -12)).pack(side=tk.LEFT)
        tk.Entry(row, textvariable=var, width=5, bg="#F9FAFB", relief=tk.FLAT,
                 font=("Consolas", -12)).pack(side=tk.LEFT, padx=(0, 6))
        slider = tk.Scale(row, from_=10, to=300, orient=tk.HORIZONTAL, variable=scale_var, command=command,
                          length=180, bg="#FFFFFF", highlightthickness=0, troughcolor="#E5E7EB",
                          showvalue=False)
        slider.pack(side=tk.LEFT)
        percent_label = tk.Label(row, text="100%", width=6, bg="#FFFFFF", fg="#2563EB",
                                 font=("Consolas", -12, "bold"))
        percent_label.pack(side=tk.LEFT, padx=(4, 0))
        setattr(self, percent_attr, percent_label)

    def _small_entry(self, parent, label, var, suffix):
        group = tk.Frame(parent, bg="#FFFFFF")
        group.pack(side=tk.LEFT, padx=(0, 7))
        tk.Label(group, text=label, bg="#FFFFFF", fg="#374151", font=("Microsoft YaHei", -11)).pack(side=tk.LEFT)
        tk.Entry(group, textvariable=var, width=4, bg="#F9FAFB", relief=tk.FLAT,
                 font=("Consolas", -11)).pack(side=tk.LEFT, padx=(3, 1))
        tk.Label(group, text=suffix, bg="#FFFFFF", fg="#6B7280", font=("Microsoft YaHei", -11)).pack(side=tk.LEFT)


    def start_auto_calibration(self):
        if self.current_frame is None:
            messagebox.showwarning("无法自动校准", "当前还没有截图，请先选择区域并等待预览画面刷新。")
            return
        if not self.current_region_info:
            messagebox.showwarning("无法自动校准", "请先选择要校准的区域。")
            return
        selected = self.selected_template.get()
        if selected not in self.templates:
            messagebox.showwarning("无法自动校准", "请先选择一个有效模板。")
            return
        if self.base_w <= 0 or self.base_h <= 0:
            messagebox.showwarning("无法自动校准", "模板基准尺寸无效。")
            return

        try:
            min_scale = self.auto_min_percent.get() / 100.0
            max_scale = self.auto_max_percent.get() / 100.0
            coarse_step = self.auto_coarse_step.get() / 100.0
            refine_step = self.auto_refine_step.get() / 100.0
        except Exception:
            messagebox.showwarning("参数错误", "自动校准参数必须是数字。")
            return

        if min_scale <= 0 or max_scale <= min_scale or coarse_step <= 0 or refine_step <= 0:
            messagebox.showwarning("参数错误", "请检查搜索范围和步长。")
            return

        preprocess_func = self.current_region_info[4]
        template = self.templates[selected].copy()
        frames = [self.current_frame.copy()]

        self.auto_btn.config_state(False, "自动校准中...")
        self.auto_result_label.config(text="自动校准结果: 正在搜索，请稍候...")

        worker = threading.Thread(
            target=self._auto_calibration_worker,
            args=(frames, template, selected, preprocess_func, min_scale, max_scale, coarse_step, refine_step),
            daemon=True,
        )
        worker.start()

    def _auto_calibration_worker(self, frames, template, selected, preprocess_func,
                                 min_scale, max_scale, coarse_step, refine_step):
        try:
            best = self._search_best_size(
                frames,
                template,
                preprocess_func,
                min_scale,
                max_scale,
                coarse_step,
                refine_step,
            )
            self.root.after(0, self._apply_auto_result, best, selected)
        except Exception as e:
            self.root.after(0, self._auto_failed, str(e))

    def _search_best_size(self, frames, template, preprocess_func, min_scale, max_scale, coarse_step, refine_step):
        best = self._search_grid(frames, template, preprocess_func, min_scale, max_scale, coarse_step)

        refine_min_w = max(min_scale, best["scale_w"] - coarse_step)
        refine_max_w = min(max_scale, best["scale_w"] + coarse_step)
        refine_min_h = max(min_scale, best["scale_h"] - coarse_step)
        refine_max_h = min(max_scale, best["scale_h"] + coarse_step)

        return self._search_grid(
            frames,
            template,
            preprocess_func,
            refine_min_w,
            refine_max_w,
            refine_step,
            refine_min_h,
            refine_max_h,
        )

    def _search_grid(self, frames, template, preprocess_func, min_scale_w, max_scale_w, step,
                     min_scale_h=None, max_scale_h=None):
        if min_scale_h is None:
            min_scale_h = min_scale_w
        if max_scale_h is None:
            max_scale_h = max_scale_w

        best = {
            "score": -1.0,
            "width": self.base_w,
            "height": self.base_h,
            "scale_w": 1.0,
            "scale_h": 1.0,
        }
        seen_sizes = set()

        sw = min_scale_w
        while sw <= max_scale_w + 1e-9:
            target_w = max(1, int(round(self.base_w * sw)))
            sh = min_scale_h
            while sh <= max_scale_h + 1e-9:
                target_h = max(1, int(round(self.base_h * sh)))
                size_key = (target_w, target_h)
                if size_key not in seen_sizes:
                    seen_sizes.add(size_key)
                    score = self._score_size(frames, template, preprocess_func, target_w, target_h)
                    if score > best["score"]:
                        best = {
                            "score": score,
                            "width": target_w,
                            "height": target_h,
                            "scale_w": target_w / self.base_w,
                            "scale_h": target_h / self.base_h,
                        }
                sh += step
            sw += step

        return best

    def _score_size(self, frames, template, preprocess_func, target_w, target_h):
        scores = []
        for frame in frames:
            scaled = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            processed = preprocess_func(scaled)
            if template.shape[0] > processed.shape[0] or template.shape[1] > processed.shape[1]:
                scores.append(0.0)
                continue
            method = cv2.TM_CCOEFF_NORMED if preprocess_func == self.preprocess_name else cv2.TM_CCORR_NORMED
            res = cv2.matchTemplate(processed, template, method)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if not np.isfinite(max_val):
                max_val = 0.0
            scores.append(float(max_val))
        return float(np.mean(scores)) if scores else 0.0

    def _apply_auto_result(self, best, selected):
        self.target_width.set(best["width"])
        self.target_height.set(best["height"])
        self.scale_percent_w.set(best["scale_w"] * 100)
        self.scale_percent_h.set(best["scale_h"] * 100)
        self.percent_w_label.config(text=f"{best['scale_w'] * 100:.1f}%")
        self.percent_h_label.config(text=f"{best['scale_h'] * 100:.1f}%")
        self.auto_result_label.config(
            text=(
                f"自动校准结果: {best['width']}x{best['height']}\n"
                f"模板: {selected}  分数: {best['score']:.4f}  "
                f"缩放: {best['scale_w'] * 100:.1f}% x {best['scale_h'] * 100:.1f}%"
            )
        )
        self.auto_btn.config_state(True, "自动寻找XY缩放比例")
        self.update_display()

    def _auto_failed(self, error):
        self.auto_result_label.config(text=f"自动校准结果: 失败 - {error}")
        self.auto_btn.config_state(True, "自动寻找XY缩放比例")
        messagebox.showerror("自动校准失败", error)


if __name__ == "__main__":
    import ctypes

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

    root = tk.Tk()
    app = RegionScalingAutoCalibrator(root)
    root.mainloop()
