import tkinter as tk
import threading
import time
import math
import numpy as np
import mss
import json
import os
import ctypes
import cv2
from pynput.keyboard import KeyCode
from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Controller as MouseController, Button

try:
    from modules.transparent_hud import TransparentHudWindow
except Exception:
    try:
        from transparent_hud import TransparentHudWindow
    except Exception:
        TransparentHudWindow = None

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[投掷物助手] Pillow 未安装，图标将显示为文字")

class ThrowablesAssistant:
    """
    PUBG 雷火闪投掷物战术助手
    包含：抬高角度指示、瞬爆圆弧刻度、以及自动瞬爆控制。
    新增：支持 Q/E 切换标点颜色，仅使用选定颜色进行瞬爆，显示彩色图标。
    """
    def __init__(self, root, region_manager, minimap_module, elevation_module, fps=30, config_file="config.json"):
        self.root = root
        self.region_manager = region_manager
        self.minimap = minimap_module
        self.elevation = elevation_module
        self.fps = fps

        # 获取屏幕尺寸
        self.sw = self.region_manager.real_w
        self.sh = self.region_manager.real_h

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

        # 标点颜色切换
        self.color_priority = ["Yellow", "Orange", "Blue", "Green"]
        self.selected_color = "Yellow"
        self.color_hex_map = {"Yellow": "#E9E511", "Orange": "#DA6226", "Blue": "#017BC2", "Green": "#0F9D16"}

        # 加载图标模板
        self.color_icon_img = None
        self._load_color_icon()

        # ================= 从配置读取标定数据 =================
        self.calib_dists = []
        self.calib_elevations_y = []
        self.calib_times = []
        self.jump_calib_dists = []
        self.jump_calib_elevations_y = []
        self.jump_calib_times = []
        self.jump_min_dist = 50.0
        self.jump_max_dist = 80.0
        self.jump_delay_after_release = 0.3
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
                    self.jump_calib_dists = data.get("jump_calib_dists", [])
                    jump_ratios = data.get("jump_calib_elevations_ratio", [])
                    self.jump_calib_elevations_y = [self.sh * r for r in jump_ratios]
                    self.jump_calib_times = data.get("jump_calib_times", [])
                    self.jump_min_dist = data.get("jump_min_dist", 50.0)
                    self.jump_max_dist = data.get("jump_max_dist", 80.0)
                    self.jump_delay_after_release = data.get("jump_delay_after_release", 0.3)
                    self.grenade_total_time = data.get("grenade_total_time", 5.0)
                    self.arc_radius = self.sw * data.get("arc_radius_ratio", 0.097)
            except Exception as e:
                print(f"[投掷物助手] 配置读取失败，使用默认值: {e}")

        self.overlay = None
        self.canvas = None
        self.alpha_hud = TransparentHudWindow() if TransparentHudWindow else None
        self._init_overlay()

    def _load_color_icon(self):
        icon_path = "templates/pnt/0.png"
        if os.path.exists(icon_path):
            img = cv2.imread(icon_path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                self.color_icon_img = img

    def _get_colored_icon(self, color_name):
        if not PIL_AVAILABLE or self.color_icon_img is None:
            return None
        hex_color = self.color_hex_map.get(color_name, "#FFFFFF").lstrip("#")
        bgr = (int(hex_color[4:6], 16), int(hex_color[2:4], 16), int(hex_color[0:2], 16))
        bgr_img = self.color_icon_img[:, :, :3]
        alpha = self.color_icon_img[:, :, 3]
        color_layer = np.full_like(bgr_img, bgr, dtype=np.uint8)
        alpha_norm = alpha / 255.0
        result = (color_layer * alpha_norm[..., np.newaxis] + bgr_img * (1 - alpha_norm[..., np.newaxis])).astype(np.uint8)
        result = cv2.cvtColor(result, cv2.COLOR_BGR2RGBA)
        result[:, :, 3] = alpha
        pil_img = Image.fromarray(result)
        return ImageTk.PhotoImage(pil_img)

    def set_pnt_colors(self, colors):
        self.color_hex_map = {name: data.get("hex", "#FFFFFF") for name, data in colors.items()}

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)

        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.overlay.update_idletasks()

        try:
            hwnd = int(self.overlay.frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception as e:
            print(f"[投掷物助手] 隐身 API 调用失败: {e}")

    def enable_module(self, enabled: bool):
        self.is_enabled = enabled
        if self.is_enabled and not self._thread_running:
            self._thread_running = True
            self.hud_thread = threading.Thread(target=self._hud_loop, daemon=True)
            self.hud_thread.start()
        elif not self.is_enabled and self._thread_running:
            self._thread_running = False
            self.canvas.delete("throwables_hud")
            if self.alpha_hud:
                self.alpha_hud.clear()
            self.auto_throw_armed = False
            if self.throw_timer:
                self.throw_timer.cancel()

    def _show_temporary_warning(self, text, color="#E74C3C"):
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

    # ========== 颜色切换与显示 ==========
    def on_key_press(self, key):
        if not self.is_enabled:
            return
        try:
            char = None
            if hasattr(key, 'char') and key.char:
                char = key.char.lower()
            elif hasattr(key, 'vk') and key.vk is not None:
                if key.vk == 81:
                    char = 'q'
                elif key.vk == 69:
                    char = 'e'
            if char not in ['q', 'e']:
                return

            idx = self.color_priority.index(self.selected_color)
            if char == 'q':
                new_idx = (idx - 1) % len(self.color_priority)
            else:
                new_idx = (idx + 1) % len(self.color_priority)
            self.selected_color = self.color_priority[new_idx]

            # self._show_color_change()
        except Exception as e:
            print(f"[投掷物助手] 颜色切换异常: {e}")

    def _show_color_change(self):
        if not self.canvas:
            return
        self.canvas.delete("color_tip")
        cx = self.sw // 2
        cy = self.sh // 2 + 100
        hex_code = self.color_hex_map.get(self.selected_color, "#FFFFFF")
        self.canvas.create_text(cx, cy, text=f"切换到 {self.selected_color}", fill=hex_code,
                                font=("Microsoft YaHei", 14, "bold"), tags="color_tip")
        self.root.after(1500, lambda: self.canvas.delete("color_tip"))

    def _draw_color_indicator(self):
        """绘制当前使用的标点颜色指示器（文字+彩色图标，位于屏幕中下方偏左）"""
        if not self.canvas:
            return
        # 位置：屏幕宽度 1/4 处，距离底部 80 像素
        x = self.sw // 4
        y = self.sh - 80
        hex_code = self.color_hex_map.get(self.selected_color, "#FFFFFF")

        self.canvas.delete("color_indicator")
        # 文字
        self.canvas.create_text(x, y, text="当前使用标点：", fill=hex_code,
                                font=("Microsoft YaHei", 14, "bold"), anchor="e", tags="color_indicator")
        # 彩色图标
        colored_icon = self._get_colored_icon(self.selected_color)
        if colored_icon:
            self.current_icon = colored_icon
            self.canvas.create_image(x + 10, y, image=colored_icon, anchor="w", tags="color_indicator")
        else:
            # 降级：显示颜色名称
            self.canvas.create_text(x + 10, y, text=self.selected_color, fill=hex_code,
                                    font=("Microsoft YaHei", 12, "bold"), anchor="w", tags="color_indicator")

    # ========== 瞬爆逻辑：仅使用选定颜色 ==========
    def toggle_auto_throw(self):
        if not self.is_enabled:
            return

        dist_dict = self.minimap.get_measured_distance()
        dist = dist_dict.get(self.selected_color, 0.0)

        if dist <= 0.0:
            self._show_temporary_warning(f"[ 未检测到 {self.selected_color} 标点 ]")
            return

        use_jump_throw = False
        if dist >= self.jump_min_dist and dist <= self.jump_max_dist:
            if not self.jump_calib_dists or not self.jump_calib_times:
                self._show_temporary_warning("[ 跳投参数未配置 ]")
                return
            use_jump_throw = True
        elif dist > self.jump_max_dist:
            self._show_temporary_warning(f"[ 目标距离 {dist:.1f}m 太远 ]")
            return

        time_dists = self.jump_calib_dists if use_jump_throw else self.calib_dists
        time_values = self.jump_calib_times if use_jump_throw else self.calib_times
        target_time = np.interp(dist, time_dists, time_values)
        target_time = max(0.0, min(target_time, self.grenade_total_time))

        mode_text = "跳投瞬爆" if use_jump_throw else "自动瞬爆"
        print(f"[投掷助手] ⚡ {mode_text}启动! 标点颜色:{self.selected_color} 目标: {dist:.1f}m, 捏雷: {target_time:.2f}s")
        self._show_temporary_warning(f"{mode_text}: {dist:.1f}m", color="#2ECC71")

        # 模拟拉环（按 R）
        self.kb_controller.press(KeyCode.from_char('r'))
        time.sleep(0.01)
        self.kb_controller.release(KeyCode.from_char('r'))

        if self.throw_timer:
            self.throw_timer.cancel()
        self.throw_timer = threading.Timer(target_time, self._execute_throw, args=(use_jump_throw,))
        self.throw_timer.start()

    def _execute_throw(self, use_jump_throw=False):
        print("[投掷助手] 💥 瞬爆时机已到，自动抛出！")
        self.kb_controller.release(Key.end)
        self.mouse_controller.release(Button.left)
        if use_jump_throw:
            threading.Timer(self.jump_delay_after_release, self._tap_jump_key).start()

    def _tap_jump_key(self):
        self.kb_controller.press(Key.space)
        time.sleep(0.03)
        self.kb_controller.release(Key.space)

    # ================= 核心渲染循环 =================
    def _hud_loop(self):
        while self._thread_running:
            mini_dists = self.minimap.get_measured_distance()
            valid_targets = []
            for color_name, dist in mini_dists.items():
                if dist > 0.0:
                    valid_targets.append({
                        "dist": dist,
                        "color": self.color_hex_map.get(color_name, "#FFFFFF"),
                        "color_name": color_name
                    })
            self.root.after(0, self._draw_hud, valid_targets, self.color_hex_map)
            time.sleep(0.03)

    def _draw_hud(self, valid_targets, color_hex_map):
        self.canvas.delete("throwables_hud")
        if not self.is_enabled:
            if self.alpha_hud:
                self.alpha_hud.clear()
            return

        cx = self.sw / 2
        cy = self.sh / 2
        bottom_y = self.sh * 0.9

        if self.alpha_hud:
            elements = [{
                "type": "line",
                "x1": cx,
                "y1": cy,
                "x2": cx,
                "y2": bottom_y,
                "fill": "#FFFFFF",
                "alpha": 255,
                "width": 1,
            }]
            h_line_width = 30
            for target in valid_targets:
                dist = target['dist']
                color_hex = target['color']
                elev_y = self._get_elevation_y(dist)
                elements.append({
                    "type": "line",
                    "x1": cx - h_line_width,
                    "y1": elev_y,
                    "x2": cx + h_line_width,
                    "y2": elev_y,
                    "fill": color_hex,
                    "alpha": 255,
                    "width": 1,
                })
                elements.append({
                    "type": "text",
                    "x": cx + h_line_width + 8,
                    "y": elev_y,
                    "text": f"{dist:.0f}m",
                    "fill": color_hex,
                    "alpha": 153,
                    "font_size": 14,
                    "anchor": "lm",
                })
            self.alpha_hud.render_elements(elements)
            return

        self.canvas.create_line(cx, cy, cx, bottom_y, fill="#FFFFFF", width=1, tags="throwables_hud")

        for target in valid_targets:
            dist = target['dist']
            color_hex = target['color']

            # 抬高标尺
            elev_y = self._get_elevation_y(dist)
            self.canvas.create_line(cx - 30, elev_y, cx + 30, elev_y, fill=color_hex, width=1, tags="throwables_hud")
            self.canvas.create_text(cx + 38, elev_y, text=f"{dist:.0f}m", fill=color_hex,
                                    font=("Consolas", 14, "bold"), anchor="w", tags="throwables_hud")

        # 当前使用标点由主程序统一显示。

    def _get_elevation_y(self, dist):
        if dist >= self.jump_min_dist and dist <= self.jump_max_dist and self.jump_calib_dists and self.jump_calib_elevations_y:
            return np.interp(dist, self.jump_calib_dists, self.jump_calib_elevations_y)
        return np.interp(dist, self.calib_dists, self.calib_elevations_y)

    def shutdown(self):
        self._thread_running = False
        if self.alpha_hud:
            self.alpha_hud.destroy()
