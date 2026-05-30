import tkinter as tk
import mss
from pynput import keyboard, mouse
import threading
import time
import ctypes

# 导入所有独立模块
from modules.minimap_radar import MinimapRadarModule
from modules.elevation_radar import ElevationRadarModule
from modules.mortar_assistant import MortarAssistant
from modules.rocket_assistant import RocketAssistant
from modules.map_assistant import MapPointAssistant
from modules.throwables_assistant import ThrowablesAssistant
from modules.vss_assistant import VssAssistant
from modules.crossbow_assistant import CrossbowAssistant
from modules.weapon_detector import AutoWeaponDetector
from modules.largemap_radar import AutoMapDistanceAssistant

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
        # self.text_item = self.create_text(width/2, height/2, text=text, fill=self.text_color, font=("Microsoft YaHei", 10, "bold"))
        self.text_id = self.create_text(width/2, height/2, text=text, fill=self.text_color, font=("Microsoft YaHei", 10, "bold"))
        
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

class TacticalHub:
    def __init__(self, root):
        self.root = root
        self.root.title("PUBG 战术助手")
        self.root.geometry("310x770")
        self.root.configure(bg="#F9FAFB")
        self.root.attributes("-topmost", True)

        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            sw, sh = monitor["width"], monitor["height"]

        self.config_file = "config.json"
        self.hotkeys = {
            "throw": "v",                              # 瞬爆雷
            "toggle_hud": "<ctrl>+<shift>+<space>",    # 开关显示
            "measure_map": "<ctrl>+<shift>+m"          # 触发大地图测距
        }
        self.load_hotkey_config()
        self._is_capturing = False # 防止重复点击录制快捷键

        self.minimap = MinimapRadarModule(self.root)
        self.elevation = ElevationRadarModule(self.root, screen_width=sw, screen_height=sh, fps=30)
        self.minimap.set_enabled(True) 
        self.minimap.set_display(False)
        self.elevation.set_enabled(True)
        self.elevation.set_display(False)

        self.rocket = RocketAssistant(self.root, sw, sh, self.minimap, fps=30)
        self.mortar = MortarAssistant(self.root, sw, sh, self.minimap, self.elevation, fps=30)
        self.throwables = ThrowablesAssistant(self.root, sw, sh, self.minimap, self.elevation, fps=30)
        self.vss_assist = VssAssistant(self.root, sw, sh, self.minimap, fps=30)
        self.crossbow_assist = CrossbowAssistant(self.root, sw, sh, self.minimap, fps=30)
        self.map_assist = MapPointAssistant(self.root)
        self.largemap_radar = AutoMapDistanceAssistant(self.root, sw, sh, "config.json")

        # 武器武装状态位 
        self.rocket_armed = False
        self.mortar_armed = True  
        self.throwables_armed = False
        self.vss_armed = False
        self.crossbow_armed = False
        
        self.combat_hud_active = False 
        self.map_assist_active = False


        self.pressed_keys = set()
        
        # pynput 的底层物理状态记录
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
        RoundedButton(f1, 105, 30, 25, "校准大地图", self.map_assist.trigger_calibration).grid(row=0, column=0, padx=10)
        RoundedButton(f1, 105, 30, 25, "校准小地图", self.minimap.trigger_calibration).grid(row=0, column=1, padx=10)

        # 添加一条细灰线作为分割
        tk.Frame(self.root, height=1, bg="#D1D5DB").pack(fill="x", pady=10, padx=20)
        
        tk.Label(self.root, text="- 快捷键配置 -", bg="#F9FAFB", fg="#6B7280", font=("Microsoft YaHei", 9)).pack(pady=4)

        hud_text = self.hotkeys['toggle_hud'].replace("<", "").replace(">", "").upper()
        self.btn_hk_hud = RoundedButton(self.root, 230, 30, 25, f"显示开关: {hud_text}", command=lambda: self.capture_hotkey('toggle_hud', self.btn_hk_hud))
        self.btn_hk_hud.pack(pady=3)

        throw_text = self.hotkeys['throw'].replace("<", "").replace(">", "").upper()
        self.btn_hk_throw = RoundedButton(self.root, 230, 30, 25, f"手雷瞬爆: {throw_text}", command=lambda: self.capture_hotkey('throw', self.btn_hk_throw))
        self.btn_hk_throw.pack(pady=3)

        map_text = self.hotkeys['measure_map'].replace("<", "").replace(">", "").upper()
        self.btn_hk_map = RoundedButton(self.root, 230, 30, 25, f"大地图测距: {map_text}", command=lambda: self.capture_hotkey('measure_map', self.btn_hk_map))
        self.btn_hk_map.pack(pady=3)
        
        tk.Frame(self.root, height=1, bg="#D1D5DB").pack(fill="x", pady=10, padx=20)

        tk.Label(self.root, text="- 地图选择 -", bg="#F9FAFB", fg="#6B7280", font=("Microsoft YaHei", 9)).pack(pady=4)
        f_maps = tk.Frame(self.root, bg="#F9FAFB")
        f_maps.pack()
        for i, map_name in enumerate(self.maps):
            row = i // 3
            col = i % 3
            cmd = lambda idx=i: self.select_map(idx)
            btn = RoundedButton(f_maps, 70, 30, 25, map_name.split()[0], cmd, is_toggle=True)
            btn.grid(row=row, column=col, padx=5, pady=5)
            self.map_buttons.append(btn)
        self.select_map(0)

        tk.Label(self.root, text="- 标点尺寸 -", bg="#F9FAFB", fg="#6B7280", font=("Microsoft YaHei", 9)).pack(pady=4)
        f_sizes = tk.Frame(self.root, bg="#F9FAFB")
        f_sizes.pack()
        for i, (name, val) in enumerate(self.marker_sizes):
            cmd = lambda idx=i: self.select_size(idx)
            btn = RoundedButton(f_sizes, 70, 30, 20, name, cmd, is_toggle=True)
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
            "Shift+Ctrl+Space 或 N : 显示与自动识别 \n"
            "左+中键: 激活地图 | Alt +/- : 更换地图\n"
            "右键: 关闭地图 | Alt+右键 : 标记路线\n"
            "V: 自动瞬爆 | Shift+Ctrl+Tab: 大地图测距\n"
        )
        tk.Label(self.root, text=info_text, bg="#F9FAFB", fg="#9CA3AF", justify="center", font=("Microsoft YaHei", 9)).pack(side="bottom", pady=10)

    def update_hotkey_buttons(self):
        """刷新按钮显示的文本"""
        if hasattr(self, 'btn_hk_hud'):
            hud_text = self.hotkeys['toggle_hud'].replace("<", "").replace(">", "").upper()
            throw_text = self.hotkeys['throw'].replace("<", "").replace(">", "").upper()
            map_text = self.hotkeys['measure_map'].replace("<", "").replace(">", "").upper()
            
            self.btn_hk_hud.itemconfig(self.btn_hk_hud.text_id, text=f"显示开关: {hud_text}")
            self.btn_hk_throw.itemconfig(self.btn_hk_throw.text_id, text=f"手雷瞬爆: {throw_text}")
            self.btn_hk_map.itemconfig(self.btn_hk_map.text_id, text=f"大地图测距: {map_text}")

    def capture_hotkey(self, action_key, btn_widget):
        """录制新快捷键的核心逻辑 (修复 Alt 键屏蔽字符的终极版)"""
        if self._is_capturing: return
        self._is_capturing = True

        # 先停掉所有监听器，防止在改键时触发游戏功能
        if hasattr(self, 'kb_listener') and self.kb_listener: self.kb_listener.stop()
        if hasattr(self, 'hotkey_listener') and self.hotkey_listener: self.hotkey_listener.stop()

        btn_widget.itemconfig(btn_widget.text_id, text="请按下按键...")
        self.root.update()

        modifiers = []
        def on_press(key):
            name = ""
            if hasattr(key, 'name') and key.name:
                name = f"<{key.name}>"
                if name in ["<ctrl_l>", "<ctrl_r>"]: name = "<ctrl>"
                elif name in ["<shift_l>", "<shift_r>"]: name = "<shift>"
                elif name in ["<alt_l>", "<alt_r>", "<alt_gr>"]: name = "<alt>"
                elif name == "<space>": name = "<space>"
                if name in ["<ctrl>", "<shift>", "<alt>"]:
                    if name not in modifiers:
                        modifiers.append(name)
                    return True 
                else:
                    finish_capture(name)
                    return False

            char = None
            if hasattr(key, 'char') and key.char:
                char = key.char
                if 1 <= ord(char) <= 26:
                    char = chr(ord(char) + 96)
            elif hasattr(key, 'vk') and key.vk is not None:
                # 65-90 是 A-Z，48-57 是数字 0-9
                if 65 <= key.vk <= 90:
                    char = chr(key.vk).lower()
                elif 48 <= key.vk <= 57:
                    char = chr(key.vk)

            if char:
                finish_capture(char.lower())
                return False

        def finish_capture(main_key):
            combo_str = "+".join(modifiers + [main_key])
            self.hotkeys[action_key] = combo_str
            self.save_hotkey_config()
            self._is_capturing = False
            self.root.after(0, self.update_hotkey_buttons)
            self.root.after(100, self.start_listeners)

        self.temp_listener = keyboard.Listener(on_press=on_press)
        self.temp_listener.start()

    def load_hotkey_config(self):
        import json, os
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "hotkeys" in data:
                        self.hotkeys.update(data["hotkeys"])
            except: pass

    def save_hotkey_config(self):
        import json, os
        data = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except: pass
        data["hotkeys"] = self.hotkeys
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def add_assistant_button(self, text, command):
        current_count = len(self.assistant_buttons)
        row = current_count // 2
        col = current_count % 2
        btn = RoundedButton(self.f_assistants, 105, 35, 25, text, command, is_toggle=True)
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
        self.vss_armed = False
        self.rocket_armed = False
        self.crossbow_armed = False
        self.throwables_armed = False
        self.mortar_armed = True 
        
        if weapon_name is None:
            self.status_var.set("当前状态: 未识别到可用武器")
        else:
            self.status_var.set(f"当前识别: 正在使用 {weapon_name}")
            if weapon_name == "VSS": self.vss_armed = True
            elif weapon_name == "火箭筒": self.rocket_armed = True
            elif weapon_name == "十字弩": self.crossbow_armed = True
            elif weapon_name == "手榴弹": self.throwables_armed = True

        self.btn_vss.set_active(self.vss_armed)
        self.btn_rocket.set_active(self.rocket_armed)
        self.btn_crossbow.set_active(self.crossbow_armed)
        self.btn_throwables.set_active(self.throwables_armed)
        self.btn_mortar.set_active(self.mortar_armed) 

        self.sync_combat_hud()

    def sync_combat_hud(self):
        active = self.combat_hud_active
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

        self.largemap_radar.set_display(active)

    def _sensor_linkage_loop(self):
        while True:
            if self.combat_hud_active:
                mini_dists = self.minimap.get_measured_distance()
                valid_colors = {color: (dist > 0) for color, dist in mini_dists.items()}
                self.elevation.set_valid_colors(valid_colors)
            time.sleep(0.05)

    def trigger_toggle_hud(self):
        self.root.after(0, self.toggle_main_trigger)

    def trigger_largemap_radar(self):
        if getattr(self, 'combat_hud_active', False):
            self.root.after(0, self.largemap_radar.toggle_mode)

    def start_listeners(self):
        if hasattr(self, 'kb_listener') and self.kb_listener: self.kb_listener.stop()
        if hasattr(self, 'mouse_listener') and self.mouse_listener: self.mouse_listener.stop()
        if hasattr(self, 'hotkey_listener') and self.hotkey_listener: self.hotkey_listener.stop()

        self.kb_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.kb_listener.start()

        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.mouse_listener.start()

        mapping = {
            self.hotkeys['toggle_hud']: self.trigger_toggle_hud,
            self.hotkeys['measure_map']: self.trigger_largemap_radar
        }
        self.hotkey_listener = keyboard.GlobalHotKeys(mapping)
        self.hotkey_listener.start()

        if getattr(self, 'linkage_thread', None) is None or not self.linkage_thread.is_alive():
            self.linkage_thread = threading.Thread(target=self._sensor_linkage_loop, daemon=True)
            self.linkage_thread.start()

    def on_key_press(self, key):
        try:
            key_name = key.char.lower() if hasattr(key, 'char') and key.char else f"<{key.name}>"
        except:
            key_name = str(key)

        if key_name == 'n':
            self.root.after(0, self.toggle_main_trigger)
        elif key_name == '<esc>':
            if getattr(self, 'throwables_active', False):
                self.root.after(0, self.throwables.cancel_throw)

        throw_key_main = self.hotkeys['throw'].split('+')[-1]
        if key_name == throw_key_main:
            if getattr(self, 'throwables_armed', False) and getattr(self, 'combat_hud_active', False):
                self.throwables_active = True
                self.root.after(0, self.throwables.activate_throw)

    def on_key_release(self, key):
        try:
            key_name = key.char.lower() if hasattr(key, 'char') and key.char else f"<{key.name}>"
        except:
            key_name = str(key)

        throw_key_main = self.hotkeys['throw'].split('+')[-1]
        if key_name == throw_key_main:
            if getattr(self, 'throwables_active', False):
                self.throwables_active = False
                self.root.after(0, self.throwables.execute_throw)

    def on_mouse_click(self, x, y, button, pressed):

        self.root.after(0, self.largemap_radar.on_mouse_click, x, y, button, pressed)
        if button == mouse.Button.left:
            self.left_pressed = pressed
        elif button == mouse.Button.middle:
            self.middle_pressed = pressed

        if self.left_pressed and self.middle_pressed:
            if not self.map_assist_active:  # 避免长按时疯狂重复刷新 UI
                self.map_assist_active = True
                self.root.after(0, lambda: self.map_assist.set_enabled(True))

        if button == mouse.Button.right and pressed:
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
        self.largemap_radar.set_display(False)
        
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TacticalHub(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()