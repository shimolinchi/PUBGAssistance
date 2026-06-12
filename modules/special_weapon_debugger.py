import json
import os
import tkinter as tk
from tkinter import ttk


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, width=112, height=30, bg="#2563EB", fg="#FFFFFF"):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, bd=0)
        self.command = command
        self.bg_color = bg
        self.hover_color = self._adjust_color(bg, 0.9)
        self.rect = self._round_rect(1, 1, width - 1, height - 1, 12, fill=bg, outline="")
        self.create_text(width / 2, height / 2, text=text, fill=fg, font=("Microsoft YaHei", -12, "bold"))
        self.bind("<ButtonRelease-1>", lambda _e: self.command() if self.command else None)
        self.bind("<Enter>", lambda _e: self.itemconfig(self.rect, fill=self.hover_color))
        self.bind("<Leave>", lambda _e: self.itemconfig(self.rect, fill=self.bg_color))

    def _round_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
                  x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
                  x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

    @staticmethod
    def _adjust_color(hex_color, factor):
        hex_color = hex_color.lstrip("#")
        r = max(0, min(255, int(int(hex_color[0:2], 16) * factor)))
        g = max(0, min(255, int(int(hex_color[2:4], 16) * factor)))
        b = max(0, min(255, int(int(hex_color[4:6], 16) * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"


class SpecialWeaponDebugger:
    WEAPON_OPTIONS = ["火箭筒", "VSS", "十字弩", "迫击炮", "投掷物", "C4"]
    LINE_COLORS = ["#2563EB", "#16A34A", "#EA580C", "#7C3AED"]

    def __init__(self, root, config_file="config.json", modules=None):
        self.root = root
        self.config_file = config_file
        self.modules = modules or {}
        self.config = {}
        self.weapon_var = tk.StringVar(value="火箭筒")
        self.status_var = tk.StringVar(value="就绪")
        self.help_var = tk.StringVar(value="")
        self.current_chart = None
        self.drag_target = None
        self.point_radius = 5
        self.chart_defs = []
        self.param_vars = {}

        self.root.title("特殊武器参数调试")
        self.root.geometry("840x500")
        self.root.minsize(800, 470)
        self.root.configure(bg="#F3F6FA")
        self.root.attributes("-topmost", True)

        self._load_config()
        self._build_ui()
        self._render_current_weapon()

    def _build_ui(self):
        main = tk.Frame(self.root, bg="#F3F6FA")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        left = tk.Frame(main, bg="#F3F6FA", width=190)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)

        right = tk.Frame(main, bg="#F3F6FA")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(left, text="特殊武器", bg="#F3F6FA", fg="#111827",
                 font=("Microsoft YaHei", -18, "bold")).pack(anchor="w", pady=(0, 4))

        selector = self._card(left, "选择武器")
        combo = ttk.Combobox(selector, textvariable=self.weapon_var, values=self.WEAPON_OPTIONS, state="readonly")
        combo.pack(fill=tk.X, padx=8, pady=7)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._render_current_weapon())

        controls = self._card(left, "操作")
        row1 = tk.Frame(controls, bg="#FFFFFF")
        row1.pack(fill=tk.X, padx=8, pady=(8, 5))
        RoundedButton(row1, "保存", self.save, width=80, height=28, bg="#2563EB").pack(side=tk.LEFT, padx=(0, 6))
        RoundedButton(row1, "重载", self.reload, width=80, height=28, bg="#7C3AED").pack(side=tk.LEFT)
        row2 = tk.Frame(controls, bg="#FFFFFF")
        row2.pack(fill=tk.X, padx=8, pady=(0, 7))
        RoundedButton(row2, "添加标点", self.add_point, width=166, height=28, bg="#0EA5E9").pack(side=tk.LEFT)
        tk.Label(controls, text="拖动点可同时改距离和数值；右键点击点删除。",
                 bg="#FFFFFF", fg="#6B7280", font=("Microsoft YaHei", -11), wraplength=165,
                 justify=tk.LEFT).pack(fill=tk.X, padx=8, pady=(0, 7))

        status = self._card(left, "状态")
        tk.Label(status, textvariable=self.status_var, bg="#FFFFFF", fg="#2563EB",
                 font=("Microsoft YaHei", -11, "bold"), wraplength=165,
                 justify=tk.LEFT).pack(fill=tk.X, padx=8, pady=(7, 3))
        tk.Label(status, textvariable=self.help_var, bg="#FFFFFF", fg="#6B7280",
                 font=("Microsoft YaHei", -10), wraplength=165,
                 justify=tk.LEFT).pack(fill=tk.X, padx=8, pady=(0, 8))

        self.right = right

    def _card(self, parent, title):
        frame = tk.LabelFrame(parent, text=f" {title} ", bg="#FFFFFF", fg="#111827",
                              font=("Microsoft YaHei", -12, "bold"), bd=1, relief=tk.SOLID,
                              highlightbackground="#E5E7EB")
        frame.pack(fill=tk.X, pady=(0, 6))
        return frame

    def _right_card(self, title):
        frame = tk.LabelFrame(self.right, text=f" {title} ", bg="#FFFFFF", fg="#111827",
                              font=("Microsoft YaHei", -12, "bold"), bd=1, relief=tk.SOLID,
                              highlightbackground="#E5E7EB")
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        return frame

    def _load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {}
        self.config.setdefault("rocket_config", {})
        self.config.setdefault("vss_config", {})
        self.config.setdefault("crossbow_config", {})
        self.config.setdefault("mortar_config", {})
        self.config.setdefault("throwables_config", {})
        self.config.setdefault("c4_config", {"target_speed": 50.0, "jump_distance_threshold": 20.0})

    def _clear_right(self):
        for child in self.right.winfo_children():
            child.destroy()
        self.chart_defs = []
        self.param_vars = {}
        self.current_chart = None
        self.drag_target = None

    def _render_current_weapon(self):
        self._clear_right()
        weapon = self.weapon_var.get()
        if weapon == "火箭筒":
            cfg = self.config["rocket_config"]
            self._create_chart_panel("火箭筒：距离 -> 归一化准星抬高高度", [self._curve_def(cfg, "calib_dists", "calib_ratios", "抬高高度")])
        elif weapon == "VSS":
            cfg = self.config["vss_config"]
            self._create_chart_panel("VSS：距离 -> 归一化下坠高度", [self._curve_def(cfg, "calib_dists", "calib_drops_ratio", "下坠高度")])
        elif weapon == "十字弩":
            cfg = self.config["crossbow_config"]
            self._create_chart_panel("十字弩：距离 -> 归一化下坠高度", [self._curve_def(cfg, "calib_dists", "calib_drops_ratio", "下坠高度")])
        elif weapon == "迫击炮":
            self._create_param_panel("迫击炮高度修正", self.config["mortar_config"], [("a_param", "上坡修正 a"), ("b_param", "下坡修正 b")])
        elif weapon == "投掷物":
            cfg = self.config["throwables_config"]
            self._create_chart_panel("投掷物 20-50m：距离 -> 准星抬高 / 瞬爆时间", [
                self._curve_def(cfg, "calib_dists", "calib_elevations_ratio", "抬高高度"),
                self._curve_def(cfg, "calib_dists", "calib_times", "瞬爆时间"),
            ])
            self._create_chart_panel("投掷物 50-80m 跳投：距离 -> 准星抬高 / 瞬爆时间", [
                self._curve_def(cfg, "jump_calib_dists", "jump_calib_elevations_ratio", "跳投抬高"),
                self._curve_def(cfg, "jump_calib_dists", "jump_calib_times", "跳投时间"),
            ])
        elif weapon == "C4":
            self._create_param_panel("C4 推荐参数", self.config["c4_config"], [("target_speed", "推荐起步速度 km/h"), ("jump_distance_threshold", "推荐跳车距离 m")])
        self.status_var.set(f"当前：{weapon}")
        self.help_var.set(self._help_text_for_weapon(weapon))

    def _help_text_for_weapon(self, weapon):
        if weapon == "火箭筒":
            return "归一化准星高度：从准星到屏幕下方标尺底端的比例，0 表示准星处，1 表示标尺底端。"
        if weapon == "VSS":
            return "归一化下坠高度：以屏幕高度为 1 的下坠比例，距离越远横线通常越低。"
        if weapon == "十字弩":
            return "归一化下坠高度：箭矢落点相对准星向下的屏幕高度比例。"
        if weapon == "投掷物":
            return "抬高高度是准星抬高位置的屏幕比例；瞬爆时间是拉环后到松开左键的等待时间。50m 以上为跳投参数。"
        if weapon == "迫击炮":
            return "a/b 是高低差距离修正系数：目标更高时用 a，目标更低时用 b。"
        if weapon == "C4":
            return "推荐起步速度用于判断何时冲向目标；推荐跳车距离表示靠近目标多少米时提示跳车。"
        return ""

    def _curve_def(self, config, x_key, y_key, label):
        config.setdefault(x_key, [])
        config.setdefault(y_key, [])
        return {"config": config, "x_key": x_key, "y_key": y_key, "label": label}

    def _create_chart_panel(self, title, curve_defs):
        frame = self._right_card(title)
        chart = tk.Canvas(frame, bg="#F8FAFC", highlightthickness=1, highlightbackground="#E5E7EB")
        chart.pack(fill=tk.BOTH, expand=True, padx=7, pady=7)
        chart.curve_defs = curve_defs
        chart.point_map = {}
        self.chart_defs.append(chart)
        chart.bind("<Configure>", lambda _e, c=chart: self._draw_chart(c))
        chart.bind("<ButtonPress-1>", lambda e, c=chart: self._on_chart_press(e, c))
        chart.bind("<B1-Motion>", lambda e, c=chart: self._on_chart_drag(e, c))
        chart.bind("<ButtonRelease-1>", self._on_chart_release)
        chart.bind("<ButtonPress-3>", lambda e, c=chart: self._on_chart_right_click(e, c))

    def _create_param_panel(self, title, config, fields):
        frame = self._right_card(title)
        body = tk.Frame(frame, bg="#FFFFFF")
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        for i, (key, label) in enumerate(fields):
            card = tk.Frame(body, bg="#F8FAFC", highlightthickness=1, highlightbackground="#E5E7EB")
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 10) if i == 0 else (0, 0), pady=0)
            tk.Label(card, text=label, anchor="w", bg="#F8FAFC", fg="#374151",
                     font=("Microsoft YaHei", -13, "bold")).pack(fill=tk.X, padx=12, pady=(12, 6))
            var = tk.DoubleVar(value=float(config.get(key, 0.0)))
            self.param_vars[key] = (config, var)
            value_row = tk.Frame(card, bg="#F8FAFC")
            value_row.pack(fill=tk.X, padx=12, pady=(0, 8))
            tk.Entry(value_row, textvariable=var, width=10, bg="#FFFFFF", relief=tk.FLAT,
                     font=("Consolas", -16, "bold"), justify=tk.CENTER).pack(side=tk.LEFT)
            tk.Scale(card, from_=0, to=200 if "speed" in key else 100, resolution=0.1, orient=tk.HORIZONTAL,
                     variable=var, bg="#F8FAFC", highlightthickness=0, troughcolor="#E5E7EB",
                     showvalue=False).pack(fill=tk.X, padx=10, pady=(0, 12))

    def _draw_chart(self, chart):
        chart.delete("all")
        w = max(1, chart.winfo_width())
        h = max(1, chart.winfo_height())
        ml, mr, mt, mb = 52, 20, 24, 34
        x0, y0 = ml, mt
        x1, y1 = w - mr, h - mb
        plot_w, plot_h = max(1, x1 - x0), max(1, y1 - y0)
        all_x, all_y = [], []
        for curve in chart.curve_defs:
            xs = curve["config"].get(curve["x_key"], [])
            ys = curve["config"].get(curve["y_key"], [])
            count = min(len(xs), len(ys))
            all_x.extend(xs[:count])
            all_y.extend(ys[:count])
        if not all_x or not all_y:
            chart.create_text(w / 2, h / 2, text="暂无曲线数据", fill="#6B7280", font=("Microsoft YaHei", -14, "bold"))
            return
        min_x, max_x = self._range(all_x, include_zero=False)
        min_y, max_y = self._range(all_y, include_zero=True)
        for i in range(6):
            y = y1 - plot_h * i / 5
            value = min_y + (max_y - min_y) * i / 5
            chart.create_line(x0, y, x1, y, fill="#E5E7EB")
            chart.create_text(x0 - 7, y, text=f"{value:.2f}", fill="#6B7280", font=("Consolas", -9), anchor="e")
        for i in range(6):
            x = x0 + plot_w * i / 5
            value = min_x + (max_x - min_x) * i / 5
            chart.create_line(x, y0, x, y1, fill="#EEF2F7")
            chart.create_text(x, y1 + 13, text=f"{value:.0f}m", fill="#6B7280", font=("Consolas", -9), anchor="n")
        chart.create_line(x0, y1, x1, y1, fill="#111827", width=2)
        chart.create_line(x0, y0, x0, y1, fill="#111827", width=2)
        chart.point_map = {}
        for curve_index, curve in enumerate(chart.curve_defs):
            xs = curve["config"].get(curve["x_key"], [])
            ys = curve["config"].get(curve["y_key"], [])
            pairs = sorted([(float(x), float(y), i) for i, (x, y) in enumerate(zip(xs, ys))], key=lambda item: item[0])
            color = self.LINE_COLORS[curve_index % len(self.LINE_COLORS)]
            coords = []
            for x_val, y_val, original_index in pairs:
                px = x0 + (x_val - min_x) / (max_x - min_x) * plot_w
                py = y1 - (y_val - min_y) / (max_y - min_y) * plot_h
                coords.extend([px, py])
                point_id = chart.create_oval(px - self.point_radius, py - self.point_radius,
                                             px + self.point_radius, py + self.point_radius,
                                             fill=color, outline="#FFFFFF", width=2)
                chart.point_map[point_id] = (curve, original_index, min_x, max_x, min_y, max_y, x0, x1, y0, y1)
                chart.create_text(px, py - 11, text=f"{x_val:.0f},{y_val:.2f}", fill=color, font=("Consolas", -8, "bold"))
            if len(coords) >= 4:
                chart.create_line(*coords, fill=color, width=2)
            chart.create_text(x1 - 4, y0 + 14 + curve_index * 15, text=curve["label"], fill=color,
                              font=("Microsoft YaHei", -10, "bold"), anchor="e")

    def _range(self, values, include_zero=False):
        min_val, max_val = min(values), max(values)
        if include_zero:
            min_val = min(0.0, min_val)
        if abs(max_val - min_val) < 1e-6:
            max_val += 1.0
        pad = (max_val - min_val) * 0.1
        return min_val - pad, max_val + pad

    def _on_chart_press(self, event, chart):
        nearest = None
        nearest_dist = 999
        for point_id in chart.point_map:
            coords = chart.coords(point_id)
            if len(coords) != 4:
                continue
            cx, cy = (coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2
            dist = abs(event.x - cx) + abs(event.y - cy)
            if dist < nearest_dist:
                nearest, nearest_dist = point_id, dist
        self.current_chart = chart
        self.drag_target = chart.point_map[nearest] if nearest and nearest_dist <= 18 else None

    def _on_chart_drag(self, event, chart):
        if not self.drag_target:
            return
        curve, index, min_x, max_x, min_y, max_y, x0, x1, y0, y1 = self.drag_target
        x = min(max(event.x, x0), x1)
        y = min(max(event.y, y0), y1)
        x_val = min_x + (x - x0) / (x1 - x0) * (max_x - min_x)
        y_val = max_y - (y - y0) / (y1 - y0) * (max_y - min_y)
        xs = curve["config"].get(curve["x_key"], [])
        ys = curve["config"].get(curve["y_key"], [])
        if index < len(xs) and index < len(ys):
            xs[index] = round(max(0.0, x_val), 3)
            ys[index] = round(max(0.0, y_val), 5)
        self._draw_chart(chart)

    def _on_chart_release(self, _event):
        self.drag_target = None

    def _on_chart_right_click(self, event, chart):
        nearest = None
        nearest_dist = 999
        for point_id in chart.point_map:
            coords = chart.coords(point_id)
            if len(coords) != 4:
                continue
            cx, cy = (coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2
            dist = abs(event.x - cx) + abs(event.y - cy)
            if dist < nearest_dist:
                nearest, nearest_dist = point_id, dist
        if not nearest or nearest_dist > 18:
            return
        curve, index, *_ = chart.point_map[nearest]
        xs = curve["config"].get(curve["x_key"], [])
        if len(xs) <= 2:
            self.status_var.set("至少保留 2 个标点。")
            return
        if index < len(xs):
            xs.pop(index)
        for related in chart.curve_defs:
            if related["config"] is curve["config"] and related["x_key"] == curve["x_key"]:
                ys = related["config"].get(related["y_key"], [])
                if index < len(ys):
                    ys.pop(index)
        self._draw_chart(chart)
        self.status_var.set("已删除标点。")

    def add_point(self):
        if not self.chart_defs:
            self.status_var.set("当前页面没有曲线可添加。")
            return
        chart = self.current_chart or self.chart_defs[0]
        inserted_by_x_key = {}
        for curve in chart.curve_defs:
            x_group = (id(curve["config"]), curve["x_key"])
            xs = curve["config"].get(curve["x_key"], [])
            ys = curve["config"].get(curve["y_key"], [])
            if not xs or not ys:
                if x_group not in inserted_by_x_key:
                    xs.append(50.0)
                    inserted_by_x_key[x_group] = len(xs) - 1
                ys.append(0.5)
                continue
            if x_group in inserted_by_x_key:
                insert_index = inserted_by_x_key[x_group]
                mid_index = max(0, min(insert_index - 1, len(ys) - 1))
                next_index = max(0, min(insert_index, len(ys) - 1))
                y_val = (float(ys[mid_index]) + float(ys[next_index])) / 2 if next_index != mid_index else float(ys[mid_index])
                ys.append(round(y_val, 5))
                continue
            mid_index = max(0, len(xs) // 2 - 1)
            next_index = min(len(xs) - 1, mid_index + 1)
            x_val = (float(xs[mid_index]) + float(xs[next_index])) / 2 if next_index != mid_index else float(xs[mid_index]) + 1.0
            y_val = (float(ys[mid_index]) + float(ys[next_index])) / 2 if next_index != mid_index else float(ys[mid_index])
            xs.append(round(x_val, 3))
            inserted_by_x_key[x_group] = len(xs) - 1
            ys.append(round(y_val, 5))
        self._draw_chart(chart)
        self.status_var.set("已在曲线中部添加标点。")

    def _sort_curve_pairs(self, config, x_key, y_keys):
        xs = config.get(x_key, [])
        if not xs:
            return
        count = min([len(xs)] + [len(config.get(y_key, [])) for y_key in y_keys])
        order = sorted(range(count), key=lambda i: float(xs[i]))
        config[x_key] = [xs[i] for i in order]
        for y_key in y_keys:
            ys = config.get(y_key, [])
            config[y_key] = [ys[i] for i in order]

    def _sort_all_curves(self):
        self._sort_curve_pairs(self.config.get("rocket_config", {}), "calib_dists", ["calib_ratios"])
        self._sort_curve_pairs(self.config.get("vss_config", {}), "calib_dists", ["calib_drops_ratio"])
        self._sort_curve_pairs(self.config.get("crossbow_config", {}), "calib_dists", ["calib_drops_ratio"])
        self._sort_curve_pairs(self.config.get("throwables_config", {}), "calib_dists", ["calib_elevations_ratio", "calib_times"])
        self._sort_curve_pairs(self.config.get("throwables_config", {}), "jump_calib_dists", ["jump_calib_elevations_ratio", "jump_calib_times"])

    def _apply_to_modules(self):
        rocket = self.modules.get("rocket")
        if rocket:
            cfg = self.config.get("rocket_config", {})
            pairs = sorted(zip(cfg.get("calib_dists", []), cfg.get("calib_ratios", [])))
            rocket.calib_dists = [p[0] for p in pairs]
            rocket.calib_ratios = [p[1] for p in pairs]
        vss = self.modules.get("vss")
        if vss:
            cfg = self.config.get("vss_config", {})
            vss.calib_dists = cfg.get("calib_dists", [])
            vss.calib_drops_ratio = cfg.get("calib_drops_ratio", [])
        crossbow = self.modules.get("crossbow")
        if crossbow:
            cfg = self.config.get("crossbow_config", {})
            crossbow.calib_dists = cfg.get("calib_dists", [])
            crossbow.calib_drops_ratio = cfg.get("calib_drops_ratio", [])
        mortar = self.modules.get("mortar")
        if mortar:
            cfg = self.config.get("mortar_config", {})
            mortar.a_param = cfg.get("a_param", mortar.a_param)
            mortar.b_param = cfg.get("b_param", mortar.b_param)
        throwables = self.modules.get("throwables")
        if throwables:
            cfg = self.config.get("throwables_config", {})
            throwables.calib_dists = cfg.get("calib_dists", [])
            throwables.calib_elevations_y = [throwables.sh * r for r in cfg.get("calib_elevations_ratio", [])]
            throwables.calib_times = cfg.get("calib_times", [])
            throwables.jump_calib_dists = cfg.get("jump_calib_dists", [])
            throwables.jump_calib_elevations_y = [throwables.sh * r for r in cfg.get("jump_calib_elevations_ratio", [])]
            throwables.jump_calib_times = cfg.get("jump_calib_times", [])
            throwables.jump_delay_after_release = cfg.get("jump_delay_after_release", throwables.jump_delay_after_release)
        c4 = self.modules.get("c4")
        if c4:
            cfg = self.config.get("c4_config", {})
            c4.target_speed = cfg.get("target_speed", c4.target_speed)
            c4.jump_distance_threshold = cfg.get("jump_distance_threshold", c4.jump_distance_threshold)

    def _commit_param_vars(self):
        for key, (config, var) in self.param_vars.items():
            config[key] = float(var.get())

    def save(self):
        self._commit_param_vars()
        self._sort_all_curves()
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)
        self._apply_to_modules()
        self.status_var.set("参数已保存并应用。")

    def reload(self):
        self._load_config()
        self._render_current_weapon()
        self._apply_to_modules()
        self.status_var.set("已从 config.json 重载。")

    def on_closing(self):
        self.root.destroy()


def open_special_weapon_debugger(parent, config_file="config.json", modules=None):
    window = tk.Toplevel(parent) if parent else tk.Tk()
    app = SpecialWeaponDebugger(window, config_file=config_file, modules=modules)
    return app
