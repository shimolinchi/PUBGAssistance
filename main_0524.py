import tkinter as tk
import ctypes
import mss  # 仅用于获取真实屏幕分辨率
from pynput.mouse import Controller
from pynput import keyboard

from minimap_radar import MinimapRadarModule
from compass_radar import CompassRadarModule
from elevation_radar import ElevationRadarModule
from mortar_assistance import MortarAssistance

# 1. 顶部罗盘捕捉区域 (极度扁平的长条)
COMPASS_START_Y = 0.00   # 顶端开始
COMPASS_END_Y   = 0.10   # 占屏幕高度前 10%
COMPASS_START_X = 0.00   # 最左侧
COMPASS_END_X   = 1.00   # 最右侧

# 2. 中心高低角捕捉区域 (极度细长的竖条，避开顶部罗盘)
ELEV_START_Y    = 0.11   # 从 11% 开始 (完美避开顶部 10% 的罗盘)
ELEV_END_Y      = 0.66   # 到 66% 结束 (大约屏幕三分之二)
ELEV_START_X    = 0.47   # 中心偏左一点 (宽度占屏幕宽度的 6%)
ELEV_END_X      = 0.53   # 中心偏右一点

# 3. 迫击炮距离显示区域
DIST_START_Y    = 0.490  # 文字框左上角y
DIST_END_Y      = 0.535  # 文字框右下角y
DIST_START_X    = 0.680  # 文字框左上角x
DIST_END_X      = 0.720  # 文字框右下角x

