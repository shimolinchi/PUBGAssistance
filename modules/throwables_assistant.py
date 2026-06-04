import tkinter as tk
import threading
import time
import math
import numpy as np
import mss
import json
import os
import ctypes
from pynput.keyboard import KeyCode
from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Controller as MouseController, Button

class ThrowablesAssistant:
    """
    PUBG 雷火闪投掷物战术助手
    包含：抬高角度指示、瞬爆圆弧刻度、以及自动瞬爆控制。
    """
    def __init__(self, root, region_manager, minimap_module, elevation_module, fps=30, config_file="config.json"):
        self.root = root
        self.region_manager = region_manager
        self.minimap = minimap_module
        self.elevation = elevation_module
        self.fps = fps

        # 获取屏幕尺寸
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()

        # 状态控制
        self.is_enabled = False
        self._thread_running = False
        self.hud_thread = None

        # 控制器
        self.kb_controller = KeyboardController()
        self.mouse_controller = MouseController()

        # 瞬爆状态
        self.auto_throw_armed = False
        self.throw_timer = None

        # ================= 从配置读取标定数据 =================
        self.calib_dists = []
        self.calib_elevations_y = []
        self.calib_times = []
        self.grenade_total_time = 5.0
        self.arc_radius = self.sw * 0.097  # 默认值

        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    data = config.get("throwables_config", {})

                    self.calib_dists = data.get("calib_dists", [])
                    # 将比例转回当前分辨率的像素坐标
                    ratios = data.get("calib_elevations_ratio", [])
                    self.calib_elevations_y = [self.sh * r for r in ratios]

                    self.calib_times = data.get("calib_times", [])
                    self.grenade_total_time = data.get("grenade_total_time", 5.0)
                    self.arc_radius = self.sw * data.get("arc_radius_ratio", 0.097)
            except Exception as e:
                print(f"[投掷物助手] 配置读取失败，使用默认值: {e}")

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

        # ========== 一次性强制最高层（与其他模块一致） ==========
        try:
            hwnd = int(self.overlay.frame(), 16)
            GWLP_EXSTYLE = -20
            WS_EX_TOPMOST = 0x00000008
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWLP_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWLP_EXSTYLE, ex_style | WS_EX_TOPMOST)

            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)

            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.BringWindowToTop(hwnd)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception as e:
            print(f"[投掷物助手] 窗口置顶失败: {e}")

    def enable_module(self, enabled: bool):
        self.is_enabled = enabled
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.hud_thread = threading.Thread(target=self._hud_loop, daemon=True)
            self.hud_thread.start()
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            self.canvas.delete("throwables_hud")
            self.auto_throw_armed = False
            if self.throw_timer:
                self.throw_timer.cancel()

    def _show_temporary_warning(self, text, color="#E74C3C"):
        """显示一段短暂的警告文字，2秒后自动消失"""
        warn_y = self.sh * 0.75
        self.canvas.delete("temp_warning")
        self.canvas.create_text(
            self.sw/2, warn_y,
            text=text,
            fill=color,
            font=("Microsoft YaHei", 12, "bold"),
            tags="temp_warning"
        )
        self.root.after(2000, lambda: self.canvas.delete("temp_warning"))

    def toggle_auto_throw(self):
        """主程序按 V 键时调用此函数：整合检测与拉环执行"""
        if not self.is_enabled:
            return

        mini_dists = self.minimap.get_measured_distance()
        valid_times = []
        valid_dists = []

        for color, dist in mini_dists.items():
            if dist > 0.0:
                target_time = np.interp(dist, self.calib_dists, self.calib_times)
                valid_times.append(target_time)
                valid_dists.append(dist)

        if len(valid_times) == 0:
            self._show_temporary_warning("[ 未检测到有效标点 ]")
            return

        avg_dist = sum(valid_dists) / len(valid_dists)
        if avg_dist > 50.0:
            self._show_temporary_warning(f"[ 目标距离 {avg_dist:.1f}m 太远 ]")
            return

        avg_time = sum(valid_times) / len(valid_times)
        print(f"[投掷助手] ⚡ 瞬爆启动! 目标: {avg_dist:.1f}m, 捏雷: {avg_time:.2f}s")
        self._show_temporary_warning(f"自动瞬爆准备: {avg_dist:.1f}m", color="#2ECC71")

        # 模拟拉环（按 R）
        self.kb_controller.press(KeyCode.from_char('r'))
        time.sleep(0.01)
        self.kb_controller.release(KeyCode.from_char('r'))

        # 启动计时器
        if self.throw_timer:
            self.throw_timer.cancel()
        self.throw_timer = threading.Timer(avg_time, self._execute_throw)
        self.throw_timer.start()

    def _execute_throw(self):
        """时间一到，通过 pynput 硬件级模拟松手动作"""
        print("[投掷助手] 💥 瞬爆时机已到，自动抛出！")
        self.kb_controller.release(Key.end)
        self.mouse_controller.release(Button.left)

    # ================= 核心渲染循环 =================
    def _draw_hud(self, valid_targets):
        self.canvas.delete("throwables_hud")
        if not self.is_enabled:
            return

        cx = self.sw / 2
        cy = self.sh / 2

        # 垂直参考线
        bottom_y = self.sh * 0.9
        self.canvas.create_line(cx, cy, cx, bottom_y, fill="#FFFFFF", width=1, tags="throwables_hud")

        # 瞬爆圆弧设定：从右下 +25° 到右上 -25°
        arc_start_deg = 25
        arc_end_deg = -25

        for target in valid_targets:
            dist = target['dist']
            color = target['color']

            # 抬高标尺
            elev_y = np.interp(dist, self.calib_dists, self.calib_elevations_y)
            self.canvas.create_line(cx, elev_y, cx + 30, elev_y, fill=color, width=1, tags="throwables_hud")
            self.canvas.create_oval(cx + 30, elev_y - 4, cx + 38, elev_y + 4, fill=color, outline="", tags="throwables_hud")
            self.canvas.create_text(cx + 45, elev_y, text=f"{dist:.0f}m", fill=color, font=("Consolas", 12, "bold"), anchor="w", tags="throwables_hud")

            # 圆弧瞬爆倒计时
            target_time = np.interp(dist, self.calib_dists, self.calib_times)
            target_time = max(0.0, min(target_time, self.grenade_total_time))

            time_ratio = target_time / self.grenade_total_time
            current_deg = arc_start_deg + time_ratio * (arc_end_deg - arc_start_deg)
            rad = math.radians(current_deg)

            p_outer_x = cx + self.arc_radius * math.cos(rad)
            p_outer_y = cy + self.arc_radius * math.sin(rad)
            p_inner_x = cx + (self.arc_radius - 10) * math.cos(rad)
            p_inner_y = cy + (self.arc_radius - 10) * math.sin(rad)

            self.canvas.create_line(p_outer_x, p_outer_y, p_inner_x, p_inner_y, fill=color, width=2, tags="throwables_hud")
            text_x = p_outer_x + 10
            self.canvas.create_text(text_x, p_outer_y, text=f"{target_time:.1f}s", fill=color, font=("Consolas", 12, "bold"), anchor="w", tags="throwables_hud")

    def _hud_loop(self):
        color_hex_map = {
            "Yellow": "#E3D43C", "Orange": "#B3500D",
            "Blue": "#1A3EA3", "Green": "#109166"
        }
        while self._thread_running:
            mini_dists = self.minimap.get_measured_distance()
            valid_targets = []
            for color, dist in mini_dists.items():
                if dist > 0.0:
                    valid_targets.append({
                        "dist": dist,
                        "color": color_hex_map[color]
                    })
            self.root.after(0, self._draw_hud, valid_targets)
            time.sleep(0.03)