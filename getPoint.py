from pynput import mouse, keyboard

class CoordinateCatcher:
    def __init__(self):
        # 你可以在这里直接修改你的屏幕分辨率
        self.screen_w = 1920
        self.screen_h = 1080
        
        self.cx = self.screen_w / 2
        self.cy = self.screen_h / 2
        self.narrow_edge = min(self.screen_w, self.screen_h)
        
        self.points = []

    def start(self):
        print(f"=== PUBG 地图点位抓取工具 ===")
        print(f"当前设定的屏幕分辨率: {self.screen_w}x{self.screen_h}")
        print("操作说明：")
        print("1. 在游戏中打开全屏大地图。")
        print("2. 使用鼠标【左键】点击你想记录的位置。")
        print("3. 抓取完毕后，按键盘【ESC】键退出并生成最终代码。")
        print("---------------------------------\n")

        # 启动鼠标监听 (非阻塞)
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.mouse_listener.start()

        # 启动键盘监听 (阻塞，直到按下 ESC 返回 False)
        with keyboard.Listener(on_press=self.on_key_press) as kbd_listener:
            kbd_listener.join()

    def on_click(self, x, y, button, pressed):
        # 只在鼠标左键“按下”的那一刻触发
        if button == mouse.Button.right and pressed:
            # 逆向计算归一化坐标
            nx = (x - self.cx) / (self.narrow_edge / 2)
            ny = (self.cy - y) / (self.narrow_edge / 2)
            
            # 保留 3 位小数，避免数据太长，3位小数对应千分之一的精度，对游戏地图完全足够了
            nx = round(nx, 3)
            ny = round(ny, 3)
            
            self.points.append((nx, ny))
            print(f"已捕获点位: 像素({int(x)}, {int(y)}) -> 归一化({nx}, {ny})")

    def on_key_press(self, key):
        if key == keyboard.Key.esc:
            self.mouse_listener.stop()
            print("\n\n=== 抓取结束 ===")
            print("请复制下方的数组，直接粘贴到你的 MAP_DATA 对应位置中：\n")
            
            # 格式化输出为一行代码，方便直接复制
            formatted_list = "[" + ", ".join([f"({x}, {y})" for x, y in self.points]) + "]"
            print(formatted_list)
            print("\n")
            return False # 停止键盘监听

if __name__ == "__main__":
    catcher = CoordinateCatcher()
    catcher.start()