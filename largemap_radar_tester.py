import tkinter as tk
import json
import os
from pynput import mouse, keyboard
from largemap_radar import AutoMapDistanceAssistant

class AutoMapDistanceTester:
    def __init__(self, root):
        self.root = root
        self.root.title("自动测距独立测试台")
        self.root.geometry("380x200")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        self._ensure_dummy_config()

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.assistant = AutoMapDistanceAssistant(self.root, sw, sh, "config.json")

        self.init_ui()
        self.start_listeners()

    def init_ui(self):
        tk.Label(self.root, text="半自动大地图测距测试台", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=15)
        
        tk.Button(self.root, text="▶ 手动触发测距 (模拟快捷键)", command=self.assistant.toggle_mode, 
                  bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10, "bold")).pack(fill="x", padx=40, pady=5)
                  
        tk.Label(self.root, text="快捷键: Ctrl + Shift + M\n第1步: 左键点击玩家位置\n第2步: 后台自动扫描标点距离\n取消: 任意状态按右键", 
                 fg="#BDC3C7", bg="#2C3E50", font=("Microsoft YaHei", 10)).pack(pady=10)

    def _ensure_dummy_config(self):
        if not os.path.exists("config.json"):
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            dummy_config = {
                "map_1km_pixels": 540,
                "map_rect": {"top": 0, "left": 0, "width": sw, "height": sh},
                "minimap_colors": {
                    "Yellow": {"lower": [26, 150, 160], "upper": [30, 255, 255], "hex": "#E3D43C"},
                    "Orange": {"lower": [10, 160, 160], "upper": [14, 255, 255], "hex": "#B3500D"},
                    "Blue":   {"lower": [110, 120, 160], "upper": [114, 255, 255], "hex": "#1A3EA3"},
                    "Green":  {"lower": [78, 150, 120], "upper": [82, 255, 255], "hex": "#109166"}
                }
            }
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(dummy_config, f, indent=4)

    def start_listeners(self):
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.mouse_listener.start()
        
        self.hotkey_listener = keyboard.GlobalHotKeys({
            '<ctrl>+<shift>+m': self.assistant.toggle_mode
        })
        self.hotkey_listener.start()

    def on_mouse_click(self, x, y, button, pressed):
        self.root.after(0, self.assistant.on_mouse_click, x, y, button, pressed)

    def on_closing(self):
        self.mouse_listener.stop()
        self.hotkey_listener.stop()
        self.assistant.cancel()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoMapDistanceTester(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()