class PubgAssistance:
    def __init__(self, root):
        self.root = root
        self.root.title("PUBG 战术指挥中枢")
        self.root.geometry("380x350")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            self.screen_width = monitor["width"]
            self.screen_height = monitor["height"]

        print(f"[系统] 检测到屏幕分辨率: {self.screen_width}x{self.screen_height}")

        # ================= 实例化核心模块 =================
        self.minimap = MinimapRadarModule(self.root)
        self.compass = CompassRadarModule(screen_width=self.screen_width)
        self.elevation = ElevationRadarModule(screen_width=self.screen_width, screen_height=self.screen_height)
        self.assistance = MortarAssistance(self.minimap, self.compass, self.elevation)

        # 动态分配计算好的截取区域
        self.compass.monitor = self._calc_rect(COMPASS_START_X, COMPASS_END_X, COMPASS_START_Y, COMPASS_END_Y)
        self.elevation.monitor = self._calc_rect(ELEV_START_X, ELEV_END_X, ELEV_START_Y, ELEV_END_Y)
        self.assistance.ocr_monitor = self._calc_rect(DIST_START_X, DIST_END_X, DIST_START_Y, DIST_END_Y)
        
        # 默认小地图区域防护 (如果未配置文件标定)
        if not self.minimap.monitor:
            self.minimap.monitor = self._calc_rect(0.7, 0.9, 0.6, 0.9)

        # ================= 状态控制变量 =================
        self.is_running = False
        self.show_zones = False     # 是否显示监控区域虚线框
        self.show_targets = True    # 是否显示识别到的目标标点与数据
        
        self.minimap.set_display(False) # 关闭小地图模块自带的绘图，由主程序统一接管
        
        self.init_ui()
        self.init_master_overlay()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 启动键盘监听器
        self.kb_listener = keyboard.Listener(on_press=self.on_key_press)
        self.kb_listener.start()
        
        # 启动主渲染循环
        self.draw_loop()

    def _calc_rect(self, start_x_ratio, end_x_ratio, start_y_ratio, end_y_ratio):
        """将 0~1 的比例换算为真实的像素监控区域"""
        left = int(start_x_ratio * self.screen_width)
        top = int(start_y_ratio * self.screen_height)
        width = int((end_x_ratio - start_x_ratio) * self.screen_width)
        height = int((end_y_ratio - start_y_ratio) * self.screen_height)
        return {"top": top, "left": left, "width": width, "height": height}
    
    def init_master_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)
        
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 防截图黑科技
        self.overlay.update_idletasks()
        try:
            hwnd = int(self.overlay.frame(), 16)
            result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
            if result == 0:
                hwnd_alt = self.overlay.winfo_id()
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd_alt, 17)
        except Exception as e:
            print("隐藏画布失败:", e)

    def init_ui(self):
        tk.Label(self.root, text="PUBG 全局控制台", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 14, "bold")).pack(pady=10)
        
        # UI：小地图标定
        tk.Button(self.root, text="📏 重新标定小地图", command=self.minimap.trigger_calibration, 
                  bg="#3498DB", fg="white", font=("Microsoft YaHei", 10)).pack(fill="x", padx=30, pady=5)
                  
        # UI：监控区域显示开关
        self.btn_zones = tk.Button(self.root, text="显示监控区域: 关", command=self.toggle_zones, 
                                   bg="#7F8C8D", fg="white", font=("Microsoft YaHei", 10))
        self.btn_zones.pack(fill="x", padx=30, pady=5)
        
        # UI：目标标记显示开关
        self.btn_targets = tk.Button(self.root, text="显示目标标点: 开", command=self.toggle_targets, 
                                     bg="#2980B9", fg="white", font=("Microsoft YaHei", 10))
        self.btn_targets.pack(fill="x", padx=30, pady=5)

        # UI：F1 状态指示灯
        self.btn_f1 = tk.Button(self.root, text="F1: 迫击炮助手 (已停止)", state="disabled", 
                                disabledforeground="white", bg="#2ECC71", font=("Microsoft YaHei", 12, "bold"))
        self.btn_f1.pack(fill="x", padx=20, pady=15)

        self.show_osd = True
        self.btn_osd = tk.Button(self.root, text="显示左上角数据: 开", command=self.toggle_osd, 
                                 bg="#8E44AD", fg="white", font=("Microsoft YaHei", 10))
        self.btn_osd.pack(fill="x", padx=30, pady=5)

    def toggle_osd(self):
        self.show_osd = not self.show_osd
        self.btn_osd.config(text=f"显示左上角数据: {'开' if self.show_osd else '关'}")

    def toggle_zones(self):
        self.show_zones = not self.show_zones
        self.btn_zones.config(text=f"显示监控区域: {'开' if self.show_zones else '关'}", 
                              bg="#2980B9" if self.show_zones else "#7F8C8D")

    def toggle_targets(self):
        self.show_targets = not self.show_targets
        self.btn_targets.config(text=f"显示目标标点: {'开' if self.show_targets else '关'}", 
                                bg="#2980B9" if self.show_targets else "#7F8C8D")

    def draw_loop(self):
        """统一的渲染引擎：控制所有透明框的绘制"""
        self.canvas.delete("all")
        
        # 1. 绘制截取区域框 (由 UI 按钮控制)
        if self.show_zones:
            self.draw_zone(self.compass.monitor, "罗盘方位区")
            self.draw_zone(self.elevation.monitor, "垂直高低区")
            self.draw_zone(self.minimap.monitor, "小地图雷达区")
            self.draw_zone(self.assistance.ocr_monitor, "OCR 读数区")

        # 2. 绘制识别到的目标标点与数据 (由 UI 按钮控制，且需系统运行中或测距开启时才有数据)
        if self.show_targets and self.is_running:
            # 绘制罗盘标点 (橙色)
            h_ratio = self.compass.get_horizontal_ratio()
            if h_ratio is not None:
                abs_x = h_ratio * self.screen_width
                abs_y = self.compass.monitor["top"] + self.compass.monitor["height"] / 2
                self.canvas.create_polygon(abs_x, abs_y, abs_x-10, abs_y-20, abs_x+10, abs_y-20, fill="#FF8C00", outline="black")
                self.canvas.create_text(abs_x, abs_y+15, text=f"X:{h_ratio:.3f}", fill="#FF8C00", font=("Arial", 10, "bold"))

            # 绘制高低角标点 (天蓝色)
            v_ratio = self.elevation.get_vertical_ratio()
            if v_ratio is not None:
                abs_x = self.elevation.monitor["left"] + self.elevation.monitor["width"] / 2
                abs_y = v_ratio * self.screen_height
                self.canvas.create_polygon(abs_x, abs_y, abs_x-20, abs_y-10, abs_x-20, abs_y+10, fill="#00BFFF", outline="black")
                self.canvas.create_text(abs_x+35, abs_y, text=f"Y:{v_ratio:.3f}", fill="#00BFFF", font=("Arial", 10, "bold"))

            # 绘制小地图标点
            targets = self.minimap.get_latest_targets()
            for pt in targets:
                ax, ay = pt['x'], pt['y']
                color = pt['color']
                self.canvas.create_rectangle(ax-10, ay-20, ax+10, ay, outline=color, width=2)
                self.canvas.create_text(ax, ay+15, text=f"{pt['dist']:.1f}m", fill=color, font=("Arial", 10, "bold"))

            # 在屏幕中心偏下显示当前火控解算信息
            cx = self.screen_width / 2
            cy = self.screen_height / 2 + 150
            if self.assistance.true_distance > 0:
                self.canvas.create_text(cx, cy, text=f"装定距离: {self.assistance.true_distance:.1f}m", 
                                        fill="#E74C3C", font=("Microsoft YaHei", 14, "bold"))
                self.canvas.create_text(cx, cy+25, text=f"OCR读数: {self.assistance.current_mortar_dist}m", 
                                        fill="white", font=("Microsoft YaHei", 12))
        
        if self.show_osd and self.is_running:
            ast = self.assistance
            # 构建要显示的文本面板
            osd_text = (
                f"【火控中枢运行数据】\n"
                f"目标颜色: {list(ast.color_map.keys())[ast.target_color_index-1]}\n"
                f"测量距离 (小地图): {ast.measured_distance:.1f} m\n"
                f"罗盘偏差 (X轴): {ast.direction_deviation:.3f}\n"
                f"高低偏差 (Y轴): {ast.measured_elevation:.3f}\n"
                f"平地基准线: {ast.flat_ground_elevation:.3f}\n"
                f"--------------------------\n"
                f"解算真实距离: {ast.true_distance:.1f} m\n"
                f"OCR读取距离: {ast.current_mortar_dist} m"
            )
            
            # 画一个半透明的黑色背景框（利用黑色不会穿透的特性，这里用深灰色）
            self.canvas.create_rectangle(10, 10, 260, 200, fill="#222222", outline="#555555", tags="osd")
            # 写入绿色数据文字，坐标为 (20, 20)，anchor="nw" 表示以左上角对齐
            self.canvas.create_text(20, 20, text=osd_text, fill="#00FF00", anchor="nw", 
                                    font=("Consolas", 11, "bold"), tags="osd")

        # 约 30 FPS 刷新率
        self.root.after(30, self.draw_loop)
        

    def draw_zone(self, monitor, label):
        """绘制透明监控区域的虚线框"""
        if not monitor: return
        x1, y1 = monitor["left"], monitor["top"]
        x2, y2 = x1 + monitor["width"], y1 + monitor["height"]
        
        self.canvas.create_rectangle(x1-1, y1-1, x2+1, y2+1, outline="black", width=2)
        self.canvas.create_rectangle(x1, y1, x2, y2, outline="white", width=2, dash=(5, 5))
        self.canvas.create_text(x1+5, y1+5, text=label, fill="black", anchor="nw", font=("Microsoft YaHei", 10, "bold"))
        self.canvas.create_text(x1+4, y1+4, text=label, fill="white", anchor="nw", font=("Microsoft YaHei", 10, "bold"))

    def on_key_press(self, key):
        """键盘回调函数：F1 启停控制"""
        try:
            if key == keyboard.Key.f1:
                if not self.is_running:
                    # 启动
                    self.assistance.enable_ranging(True)
                    self.assistance.start_auto_adjustment(target_color_index=1)
                    self.is_running = True            
                    self.btn_f1.config(text="F1: 迫击炮助手 (运行中)", bg="#E74C3C")
                    print("[热键] 迫击炮助手已启动")
                else:
                    # 停止
                    self.assistance.stop_auto_adjustment()
                    self.assistance.enable_ranging(False)
                    self.is_running = False
                    self.btn_f1.config(text="F1: 迫击炮助手 (已停止)", bg="#2ECC71")
                    print("[热键] 迫击炮助手已停止")
        except AttributeError:
            pass

    def on_closing(self):
        """清理资源、停止线程"""
        self.kb_listener.stop()
        self.assistance.stop_auto_adjustment()
        self.assistance.enable_ranging(False)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PubgAssistance(root)
    root.mainloop()