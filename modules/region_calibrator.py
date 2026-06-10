import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import cv2
import numpy as np
import mss
import threading
import time
import json
from PIL import Image, ImageTk

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from region_manager import RegionManager


class RegionScalingCalibrator:
    def __init__(self, root):
        self.root = root
        self.root.title("区域缩放校准器 - 武器/名称/姿势")
        # 调整窗口长宽比例，适应右侧纵向三列布局
        self.root.geometry("1000x900")
        self.root.attributes("-topmost", True)
        # 换用现代化的浅灰白背景
        self.root.configure(bg="#F5F6FA")

        self.rm = RegionManager(self.root, config_file="config.json")

        self.regions = [
            ("weapon_region", "武器图标区域", "weapon_region",
             "templates/weapons", self.preprocess_weapon),
            ("weapon1_name_region", "主武器1名称区域", "weapon1_name_region",
             "templates/equipments/names", self.preprocess_name),
            ("weapon2_name_region", "主武器2名称区域", "weapon2_name_region",
             "templates/equipments/names", self.preprocess_name),
            ("stance_region", "姿势区域", "stance_region",
             "templates/gestures", self.preprocess_weapon),
        ]

        self.current_region_key = tk.StringVar()
        self.current_region_info = None
        self.template_names = []
        self.templates = {}               
        self.selected_template = tk.StringVar()

        self.base_w = 0      
        self.base_h = 0      
        self.real_region_rect = None

        self.config_file = "config.json"
        self.target_sizes = {}            
        self.load_all_configs()

        self.target_width = tk.IntVar()
        self.target_height = tk.IntVar()
        self.scale_percent_w = tk.DoubleVar(value=100.0)
        self.scale_percent_h = tk.DoubleVar(value=100.0)

        self.current_frame = None
        self.stop_flag = False
        self.capture_thread = None

        # 预览图画布中心和尺寸设置
        self.canvas_w = 480
        self.canvas_h = 240
        self.canvas_cx = self.canvas_w // 2
        self.canvas_cy = self.canvas_h // 2

        self.build_ui()
        self.load_region_list()
        self.start_capture()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    @staticmethod
    def preprocess_weapon(img_bgr):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = np.ones((2, 2), np.uint8)
        edges_dilated = cv2.dilate(edges, kernel, iterations=1)
        return edges_dilated

    @staticmethod
    def preprocess_name(img_bgr):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        return blurred

    def load_all_configs(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    scaling = config.get("region_scaling_settings", {})
                    for rk, _, _, _, _ in self.regions:
                        if rk in scaling:
                            self.target_sizes[rk] = scaling[rk]
                            print(f"[校准器] 加载 {rk} 配置: {scaling[rk]}")
            except Exception as e:
                print(f"[校准器] 读取配置失败: {e}")

    def save_current_config(self):
        region_key = self.current_region_key.get()
        if not region_key:
            return
        config = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        if "region_scaling_settings" not in config:
            config["region_scaling_settings"] = {}
        config["region_scaling_settings"][region_key] = {
            "width": self.target_width.get(),
            "height": self.target_height.get()
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self.target_sizes[region_key] = {"width": self.target_width.get(), "height": self.target_height.get()}
            messagebox.showinfo("保存成功", f"{region_key} 缩放尺寸已保存: {self.target_width.get()}x{self.target_height.get()}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def load_templates_for_region(self, templates_dir, preprocess_func):
        self.templates.clear()
        self.template_names = []

        if not os.path.exists(templates_dir):
            print(f"[校准器] 模板目录不存在: {templates_dir}")
            return

        for item_name in os.listdir(templates_dir):
            item_path = os.path.join(templates_dir, item_name)
            if not os.path.isdir(item_path):
                if item_name.lower().endswith(".png"):
                    self._load_single_template(item_path, item_name[:-4], preprocess_func)
                continue
            for filename in os.listdir(item_path):
                if not filename.lower().endswith(".png"):
                    continue
                file_path = os.path.join(item_path, filename)
                self._load_single_template(file_path, item_name, preprocess_func)

        if self.templates:
            self.template_names = list(self.templates.keys())
            self.selected_template.set(self.template_names[0])
            first_tpl = self.templates[self.template_names[0]]
            self.base_w = first_tpl.shape[1]
            self.base_h = first_tpl.shape[0]
            print(f"[校准器] 模板基准尺寸: {self.base_w}x{self.base_h}")
        else:
            self.selected_template.set("")
            self.base_w = 0
            self.base_h = 0

    def _load_single_template(self, file_path, template_key, preprocess_func):
        img = cv2.imread(file_path, cv2.IMREAD_COLOR)
        if img is None:
            return
        processed = preprocess_func(img)
        self.templates[template_key] = processed

    def build_ui(self):
        # 左侧控制面板，加宽以便容纳更长的滑块
        control_frame = tk.Frame(self.root, bg="#F5F6FA", width=460)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=15, pady=15)
        control_frame.pack_propagate(False) # 固定宽度

        # 区域选择
        region_selector_frame = tk.LabelFrame(control_frame, text=" 选择要校准的区域 ", bg="#FFFFFF", fg="#2C3E50", font=("Microsoft YaHei", 10, "bold"))
        region_selector_frame.pack(fill=tk.X, pady=8)
        region_values = [rk for rk, _, _, _, _ in self.regions]
        self.region_combo = ttk.Combobox(region_selector_frame, textvariable=self.current_region_key,
                                         values=region_values, state="readonly")
        self.region_combo.pack(fill=tk.X, padx=10, pady=10)
        self.region_combo.bind("<<ComboboxSelected>>", self.on_region_selected)

        self.info_label = tk.Label(control_frame, text="请选择一个区域", bg="#F5F6FA", fg="#7F8C8D", justify=tk.LEFT, font=("Microsoft YaHei", 9))
        self.info_label.pack(fill=tk.X, pady=5)

        # 模板选择
        template_frame = tk.LabelFrame(control_frame, text=" 选择模板（用于计算匹配率） ", bg="#FFFFFF", fg="#2C3E50", font=("Microsoft YaHei", 10, "bold"))
        template_frame.pack(fill=tk.X, pady=8)
        self.template_combo = ttk.Combobox(template_frame, textvariable=self.selected_template, values=[], state="readonly")
        self.template_combo.pack(fill=tk.X, padx=10, pady=10)
        self.template_combo.bind("<<ComboboxSelected>>", lambda e: self.update_display())

        # 缩放设置
        size_frame = tk.LabelFrame(control_frame, text=" 缩放目标尺寸设置 ", bg="#FFFFFF", fg="#2C3E50", font=("Microsoft YaHei", 10, "bold"))
        size_frame.pack(fill=tk.X, pady=8)

        # 宽度控制
        w_frame = tk.Frame(size_frame, bg="#FFFFFF")
        w_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(w_frame, text="宽度:", bg="#FFFFFF", fg="#2C3E50", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.width_entry = tk.Entry(w_frame, textvariable=self.target_width, width=6)
        self.width_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(w_frame, text="百分比:", bg="#FFFFFF", fg="#2C3E50", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(10, 5))
        # 加长滑块 (length=220)
        self.w_slider = tk.Scale(w_frame, from_=10, to=300, orient=tk.HORIZONTAL,
                                 variable=self.scale_percent_w, command=self.on_width_scale, 
                                 length=220, bg="#FFFFFF", highlightthickness=0, troughcolor="#E0E6ED")
        self.w_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.percent_w_label = tk.Label(w_frame, text="100%", bg="#FFFFFF", fg="#3498DB", width=6, font=("Microsoft YaHei", 9, "bold"))
        self.percent_w_label.pack(side=tk.LEFT)

        # 高度控制
        h_frame = tk.Frame(size_frame, bg="#FFFFFF")
        h_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(h_frame, text="高度:", bg="#FFFFFF", fg="#2C3E50", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.height_entry = tk.Entry(h_frame, textvariable=self.target_height, width=6)
        self.height_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(h_frame, text="百分比:", bg="#FFFFFF", fg="#2C3E50", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(10, 5))
        # 加长滑块 (length=220)
        self.h_slider = tk.Scale(h_frame, from_=10, to=300, orient=tk.HORIZONTAL,
                                 variable=self.scale_percent_h, command=self.on_height_scale,
                                 length=220, bg="#FFFFFF", highlightthickness=0, troughcolor="#E0E6ED")
        self.h_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.percent_h_label = tk.Label(h_frame, text="100%", bg="#FFFFFF", fg="#3498DB", width=6, font=("Microsoft YaHei", 9, "bold"))
        self.percent_h_label.pack(side=tk.LEFT)

        btn_frame = tk.Frame(size_frame, bg="#FFFFFF")
        btn_frame.pack(fill=tk.X, pady=10, padx=10)
        tk.Button(btn_frame, text="应用刷新", command=self.apply_custom_size, bg="#3498DB", fg="white", font=("Microsoft YaHei", 9), relief=tk.FLAT).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(btn_frame, text="保存配置", command=self.save_current_config, bg="#2ECC71", fg="white", font=("Microsoft YaHei", 9), relief=tk.FLAT).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(btn_frame, text="恢复默认", command=self.reset_to_default, bg="#E74C3C", fg="white", font=("Microsoft YaHei", 9), relief=tk.FLAT).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # 匹配结果
        result_frame = tk.LabelFrame(control_frame, text=" 实时匹配结果 ", bg="#FFFFFF", fg="#2C3E50", font=("Microsoft YaHei", 10, "bold"))
        result_frame.pack(fill=tk.X, pady=8)
        self.selected_score_label = tk.Label(result_frame, text="当前模板分数: --", bg="#FFFFFF", fg="#E67E22", font=("Microsoft YaHei", 10, "bold"))
        self.selected_score_label.pack(anchor="w", padx=15, pady=5)
        self.best_score_label = tk.Label(result_frame, text="全局最佳匹配: --", bg="#FFFFFF", fg="#27AE60", font=("Microsoft YaHei", 10, "bold"))
        self.best_score_label.pack(anchor="w", padx=15, pady=(0, 10))

        # 图像显示区域（右侧，纵向三列布局）
        image_frame = tk.Frame(self.root, bg="#F5F6FA")
        image_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 原始截图 (置于顶部)
        orig_frame = tk.LabelFrame(image_frame, text=" 原始截图 (实际分辨率) ", bg="#FFFFFF", fg="#2C3E50", font=("Microsoft YaHei", 10, "bold"))
        orig_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)
        self.orig_canvas = tk.Canvas(orig_frame, bg="#EAECEE", width=self.canvas_w, height=self.canvas_h, highlightthickness=0)
        self.orig_canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 缩放后截图 (置于中间)
        scaled_frame = tk.LabelFrame(image_frame, text=" 缩放后截图 (用于匹配) ", bg="#FFFFFF", fg="#2C3E50", font=("Microsoft YaHei", 10, "bold"))
        scaled_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)
        self.scaled_canvas = tk.Canvas(scaled_frame, bg="#EAECEE", width=self.canvas_w, height=self.canvas_h, highlightthickness=0)
        self.scaled_canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 模板图片显示 (置于底部)
        template_frame_img = tk.LabelFrame(image_frame, text=" 当前模板 (预处理后) ", bg="#FFFFFF", fg="#2C3E50", font=("Microsoft YaHei", 10, "bold"))
        template_frame_img.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)
        self.template_canvas = tk.Canvas(template_frame_img, bg="#EAECEE", width=self.canvas_w, height=self.canvas_h, highlightthickness=0)
        self.template_canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def on_width_scale(self, val):
        if self.base_w > 0:
            percent = float(val) / 100.0
            new_w = int(self.base_w * percent)
            self.target_width.set(new_w)
            self.percent_w_label.config(text=f"{percent*100:.1f}%")
            self.update_display()

    def on_height_scale(self, val):
        if self.base_h > 0:
            percent = float(val) / 100.0
            new_h = int(self.base_h * percent)
            self.target_height.set(new_h)
            self.percent_h_label.config(text=f"{percent*100:.1f}%")
            self.update_display()

    def on_size_entry_changed(self, *args):
        try:
            w = self.target_width.get()
            if self.base_w > 0:
                percent_w = (w / self.base_w) * 100
                self.scale_percent_w.set(percent_w)
                self.percent_w_label.config(text=f"{percent_w:.1f}%")
        except:
            pass
        try:
            h = self.target_height.get()
            if self.base_h > 0:
                percent_h = (h / self.base_h) * 100
                self.scale_percent_h.set(percent_h)
                self.percent_h_label.config(text=f"{percent_h:.1f}%")
        except:
            pass

    def reset_to_default(self):
        if self.base_w > 0 and self.base_h > 0:
            self.target_width.set(self.base_w)
            self.target_height.set(self.base_h)
            self.scale_percent_w.set(100.0)
            self.scale_percent_h.set(100.0)
            self.percent_w_label.config(text="100.0%")
            self.percent_h_label.config(text="100.0%")
            self.update_display()

    def apply_custom_size(self):
        self.update_display()

    def on_region_selected(self, event=None):
        region_key = self.current_region_key.get()
        for rk, name, real_key, templates_dir, preprocess_func in self.regions:
            if rk == region_key:
                self.current_region_info = (rk, name, real_key, templates_dir, preprocess_func)
                break
        if not self.current_region_info:
            return

        self.real_region_rect = self.rm.get_real_region(self.current_region_info[2])
        if not self.real_region_rect:
            messagebox.showerror("错误", f"请先校准实际区域 {self.current_region_info[2]}！")
            return

        self.load_templates_for_region(self.current_region_info[3], self.current_region_info[4])

        if not self.templates:
            messagebox.showerror("错误", f"未找到任何模板文件，请检查目录 {self.current_region_info[3]}")
            return

        if region_key in self.target_sizes:
            w = self.target_sizes[region_key]["width"]
            h = self.target_sizes[region_key]["height"]
        else:
            w = self.base_w
            h = self.base_h
        self.target_width.set(w)
        self.target_height.set(h)
        self.scale_percent_w.set((w / self.base_w) * 100)
        self.scale_percent_h.set((h / self.base_h) * 100)
        self.percent_w_label.config(text=f"{self.scale_percent_w.get():.1f}%")
        self.percent_h_label.config(text=f"{self.scale_percent_h.get():.1f}%")

        self.info_label.config(text=f"当前区域: {self.current_region_info[1]}\n模板基准尺寸: {self.base_w}x{self.base_h}\n实际截图区域: {self.real_region_rect['width']}x{self.real_region_rect['height']}")
        self.template_combo.config(values=self.template_names)
        if self.template_names:
            self.selected_template.set(self.template_names[0])
        self.update_display()

    def start_capture(self):
        self.stop_flag = False
        self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.capture_thread.start()

    def capture_loop(self):
        with mss.MSS() as sct:
            while not self.stop_flag:
                if self.real_region_rect:
                    try:
                        screenshot = sct.grab(self.real_region_rect)
                        img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
                        self.current_frame = img_bgr
                        self.root.after(0, self.update_display)
                    except Exception as e:
                        pass
                time.sleep(0.05)

    def update_display(self):
        if self.current_frame is None:
            return

        # 1. 显示原始截图
        orig_pil = Image.fromarray(cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB))
        orig_pil.thumbnail((self.canvas_w, self.canvas_h))
        orig_tk = ImageTk.PhotoImage(orig_pil)
        self.orig_canvas.delete("all")
        self.orig_canvas.create_image(self.canvas_cx, self.canvas_cy, image=orig_tk, anchor="center")
        self.orig_canvas.image = orig_tk

        # 2. 缩放截图
        target_w = self.target_width.get()
        target_h = self.target_height.get()
        if target_w <= 0 or target_h <= 0:
            return
        scaled = cv2.resize(self.current_frame, (target_w, target_h))
        scaled_pil = Image.fromarray(cv2.cvtColor(scaled, cv2.COLOR_BGR2RGB))
        scaled_pil.thumbnail((self.canvas_w, self.canvas_h))
        scaled_tk = ImageTk.PhotoImage(scaled_pil)
        self.scaled_canvas.delete("all")
        self.scaled_canvas.create_image(self.canvas_cx, self.canvas_cy, image=scaled_tk, anchor="center")
        self.scaled_canvas.image = scaled_tk

        # 3. 显示当前模板图片
        preprocess_func = self.current_region_info[4] if self.current_region_info else None
        selected = self.selected_template.get()
        if preprocess_func and selected in self.templates:
            tpl_img = self.templates[selected]
            if len(tpl_img.shape) == 2:
                tpl_display = cv2.cvtColor(tpl_img, cv2.COLOR_GRAY2BGR)
            else:
                tpl_display = tpl_img.copy()
            tpl_pil = Image.fromarray(cv2.cvtColor(tpl_display, cv2.COLOR_BGR2RGB))
            tpl_pil.thumbnail((self.canvas_w, self.canvas_h))
            tpl_tk = ImageTk.PhotoImage(tpl_pil)
            self.template_canvas.delete("all")
            self.template_canvas.create_image(self.canvas_cx, self.canvas_cy, image=tpl_tk, anchor="center")
            self.template_canvas.image = tpl_tk
        else:
            self.template_canvas.delete("all")
            self.template_canvas.create_text(self.canvas_cx, self.canvas_cy, text="未选择模板", fill="#7F8C8D", font=("Microsoft YaHei", 12))

        # 4. 匹配计算
        if preprocess_func is None or not self.templates:
            self.selected_score_label.config(text="当前模板分数: --")
            self.best_score_label.config(text="全局最佳匹配: --")
            return

        processed_frame = preprocess_func(scaled)

        # 当前模板分数
        selected_score = 0.0
        if selected in self.templates:
            tpl = self.templates[selected]
            if tpl.shape[0] <= processed_frame.shape[0] and tpl.shape[1] <= processed_frame.shape[1]:
                method = cv2.TM_CCOEFF_NORMED if preprocess_func == self.preprocess_name else cv2.TM_CCORR_NORMED
                res = cv2.matchTemplate(processed_frame, tpl, method)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                selected_score = max_val
        self.selected_score_label.config(text=f"当前模板 [{selected}] 分数: {selected_score:.3f}")

        # 全局最佳
        best_score = 0.0
        best_name = ""
        for name, tpl in self.templates.items():
            if tpl.shape[0] <= processed_frame.shape[0] and tpl.shape[1] <= processed_frame.shape[1]:
                method = cv2.TM_CCOEFF_NORMED if preprocess_func == self.preprocess_name else cv2.TM_CCORR_NORMED
                res = cv2.matchTemplate(processed_frame, tpl, method)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                if max_val > best_score:
                    best_score = max_val
                    best_name = name
        self.best_score_label.config(text=f"全局最佳匹配: {best_name} ({best_score:.3f})")

    def load_region_list(self):
        if self.regions:
            self.current_region_key.set(self.regions[0][0])
            self.on_region_selected()

    def on_closing(self):
        self.stop_flag = True
        if self.capture_thread:
            self.capture_thread.join(timeout=1)
        self.root.destroy()


if __name__ == "__main__":
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass
    root = tk.Tk()
    app = RegionScalingCalibrator(root)
    root.mainloop()