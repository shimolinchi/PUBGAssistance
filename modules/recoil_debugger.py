import tkinter as tk
from tkinter import messagebox, ttk


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, width=120, height=32, bg="#2563EB", fg="#FFFFFF"):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, bd=0)
        self.command = command
        self.width = width
        self.height = height
        self.bg_color = bg
        self.hover_color = self._adjust_color(bg, 0.9)
        self.fg = fg
        self.rect = self._round_rect(1, 1, width - 1, height - 1, 12, fill=self.bg_color, outline="")
        self.text_id = self.create_text(width / 2, height / 2, text=text, fill=fg, font=("Microsoft YaHei", -13, "bold"))
        self.bind("<ButtonRelease-1>", self._on_click)
        self.bind("<Enter>", lambda _e: self.itemconfig(self.rect, fill=self.hover_color))
        self.bind("<Leave>", lambda _e: self.itemconfig(self.rect, fill=self.bg_color))

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
        if self.command:
            self.command()


class RecoilDebuggerWindow:
    CURVE_COLORS = {
        "weapon": "#2563EB",
        "scope": "#7C3AED",
        "grip": "#16A34A",
        "muzzle": "#EA580C",
        "stock": "#DC2626",
    }
    CURVE_NAMES = {
        "weapon": "武器",
        "scope": "倍镜",
        "grip": "握把",
        "muzzle": "枪口",
        "stock": "枪托",
    }

    def __init__(self, root, recoil_module, on_recoil_toggle=None):
        self.root = root
        self.recoil = recoil_module
        self.on_recoil_toggle = on_recoil_toggle
        self.root.title("压枪参数调试")
        self.root.geometry("800x630")
        self.root.minsize(760, 550)
        self.root.configure(bg="#FFFFFF")
        self.root.attributes("-topmost", True)

        self.weapon_var = tk.StringVar()
        self.scope_var = tk.StringVar(value="无")
        self.grip_var = tk.StringVar(value="无")
        self.muzzle_var = tk.StringVar(value="无")
        self.stock_var = tk.StringVar(value="无")
        self.node_curve_var = tk.StringVar(value="武器")
        self.status_var = tk.StringVar(value="就绪")
        self.drag_target = None
        self.point_radius = 5
        self.margin_left = 58
        self.margin_right = 54
        self.margin_top = 34
        self.margin_bottom = 42

        self._build_ui()
        self._load_options()
        self._apply_selection()
        self._draw_chart()

    def _build_ui(self):
        main = tk.Frame(self.root, bg="#FFFFFF")
        main.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)

        left = tk.Frame(main, bg="#FFFFFF", width=230)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        left.pack_propagate(False)

        right = tk.Frame(main, bg="#FFFFFF")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        title = tk.Label(left, text="压枪参数调试", bg="#FFFFFF", fg="#111827", font=("Microsoft YaHei", -18, "bold"))
        title.pack(anchor="w")

        selector = self._card(left, "1. 选择武器和配件")
        self.weapon_combo = self._combo(selector, "武器", self.weapon_var, [])
        self.scope_combo = self._combo(selector, "倍镜", self.scope_var, [])
        self.grip_combo = self._combo(selector, "握把", self.grip_var, [])
        self.muzzle_combo = self._combo(selector, "枪口", self.muzzle_var, [])
        self.stock_combo = self._combo(selector, "枪托", self.stock_var, [])

        controls = self._card(left, "2. 调试控制")
        button_row1 = tk.Frame(controls, bg="#FFFFFF")
        button_row1.pack(fill=tk.X, padx=10, pady=(9, 6))
        RoundedButton(button_row1, "保存参数", self.save_params, width=100, height=30, bg="#2563EB").pack(side=tk.LEFT, padx=(0, 8))
        RoundedButton(button_row1, "重载参数", self.reload_params, width=100, height=30, bg="#7C3AED").pack(side=tk.LEFT)

        hint = tk.Label(
            controls,
            text="压枪开关快捷键F3。拖动右侧折线点可调节参数。",
            bg="#FFFFFF",
            fg="#6B7280",
            font=("Microsoft YaHei", -12),
            wraplength=220,
            justify=tk.LEFT,
        )
        hint.pack(fill=tk.X, padx=10, pady=(0, 8))

        node_card = self._card(left, "3. 曲线节点")
        node_row = tk.Frame(node_card, bg="#FFFFFF")
        node_row.pack(fill=tk.X, padx=10, pady=(8, 6))
        tk.Label(node_row, text="曲线", width=5, anchor="w", bg="#FFFFFF", fg="#374151",
                 font=("Microsoft YaHei", -12)).pack(side=tk.LEFT)
        self.node_curve_combo = ttk.Combobox(
            node_row,
            textvariable=self.node_curve_var,
            values=["武器", "倍镜", "握把", "枪口", "枪托"],
            state="readonly",
            width=10,
        )
        self.node_curve_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        button_row3 = tk.Frame(node_card, bg="#FFFFFF")
        button_row3.pack(fill=tk.X, padx=10, pady=(0, 8))
        RoundedButton(button_row3, "增加末尾点", self.add_curve_point, width=100, height=30, bg="#0EA5E9").pack(side=tk.LEFT, padx=(0, 8))
        RoundedButton(button_row3, "减少末尾点", self.remove_curve_point, width=100, height=30, bg="#F59E0B").pack(side=tk.LEFT)

        info = self._card(left, "4. 当前状态")
        tk.Label(info, textvariable=self.status_var, bg="#FFFFFF", fg="#2563EB",
                 font=("Microsoft YaHei", -12, "bold"), wraplength=220, justify=tk.LEFT).pack(fill=tk.X, padx=10, pady=9)

        legend = self._card(left, "5. 曲线图例")
        legend_row = tk.Frame(legend, bg="#FFFFFF")
        legend_row.pack(fill=tk.X, padx=8, pady=7)
        for key in ["weapon", "scope", "grip", "muzzle", "stock"]:
            row = tk.Frame(legend_row, bg="#FFFFFF")
            row.pack(side=tk.LEFT, padx=(0, 4))
            tk.Canvas(row, width=12, height=8, bg="#FFFFFF", highlightthickness=0).pack(side=tk.LEFT)
            sample = row.winfo_children()[0]
            sample.create_line(1, 4, 11, 4, fill=self.CURVE_COLORS[key], width=3)
            tk.Label(row, text=self.CURVE_NAMES[key], bg="#FFFFFF", fg="#374151",
                     font=("Microsoft YaHei", -10)).pack(side=tk.LEFT, padx=(2, 0))

        chart_card = self._card(right, "参数曲线")
        chart_card.pack_propagate(False)
        self.chart = tk.Canvas(chart_card, bg="#F8FAFC", highlightthickness=1, highlightbackground="#E5E7EB")
        self.chart.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.chart.bind("<Configure>", lambda _e: self._draw_chart())
        self.chart.bind("<ButtonPress-1>", self._on_chart_press)
        self.chart.bind("<B1-Motion>", self._on_chart_drag)
        self.chart.bind("<ButtonRelease-1>", self._on_chart_release)

    def _card(self, parent, title):
        frame = tk.LabelFrame(parent, text=f" {title} ", bg="#FFFFFF", fg="#111827",
                              font=("Microsoft YaHei", -13, "bold"), bd=1, relief=tk.SOLID,
                              highlightbackground="#E5E7EB")
        frame.pack(fill=tk.BOTH if title == "参数曲线" else tk.X, expand=(title == "参数曲线"), pady=(0, 8))
        return frame

    def _combo(self, parent, label, var, values):
        row = tk.Frame(parent, bg="#FFFFFF")
        row.pack(fill=tk.X, padx=10, pady=(8, 0))
        tk.Label(row, text=label, width=5, anchor="w", bg="#FFFFFF", fg="#374151",
                 font=("Microsoft YaHei", -12)).pack(side=tk.LEFT)
        combo = ttk.Combobox(row, textvariable=var, values=values, state="readonly")
        combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._on_selection_changed())
        return combo

    def _load_options(self):
        weapons = sorted(self.recoil.weapon_configs.keys())
        self.weapon_combo.config(values=weapons)
        current_weapon = self.recoil.current_weapon if self.recoil.current_weapon in weapons else None
        self.weapon_var.set(current_weapon or (weapons[0] if weapons else ""))

        self.scope_combo.config(values=self._with_none(self.recoil.scope_multiplier_curves.keys()))
        self.grip_combo.config(values=self._with_none(self.recoil.grip_multiplier_curves.keys()))
        self.muzzle_combo.config(values=self._with_none(self.recoil.muzzle_multiplier_curves.keys()))
        self.stock_combo.config(values=self._with_none(self.recoil.stock_multiplier_curves.keys()))
        self.scope_var.set(self._display_value(self.recoil.scope))
        self.grip_var.set(self._display_value(self.recoil.grip))
        self.muzzle_var.set(self._display_value(self.recoil.muzzle))
        self.stock_var.set(self._display_value(self.recoil.stock))

    def _with_none(self, values):
        return ["无"] + sorted(values)

    def _display_value(self, value):
        return value if value else "无"

    def _config_value(self, value):
        return None if value == "无" else value

    def _on_selection_changed(self):
        self._apply_selection()
        self._draw_chart()

    def _apply_selection(self):
        weapon = self.weapon_var.get()
        if weapon:
            self.recoil.update_current_weapon(weapon)
        self.recoil.update_attachments({
            "scope": self._config_value(self.scope_var.get()) or "hip",
            "grip": self._config_value(self.grip_var.get()),
            "muzzle": self._config_value(self.muzzle_var.get()),
            "stock": self._config_value(self.stock_var.get()),
        })
        self._set_status()

    def _set_status(self, extra=None):
        weapon = self.weapon_var.get() or "未选择"
        state = "开启" if self.recoil.is_enabled else "关闭"
        text = f"当前武器：{weapon}\n压枪状态：{state}\n节点间隔：{self.recoil.recoil_curve_step:.2f}s"
        if extra:
            text += f"\n{extra}"
        self.status_var.set(text)

    def save_params(self):
        self._sync_public_multipliers()
        self.recoil.save_config()
        self._set_status("参数已保存到 config.json。")

    def reload_params(self):
        self.recoil.reload_config()
        self._load_options()
        self._apply_selection()
        self._draw_chart()
        self._set_status("已从 config.json 重载参数。")

    def add_curve_point(self):
        curve = self._editable_curve(self._node_curve_key())
        if curve is None:
            self._set_status("当前曲线不可编辑，请先选择对应配件。")
            return
        curve.append(curve[-1] if curve else 1.0)
        self._after_curve_changed("已增加末尾节点。")

    def remove_curve_point(self):
        curve = self._editable_curve(self._node_curve_key())
        if curve is None:
            self._set_status("当前曲线不可编辑，请先选择对应配件。")
            return
        if len(curve) <= 1:
            self._set_status("至少保留 1 个节点。")
            return
        curve.pop()
        self._after_curve_changed("已减少末尾节点。")

    def _after_curve_changed(self, message):
        self._sync_public_multipliers()
        self._apply_selection()
        self._draw_chart()
        self._set_status(message)

    def _node_curve_key(self):
        name_map = {"武器": "weapon", "倍镜": "scope", "握把": "grip", "枪口": "muzzle", "枪托": "stock"}
        return name_map.get(self.node_curve_var.get(), "weapon")

    def _editable_curve(self, key):
        if key == "weapon":
            weapon_data = self.recoil.weapon_configs.get(self.weapon_var.get(), {})
            return weapon_data.get("recoil_curve")

        target_key = self._selected_attachment_key(key)
        if not target_key:
            return None
        curve_map = {
            "scope": self.recoil.scope_multiplier_curves,
            "grip": self.recoil.grip_multiplier_curves,
            "muzzle": self.recoil.muzzle_multiplier_curves,
            "stock": self.recoil.stock_multiplier_curves,
        }[key]
        return curve_map.get(target_key)

    def _sync_public_multipliers(self):
        self.recoil.scope_multipliers = self.recoil._first_values(self.recoil.scope_multiplier_curves)
        self.recoil.grip_multipliers = self.recoil._first_values(self.recoil.grip_multiplier_curves)
        self.recoil.muzzle_multipliers = self.recoil._first_values(self.recoil.muzzle_multiplier_curves)
        self.recoil.stock_multipliers = self.recoil._first_values(self.recoil.stock_multiplier_curves)

    def _get_curves(self):
        weapon = self.weapon_var.get()
        weapon_data = self.recoil.weapon_configs.get(weapon, {})
        curves = {"weapon": weapon_data.get("recoil_curve", [])}
        scope = self._config_value(self.scope_var.get()) or "hip"
        grip = self._config_value(self.grip_var.get())
        muzzle = self._config_value(self.muzzle_var.get())
        stock = self._config_value(self.stock_var.get())
        curves["scope"] = self.recoil.scope_multiplier_curves.get(scope, [1.0])
        curves["grip"] = self.recoil.grip_multiplier_curves.get(grip, [1.0]) if grip else [1.0]
        curves["muzzle"] = self.recoil.muzzle_multiplier_curves.get(muzzle, [1.0]) if muzzle else [1.0]
        curves["stock"] = self.recoil.stock_multiplier_curves.get(stock, [1.0]) if stock else [1.0]
        return curves

    def _draw_chart(self):
        if not hasattr(self, "chart"):
            return
        self.chart.delete("all")
        w = max(1, self.chart.winfo_width())
        h = max(1, self.chart.winfo_height())
        plot_w = max(1, w - self.margin_left - self.margin_right)
        plot_h = max(1, h - self.margin_top - self.margin_bottom)
        x0 = self.margin_left
        y0 = self.margin_top
        x1 = x0 + plot_w
        y1 = y0 + plot_h
        curves = self._get_curves()
        weapon_values = curves.get("weapon", [])
        attachment_values = [v for key, values in curves.items() if key != "weapon" for v in values]
        if not weapon_values and not attachment_values:
            return
        weapon_min, weapon_max = self._axis_range(weapon_values, include_zero=True)
        attachment_min, attachment_max = self._attachment_axis_range(attachment_values)
        max_nodes = max(len(values) for values in curves.values())

        for i in range(6):
            y = y1 - plot_h * i / 5
            weapon_value = weapon_min + (weapon_max - weapon_min) * i / 5
            attachment_value = attachment_min + (attachment_max - attachment_min) * i / 5
            self.chart.create_line(x0, y, x1, y, fill="#E5E7EB")
            self.chart.create_text(x0 - 8, y, text=f"{weapon_value:.1f}", fill=self.CURVE_COLORS["weapon"], font=("Consolas", -10), anchor="e")
            self.chart.create_text(x1 + 8, y, text=f"{attachment_value:.2f}", fill="#6B7280", font=("Consolas", -10), anchor="w")
        for i in range(max_nodes):
            x = x0 + plot_w * i / max(1, max_nodes - 1)
            t = i * self.recoil.recoil_curve_step
            self.chart.create_line(x, y0, x, y1, fill="#EEF2F7")
            self.chart.create_text(x, y1 + 18, text=f"{t:.1f}s", fill="#6B7280", font=("Consolas", -10), anchor="n")
        self.chart.create_line(x0, y1, x1, y1, fill="#111827", width=2)
        self.chart.create_line(x0, y0, x0, y1, fill="#111827", width=2)
        self.chart.create_line(x1, y0, x1, y1, fill="#6B7280", width=2)

        self.point_map = {}
        for key, values in curves.items():
            points = []
            for index, value in enumerate(values):
                x = x0 + plot_w * index / max(1, max_nodes - 1)
                axis_min, axis_max = (weapon_min, weapon_max) if key == "weapon" else (attachment_min, attachment_max)
                y = y1 - (value - axis_min) / (axis_max - axis_min) * plot_h
                points.append((x, y, index, value))
            if len(points) > 1:
                coords = []
                for x, y, _index, _value in points:
                    coords.extend([x, y])
                self.chart.create_line(*coords, fill=self.CURVE_COLORS[key], width=2, smooth=False)
            for x, y, index, value in points:
                point_id = self.chart.create_oval(
                    x - self.point_radius, y - self.point_radius,
                    x + self.point_radius, y + self.point_radius,
                    fill=self.CURVE_COLORS[key], outline="#FFFFFF", width=2,
                )
                axis_min, axis_max = (weapon_min, weapon_max) if key == "weapon" else (attachment_min, attachment_max)
                self.point_map[point_id] = (key, index, axis_min, axis_max, y0, y1)
                self.chart.create_text(x, y - 12, text=f"{value:.2f}", fill=self.CURVE_COLORS[key], font=("Consolas", -9, "bold"))

        self.chart.create_text(x0 + 4, y0 - 18, text="枪械压枪参数", fill=self.CURVE_COLORS["weapon"], font=("Microsoft YaHei", -11, "bold"), anchor="w")
        self.chart.create_text(x1 - 4, y0 - 18, text="配件补偿系数", fill="#6B7280", font=("Microsoft YaHei", -11, "bold"), anchor="e")
        self.chart.create_text(x1, y1 + 34, text="时间", fill="#374151", font=("Microsoft YaHei", -11, "bold"), anchor="e")

    def _axis_range(self, values, include_zero=False):
        if not values:
            return 0.0, 1.0
        min_val = min(values)
        max_val = max(values)
        if include_zero:
            min_val = min(0.0, min_val)
        if max_val - min_val < 0.01:
            max_val += 1.0
        pad = (max_val - min_val) * 0.12
        return min_val - pad, max_val + pad

    def _attachment_axis_range(self, values):
        if not values:
            return 0.0, 1.0
        max_val = max(1.0, max(values))
        return 0.0, max_val * 1.08

    def _on_chart_press(self, event):
        nearest = None
        nearest_dist = 999
        for item_id in self.point_map:
            coords = self.chart.coords(item_id)
            if len(coords) != 4:
                continue
            cx = (coords[0] + coords[2]) / 2
            cy = (coords[1] + coords[3]) / 2
            dist = abs(event.x - cx) + abs(event.y - cy)
            if dist < nearest_dist:
                nearest = item_id
                nearest_dist = dist
        self.drag_target = self.point_map[nearest] if nearest and nearest_dist <= 18 else None

    def _on_chart_drag(self, event):
        if not self.drag_target:
            return
        key, index, min_val, max_val, y0, y1 = self.drag_target
        y = min(max(event.y, y0), y1)
        value = max_val - (y - y0) / (y1 - y0) * (max_val - min_val)
        if key != "weapon":
            value = max(0.0, value)
        self._set_curve_value(key, index, round(value, 3))
        self._apply_selection()
        self._draw_chart()

    def _on_chart_release(self, _event):
        self.drag_target = None

    def _set_curve_value(self, key, index, value):
        if key == "weapon":
            weapon_data = self.recoil.weapon_configs.get(self.weapon_var.get(), {})
            if "recoil_curve" in weapon_data and index < len(weapon_data["recoil_curve"]):
                weapon_data["recoil_curve"][index] = value
            return
        target_key = self._selected_attachment_key(key)
        if not target_key:
            return
        curve_map = {
            "scope": self.recoil.scope_multiplier_curves,
            "grip": self.recoil.grip_multiplier_curves,
            "muzzle": self.recoil.muzzle_multiplier_curves,
            "stock": self.recoil.stock_multiplier_curves,
        }[key]
        curve = curve_map.get(target_key)
        if curve and index < len(curve):
            curve[index] = max(0.0, value)
            self._sync_public_multipliers()

    def _selected_attachment_key(self, key):
        if key == "scope":
            return self._config_value(self.scope_var.get()) or "hip"
        if key == "grip":
            return self._config_value(self.grip_var.get())
        if key == "muzzle":
            return self._config_value(self.muzzle_var.get())
        if key == "stock":
            return self._config_value(self.stock_var.get())
        return None

    def on_closing(self):
        self.root.destroy()


def open_recoil_debugger(parent, recoil_module, on_recoil_toggle=None):
    window = tk.Toplevel(parent) if parent else tk.Tk()
    app = RecoilDebuggerWindow(window, recoil_module, on_recoil_toggle=on_recoil_toggle)
    return app
