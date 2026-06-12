import ctypes
import os
import sys
import threading
import time
import tkinter as tk

import mss

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from region_manager import RegionManager
from scope_motion_tracker import ScopeMotionTracker


class ScopeMotionTrackerTester:
    def __init__(self, root):
        self.root = root
        self.root.title("Scope Motion Tracker Tester")
        self.root.geometry("390x330")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        self.rm = RegionManager(self.root, config_file="config.json")
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()
        self.region_var = tk.StringVar(value="scope_top_edge_4x_region")
        self.tracker = ScopeMotionTracker(self.sw, self.sh, self.rm, region_name=self.region_var.get())

        self.is_running = False
        self.worker_thread = None
        self.stop_flag = False
        self.last_edge_y = None
        self.last_dy = 0.0
        self.last_confidence = 0.0
        self.last_found = False
        self.last_fps = 0.0

        self.overlay = None
        self.canvas = None
        self._init_overlay()
        self._build_ui()
        self._update_overlay_loop()

    def _init_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)

        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.overlay.update_idletasks()

        try:
            hwnd = int(self.overlay.frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except Exception as e:
            print(f"[ScopeMotionTester] overlay setup failed: {e}")

    def _build_ui(self):
        title = tk.Label(
            self.root,
            text="Scope Motion Tracker",
            fg="white",
            bg="#2C3E50",
            font=("Microsoft YaHei", 14, "bold"),
        )
        title.pack(pady=(12, 6))

        region = self.rm.get_real_region(self.region_var.get())
        if region:
            region_text = (
                f"{self.region_var.get()}: "
                f"{region['left']},{region['top']} {region['width']}x{region['height']}"
            )
            region_color = "#2ECC71"
        else:
            region_text = f"{self.region_var.get()} not calibrated"
            region_color = "#E74C3C"
        tk.Label(self.root, text=region_text, fg=region_color, bg="#2C3E50", font=("Consolas", 9)).pack(pady=4)

        tk.OptionMenu(
            self.root,
            self.region_var,
            "scope_top_edge_4x_region",
            "scope_top_edge_6x_region",
            "scope_top_edge_8x_region",
            command=lambda _v: self.switch_region(),
        ).pack(fill="x", padx=44, pady=4)

        self.status_var = tk.StringVar(value="dy=0.00  conf=0.00  found=False  fps=0")
        tk.Label(
            self.root,
            textvariable=self.status_var,
            fg="#F1C40F",
            bg="#2C3E50",
            font=("Consolas", 11, "bold"),
        ).pack(pady=8)

        self.btn_toggle = tk.Button(
            self.root,
            text="Start Tracking",
            command=self.toggle_tracker,
            bg="#2ECC71",
            fg="white",
            font=("Microsoft YaHei", 11, "bold"),
        )
        self.btn_toggle.pack(fill="x", padx=44, pady=5)

        self.btn_reset = tk.Button(
            self.root,
            text="Reset Baseline",
            command=self.reset_tracker,
            bg="#3498DB",
            fg="white",
            font=("Microsoft YaHei", 10, "bold"),
        )
        self.btn_reset.pack(fill="x", padx=44, pady=5)

        self.btn_calibrate = tk.Button(
            self.root,
            text="Calibrate Scope Top Edge Region",
            command=self.calibrate_region,
            bg="#9B59B6",
            fg="white",
            font=("Microsoft YaHei", 10, "bold"),
        )
        self.btn_calibrate.pack(fill="x", padx=44, pady=5)

        self.btn_quit = tk.Button(
            self.root,
            text="Quit",
            command=self.on_closing,
            bg="#E74C3C",
            fg="white",
            font=("Microsoft YaHei", 10, "bold"),
        )
        self.btn_quit.pack(fill="x", padx=44, pady=(12, 5))

    def toggle_tracker(self):
        self.is_running = not self.is_running
        if self.is_running:
            self.stop_flag = False
            self.tracker.reset()
            self.worker_thread = threading.Thread(target=self._tracking_loop, daemon=True)
            self.worker_thread.start()
            self.btn_toggle.config(text="Stop Tracking", bg="#E74C3C")
        else:
            self.stop_flag = True
            self.btn_toggle.config(text="Start Tracking", bg="#2ECC71")
            self.canvas.delete("scope_motion")

    def reset_tracker(self):
        self.tracker.reset()
        self.last_edge_y = None
        self.last_dy = 0.0
        self.last_confidence = 0.0
        self.last_found = False

    def calibrate_region(self):
        was_running = self.is_running
        if was_running:
            self.toggle_tracker()
        self.rm.calibrate_region(self.region_var.get())
        self.tracker = ScopeMotionTracker(self.sw, self.sh, self.rm, region_name=self.region_var.get())

    def switch_region(self):
        self.tracker.set_region_name(self.region_var.get())
        self.reset_tracker()

    def _tracking_loop(self):
        frame_count = 0
        fps_start = time.perf_counter()
        with mss.mss() as sct:
            while not self.stop_flag:
                start = time.perf_counter()
                dy, confidence, found = self.tracker.detect_motion(sct)
                self.last_dy = dy
                self.last_confidence = confidence
                self.last_found = found
                self.last_edge_y = self.tracker.last_edge_y

                frame_count += 1
                now = time.perf_counter()
                if now - fps_start >= 0.5:
                    self.last_fps = frame_count / (now - fps_start)
                    frame_count = 0
                    fps_start = now

                elapsed = time.perf_counter() - start
                time.sleep(max(0.0, 0.005 - elapsed))

    def _update_overlay_loop(self):
        self.canvas.delete("scope_motion")
        if self.is_running:
            rect = self.tracker.monitor
            x1 = rect["left"]
            y1 = rect["top"]
            x2 = x1 + rect["width"]
            y2 = y1 + rect["height"]
            color = "#2ECC71" if self.last_found else "#E74C3C"
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2, tags="scope_motion")
            if self.last_edge_y is not None and self.last_found:
                y = self.last_edge_y
                self.canvas.create_line(x1 - 80, y, x2 + 80, y, fill="#00D1B2", width=2, tags="scope_motion")

            self.status_var.set(
                f"dy={self.last_dy:6.2f}  "
                f"conf={self.last_confidence:.2f}  "
                f"found={self.last_found}  "
                f"fps={self.last_fps:.0f}"
            )
        self.root.after(33, self._update_overlay_loop)

    def on_closing(self):
        self.stop_flag = True
        self.is_running = False
        if self.overlay:
            self.overlay.destroy()
        self.root.destroy()


if __name__ == "__main__":
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    root = tk.Tk()
    app = ScopeMotionTrackerTester(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
