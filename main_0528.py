import tkinter as tk
import mss
from pynput import keyboard, mouse
import threading
import time
import ctypes

# 导入所有独立模块
from minimap_radar import MinimapRadarModule
from elevation_radar import ElevationRadarModule
from mortar_assistant import MortarAssistant
from rocket_assistant import RocketAssistant
from map_assistant import MapPointAssistant
from throwables_assistant import ThrowablesAssistant
from vss_assistant import VssAssistant
from crossbow_assistant import CrossbowAssistant
from weapon_detector import AutoWeaponDetector

# ================= 自定义真·圆角按钮组件 =================
class RoundedButton(tk.Canvas):
    def __init__(self, parent, width, height, radius, text, command, is_toggle=False, *args, **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, *args, **kwargs)
        self.command = command
        self.is_toggle = is_toggle
        self.is_active = False
        
        self.color_default = "#FFFFFF"
        self.color_hover = "#F3F4F6"
        self.color_pressed = "#D1D5DB"
        self.color_active = "#E5E7EB"
        self.text_color = "#000000"
        
        self.radius = radius
        self.rect = self._create_rounded_rect(0, 0, width, height, radius, fill=self.color_default, outline="#E5E7EB", width=1)
        self.text_item = self.create_text(width/2, height/2, text=text, fill=self.text_color, font=("Microsoft YaHei", 10, "bold"))
        
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_hover)
        self.bind("<Leave>", self._on_leave)

    def _create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2, x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_press(self, event):
        self.itemconfig(self.rect, fill=self.color_pressed)

    def _on_release(self, event):
        if self.is_toggle:
            self.is_active = not self.is_active
        self.itemconfig(self.rect, fill=self.color_active if self.is_active else self.color_hover)
        if self.command:
            self.command()

    def _on_hover(self, event):
        if not self.is_active:
            self.itemconfig(self.rect, fill=self.color_hover)

    def _on_leave(self, event):
        if not self.is_active:
            self.itemconfig(self.rect, fill=self.color_default)
            
    def set_active(self, state):
        self.is_active = state
        self.itemconfig(self.rect, fill=self.color_active if self.is_active else self.color_default)

