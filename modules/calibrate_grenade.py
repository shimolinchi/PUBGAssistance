import time
from pynput import keyboard, mouse

class GrenadeTimerCalibrator:
    def __init__(self):
        self.is_timing = False
        self.start_time = 0.0
        
        print("=======================================")
        print("💣 雷火闪助手 - 瞬爆计时标定程序")
        print("=======================================")
        print("测试流程:")
        print("1. 游戏中切出手雷，按住左键/End键准备")
        print("2. 按下 [R] 键开始计时 (模拟拉环)")
        print("3. 松开 [鼠标左键] 或 [End] 键停止计时 (模拟扔出)")
        print("4. 按下 [ESC] 键可随时退出标定程序")
        print("=======================================\n")

    def on_key_press(self, key):
        """监听按键按下事件"""
        try:
            # 捕获 R 键按下 (处理大小写兼容)
            if hasattr(key, 'char') and key.char and key.char.lower() == 'r':
                if not self.is_timing:
                    self.start_time = time.time()
                    self.is_timing = True
                    print("[ 计时开始 ] ⏱️ 已拉环！正在计算捏雷时间...")
        except Exception:
            pass

    def on_key_release(self, key):
        """监听按键松开事件"""
        # 捕获 End 键松开
        if key == keyboard.Key.end:
            self.stop_timer("End键")
        
        # 捕获 ESC 键退出程序
        if key == keyboard.Key.f1:
            print("🛑 退出标定程序...")
            return False # 返回 False 会停止 keyboard.Listener

    def on_mouse_click(self, x, y, button, pressed):
        """监听鼠标点击事件"""
        # 捕获鼠标左键松开 (pressed 为 False 代表松开)
        if button == mouse.Button.left and not pressed:
            self.stop_timer("鼠标左键")

    def stop_timer(self, trigger_name):
        """停止计时并计算时间差"""
        if self.is_timing:
            elapsed = time.time() - self.start_time
            self.is_timing = False
            print(f"[ 投掷动作 ] 💥 {trigger_name}已松开！雷在手中停留了: {elapsed:.3f} 秒\n")

if __name__ == "__main__":
    calibrator = GrenadeTimerCalibrator()
    
    # 启动鼠标监听器 (后台线程)
    mouse_listener = mouse.Listener(on_click=calibrator.on_mouse_click)
    mouse_listener.start()
    
    # 启动键盘监听器 (阻塞主线程，直到按下 ESC 返回 False)
    with keyboard.Listener(on_press=calibrator.on_key_press, on_release=calibrator.on_key_release) as kb_listener:
        kb_listener.join()
    
    # 键盘监听结束后，顺便停掉鼠标监听
    mouse_listener.stop()