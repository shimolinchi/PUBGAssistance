import os
import threading
import time

import mss
import mss.tools
from pynput import keyboard, mouse


class JumpThrowCalibrator:
    def __init__(self, jump_delay=0.3, output_dir="jump_throw_captures"):
        self.jump_delay = jump_delay
        self.output_dir = output_dir
        self.armed = False
        self.lock = threading.Lock()
        self.keyboard_controller = keyboard.Controller()
        os.makedirs(self.output_dir, exist_ok=True)

        print("=======================================")
        print("跳投标定程序")
        print("=======================================")
        print("1. 游戏中按住鼠标左键准备投掷")
        print("2. 按 V 键进入捕获状态")
        print("3. 松开鼠标左键后立即截全屏图")
        print(f"4. 截图后延迟 {self.jump_delay:.2f}s 自动按空格")
        print("5. 按 F1 或 Esc 退出")
        print("=======================================")

    def on_key_press(self, key):
        if key in (keyboard.Key.f1, keyboard.Key.esc):
            print("退出跳投标定程序")
            return False
        try:
            if hasattr(key, "char") and key.char and key.char.lower() == "v":
                with self.lock:
                    self.armed = True
                print("[已就绪] 等待鼠标左键松开...")
        except Exception:
            pass

    def on_mouse_click(self, _x, _y, button, pressed):
        if button != mouse.Button.left or pressed:
            return
        with self.lock:
            if not self.armed:
                return
            self.armed = False
        self.capture_and_jump()

    def capture_and_jump(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        millis = int((time.time() % 1) * 1000)
        output_path = os.path.join(self.output_dir, f"jump_throw_{timestamp}_{millis:03d}.png")

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
            threading.Thread(target=self._save_screenshot, args=(screenshot, output_path), daemon=True).start()
            print(f"[截图完成] {output_path}")
        except Exception as exc:
            print(f"[截图失败] {exc}")

        threading.Timer(self.jump_delay, self.tap_space).start()

    def _save_screenshot(self, screenshot, output_path):
        try:
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=output_path)
        except Exception as exc:
            print(f"[保存失败] {exc}")

    def tap_space(self):
        try:
            self.keyboard_controller.press(keyboard.Key.space)
            time.sleep(0.03)
            self.keyboard_controller.release(keyboard.Key.space)
            print("[跳跃触发] 已按下空格")
        except Exception as exc:
            print(f"[跳跃失败] {exc}")


if __name__ == "__main__":
    calibrator = JumpThrowCalibrator(jump_delay=0.3)
    mouse_listener = mouse.Listener(on_click=calibrator.on_mouse_click)
    mouse_listener.start()
    with keyboard.Listener(on_press=calibrator.on_key_press) as keyboard_listener:
        keyboard_listener.join()
    mouse_listener.stop()
