import tkinter as tk
import mss
from pynput import keyboard, mouse
import threading

# 导入所有独立模块
from minimap_radar import MinimapRadarModule
from elevation_radar import ElevationRadarModule
from mortar_assistance import MortarAssistance
from rocket_assistance import RocketAssistance
from map_assistance import MapPointAssistance
import ctypes

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
        self.root.title("PUBG 全局战术中枢")
        # 为新增的一行按钮扩容高度
        self.root.geometry("250x450")
        self.root.configure(bg="#F9FAFB")
        self.root.attributes("-topmost", True)

        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            sw, sh = monitor["width"], monitor["height"]

        # 1. 实例化所有模块
        self.minimap = MinimapRadarModule(self.root)
        self.elevation = ElevationRadarModule(self.root, screen_width=sw, screen_height=sh, fps=30)
        self.rocket = RocketAssistance(self.root, sw, sh, self.minimap, fps=30)
        self.mortar = MortarAssistance(self.root, sw, sh, self.minimap, self.elevation, fps=30)
        self.map_assist = MapPointAssistance(self.root)

        # 2. 地图控制与 UI 变量
        self.maps = ["艾伦格 (Erangel)", "米拉玛 (Miramar)", "泰戈 (Taego)", "荣都 (Rondo)", "维寒迪 (Vikendi)", "帝斯顿 (Deston)"]
        self.current_map_idx = 0
        self.map_buttons = []
        
        # === 新增：标点尺寸控制状态 ===
        self.marker_sizes = [("小标点", "small"), ("中标点", "medium"), ("大标点", "large")]
        self.size_buttons = []
        
        self.rocket_armed = False
        self.mortar_armed = False
        self.combat_hud_active = False 
        self.map_assist_active = False

        # 3. 状态机：精准控制全局按键防抖
        self.pressed_keys = set()
        self.left_pressed = False
        self.middle_pressed = False
        self._combo_locked = False

        self.init_ui()
        self.start_listeners()

    def init_ui(self):
        tk.Label(self.root, text="PUBG TACTICAL HUB", bg="#F9FAFB", fg="#111827", font=("Impact", 18)).pack(pady=10)

        # 第一行: 两个校准按键
        f1 = tk.Frame(self.root, bg="#F9FAFB")
        f1.pack(pady=5)
        RoundedButton(f1, 90, 35, 25, "校准大地图", self.map_assist.trigger_calibration).grid(row=0, column=0, padx=10)
        RoundedButton(f1, 90, 35, 25, "校准小地图", self.minimap.trigger_calibration).grid(row=0, column=1, padx=10)

        # 第二、三行: 六个地图选择
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

        # === 新增：第四行：三个标点尺寸 ===
        tk.Label(self.root, text="- 标点尺寸 -", bg="#F9FAFB", fg="#6B7280", font=("Microsoft YaHei", 9)).pack(pady=4)
        f_sizes = tk.Frame(self.root, bg="#F9FAFB")
        f_sizes.pack()
        for i, (name, val) in enumerate(self.marker_sizes):
            cmd = lambda idx=i: self.select_size(idx)
            # 按钮宽度120，并排放置
            btn = RoundedButton(f_sizes, 60, 35, 20, name, cmd, is_toggle=True)
            btn.grid(row=0, column=i, padx=5)
            self.size_buttons.append(btn)
        self.select_size(1) # 默认选中下标1，也就是"中标点"

        # 第五行: 两个火控激活按钮
        tk.Label(self.root, text="- 瞄准开关 -", bg="#F9FAFB", fg="#6B7280", font=("Microsoft YaHei", 9)).pack(pady=4)
        f4 = tk.Frame(self.root, bg="#F9FAFB")
        f4.pack(pady=2)
        self.btn_rocket = RoundedButton(f4, 90, 35, 20, "启用火箭筒", self.toggle_rocket_arm, is_toggle=True)
        self.btn_rocket.grid(row=0, column=0, padx=10)
        self.btn_mortar = RoundedButton(f4, 90, 35, 20, "启用迫击炮", self.toggle_mortar_arm, is_toggle=True)
        self.btn_mortar.grid(row=0, column=1, padx=10)

        # 最下方: 简略描述
        info_text = (
            "Shift+Ctrl+Space 或 N : 启停瞄准显示 \n Alt + / - : 切换地图\n"
            "鼠标 左键+中键 : 激活大地图 \n 右键 : 关闭 | Alt+右键 : 不关闭"
        )
        tk.Label(self.root, text=info_text, bg="#F9FAFB", fg="#9CA3AF", justify="center", font=("Microsoft YaHei", 9)).pack(side="bottom", pady=15)

    # ================= UI 与系统逻辑联动 =================
    def select_map(self, idx):
        self.current_map_idx = idx % len(self.maps)
        for i, btn in enumerate(self.map_buttons):
            btn.set_active(i == self.current_map_idx)
        self.map_assist.set_map(self.maps[self.current_map_idx])

    def select_size(self, idx):
        """处理标点大小的切换逻辑"""
        for i, btn in enumerate(self.size_buttons):
            btn.set_active(i == idx)
        # 向下传达指令给地图模块
        size_key = self.marker_sizes[idx][1]
        self.map_assist.set_marker_size(size_key)

    def toggle_rocket_arm(self):
        self.rocket_armed = not self.rocket_armed
        self.sync_combat_hud()

    def toggle_mortar_arm(self):
        self.mortar_armed = not self.mortar_armed
        self.sync_combat_hud()

    def sync_combat_hud(self):
        self.rocket.enable_module(self.rocket_armed and self.combat_hud_active)
        self.mortar.enable_module(self.mortar_armed and self.combat_hud_active)

    # ================= 键盘与鼠标全局监听 (核心) =================
    def start_listeners(self):
        self.kb_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.kb_listener.start()
        self.mouse_listener.start()

    def on_key_press(self, key):
        self.pressed_keys.add(key)
        
        if hasattr(key, 'char') and key.char and key.char.lower() == 'n':
            self.combat_hud_active = not self.combat_hud_active
            self.root.after(0, self.sync_combat_hud)
            
        if (keyboard.Key.shift in self.pressed_keys or keyboard.Key.shift_l in self.pressed_keys) and \
           (keyboard.Key.ctrl in self.pressed_keys or keyboard.Key.ctrl_l in self.pressed_keys) and \
           (keyboard.Key.space in self.pressed_keys):
            self.combat_hud_active = not self.combat_hud_active
            self.root.after(0, self.sync_combat_hud)
            self.pressed_keys.remove(keyboard.Key.space)

        if keyboard.Key.alt_l in self.pressed_keys or keyboard.Key.alt_r in self.pressed_keys:
            if hasattr(key, 'char'):
                if key.char == '=' or key.char == '+':
                    self.root.after(0, lambda: self.select_map(self.current_map_idx + 1))
                elif key.char == '-':
                    self.root.after(0, lambda: self.select_map(self.current_map_idx - 1))

    def on_key_release(self, key):
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    def on_mouse_click(self, x, y, button, pressed):
        # 1. 物理按键状态追踪 (组合键的命脉，千万别删)
        if button == mouse.Button.left:
            self.left_pressed = pressed
        elif button == mouse.Button.middle:
            self.middle_pressed = pressed

        # 2. 快捷键：左键 + 中键 切换地图显示
        if self.left_pressed and self.middle_pressed and pressed:
            if self._combo_locked: return
            self._combo_locked = True
            
            self.map_assist_active = not self.map_assist_active
            self.root.after(0, lambda: self.map_assist.set_enabled(self.map_assist_active))
            return

        # 任何一键松开，解除防抖锁
        if not pressed and button in (mouse.Button.left, mouse.Button.middle):
            self._combo_locked = False

        # 3. 快捷键：右键直接关闭大地图助手
        elif button == mouse.Button.right:
                # 0x12 是 Alt 键 (VK_ALT) 的硬件虚拟键码
                is_alt_pressed = (ctypes.windll.user32.GetAsyncKeyState(0x12) & 0x8000) != 0
                
                if is_alt_pressed:
                    # Alt + 右键：什么都不做 (pass)，完美实现“保持图层开启，绝对不关闭”
                    pass
                else:
                    # 纯右键：关闭整个图层
                    self.map_assist_active = False
                    self.root.after(0, lambda: self.map_assist.set_enabled(False))

    def on_closing(self):
        self.kb_listener.stop()
        self.mouse_listener.stop()
        self.rocket.enable_module(False)
        self.mortar.enable_module(False)
        self.map_assist.set_enabled(False)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TacticalHub(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()