# ================= 全局战术中枢主类 =================
class TacticalHub:
    def __init__(self, root):
        self.root = root
        self.root.title("PUBG 战术助手")
        self.root.geometry("250x600")
        self.root.configure(bg="#F9FAFB")
        self.root.attributes("-topmost", True)

        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            sw, sh = monitor["width"], monitor["height"]

        # ==================== 1. 实例化核心底层传感器 ====================
        self.minimap = MinimapRadarModule(self.root)
        self.elevation = ElevationRadarModule(self.root, screen_width=sw, screen_height=sh, fps=30)
        self.minimap.set_enabled(True) 
        self.minimap.set_display(False)
        self.elevation.set_enabled(True)
        self.elevation.set_display(False)

        # ==================== 2. 实例化上层武器助手 ====================
        self.rocket = RocketAssistant(self.root, sw, sh, self.minimap, fps=30)
        self.mortar = MortarAssistant(self.root, sw, sh, self.minimap, self.elevation, fps=30)
        self.throwables = ThrowablesAssistant(self.root, sw, sh, self.minimap, self.elevation, fps=30)
        self.vss_assist = VssAssistant(self.root, sw, sh, self.minimap, fps=30)
        self.crossbow_assist = CrossbowAssistant(self.root, sw, sh, self.minimap, fps=30)
        self.map_assist = MapPointAssistant(self.root)

        # 武器武装状态位 
        self.rocket_armed = False
        self.mortar_armed = True   # 迫击炮默认开启
        self.throwables_armed = False
        self.vss_armed = False
        self.crossbow_armed = False
        
        self.combat_hud_active = False 
        self.map_assist_active = False


        self.pressed_keys = set()
        
        # 纯 pynput 的底层物理状态记录
        self.left_pressed = False
        self.middle_pressed = False
        self.alt_pressed = False
        
        self.linkage_thread = None

        self.maps = [
            "艾伦格 (Erangel)", 
            "米拉玛 (Miramar)", 
            "泰戈 (Taego)", 
            "荣都 (Rondo)", 
            "帝斯顿 (Deston)", 
            "维寒迪 (Vikendi)"
        ] 
        self.current_map_index = 0
        self.map_buttons = []
        self.current_map_index = 0
        self.map_buttons = []
        self.marker_sizes = [("小", "small"), ("中", "medium"), ("大", "large")]
        self.size_buttons = []
        self.assistant_buttons = []

        # 初始化 UI 面板
        self.init_ui()

        # ==================== 3. 注册 UI 状态标签与自动探测器 ====================
        self.status_var = tk.StringVar(value="当前状态: 未开启显示")
        self.lbl_weapon_status = tk.Label(
            self.root, 
            textvariable=self.status_var, 
            fg="#2563EB", bg="#F9FAFB", font=("Microsoft YaHei", 10, "bold")
        )
        self.lbl_weapon_status.pack(pady=10) 

        test_templates = {
            "VSS": "templates/vss.png", 
            "火箭筒": "templates/rocket.png",
            "十字弩": "templates/crossbow.png",
            "手榴弹": "templates/grenade.png"
        }
        
        self.weapon_detector = AutoWeaponDetector(
            screen_width=sw, 
            screen_height=sh, 
            templates_config=test_templates, 
            on_switch_callback=self.on_auto_weapon_switch 
        )

        self.start_listeners()

    def init_ui(self):
        tk.Label(self.root, text="PUBG TACTICAL HUB", bg="#F9FAFB", fg="#111827", font=("Impact", 18)).pack(pady=10)

        f1 = tk.Frame(self.root, bg="#F9FAFB")
        f1.pack(pady=5)
        RoundedButton(f1, 90, 35, 25, "校准大地图", self.map_assist.trigger_calibration).grid(row=0, column=0, padx=10)
        RoundedButton(f1, 90, 35, 25, "校准小地图", self.minimap.trigger_calibration).grid(row=0, column=1, padx=10)

        tk.Label(self.root, text="- 地图选择 -", bg="#F9FAFB", fg="#6B7280", font=("Microsoft YaHei", 9)).pack(pady=4)
        f_maps = tk.Frame(self.root, bg="#F9FAFB")
        f_maps.pack()
        for i, map_name in enumerate(self.maps):
            row = i // 3
            col = i % 3
            cmd = lambda idx=i: self.select_map(idx)
            btn = RoundedButton(f_maps, 60, 35, 20, map_name.split()[0], cmd, is_toggle=True)
            btn.grid(row=row, column=col, padx=5, pady=5)
            self.map_buttons.append(btn)
        self.select_map(0)

        tk.Label(self.root, text="- 标点尺寸 -", bg="#F9FAFB", fg="#6B7280", font=("Microsoft YaHei", 9)).pack(pady=4)
        f_sizes = tk.Frame(self.root, bg="#F9FAFB")
        f_sizes.pack()
        for i, (name, val) in enumerate(self.marker_sizes):
            cmd = lambda idx=i: self.select_size(idx)
            btn = RoundedButton(f_sizes, 60, 35, 20, name, cmd, is_toggle=True)
            btn.grid(row=0, column=i, padx=5)
            self.size_buttons.append(btn)
        self.select_size(1)

        tk.Label(self.root, text="- 瞄准开关 -", bg="#F9FAFB", fg="#6B7280", font=("Microsoft YaHei", 9)).pack(pady=4)
        self.f_assistants = tk.Frame(self.root, bg="#F9FAFB")
        self.f_assistants.pack(pady=2)
        
        self.btn_rocket = self.add_assistant_button("启用火箭筒", self.toggle_rocket_arm)
        self.btn_mortar = self.add_assistant_button("启用迫击炮", self.toggle_mortar_arm)
        self.btn_throwables = self.add_assistant_button("启用投掷物", self.toggle_throwables_arm)
        self.btn_vss = self.add_assistant_button("启用 VSS", self.toggle_vss_arm)
        self.btn_crossbow = self.add_assistant_button("启用十字弩", self.toggle_crossbow_arm)
        
        info_text = (
            "Shift+Ctrl+Space 或 N : 启停显示与自动识别 \n"
            "V: 自动瞬爆 | R: 拉环 | Alt +/- : 换图 \n"
            "左键+中键 : 激活地图 | 右键: 关 | Alt+右键 : 留"
        )
        tk.Label(self.root, text=info_text, bg="#F9FAFB", fg="#9CA3AF", justify="center", font=("Microsoft YaHei", 9)).pack(side="bottom", pady=10)

    def add_assistant_button(self, text, command):
        current_count = len(self.assistant_buttons)
        row = current_count // 2
        col = current_count % 2
        btn = RoundedButton(self.f_assistants, 90, 35, 20, text, command, is_toggle=True)
        btn.grid(row=row, column=col, padx=10, pady=5)
        self.assistant_buttons.append(btn)
        return btn

    def select_map(self, idx):
        self.current_map_idx = idx % len(self.maps)
        for i, btn in enumerate(self.map_buttons):
            btn.set_active(i == self.current_map_idx)
        self.map_assist.set_map(self.maps[self.current_map_idx])

    def select_size(self, idx):
        for i, btn in enumerate(self.size_buttons):
            btn.set_active(i == idx)
        size_key = self.marker_sizes[idx][1]
        self.map_assist.set_marker_size(size_key)

    # 手动点击按钮时的回退机制
    def toggle_rocket_arm(self): self.rocket_armed = not self.rocket_armed; self.sync_combat_hud()
    def toggle_mortar_arm(self): self.mortar_armed = not self.mortar_armed; self.sync_combat_hud()
    def toggle_throwables_arm(self): self.throwables_armed = not self.throwables_armed; self.sync_combat_hud()
    def toggle_vss_arm(self): self.vss_armed = not self.vss_armed; self.sync_combat_hud()
    def toggle_crossbow_arm(self): self.crossbow_armed = not self.crossbow_armed; self.sync_combat_hud()

    def toggle_main_trigger(self):
        self.combat_hud_active = not self.combat_hud_active
        if self.combat_hud_active:
            self.status_var.set("当前状态: 正在识别武器...")
            self.weapon_detector.start() 
        else:
            self.status_var.set("当前状态: 未开启显示")
            self.weapon_detector.stop()  
        self.root.after(0, self.sync_combat_hud)

    def on_auto_weapon_switch(self, weapon_name):
        if not self.combat_hud_active:
            return
        self.root.after(0, lambda: self._sync_weapon_ui(weapon_name))

    def _sync_weapon_ui(self, weapon_name):
        # 1. 重置除了迫击炮外的所有状态
        self.vss_armed = False
        self.rocket_armed = False
        self.crossbow_armed = False
        self.throwables_armed = False
        self.mortar_armed = True 
        
        # 2. 根据识别结果开启对应武装
        if weapon_name is None:
            self.status_var.set("当前状态: 未识别到可用武器")
        else:
            self.status_var.set(f"当前识别: 正在使用 {weapon_name}")
            if weapon_name == "VSS": self.vss_armed = True
            elif weapon_name == "火箭筒": self.rocket_armed = True
            elif weapon_name == "十字弩": self.crossbow_armed = True
            elif weapon_name == "手榴弹": self.throwables_armed = True

        # 3. 同步按键 UI
        self.btn_vss.set_active(self.vss_armed)
        self.btn_rocket.set_active(self.rocket_armed)
        self.btn_crossbow.set_active(self.crossbow_armed)
        self.btn_throwables.set_active(self.throwables_armed)
        self.btn_mortar.set_active(self.mortar_armed) 

        # 4. 同步图层
        self.sync_combat_hud()

    def sync_combat_hud(self):
        r_active = self.rocket_armed and self.combat_hud_active
        m_active = self.mortar_armed and self.combat_hud_active
        t_active = self.throwables_armed and self.combat_hud_active
        v_active = self.vss_armed and self.combat_hud_active
        c_active = self.crossbow_armed and self.combat_hud_active
        
        self.rocket.enable_module(r_active)
        self.mortar.enable_module(m_active)
        self.throwables.enable_module(t_active)
        self.vss_assist.enable_module(v_active)
        self.crossbow_assist.enable_module(c_active)

        minimap_needed = r_active or m_active or t_active or v_active or c_active
        self.minimap.set_display(minimap_needed)
        
        elevation_needed = m_active or t_active
        self.elevation.set_display(elevation_needed)

    def _sensor_linkage_loop(self):
        while True:
            if self.combat_hud_active:
                mini_dists = self.minimap.get_measured_distance()
                valid_colors = {color: (dist > 0) for color, dist in mini_dists.items()}
                self.elevation.set_valid_colors(valid_colors)
            time.sleep(0.05)

    # ================= 键盘与鼠标全局监听 (核心修复) =================
    def start_listeners(self):
        self.kb_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.kb_listener.start()
        self.mouse_listener.start()
        self.linkage_thread = threading.Thread(target=self._sensor_linkage_loop, daemon=True)
        self.linkage_thread.start()

    def on_key_press(self, key):
        self.pressed_keys.add(key)
        
        # 【新增】：精确记录 Alt 键的状态，供鼠标右键判断使用
        if key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            self.alt_pressed = True
        
        # N 键触发 (全局启停)
        if hasattr(key, 'char') and key.char and key.char.lower() == 'n':
            self.root.after(0, self.toggle_main_trigger)
            
        # Shift+Ctrl+Space 触发 (全局启停)
        if (keyboard.Key.shift in self.pressed_keys or keyboard.Key.shift_l in self.pressed_keys) and \
           (keyboard.Key.ctrl in self.pressed_keys or keyboard.Key.ctrl_l in self.pressed_keys) and \
           (keyboard.Key.space in self.pressed_keys):
            self.root.after(0, self.toggle_main_trigger)
            self.pressed_keys.remove(keyboard.Key.space)

        # Alt +/- 切换地图
        if self.alt_pressed:
            if hasattr(key, 'char'):
                if key.char == '=' or key.char == '+':
                    self.root.after(0, lambda: self.select_map(self.current_map_idx + 1))
                elif key.char == '-':
                    self.root.after(0, lambda: self.select_map(self.current_map_idx - 1))

        # 战斗状态下的投掷物快捷键
        if self.combat_hud_active and hasattr(key, 'char') and key.char:
            char_lower = key.char.lower()
            if char_lower == 'v':
                self.root.after(0, self.throwables.toggle_auto_throw)
            # elif char_lower == 'r':
            #     self.root.after(0, self.throwables.trigger_pull_pin)

    def on_key_release(self, key):
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)
            
        # 【新增】：松开 Alt 键时清除状态
        if key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            self.alt_pressed = False

    def on_mouse_click(self, x, y, button, pressed):
        # 1. 实时更新 pynput 鼠标物理状态
        if button == mouse.Button.left:
            self.left_pressed = pressed
        elif button == mouse.Button.middle:
            self.middle_pressed = pressed

        # 2. 绝对开启逻辑：左键 和 中键 均处于按下状态
        if self.left_pressed and self.middle_pressed:
            if not self.map_assist_active:  # 避免长按时疯狂重复刷新 UI
                self.map_assist_active = True
                self.root.after(0, lambda: self.map_assist.set_enabled(True))

        # 3. 绝对关闭逻辑：按下右键
        if button == mouse.Button.right and pressed:
            # 只有当目前处于显示状态，且没有按住 Alt 时，才执行关闭
            if self.map_assist_active and not self.alt_pressed:
                self.map_assist_active = False
                self.root.after(0, lambda: self.map_assist.set_enabled(False))

    def on_closing(self):
        self.kb_listener.stop()
        self.mouse_listener.stop()
        
        self.rocket.enable_module(False)
        self.mortar.enable_module(False)
        self.throwables.enable_module(False)
        self.vss_assist.enable_module(False)
        self.map_assist.set_enabled(False)
        self.crossbow_assist.enable_module(False)
        
        self.minimap.set_enabled(False)
        self.elevation.set_enabled(False)
        
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TacticalHub(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()