import mss
from pynput import mouse
import sys

# 设置常量
SCREEN_HALF_HEIGHT = 432.0

# 用于存储结果
results = []

def get_screen_info():
    """获取主屏幕分辨率以确认高度"""
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        return monitor['height']

def on_click(x, y, button, pressed):
    if pressed and button == mouse.Button.right:
        # 获取屏幕高度
        screen_height = get_screen_info()
        center_y = screen_height / 2
        
        # 计算垂直距离
        vertical_dist = y - center_y
        
        # 计算比例
        ratio = vertical_dist / SCREEN_HALF_HEIGHT
        
        results.append(ratio)
        print(f"右键点击坐标: ({x}, {y}) | 垂直距离中心: {vertical_dist} | 计算比值: {ratio:.4f}")

def main():
    print("程序已启动。")
    print("请进行鼠标右键点击。")
    print("按下 'Ctrl+C' 终止程序并查看汇总结果。")

    # 启动监听器
    with mouse.Listener(on_click=on_click) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            # 捕获终止信号
            print("\n" + "="*30)
            print("程序终止，正在输出所有记录的数据：")
            for i, val in enumerate(results, 1):
                print(f"记录 {i}: {val:.4f}")
            print("="*30)
            sys.exit()

if __name__ == "__main__":
    main()

# 0.0648, 0.0532, 0.0856, 0.0949, 0.1157, 0.1319, 0.1435, 0.1667, 0.1852, 0.1968, 0.2054, 0.2361, 0.2523, 0.2894, 0.3333, 0.3819, 0.4190, 0.4907, 0.5301, 0.5972, 0.7222
# 0.0, 0.0, 31.0, 38.8, 43.3, 51.1, 57.2, 63.3, 69.5, 77.1, 77.1, 84.7, 92.4, 101.7, 110.7, 120.0, 129.1, 138.3, 146.0, 155.2, 164.4



# 1.0, 9.0, 17.0, 33.0, 41.0, 51.0, 62.0, 71.0, 82.0, 94.0, 108.0, 119.0, 130.0, 135.0, 151.0, 164.0, 175.0, 185.0, 196.0, 206.0


# 29.1, 41.5, 50.5, 62.8, 72.0, 82.7, 91.9, 102.6, 113.3, 122.5, 131.8, 140.9, 151.6, 160.9, 171.6, 182.3, 193.0, 203.7, 214.4, 225.2