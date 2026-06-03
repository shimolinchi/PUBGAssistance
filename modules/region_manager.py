import tkinter as tk
import json
import os
import math

class RegionManager:
    """
    绝地求生 全局视觉与校准管理器
    包含：区域框选 (Regions) 和 比例尺画线 (Scales)
    """
    def __init__(self, root, config_file="config.json"):
        self.root = root
        self.config_file = config_file
        
        self.show_debug = False
        
        # 1. 矩形区域数据 (默认值)
        self.regions = {
            "scope_region": {"left": 0, "top": 0, "width": 1920, "height": 1080},
            "weapon_region": {"left": 800, "top": 900, "width": 300, "height": 100},
            "stance_region": {"left": 400, "top": 950, "width": 50, "height": 50},
            "minimap_region": {"left": 1600, "top": 800, "width": 300, "height": 300},
            "largemap_region": {"left": 400, "top": 100, "width": 1100, "height": 800},
            "elevation_region": {"left": 960, "top": 540, "width": 100, "height": 300},
            "compass_region": {"left": 800, "top": 20, "width": 300, "height": 40},
            "crosshair_region": {"left": 800, "top": 900, "width": 300, "height": 100},
        }
        
        # 2. 比例尺数据 (像素距离，默认值)
        self.scales = {
            "minimap_100m_px": 100.0,
            "largemap_1km_px": 150.0
        }
        
        self._load_config()
        
        self.debug_overlay = None
        self.debug_canvas = None
        self._init_debug_overlay()

    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 加载区域
                    if "detection_regions" in config:
                        for key in self.regions.keys():
                            if key in config["detection_regions"]:
                                self.regions[key] = config["detection_regions"][key]
                    # 加载比例尺
                    if "map_scales" in config:
                        for key in self.scales.keys():
                            if key in config["map_scales"]:
                                self.scales[key] = config["map_scales"][key]
            except Exception as e:
                print(f"[全局管理] 配置加载失败: {e}")

    def _save_config(self):
        config = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except: pass
        
        config["detection_regions"] = self.regions
        config["map_scales"] = self.scales
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print("[全局管理] 区域与比例尺配置已保存！")
        except Exception as e:
            print(f"[全局管理] 保存失败: {e}")

    def get_region(self, region_name):
        return self.regions.get(region_name)

    def get_scale(self, scale_name):
        return self.scales.get(scale_name)

    # ==================== 调试图层 ====================
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
            "compass_region": "#F1C40F"
        }
        
        # 画区域框
        for name, rect in self.regions.items():
            x1, y1 = rect["left"], rect["top"]
            x2, y2 = x1 + rect["width"], y1 + rect["height"]
            color = color_map.get(name, "white")
            self.debug_canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2, tags="debug_elem")
            self.debug_canvas.create_text(x1 + 5, y1 - 10, text=name, fill=color, font=("Consolas", 10, "bold"), anchor="w", tags="debug_elem")
            
        # 在屏幕中央提示当前比例尺数据
        scale_text = f"小地图 100m = {self.scales['minimap_100m_px']:.1f} 像素\n大地图 1km = {self.scales['largemap_1km_px']:.1f} 像素"
        cx, cy = self.root.winfo_screenwidth() // 2, 50
        self.debug_canvas.create_text(cx, cy, text=scale_text, fill="#1ABC9C", font=("Microsoft YaHei", 12, "bold"), justify="center", tags="debug_elem")

    # ==================== 校准 1：矩形区域标定 ====================
    def calibrate_region(self, region_name):
        if region_name not in self.regions: return
        # 如果是小地图，强制锁定为正方形标定
        force_square = (region_name == "minimap_region")
        self._start_calibration_overlay(region_name, is_line=False, is_square=force_square)

    # ==================== 校准 2：距离比例尺标定 ====================
    def calibrate_scale(self, scale_name):
        if scale_name not in self.scales: return
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
                    # 【核心修改】：如果是正方形模式，取最大偏移量作为边长
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
                import math
                px_length = math.hypot(end_x - calib_win.start_x, end_y - calib_win.start_y)
                if px_length > 5:
                    self.scales[target_name] = px_length
                    self._save_config()
            else:
                # 【核心修改】：保存正方形坐标
                if is_square:
                    side = max(abs(end_x - calib_win.start_x), abs(end_y - calib_win.start_y))
                    end_x = calib_win.start_x + (side if end_x > calib_win.start_x else -side)
                    end_y = calib_win.start_y + (side if end_y > calib_win.start_y else -side)
                
                left = min(calib_win.start_x, end_x)
                top = min(calib_win.start_y, end_y)
                width = abs(end_x - calib_win.start_x)
                height = abs(end_y - calib_win.start_y)
                
                if width > 5 and height > 5:
                    self.regions[target_name] = {"left": left, "top": top, "width": width, "height": height}
                    self._save_config()
            
            calib_win.destroy()
            if self.show_debug:
                self.debug_overlay.deiconify()
                self._draw_debug_regions()

        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)