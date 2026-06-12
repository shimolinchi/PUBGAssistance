import tkinter as tk
import threading
import time
import ctypes
import cv2
import numpy as np
import os

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[C4助手] Pillow 未安装，图标将显示为文字")

class C4Assistant:
    def __init__(self, root, region_manager, minimap_module, fps=30, explosion_margin=2.0, target_speed=50.0, jump_distance_threshold=20.0):
        self.root = root
        self.rm = region_manager
        self.minimap = minimap_module
        self.fps = fps
        self.explosion_margin = explosion_margin
        self.target_speed = target_speed
        self.jump_distance_threshold = jump_distance_threshold  # 新增：跳车距离阈值（米）

        self.sw = self.rm.real_w
        self.sh = self.rm.real_h

        self.color_priority = ["Yellow", "Orange", "Blue", "Green"]
        self.selected_color = "Yellow"
        self.color_hex_map = {"Yellow": "#E9E511", "Orange": "#DA6226", "Blue": "#017BC2", "Green": "#0F9D16"}
        self.distance = 0.0

        self.is_enabled = False
        self.c4_equipped = False
        self.is_installing = False
        self.is_active = False
        self.install_start_time = 0
        self.cancel_right_pressed = False
        self.cancel_right_press_time = 0
        self.cancel_hold_seconds = 0.35
        self.explosion_time = 0
        self.thread_running = False
        self.update_thread = None

        self.start_prompt_shown = False
        self.jump_prompt_shown = False          # 新增：是否已显示过跳车提示

        self.color_icon_img = None
        self._load_color_icon()

        self.overlay = None
        self.canvas = None
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
        except:
            pass

    def enable_module(self, enabled: bool):
        self.is_enabled = enabled
        if not enabled:
            self._reset()
            self._clear_display()
        else:
            self._update_status_display()

    def _update_status_display(self):
        if not self.is_enabled or not self.canvas:
            return
        self.canvas.delete("c4_hud")

    def on_weapon_detected(self, weapon_name: str, score: float):
        if self.is_installing or self.is_active:
            return
        self.c4_equipped = (weapon_name == "C4")
        if not self.c4_equipped:
            self._reset()

    def on_mouse_left_press(self):
        if not self.is_enabled or not self.c4_equipped or self.is_active or self.is_installing:
            return
        self.is_installing = True
        self.install_start_time = time.time()
        self.cancel_right_pressed = False
        self.cancel_right_press_time = 0
        self._show_installing()
        self.root.after(4000, self._on_install_finish)

    def on_mouse_right_click(self, pressed):
        if not self.is_installing or self.is_active:
            self.cancel_right_pressed = False
            self.cancel_right_press_time = 0
            return
        if pressed:
            self.cancel_right_pressed = True
            self.cancel_right_press_time = time.time()
            self.root.after(int(self.cancel_hold_seconds * 1000), self._check_cancel_install)
        else:
            self.cancel_right_pressed = False
            self.cancel_right_press_time = 0

    def _check_cancel_install(self):
        if not self.is_installing or self.is_active or not self.cancel_right_pressed:
            return
        if time.time() - self.cancel_right_press_time >= self.cancel_hold_seconds:
            self._cancel_install()

    def _cancel_install(self):
        if not self.is_installing:
            return
        self.is_installing = False
        self.cancel_right_pressed = False
        self.cancel_right_press_time = 0
        self._clear_display()

    def _on_install_finish(self):
        if not self.is_installing:
            return
        self.is_installing = False
        self.is_active = True
        total_seconds = 16.0 - self.explosion_margin
        self.explosion_time = time.time() + total_seconds
        self.start_prompt_shown = False
        self.jump_prompt_shown = False           # 新增：重置跳车提示标志
        self._start_update_loop()

    def _start_update_loop(self):
        if self.update_thread and self.update_thread.is_alive():
            return
        self.thread_running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()

    def _update_loop(self):
        while self.thread_running and self.is_active and self.is_enabled:
            now = time.time()
            remaining = self.explosion_time - now
            if remaining <= 0:
                self.root.after(0, self._clear_display)
                self._reset()
                break

            dist_dict = self.minimap.get_measured_distance()
            new_dist = dist_dict.get(self.selected_color, 0.0)
            if new_dist > 0:
                self.distance = new_dist

            # 推荐起步逻辑（原有）
            recommended_speed = 0.0
            if remaining > 0 and self.distance > 0:
                recommended_speed = (self.distance / remaining) * 3.6

            show_start_prompt = False
            if not self.start_prompt_shown and recommended_speed <= self.target_speed and self.distance > 0:
                show_start_prompt = True
                self.start_prompt_shown = True
                self.root.after(2000, self._clear_start_prompt)

            # 新增：推荐跳车逻辑（首次距离 ≤ 阈值）
            if not self.jump_prompt_shown and self.distance > 0 and self.distance <= self.jump_distance_threshold:
                self.jump_prompt_shown = True
                self.root.after(0, self._show_jump_prompt)
                self.root.after(2000, self._clear_jump_prompt)

            countdown = max(0, remaining)
            if countdown <= 2:
                color = "#E74C3C"
            elif countdown <= 4:
                color = "#F39C12"
            elif countdown <= 6:
                color = "#F1C40F"
            else:
                color = "white"

            self.root.after(0, self._draw_ui, countdown, color, recommended_speed, show_start_prompt)

            time.sleep(1.0 / self.fps)

        self.root.after(0, self._clear_display)

    def _clear_start_prompt(self):
        if self.canvas:
            self.canvas.delete("start_prompt")

    def _clear_jump_prompt(self):
        """清除推荐跳车提示"""
        if self.canvas:
            self.canvas.delete("jump_prompt")

    def _show_jump_prompt(self):
        """显示推荐跳车文本（与推荐起步相同位置样式）"""
        if not self.canvas:
            return
        cx = self.sw // 2
        cy = self.sh // 2 + 280
        self.canvas.create_text(cx, cy + 50, text="推荐跳车", fill="#E74C3C",
                                font=("Microsoft YaHei", 15, "bold"), tags="jump_prompt")

    def _draw_color_indicator(self):
        cx = self.sw // 4
        cy = self.sh // 2 + 280
        icon_y = cy + 40

        hex_code = self.color_hex_map.get(self.selected_color, "#FFFFFF")

        # 文字与标点同色
        self.canvas.create_text(cx, icon_y, text="当前使用标点：", fill=hex_code,
                                font=("Microsoft YaHei", 15, "bold"), tags="c4_hud")
        # 图标
        colored_icon = self._get_colored_icon(self.selected_color)
        if colored_icon:
            self.current_icon = colored_icon
            self.canvas.create_image(cx + 70, icon_y, image=colored_icon, anchor="center", tags="c4_hud")
        else:
            # 降级：显示文字颜色
            self.canvas.create_text(cx, icon_y, text=self.selected_color, fill=hex_code,
                                    font=("Microsoft YaHei", 15, "bold"), tags="c4_hud")

    def _draw_ui(self, countdown, color, recommended_speed, show_start_prompt):
        if not self.is_enabled or not self.canvas:
            return
        self.canvas.delete("c4_hud")
        cx = self.sw // 2
        cy = self.sh // 2 + 280

        if self.is_active:
            font_size = 48 if countdown <= 6 else 35
            self.canvas.create_text(cx, cy - 60, text=f"{countdown:.1f} s", fill=color,
                                    font=("Microsoft YaHei", font_size, "bold"), tags="c4_hud")
            if recommended_speed > 0 and recommended_speed <= 160:
                speed_text = f"{recommended_speed:.1f} km/h"
            elif recommended_speed > 160:
                speed_text = ">160 km/h"
            else:
                speed_text = "N/A"
            self.canvas.create_text(cx, cy + 5, text=f"建议车速: {speed_text}", fill="#3498DB",
                                    font=("Microsoft YaHei", 15, "bold"), tags="c4_hud")
            if show_start_prompt:
                self.canvas.create_text(cx, cy + 50, text="推荐起步", fill="#2ECC71",
                                        font=("Microsoft YaHei", 15, "bold"), tags="start_prompt")

    def _show_installing(self):
        if not self.canvas:
            return
        self.canvas.delete("c4_hud")
        cx = self.sw // 2
        cy = self.sh // 2 + 280
        self.canvas.create_text(cx, cy, text="C4安装中，长按鼠标右键取消", fill="#F39C12",
                                font=("Microsoft YaHei", 15, "bold"), tags="c4_hud")
        self.root.after(4000, lambda: self.canvas.delete("c4_hud") if self.is_active else None)

    def _clear_display(self):
        if self.canvas:
            self.canvas.delete("c4_hud")
            self.canvas.delete("start_prompt")
            self.canvas.delete("jump_prompt")      # 清除跳车提示

    def _reset(self):
        self.thread_running = False
        # 不要在此 join 线程，让线程自然退出
        self.update_thread = None
        self.is_installing = False
        self.is_active = False
        self.cancel_right_pressed = False
        self.cancel_right_press_time = 0
        self.distance = 0.0
        self.start_prompt_shown = False
        self.jump_prompt_shown = False            # 重置跳车提示标志
        self._clear_display()
        if self.is_enabled:
            self._update_status_display()

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

            if char == 'q':
                idx = self.color_priority.index(self.selected_color)
                new_idx = (idx - 1) % len(self.color_priority)
                self.selected_color = self.color_priority[new_idx]
            elif char == 'e':
                idx = self.color_priority.index(self.selected_color)
                new_idx = (idx + 1) % len(self.color_priority)
                self.selected_color = self.color_priority[new_idx]
            # 主程序统一显示和同步当前使用标点。
        except Exception as e:
            pass

    def _show_color_change(self):
        if not self.canvas:
            return
        self.canvas.delete("color_tip")
        cx = self.sw // 2
        cy = self.sh // 2 + 280
        self.canvas.create_text(cx, cy, text=f"切换到 {self.selected_color}", fill="#2ECC71",
                                font=("Microsoft YaHei", 15), tags="color_tip")
        self.root.after(1500, lambda: self.canvas.delete("color_tip"))

    def _refresh_color_display(self):
        """强制刷新标点颜色显示（不删除其他内容）"""
        if not self.is_enabled or not self.canvas:
            return
            
        try:
            self._update_status_display()
            # 强制立刻刷新画面，不等待主事件循环排队
            if hasattr(self, 'overlay') and self.overlay:
                self.overlay.update()
        except Exception as e:
            print(f"[C4助手] UI 刷新异常: {e}")

    def shutdown(self):
        self.thread_running = False
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=0.5)
        if self.overlay:
            self.overlay.destroy()
