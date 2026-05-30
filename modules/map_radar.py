import tkinter as tk
import math
import json
import os
from pynput import mouse

class MapDistanceAssistant:
    """PUBG 大地图手动测距模块"""
    def __init__(self, root, screen_width, screen_height, config_file="config.json"):
        self.root = root
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.config_file = config_file
        
        # 核心数据
        self.map_rect = None
        self.map_1km_pixels = 540 # 默认 1km 对应的像素数
        self.load_config()

        # 状态机: "IDLE", "WAIT_P1", "WAIT_P2", "DONE"
        self.state = "IDLE"
        self.pt1 = None
        self.pt2 = None
        self.distance_m = 0.0

        self.overlay = None
        self.canvas = None
        self._init_overlay()

    def load_config(self):
        """读取 config.json 中的大地图标定和像素比例"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    self.map_rect = config_data.get("map_rect")
                    self.map_1km_pixels = config_data.get("map_1km_pixels", 540)
            except Exception as e:
                print(f"[测距模块] 配置文件读取失败: {e}")

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True, "-topmost", True, "-transparentcolor", "black")
        self.overlay.overrideredirect(True)
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # 让窗口隐身，防止阻挡鼠标点击 (仅作为显示层)
        self.overlay.update_idletasks()
        try:
            import ctypes
            hwnd = int(self.overlay.frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception:
            pass

    # ================= 状态机与按键事件 =================
    def toggle_mode(self):
        """由主程序快捷键调用 (Ctrl+Shift+`)"""
        # 每次启动时重新读取一下配置，以防中途被修改
        self.load_config()
        
        if self.state == "IDLE" or self.state == "DONE":
            self.state = "WAIT_P1"
            self.pt1 = None
            self.pt2 = None
            print("[测距模块] 启动测距，等待点击起点...")
        else:
            self.cancel()
        self._update_ui()

    def cancel(self):
        """重置状态机并清空画布"""
        self.state = "IDLE"
        self.pt1 = None
        self.pt2 = None
        self._update_ui()
        print("[测距模块] 测距已取消/退出")

    def on_mouse_click(self, x, y, button, pressed):
        """由主程序的 pynput listener 转发过来"""
        if not pressed:
            return

        # 任何状态下按下右键 -> 直接退出测距
        if button == mouse.Button.right:
            if self.state != "IDLE":
                self.cancel()
            return

        # 状态机：处理左键点击
        if button == mouse.Button.left:
            if self.state == "WAIT_P1":
                self.pt1 = (x, y)
                self.state = "WAIT_P2"
                self._update_ui()
                print(f"[测距模块] 起点已确认: {self.pt1}，等待终点...")
                
            elif self.state == "WAIT_P2":
                self.pt2 = (x, y)
                self._calculate_distance()
                self.state = "DONE"
                self._update_ui()
                print(f"[测距模块] 终点已确认: {self.pt2}，测距完成: {self.distance_m:.1f}m")

    def _calculate_distance(self):
        """计算两点之间的实际距离(米)"""
        if self.pt1 and self.pt2:
            dx = self.pt2[0] - self.pt1[0]
            dy = self.pt2[1] - self.pt1[1]
            px_distance = math.hypot(dx, dy)
            # 像素距离 / 1km的像素数 * 1000 = 实际米数
            self.distance_m = (px_distance / self.map_1km_pixels) * 1000.0

    # ================= UI 渲染层 =================
    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Canvas 画圆角矩形的黑科技"""
        points = [x1+radius, y1, x2-radius, y1, x2, y1, x2, y1+radius,
                  x2, y2-radius, x2, y2, x2-radius, y2, x1+radius, y2,
                  x1, y2, x1, y2-radius, x1, y1+radius, x1, y1]
        self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _update_ui(self):
        """根据当前状态机渲染画面"""
        self.canvas.delete("all")
        
        if self.state == "IDLE":
            return

        # 1. 绘制标点和连线
        if self.pt1:
            cx, cy = self.pt1
            self.canvas.create_oval(cx-4, cy-4, cx+4, cy+4, fill="#E3D43C", outline="black", width=2)
        if self.pt2:
            cx, cy = self.pt2
            self.canvas.create_oval(cx-4, cy-4, cx+4, cy+4, fill="#E74C3C", outline="black", width=2)
        if self.pt1 and self.pt2:
            self.canvas.create_line(self.pt1[0], self.pt1[1], self.pt2[0], self.pt2[1], 
                                    fill="#E3D43C", width=3, dash=(6, 4))

        # 2. 准备 HUD 文本内容
        bg_color = "#1E1E1E" # 深灰色背景
        if self.state == "WAIT_P1":
            text = "📍 请左键点击起点 (右键取消)"
            bg_color = "#2980B9"
        elif self.state == "WAIT_P2":
            text = "🎯 请左键点击终点 (右键取消)"
            bg_color = "#D35400"
        elif self.state == "DONE":
            text = f"直线距离: {self.distance_m:.0f} m"
            bg_color = "#27AE60"

        # 3. 计算 HUD 位置 (在迫击炮上方一点)
        box_w, box_h = 240, 45
        
        # 迫击炮的总宽度是 465 (4*105 + 3*15)，这里让测距的 UI 和迫击炮右对齐
        mortar_total_width = 465 
        start_x = self.screen_width - mortar_total_width - 25
        # 测距 HUD 靠右对齐
        x1 = start_x + mortar_total_width - box_w
        # 迫击炮的 Y 是 0.465，这里设为 0.40 (往上挪大约 70 像素)
        y1 = self.screen_height * 0.40 
        
        x2 = x1 + box_w
        y2 = y1 + box_h

        # 4. 绘制 HUD
        self._draw_rounded_rect(x1, y1, x2, y2, radius=12, fill=bg_color, outline="#34495E", width=2)
        
        cx = x1 + box_w / 2
        cy = y1 + box_h / 2
        font_size = 14 if self.state == "DONE" else 11
        self.canvas.create_text(cx, cy, text=text, fill="#FFFFFF", font=("Microsoft YaHei", font_size, "bold"))