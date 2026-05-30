import tkinter as tk
import json
import os
from pynput import mouse, keyboard
from modules.map_radar import MapDistanceAssistant

class MapDistanceTester:
    def __init__(self, root):
        self.root = root
        self.root.title("测距模块测试台")
        self.root.geometry("350x200")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 1. 自动生成一个基础的 config.json (如果不存在的话)
        self._ensure_dummy_config()

        # 2. 实例化你的测距助手
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.assistant = MapDistanceAssistant(self.root, sw, sh, "config.json")

        self.init_ui()
        self.start_listeners()

    def init_ui(self):
        tk.Label(self.root, text="大地图测距独立测试台", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 12, "bold")).pack(pady=15)
        
        tk.Button(self.root, text="▶ 手动触发测距 (模拟快捷键)", command=self.assistant.toggle_mode, 
                  bg="#2ECC71", fg="white", font=("Microsoft YaHei", 10, "bold")).pack(fill="x", padx=40, pady=5)
                  
        tk.Label(self.root, text="全局快捷键: Ctrl + Shift + `\n左键点击标点 | 右键随时取消", 
                 fg="#BDC3C7", bg="#2C3E50", font=("Microsoft YaHei", 10)).pack(pady=10)

    def _ensure_dummy_config(self):
        """确保当前目录下有一个 config.json 供模块读取"""
        if not os.path.exists("config.json"):
            print("[测试台] 未找到 config.json，正在自动生成基础配置...")
            dummy_config = {
                "map_1km_pixels": 540,
                "map_rect": {"top": 100, "left": 100, "side": 800}
            }
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(dummy_config, f, indent=4)

    def start_listeners(self):
        # 1. 启动鼠标监听
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.mouse_listener.start()

        # 2. 启动键盘热键监听 (注意: ` 键在不同键盘布局下可能需要调整)
        self.hotkey_listener = keyboard.GlobalHotKeys({
            '<ctrl>+<shift>+`': self.assistant.toggle_mode
        })
        self.hotkey_listener.start()

    def on_mouse_click(self, x, y, button, pressed):
        """接收物理鼠标点击，并通过 root.after 安全地丢给主线程的 Tkinter 处理"""
        # 注意：因为 pynput 运行在独立的后台线程，直接调用会引起 Tkinter 崩溃或无响应
        # 必须使用 root.after(0, ...) 将事件转交回主线程
        self.root.after(0, self.assistant.on_mouse_click, x, y, button, pressed)

    def on_closing(self):
        print("[测试台] 正在关闭...")
        self.mouse_listener.stop()
        self.hotkey_listener.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MapDistanceTester(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()