import ctypes
import time
import threading
from pynput import mouse, keyboard

# Windows API 常量
MOUSEEVENTF_MOVE = 0x0001

# 全局状态标志
is_active = False
exit_script = False

def move_mouse_relative(dx, dy):
    """
    调用底层 API 向系统发送相对鼠标位移信号
    """
    ctypes.windll.user32.mouse_event(
        MOUSEEVENTF_MOVE,
        dx,
        dy,
        0,
        0
    )

def mouse_worker():
    """
    后台执行线程：根据全局标志决定是否高频发送移动指令
    """
    global is_active, exit_script
    while not exit_script:
        if is_active:
            # 持续向下移动 10 个像素单位
            move_mouse_relative(0, 10)
            # 极短的延迟，模拟开火间隔或连贯的下压
            time.sleep(0.02)
        else:
            # 未激活时休眠，降低 CPU 占用
            time.sleep(0.01)

def on_click(x, y, button, pressed):
    """
    pynput 鼠标点击事件回调
    """
    global is_active
    # 检测是否为鼠标左键
    if button == mouse.Button.left:
        # pressed 为 True 表示按下，False 表示松开
        is_active = pressed

def on_press(key):
    """
    pynput 键盘按下事件回调
    """
    global exit_script
    # 按下 Esc 键退出程序
    if key == keyboard.Key.esc:
        print("检测到 Esc 键，正在退出脚本...")
        exit_script = True
        # 停止鼠标监听器
        mouse_listener.stop()
        # 返回 False 停止键盘监听器
        return False

if __name__ == "__main__":
    print("--- Pynput + Ctypes 鼠标左键下压测试脚本 ---")
    print("测试方法: 按住鼠标左键，指针将向下移动。松开停止。")
    print("安全退出: 按下键盘 'Esc' 键退出脚本。")

    # 启动后台移动线程
    worker_thread = threading.Thread(target=mouse_worker)
    worker_thread.start()

    # 实例化监听器
    mouse_listener = mouse.Listener(on_click=on_click)
    keyboard_listener = keyboard.Listener(on_press=on_press)

    # 启动鼠标监听器
    mouse_listener.start()

    # 启动键盘监听器并阻塞主线程，直到按下 Esc
    with keyboard_listener:
        keyboard_listener.join()
        
    # 等待工作线程安全结束
    worker_thread.join()
    mouse_listener.join()
    print("脚本已完全退出。")