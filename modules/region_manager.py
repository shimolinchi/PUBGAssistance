import tkinter as tk
import json
import os

class RegionManager:
    """
    绝地求生视觉检测区域管理器
    负责读取、保存、校准和可视化游戏内的关键检测区域。
    """
    def __init__(self, root, config_file="config.json"):
        self.root = root
        self.config_file = config_file
        
        # 控制是否显示调试框
        self.show_debug = False
        
        # 默认区域数据
        self.regions = {
            "scope_region": {"left": 0, "top": 0, "width": 1920, "height": 1080},
            "weapon_region": {"left": 800, "top": 900, "width": 300, "height": 100},
            "stance_region": {"left": 400, "top": 950, "width": 50, "height": 50}
        }
        
        self._load_config()
        
        # 调试图层 (平时隐藏)
        self.debug_overlay = None
        self.debug_canvas = None
        self._init_debug_overlay()

    def _load_config(self):
        """从 config.json 加载区域数据"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if "detection_regions" in config:
                        saved_regions = config["detection_regions"]
                        for key in self.regions.keys():
                            if key in saved_regions:
                                self.regions[key] = saved_regions[key]
            except Exception as e:
                print(f"[区域管理] 配置加载失败: {e}")

    def _save_config(self):
        """将区域数据保存回 config.json"""
        config = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        
        config["detection_regions"] = self.regions
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print("[区域管理] 区域配置已保存。")
        except Exception as e:
            print(f"[区域管理] 保存失败: {e}")

    def get_region(self, region_name):
        """获取指定区域的字典 {left, top, width, height}"""
        return self.regions.get(region_name)

    # ==================== 调试图层 ====================
    def _init_debug_overlay(self):
        self.debug_overlay = tk.Toplevel(self.root)
        self.debug_overlay.attributes("-fullscreen", True)
        self.debug_overlay.attributes("-topmost", True)
        self.debug_overlay.attributes("-transparentcolor", "black")
        self.debug_overlay.overrideredirect(True)
        self.debug_overlay.withdraw() # 默认隐藏
        
        self.debug_canvas = tk.Canvas(self.debug_overlay, bg="black", highlightthickness=0)
        self.debug_canvas.pack(fill=tk.BOTH, expand=True)

    def set_debug_mode(self, is_show: bool):
        """开关调试框显示"""
        self.show_debug = is_show
        if self.show_debug:
            self.debug_overlay.deiconify()
            self._draw_debug_regions()
        else:
            self.debug_overlay.withdraw()

    def _draw_debug_regions(self):
        self.debug_canvas.delete("debug_box")
        color_map = {
            "scope_region": "#F1C40F",  # 倍镜区：黄色
            "weapon_region": "#E74C3C", # 武器区：红色
            "stance_region": "#2ECC71"  # 姿势区：绿色
        }
        
        for name, rect in self.regions.items():
            x1, y1 = rect["left"], rect["top"]
            x2, y2 = x1 + rect["width"], y1 + rect["height"]
            color = color_map.get(name, "white")
            
            self.debug_canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=3, tags="debug_box")
            self.debug_canvas.create_text(x1 + 5, y1 - 10, text=name, fill=color, font=("Consolas", 12, "bold"), anchor="w", tags="debug_box")

    # ==================== 交互式标定系统 ====================
    def calibrate_region(self, region_name):
        """启动全屏半透明遮罩，允许玩家框选区域"""
        if region_name not in self.regions:
            return

        print(f"正在标定: {region_name} - 请按住鼠标左键拖拽框选")
        
        # 临时关闭调试层以防干扰
        if self.show_debug:
            self.debug_overlay.withdraw()

        calib_win = tk.Toplevel(self.root)
        calib_win.attributes("-fullscreen", True)
        calib_win.attributes("-topmost", True)
        calib_win.attributes("-alpha", 0.3) # 整体半透明
        calib_win.config(cursor="crosshair")
        
        canvas = tk.Canvas(calib_win, bg="black", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # 内部状态变量
        calib_win.start_x = -1
        calib_win.start_y = -1
        calib_win.rect_id = None

        def on_mouse_down(event):
            calib_win.start_x = event.x
            calib_win.start_y = event.y
            calib_win.rect_id = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=2)

        def on_mouse_drag(event):
            if calib_win.rect_id:
                canvas.coords(calib_win.rect_id, calib_win.start_x, calib_win.start_y, event.x, event.y)

        def on_mouse_up(event):
            end_x, end_y = event.x, event.y
            
            # 计算并确立合法的 left, top, width, height
            left = min(calib_win.start_x, end_x)
            top = min(calib_win.start_y, end_y)
            width = abs(end_x - calib_win.start_x)
            height = abs(end_y - calib_win.start_y)
            
            if width > 5 and height > 5: # 防止误触
                self.regions[region_name] = {
                    "left": left, "top": top, "width": width, "height": height
                }
                self._save_config()
            
            calib_win.destroy()
            
            # 恢复调试层显示
            if self.show_debug:
                self.debug_overlay.deiconify()
                self._draw_debug_regions()

        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)