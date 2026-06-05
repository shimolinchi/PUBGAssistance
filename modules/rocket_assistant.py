import threading
import time
import numpy as np
import tkinter as tk
import ctypes
from ctypes import wintypes
import json
import os

class RocketAssistant:
    """
    火箭筒/榴弹发射器 战术标尺辅助模块
    读取小地图距离，通过三次多项式自动拟合数据，在屏幕中心下方渲染动态刻度线。
    """
    def __init__(self, root, region_manager, minimap_module, fps=30, config_file="config.json"):
        self.root = root
        self.region_manager = region_manager
        self.screen_width = region_manager.real_w
        self.screen_height = region_manager.real_h
        self.fps = fps
        self.minimap = minimap_module          # 小地图雷达模块实例
        
        self.is_enabled = False
        self._thread_running = False
        self.hud_thread = None

        # 颜色映射（与小地图模块保持一致）
        self.color_map = {
            "Yellow": "#E3D43C", "Orange": "#B3500D", 
            "Blue": "#1A3EA3", "Green": "#109166"
        }

        # 标定数据（距离 vs 屏幕下落比例）
        self.calib_dists = []      # 距离（米）
        self.calib_ratios = []     # 对应的屏幕垂直比例（0~1，0=准星，1=标尺底端）
        self.end_y = self.screen_height * 0.9   # 标尺底端 Y 坐标（默认屏幕下方 90% 处）

        # 加载配置文件中的火箭筒标定数据
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    data = config.get("rocket_config", {})
                    raw_dists = data.get("calib_dists", [])
                    raw_ratios = data.get("calib_ratios", [])
                    if len(raw_dists) == len(raw_ratios) and len(raw_dists) > 0:
                        # 按距离排序，确保插值单调
                        sorted_pairs = sorted(zip(raw_dists, raw_ratios))
                        self.calib_dists = [p[0] for p in sorted_pairs]
                        self.calib_ratios = [p[1] for p in sorted_pairs]
                    self.end_y = self.screen_height * data.get("end_y_ratio", 0.9)
            except Exception as e:
                print(f"[火箭筒助手] 配置加载失败: {e}")

        # 计算标尺几何参数
        self.center_x = self.screen_width / 2
        self.center_y = self.screen_height / 2
        self.line_length = self.end_y - self.center_y   # 准星到标尺底端的像素长度

        # 创建透明覆盖层
        self.overlay = None
        self.canvas = None
        self._init_overlay()

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)

        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.overlay.update_idletasks()

        # 强制顶层样式（一次）
        try:
            hwnd = int(self.overlay.frame(), 16)
            GWLP_EXSTYLE = -20
            WS_EX_TOPMOST = 0x00000008
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWLP_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWLP_EXSTYLE, ex_style | WS_EX_TOPMOST)
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception as e:
            print(f"窗口顶层设置失败: {e}")

        # 关键：当窗口失去焦点（即用户点击其他窗口）时，重新提升
        def on_focus_out(event):
            self.overlay.lift()
            self.overlay.attributes("-topmost", True)
            # 可选：再次调用 API 确保
            try:
                hwnd = int(self.overlay.frame(), 16)
                ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001)
            except:
                pass

        self.overlay.bind("<FocusOut>", on_focus_out)

    def enable_module(self, enable: bool):
        """启动/停止整个火箭筒辅助系统（同时控制小地图雷达）"""
        self.is_enabled = enable
        # 同步控制小地图雷达的启停
        # self.minimap.set_enabled(enable)

        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.hud_thread = threading.Thread(target=self._hud_loop, daemon=True)
            self.hud_thread.start()
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            self.canvas.delete("rocket_hud")

    def _calculate_drop_ratio(self, distance):
        """根据距离插值计算屏幕下落比例（0~1）"""
        if not self.calib_dists:
            return 0.0
        # 边界处理：超出标定范围时使用最近端点
        if distance <= self.calib_dists[0]:
            return self.calib_ratios[0]
        if distance >= self.calib_dists[-1]:
            return self.calib_ratios[-1]
        # 线性插值
        ratio = np.interp(distance, self.calib_dists, self.calib_ratios)
        return max(0.0, min(1.0, ratio))

    def _hud_loop(self):
        """后台线程：定期获取小地图数据，计算标尺位置，并刷新UI"""
        while self._thread_running:
            start_time = time.time()

            # 从小地图雷达获取当前各颜色目标的距离（米）
            mini_dists = self.minimap.get_measured_distance()
            hud_data = []

            for color_name, base_hex in self.color_map.items():
                dist = mini_dists.get(color_name, 0.0)
                if dist > 0:   # 只显示有效距离的目标
                    ratio = self._calculate_drop_ratio(dist)
                    hud_data.append({
                        "color": base_hex,
                        "ratio": ratio,
                        "distance": dist
                    })

            # 在主线程中绘制标尺
            self.root.after(0, self._render_hud, hud_data)

            elapsed = time.time() - start_time
            sleep_time = max(0, (1.0 / self.fps) - elapsed)
            time.sleep(sleep_time)

    def _render_hud(self, data):
        """在主线程中绘制标尺和刻度标记"""
        if not self._thread_running:
            return
        self.canvas.delete("rocket_hud")

        # 绘制中心基准线（从准星到底端）
        self.canvas.create_line(self.center_x, self.center_y, self.center_x, self.end_y,
                                fill="white", width=2, tags="rocket_hud")

        # 绘制每个目标的刻度横线和三角指示器
        h_line_width = 30   # 横线向左延伸的长度（像素）
        for item in data:
            c_hex = item["color"]
            ratio = item["ratio"]
            dist = item["distance"]

            # 可选：过滤超出合理范围的距离（例如大于200米）
            if dist > 200:
                continue

            # 计算横线的 Y 坐标（屏幕像素）
            target_y = self.center_y + ratio * self.line_length
            # 确保不超出屏幕底部
            if target_y > self.screen_height - 10:
                target_y = self.screen_height - 10

            left_x = self.center_x - h_line_width

            # 画横线
            self.canvas.create_line(left_x, target_y, self.center_x, target_y,
                                    fill=c_hex, width=1, tags="rocket_hud")

            # 画左侧三角指示器（尖角指向横线右端）
            tri_w = 8
            tri_h = 10
            pt_tip = (left_x, target_y)
            pt_top = (left_x - tri_w, target_y - tri_h // 2)
            pt_bot = (left_x - tri_w, target_y + tri_h // 2)
            self.canvas.create_polygon(pt_tip, pt_top, pt_bot, fill=c_hex, outline="black", tags="rocket_hud")

            # 显示距离文字（位于三角左侧）
            self.canvas.create_text(left_x - tri_w - 5, target_y, text=f"{dist:.0f}m",
                                    fill=c_hex, font=("Consolas", 12, "bold"), anchor="e", tags="rocket_hud")