import tkinter as tk
import threading
import time
import math
import numpy as np
import mss
import json
import os
from pynput.keyboard import KeyCode
from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Controller as MouseController, Button

class ThrowablesAssistant:
    """
    PUBG 雷火闪投掷物战术助手
    包含：抬高角度指示、瞬爆圆弧刻度、以及自动瞬爆控制。
    """
    def __init__(self, root, screen_width, screen_height, minimap_module, elevation_module, fps=30, config_file="config.json"):
        self.root = root
        self.sw = screen_width
        self.sh = screen_height
        self.minimap = minimap_module
        self.elevation = elevation_module
        self.fps = fps
        
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
        self.arc_radius = self.sw * 0.097 # 默认值

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
        
        # 忽略鼠标穿透
        self.overlay.update_idletasks()
        try:
            import ctypes
            hwnd = int(self.overlay.frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception: pass

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

    def _show_temporary_warning(self, text, color = "#E74C3C"):
        """显示一段短暂的警告文字，2秒后自动消失"""
        warn_y = self.sh * 0.75
        # 先清除可能存在的旧警告
        self.canvas.delete("temp_warning")
        
        # 绘制新警告
        text_id = self.canvas.create_text(
            self.sw/2, warn_y, 
            text=text, 
            fill=color, 
            font=("Microsoft YaHei", 12, "bold"), 
            tags="temp_warning" # 使用专用 tag 方便管理
        )
        
        # 使用 after 在 2000 毫秒 (2秒) 后执行删除操作
        # 注意：这里需要确保在删除前没有被其他操作覆盖，所以用 temp_warning 标签
        self.root.after(2000, lambda: self.canvas.delete("temp_warning"))

    def toggle_auto_throw(self):
        """主程序按 V 键时调用此函数：整合检测与拉环执行"""
        if not self.is_enabled: return

        # 1. 收集传感器数据
        mini_dists = self.minimap.get_measured_distance()
        valid_times = []
        valid_dists = []

        for color, dist in mini_dists.items():
            if dist > 0.0:
                target_time = np.interp(dist, self.calib_dists, self.calib_times)
                valid_times.append(target_time)
                valid_dists.append(dist)

        # 2. 检查可用性
        if len(valid_times) == 0:
            self._show_temporary_warning("[ 未检测到有效标点 ]")
            return

        avg_dist = sum(valid_dists) / len(valid_dists)
        if avg_dist > 50.0:
            self._show_temporary_warning(f"[ 目标距离 {avg_dist:.1f}m 太远 ]")
            return

        # 3. 校验通过，执行逻辑
        avg_time = sum(valid_times) / len(valid_times)
        print(f"[投掷助手] ⚡ 瞬爆启动! 目标: {avg_dist:.1f}m, 捏雷: {avg_time:.2f}s")
        
        # 弹出绿色提示
        self._show_temporary_warning(f"自动瞬爆准备: {avg_dist:.1f}m", color="#2ECC71")

        # 4. 模拟游戏内拉环 (按下 R)
        # self.kb_controller.press('R')
        # self.kb_controller.release('R')

        self.kb_controller.press(KeyCode.from_char('r'))
        time.sleep(0.01)
        self.kb_controller.release(KeyCode.from_char('r'))

        # 5. 启动计时器，倒计时后执行抛出
        if self.throw_timer:
            self.throw_timer.cancel()
        
        self.throw_timer = threading.Timer(avg_time, self._execute_throw)
        self.throw_timer.start()

        

    # def trigger_pull_pin(self):
    #     """主程序按 R 键 (拉环) 时调用此函数"""
    #     if not self.is_enabled or not self.auto_throw_armed:
    #         return
            
    #     # 1. 收集双传感器有效数据
    #     mini_dists = self.minimap.get_measured_distance()
    #     elevations = self.elevation.get_measured_elevations()
        
    #     valid_times = []
    #     valid_dists = []

    #     for color, dist in mini_dists.items():
    #         if dist > 0.0 :
    #             target_time = np.interp(dist, self.calib_dists, self.calib_times)
    #             valid_times.append(target_time)
    #             valid_dists.append(dist)


        
    #     # 2. 判断是否符合自动瞬爆启动条件
    #     if len(valid_times) == 0:
    #         print("[投掷助手] ❌ 未检测到有效标点，自动瞬爆已关闭。")

            
    #         warn_y = self.sh * 0.75
    #         self._show_temporary_warning("[ 未检测到有效标点，自动瞬爆已关闭 ]")
    #         self.auto_throw_armed = False
    #         return
            
    #     avg_dist = sum(valid_dists) / len(valid_dists)
    #     if avg_dist > 50.0:
    #         print(f"[投掷助手] ❌ 目标距离 ({avg_dist:.1f}m) 超过 50 米，自动瞬爆已关闭。")
            
    #         warn_y = self.sh * 0.75
    #         self._show_temporary_warning("[ 目标距离过远，自动瞬爆已关闭 ]")
    #         self.auto_throw_armed = False
    #         return
            
    #     # 3. 启动后台精准延时抛掷
    #     avg_time = sum(valid_times) / len(valid_times)
    #     print(f"[投掷助手] ⏱️ 目标确认! 平均距离: {avg_dist:.1f}m, 预计持雷时间: {avg_time:.2f}秒。")
        
    #     if self.throw_timer:
    #         self.throw_timer.cancel()
        
    #     self.throw_timer = threading.Timer(avg_time, self._execute_throw)
    #     self.throw_timer.start()
        
    #     # 消耗掉本次 V 键赋予的待命状态
    #     self.auto_throw_armed = False

    def _execute_throw(self):
        """时间一到，通过 pynput 硬件级模拟松手动作"""
        print("[投掷助手] 💥 瞬爆时机已到，自动抛出！")
        # 释放 End 键
        self.kb_controller.release(Key.end)
        # 以防万一，同时也释放鼠标左键
        self.mouse_controller.release(Button.left)

    # ================= 核心渲染循环 =================
    def _draw_hud(self, valid_targets):
        self.canvas.delete("throwables_hud")
        if not self.is_enabled: return

        cx = self.sw / 2
        cy = self.sh / 2
        
        # ================= 第一部分：垂直参考线 =================
        bottom_y = self.sh * 0.9
        self.canvas.create_line(cx, cy, cx, bottom_y, fill="#FFFFFF", width=1, tags="throwables_hud")



        # ================= 第二部分：数据映射与渲染 =================
        # PUBG 瞬爆圆弧设定：圆心为中心，右侧。假设从右下 +25°(底部) 移动到右上 -25°(顶部)
        arc_start_deg = 25  
        arc_end_deg = -25   
        
        for target in valid_targets:
            dist = target['dist']
            color = target['color']
            
            # --- 渲染第一部分：抬高标尺 ---
            elev_y = np.interp(dist, self.calib_dists, self.calib_elevations_y)
            self.canvas.create_line(cx, elev_y, cx + 30, elev_y, fill=color, width=1, tags="throwables_hud")
            self.canvas.create_oval(cx + 30, elev_y - 4, cx + 38, elev_y + 4, fill=color, outline="", tags="throwables_hud")
            self.canvas.create_text(cx + 45, elev_y, text=f"{dist:.0f}m", fill=color, font=("Consolas", 12, "bold"), anchor="w", tags="throwables_hud")
            
            # --- 渲染第二部分：圆弧瞬爆倒计时 ---
            target_time = np.interp(dist, self.calib_dists, self.calib_times)
            # 限制映射时间不要超过总时间
            target_time = max(0.0, min(target_time, self.grenade_total_time))
            
            # 计算在该时间点，指针应该在哪个角度
            # 时间为 0 时在 start_deg，时间为 5.0 时在 end_deg
            time_ratio = target_time / self.grenade_total_time
            current_deg = arc_start_deg + time_ratio * (arc_end_deg - arc_start_deg)
            rad = math.radians(current_deg)
            
            # 外弧点和内弧点 (指向圆心)
            p_outer_x = cx + self.arc_radius * math.cos(rad)
            p_outer_y = cy + self.arc_radius * math.sin(rad)
            p_inner_x = cx + (self.arc_radius - 10) * math.cos(rad)
            p_inner_y = cy + (self.arc_radius - 10) * math.sin(rad)
            
            # 绘制指针
            self.canvas.create_line(p_outer_x, p_outer_y, p_inner_x, p_inner_y, fill=color, width=2, tags="throwables_hud")
            # 绘制时间文本 (放在指针靠外侧右边)
            text_x = p_outer_x + 10
            self.canvas.create_text(text_x, p_outer_y, text=f"{target_time:.1f}s", fill=color, font=("Consolas", 12, "bold"), anchor="w", tags="throwables_hud")

        # # 如果开启了自动瞬爆待命，在屏幕中下提示
        # if self.auto_throw_armed:
        #     avg_dist = sum(valid_dists) / len(valid_dists)
        #     if avg_dist > 50.0:
        #         print(f"[投掷助手] ❌ 目标距离 ({avg_dist:.1f}m) 超过 50 米，自动瞬爆已关闭。")
                
        #         warn_y = self.sh * 0.75
        #         self._show_temporary_warning("[ 目标距离过远，自动瞬爆已关闭 ]")
        #         self.canvas._show_temporary_warning("[ 自动瞬爆待命中... ]", color="#2ECC71")

    def _hud_loop(self):
        while self._thread_running:
            mini_dists = self.minimap.get_measured_distance()
            elevations = self.elevation.get_measured_elevations()
            
            valid_targets = []
            
            # 颜色名称映射为 hex 代码，保持一致
            color_hex_map = {
                "Yellow": "#E3D43C", "Orange": "#B3500D", 
                "Blue": "#1A3EA3", "Green": "#109166"
            }



            # for color, dist in mini_dists.items():
            #     elev_ratio = elevations.get(color)
            #     # 只有当：小地图能测到距离，且 垂直测高雷达有高度数据时，才进行渲染
            #     if dist > 0.0 and elev_ratio is not None:
            #         valid_targets.append({
            #             "dist": dist,
            #             "color": color_hex_map[color]
            #         })

            for color, dist in mini_dists.items():
                # 只有当：小地图能测到距离，且 垂直测高雷达有高度数据时，才进行渲染
                if dist > 0.0:
                    valid_targets.append({
                        "dist": dist,
                        "color": color_hex_map[color]
                    })



            self.root.after(0, self._draw_hud, valid_targets)
            time.sleep(0.03)