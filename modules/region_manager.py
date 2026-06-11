import tkinter as tk
import json
import os
import math
import ctypes

class RegionManager:
    """
    绝地求生 全局视觉与校准管理器
    - real_regions: 存储用户在当前屏幕分辨率下手动校准的区域（物理像素坐标）
    - real_scales: 存储用户校准的比例尺（物理像素长度）
    """
    def __init__(self, root, config_file="config.json"):
        self.root = root
        self.config_file = config_file
        self.show_debug = False

        # 获取当前屏幕实际物理分辨率
        try:
            user32 = ctypes.windll.user32
            self.real_w = user32.GetSystemMetrics(0)
            self.real_h = user32.GetSystemMetrics(1)
        except Exception:
            self.real_w = root.winfo_screenwidth()
            self.real_h = root.winfo_screenheight()

        # ---------- 实际分辨率区域（用户校准，保存到 config.json） ----------
        self.real_regions = {}
        self.real_scales = {}

        self._load_config()
        self._sync_crosshair_region()

        # 调试覆盖层
        self.debug_overlay = None
        self.debug_canvas = None
        self._init_debug_overlay()

    def _load_config(self):
        """从配置文件加载用户校准的实际区域和比例尺"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        config = json.loads(content)
                        if "real_regions" in config:
                            self.real_regions = config["real_regions"]
                            print(f"[全局管理] 加载 real_regions: {len(self.real_regions)} 个区域")
                        if "real_scales" in config:
                            self.real_scales = config["real_scales"]
                            print(f"[全局管理] 加载 real_scales: {self.real_scales}")
            except Exception as e:
                print(f"[全局管理] 配置文件加载失败: {e}")

    def _sync_crosshair_region(self):
        """根据当前真实分辨率自动生成准星区域并同步到配置文件。"""
        side = int(round(self.real_h / 1.5))
        side = max(1, min(side, self.real_w, self.real_h))
        left = int(round((self.real_w - side) / 2))
        top = int(round((self.real_h - side) / 2))
        self.real_regions["crosshair_region"] = {
            "left": left,
            "top": top,
            "width": side,
            "height": side
        }
        self._save_config()
        print(f"[全局管理] 自动同步 crosshair_region: {self.real_regions['crosshair_region']}")

    def _save_config(self):
        """保存当前实际分辨率下的区域和比例尺"""
        config = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        config = json.loads(content)
            except Exception as e:
                print(f"[全局管理] 配置文件读取错误，将覆盖: {e}")

        config["real_regions"] = self.real_regions
        config["real_scales"] = self.real_scales

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print("[全局管理] 实际区域与比例尺已保存")
        except Exception as e:
            print(f"[全局管理] 保存失败: {e}")

    def get_real_region(self, region_name):
        """返回当前分辨率下的实际像素区域（用于截图）"""
        return self.real_regions.get(region_name)

    def get_real_scale(self, scale_name):
        """返回实际像素比例尺"""
        return self.real_scales.get(scale_name)

    # ---------- 调试与校准界面 ----------
    def _init_debug_overlay(self):
        self.debug_overlay = tk.Toplevel(self.root)
        self.debug_overlay.overrideredirect(True)
        self.debug_overlay.geometry(f"{self.real_w}x{self.real_h}+0+0")
        self.debug_overlay.attributes("-topmost", True)
        self.debug_overlay.attributes("-transparentcolor", "black")

        self.debug_canvas = tk.Canvas(self.debug_overlay, bg="black", highlightthickness=0)
        self.debug_canvas.pack(fill=tk.BOTH, expand=True)
        self.debug_overlay.update_idletasks()
        self.debug_overlay.withdraw()

    def set_debug_mode(self, is_show: bool):
        self.show_debug = is_show
        if self.show_debug:
            self.debug_overlay.deiconify()
            self._draw_debug_regions()
        else:
            self.debug_overlay.withdraw()

    def _draw_debug_regions(self):
        """绘制所有已校准的区域框"""
        if not self.debug_canvas:
            return
        self.debug_canvas.delete("debug_elem")

        color_map = {
            "scope_region": "#34495E", "weapon_region": "#E74C3C", "stance_region": "#2ECC71",
            "minimap_region": "#3498DB", "largemap_region": "#9B59B6", "elevation_region": "#E67E22",
            "compass_region": "#F1C40F", "crosshair_region": "#FF69B4"
        }

        for name, rect in self.real_regions.items():
            x1 = rect["left"]
            y1 = rect["top"]
            x2 = x1 + rect["width"]
            y2 = y1 + rect["height"]
            # 边界裁剪
            x1 = max(0, min(x1, self.real_w - 1))
            y1 = max(0, min(y1, self.real_h - 1))
            x2 = max(0, min(x2, self.real_w))
            y2 = max(0, min(y2, self.real_h))
            color = color_map.get(name, "white")
            self.debug_canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2, tags="debug_elem")
            self.debug_canvas.create_text(x1 + 5, max(5, y1 - 5), text=name, fill=color,
                                          font=("Consolas", 10, "bold"), anchor="nw", tags="debug_elem")

        scale_text = f"小地图 100m = {self.real_scales.get('minimap_100m_px', 0):.1f} px\n大地图 1km = {self.real_scales.get('largemap_1km_px', 0):.1f} px"
        cx, cy = self.real_w // 2, 50
        self.debug_canvas.create_text(cx, cy, text=scale_text, fill="#1ABC9C",
                                      font=("Microsoft YaHei", 12, "bold"), justify="center", tags="debug_elem")

    def calibrate_region(self, region_name):
        """启动区域校准，直接保存用户框选的物理像素坐标"""
        if region_name not in self.real_regions:
            self.real_regions[region_name] = {"left": 0, "top": 0, "width": 100, "height": 100}
        force_square = (region_name in ["minimap_region", "largemap_region",
                                    "weapon1_number_region", "weapon2_number_region",
                                    "weapon1_scope_region", "weapon1_grip_region", "weapon1_muzzle_region", "weapon1_stock_region",
                                    "weapon2_scope_region", "weapon2_grip_region", "weapon2_muzzle_region", "weapon2_stock_region"])
        self._start_calibration_overlay(region_name, is_line=False, is_square=force_square)

    def calibrate_scale(self, scale_name):
        """启动比例尺校准，直接保存用户测量的物理像素长度"""
        if scale_name not in self.real_scales:
            self.real_scales[scale_name] = 100.0
        self._start_calibration_overlay(scale_name, is_line=True, is_square=False)

    def _start_calibration_overlay(self, target_name, is_line=False, is_square=False):
        if self.show_debug:
            self.debug_overlay.withdraw()

        calib_win = tk.Toplevel(self.root)
        calib_win.attributes("-fullscreen", True)
        calib_win.attributes("-topmost", True)
        calib_win.attributes("-alpha", 0.6)
        calib_win.configure(bg='gray')
        calib_win.config(cursor="crosshair")

        canvas = tk.Canvas(calib_win, bg='gray', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        calib_win.start_x = -1
        calib_win.start_y = -1
        calib_win.shape_id = None

        def on_cancel(event):
            calib_win.destroy()
            if self.show_debug:
                self.debug_overlay.deiconify()
                self._draw_debug_regions()

        def on_mouse_down(event):
            calib_win.start_x = event.x
            calib_win.start_y = event.y
            if is_line:
                calib_win.shape_id = canvas.create_line(event.x, event.y, event.x, event.y, fill="#2ECC71", width=3)
            else:
                calib_win.shape_id = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#E74C3C", width=2)

        def on_mouse_drag(event):
            if calib_win.shape_id:
                if is_line:
                    canvas.coords(calib_win.shape_id, calib_win.start_x, calib_win.start_y, event.x, event.y)
                else:
                    if is_square:
                        side = max(abs(event.x - calib_win.start_x), abs(event.y - calib_win.start_y))
                        end_x = calib_win.start_x + (side if event.x > calib_win.start_x else -side)
                        end_y = calib_win.start_y + (side if event.y > calib_win.start_y else -side)
                        canvas.coords(calib_win.shape_id, calib_win.start_x, calib_win.start_y, end_x, end_y)
                    else:
                        canvas.coords(calib_win.shape_id, calib_win.start_x, calib_win.start_y, event.x, event.y)

        def on_mouse_up(event):
            end_x, end_y = event.x, event.y

            if is_line:
                dx = end_x - calib_win.start_x
                dy = end_y - calib_win.start_y
                px_length = math.hypot(dx, dy)
                if px_length > 5:
                    self.real_scales[target_name] = px_length
                    self._save_config()
            else:
                if is_square:
                    side = max(abs(end_x - calib_win.start_x), abs(end_y - calib_win.start_y))
                    end_x = calib_win.start_x + (side if end_x > calib_win.start_x else -side)
                    end_y = calib_win.start_y + (side if end_y > calib_win.start_y else -side)

                real_left = min(calib_win.start_x, end_x)
                real_top = min(calib_win.start_y, end_y)
                real_width = abs(end_x - calib_win.start_x)
                real_height = abs(end_y - calib_win.start_y)

                if real_width > 5 and real_height > 5:
                    self.real_regions[target_name] = {
                        "left": real_left, "top": real_top,
                        "width": real_width, "height": real_height
                    }
                    self._save_config()

            calib_win.destroy()
            if self.show_debug:
                self.debug_overlay.deiconify()
                self._draw_debug_regions()

        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)
        canvas.bind("<Button-3>", on_cancel)
