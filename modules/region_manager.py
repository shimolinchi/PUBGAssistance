import tkinter as tk
import json
import os
import math

class RegionManager:
    """
    绝地求生 全局视觉与校准管理器 (安全存取+全分辨率版)
    """
    def __init__(self, root, config_file="config.json"):
        self.root = root
        self.config_file = config_file
        
        self.show_debug = False
        
        self.real_w = self.root.winfo_screenwidth()
        self.real_h = self.root.winfo_screenheight()
        
        self.base_w = 1920
        self.base_h = 1080
        
        self.scale_x = self.real_w / self.base_w
        self.scale_y = self.real_h / self.base_h

        self.base_regions = {
            "scope_region": {"left": 0, "top": 0, "width": 1920, "height": 1080},
            "weapon_region": {"left": 800, "top": 900, "width": 300, "height": 100},
            "stance_region": {"left": 400, "top": 950, "width": 50, "height": 50},
            "minimap_region": {"left": 1600, "top": 800, "width": 300, "height": 300},
            "largemap_region": {"left": 400, "top": 100, "width": 1100, "height": 800},
            "elevation_region": {"left": 960, "top": 540, "width": 100, "height": 300},
            "compass_region": {"left": 800, "top": 20, "width": 300, "height": 40},
            "crosshair_region": {"left": 800, "top": 900, "width": 300, "height": 100},
        }
        
        self.base_scales = {
            "minimap_100m_px": 100.0,
            "largemap_1km_px": 150.0
        }
        
        self.real_regions = {}
        self.real_scales = {}
        
        self._load_config()
        
        self.debug_overlay = None
        self.debug_canvas = None
        self._init_debug_overlay()

    def _sync_real_from_base(self):
        self.real_regions.clear()
        for key, rect in self.base_regions.items():
            self.real_regions[key] = {
                "left": int(round(rect["left"] * self.scale_x)),
                "top": int(round(rect["top"] * self.scale_y)),
                "width": int(round(rect["width"] * self.scale_x)),
                "height": int(round(rect["height"] * self.scale_y))
            }
            
        self.real_scales.clear()
        for key, val in self.base_scales.items():
            avg_scale = (self.scale_x + self.scale_y) / 2.0
            self.real_scales[key] = val * avg_scale

    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        config = json.loads(content)
                        if "detection_regions" in config:
                            for key in self.base_regions.keys():
                                if key in config["detection_regions"]:
                                    self.base_regions[key] = config["detection_regions"][key]
                        if "map_scales" in config:
                            for key in self.base_scales.keys():
                                if key in config["map_scales"]:
                                    self.base_scales[key] = config["map_scales"][key]
            except Exception as e:
                print(f"[全局管理] ⚠️ 配置文件加载失败，请检查语法错误: {e}")
        
        self._sync_real_from_base()

    def _save_config(self):
        config = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        config = json.loads(content)
            except Exception as e:
                # 【终极防误删保护】
                print(f"\n[致命错误] 配置文件 '{self.config_file}' 存在 JSON 语法错误: {e}")
                print("[致命错误] 为防止清空你原有的其他配置，本次保存已被强制拦截！")
                print("[致命错误] 请打开配置文件修复语法 (如删除多余的逗号) 后重试。\n")
                return 
        
        # 只更新我们的字典，绝对不动用户的其他配置
        config["detection_regions"] = self.base_regions
        config["map_scales"] = self.base_scales
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print("[全局管理] 区域与比例尺已安全保存！(保留了其他配置)")
        except Exception as e:
            print(f"[全局管理] 保存写入失败: {e}")

    def get_templates_region(self, region_name):
        return self.base_regions.get(region_name)

    def get_real_region(self, region_name):
        return self.real_regions.get(region_name)

    def get_templates_scale(self, scale_name):
        return self.base_scales.get(scale_name)

    def get_real_scale(self, scale_name):
        return self.real_scales.get(scale_name)

    def _init_debug_overlay(self):
        self.debug_overlay = tk.Toplevel(self.root)
        self.debug_overlay.attributes("-fullscreen", True)
        self.debug_overlay.attributes("-topmost", True)
        self.debug_overlay.attributes("-transparentcolor", "black")
        self.debug_overlay.overrideredirect(True)
        self.debug_overlay.withdraw()
        
        self.debug_canvas = tk.Canvas(self.debug_overlay, bg="black", highlightthickness=0)
        self.debug_canvas.pack(fill=tk.BOTH, expand=True)

    def set_debug_mode(self, is_show: bool):
        self.show_debug = is_show
        if self.show_debug:
            self.debug_overlay.deiconify()
            self._draw_debug_regions()
        else:
            self.debug_overlay.withdraw()

    def _draw_debug_regions(self):
        self.debug_canvas.delete("debug_elem")
        color_map = {
            "scope_region": "#34495E", "weapon_region": "#E74C3C", "stance_region": "#2ECC71",
            "minimap_region": "#3498DB", "largemap_region": "#9B59B6", "elevation_region": "#E67E22",
            "compass_region": "#F1C40F", "crosshair_region": "#FF69B4"
        }
        
        for name, rect in self.real_regions.items():
            x1, y1 = rect["left"], rect["top"]
            x2, y2 = x1 + rect["width"], y1 + rect["height"]
            color = color_map.get(name, "white")
            self.debug_canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2, tags="debug_elem")
            self.debug_canvas.create_text(x1 + 5, y1 - 10, text=name, fill=color, font=("Consolas", 10, "bold"), anchor="w", tags="debug_elem")
            
        scale_text = f"小地图 100m = {self.real_scales['minimap_100m_px']:.1f} px\n大地图 1km = {self.real_scales['largemap_1km_px']:.1f} px"
        cx, cy = self.real_w // 2, 50
        self.debug_canvas.create_text(cx, cy, text=scale_text, fill="#1ABC9C", font=("Microsoft YaHei", 12, "bold"), justify="center", tags="debug_elem")

    def calibrate_region(self, region_name):
        if region_name not in self.base_regions: return
        # 【核心修正】：大地图和小地图强制正方形
        force_square = (region_name in ["minimap_region", "largemap_region"])
        self._start_calibration_overlay(region_name, is_line=False, is_square=force_square)

    def calibrate_scale(self, scale_name):
        if scale_name not in self.base_scales: return
        self._start_calibration_overlay(scale_name, is_line=True, is_square=False)

    def _start_calibration_overlay(self, target_name, is_line=False, is_square=False):
        if self.show_debug:
            self.debug_overlay.withdraw()

        calib_win = tk.Toplevel(self.root)
        calib_win.attributes("-fullscreen", True)
        calib_win.attributes("-topmost", True)
        calib_win.attributes("-alpha", 0.3)
        calib_win.config(cursor="crosshair")
        
        canvas = tk.Canvas(calib_win, bg="black", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        calib_win.start_x = -1
        calib_win.start_y = -1
        calib_win.shape_id = None

        # 右键取消校准（不保存任何数据，直接关闭窗口）
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
                dx_real = end_x - calib_win.start_x
                dy_real = end_y - calib_win.start_y
                px_length_real = math.hypot(dx_real, dy_real)
                
                if px_length_real > 5:
                    self.real_scales[target_name] = px_length_real
                    dx_base = dx_real / self.scale_x
                    dy_base = dy_real / self.scale_y
                    self.base_scales[target_name] = math.hypot(dx_base, dy_base)
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
                    self.base_regions[target_name] = {
                        "left": int(round(real_left / self.scale_x)),
                        "top": int(round(real_top / self.scale_y)),
                        "width": int(round(real_width / self.scale_x)),
                        "height": int(round(real_height / self.scale_y))
                    }
                    self._save_config()
            
            calib_win.destroy()
            if self.show_debug:
                self.debug_overlay.deiconify()
                self._draw_debug_regions()

        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)
        canvas.bind("<Button-3>", on_cancel)   # 新增右键取消