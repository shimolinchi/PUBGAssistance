import ctypes
import os
from ctypes import wintypes

from PIL import Image, ImageChops, ImageDraw, ImageFont


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class TransparentHudWindow:
    WS_POPUP = 0x80000000
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOPMOST = 0x00000008
    WS_EX_TOOLWINDOW = 0x00000080
    SW_HIDE = 0
    SW_SHOWNOACTIVATE = 4
    ULW_ALPHA = 0x00000002
    AC_SRC_OVER = 0
    AC_SRC_ALPHA = 1
    BI_RGB = 0
    DIB_RGB_COLORS = 0

    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self._setup_winapi()
        self.hwnd = self.user32.CreateWindowExW(
            self.WS_EX_LAYERED | self.WS_EX_TRANSPARENT | self.WS_EX_TOPMOST | self.WS_EX_TOOLWINDOW,
            "STATIC",
            "",
            self.WS_POPUP,
            0,
            0,
            1,
            1,
            None,
            None,
            None,
            None,
        )
        if not self.hwnd:
            raise ctypes.WinError()
        self.visible = False
        self.font_cache = {}
        try:
            self.user32.SetWindowDisplayAffinity(self.hwnd, 17)
        except Exception:
            pass

    def _setup_winapi(self):
        self.user32.CreateWindowExW.restype = wintypes.HWND
        self.user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        self.user32.UpdateLayeredWindow.restype = wintypes.BOOL
        self.user32.UpdateLayeredWindow.argtypes = [
            wintypes.HWND,
            wintypes.HDC,
            ctypes.POINTER(POINT),
            ctypes.POINTER(SIZE),
            wintypes.HDC,
            ctypes.POINTER(POINT),
            wintypes.COLORREF,
            ctypes.POINTER(BLENDFUNCTION),
            wintypes.DWORD,
        ]
        self.user32.GetDC.restype = wintypes.HDC
        self.user32.GetDC.argtypes = [wintypes.HWND]
        self.user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.DestroyWindow.argtypes = [wintypes.HWND]
        self.gdi32.CreateCompatibleDC.restype = wintypes.HDC
        self.gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        self.gdi32.CreateDIBSection.restype = wintypes.HBITMAP
        self.gdi32.CreateDIBSection.argtypes = [
            wintypes.HDC,
            ctypes.POINTER(BITMAPINFO),
            wintypes.UINT,
            ctypes.POINTER(ctypes.c_void_p),
            wintypes.HANDLE,
            wintypes.DWORD,
        ]
        self.gdi32.SelectObject.restype = wintypes.HGDIOBJ
        self.gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        self.gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        self.gdi32.DeleteDC.argtypes = [wintypes.HDC]

    def clear(self):
        if self.hwnd and self.visible:
            self.user32.ShowWindow(self.hwnd, self.SW_HIDE)
            self.visible = False

    def destroy(self):
        if self.hwnd:
            self.user32.DestroyWindow(self.hwnd)
            self.hwnd = None

    def render_cards(self, cards):
        if not cards:
            self.clear()
            return

        margin = 3
        left = int(min(card["x1"] for card in cards) - margin)
        top = int(min(card["y1"] for card in cards) - margin)
        right = int(max(card["x2"] for card in cards) + margin)
        bottom = int(max(card["y2"] for card in cards) + margin)
        width = max(1, right - left)
        height = max(1, bottom - top)

        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for card in cards:
            x1 = int(card["x1"] - left)
            y1 = int(card["y1"] - top)
            x2 = int(card["x2"] - left)
            y2 = int(card["y2"] - top)
            fill = self._rgba(card.get("fill", "#000000"), card.get("alpha", 180))
            outline = self._rgba(card.get("outline", card.get("fill", "#000000")), card.get("outline_alpha", 230))
            outline_width = int(card.get("outline_width", 0))
            radius = int(card.get("radius", 12))
            draw.rounded_rectangle(
                (x1, y1, x2, y2),
                radius=radius,
                fill=fill,
                outline=outline if outline_width > 0 else None,
                width=outline_width,
            )

            text = card.get("text")
            if text:
                font_size = int(card.get("font_size", 14))
                font = self._font(font_size)
                text_color = self._rgba(card.get("text_fill", "#FFFFFF"), 255)
                draw.text(((x1 + x2) / 2, (y1 + y2) / 2), text, font=font, fill=text_color, anchor="mm")

        self._update_layered_window(left, top, image)

    def render_elements(self, elements):
        if not elements:
            self.clear()
            return

        margin = 8
        bounds = []
        measure_image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        measure_draw = ImageDraw.Draw(measure_image)
        for item in elements:
            if item.get("type") == "line":
                width = int(item.get("width", 1))
                bounds.append((
                    min(item["x1"], item["x2"]) - width,
                    min(item["y1"], item["y2"]) - width,
                    max(item["x1"], item["x2"]) + width,
                    max(item["y1"], item["y2"]) + width,
                ))
            elif item.get("type") == "text":
                font = self._font(int(item.get("font_size", 14)))
                text = item.get("text", "")
                bounds.append(measure_draw.textbbox((item["x"], item["y"]), text, font=font, anchor=item.get("anchor", "lm")))
            elif item.get("type") == "image" and item.get("image") is not None:
                icon_image = item["image"]
                image_w, image_h = icon_image.size
                x = item["x"]
                y = item["y"]
                anchor = item.get("anchor", "mm")
                if anchor == "lt":
                    bounds.append((x, y, x + image_w, y + image_h))
                elif anchor == "lm":
                    bounds.append((x, y - image_h / 2, x + image_w, y + image_h / 2))
                else:
                    bounds.append((x - image_w / 2, y - image_h / 2, x + image_w / 2, y + image_h / 2))

        if not bounds:
            self.clear()
            return

        left = int(min(item[0] for item in bounds) - margin)
        top = int(min(item[1] for item in bounds) - margin)
        right = int(max(item[2] for item in bounds) + margin)
        bottom = int(max(item[3] for item in bounds) + margin)
        width = max(1, right - left)
        height = max(1, bottom - top)

        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for item in elements:
            if item.get("type") == "line":
                fill = self._rgba(item.get("fill", "#FFFFFF"), item.get("alpha", 255))
                draw.line(
                    (item["x1"] - left, item["y1"] - top, item["x2"] - left, item["y2"] - top),
                    fill=fill,
                    width=int(item.get("width", 1)),
                )
            elif item.get("type") == "text":
                font = self._font(int(item.get("font_size", 14)))
                fill = self._rgba(item.get("fill", "#FFFFFF"), item.get("alpha", 153))
                draw.text((item["x"] - left, item["y"] - top), item.get("text", ""), font=font, fill=fill, anchor=item.get("anchor", "lm"))
            elif item.get("type") == "image" and item.get("image") is not None:
                icon_image = item["image"].convert("RGBA")
                alpha = max(0, min(255, int(item.get("alpha", 255))))
                if alpha < 255:
                    image_alpha = icon_image.getchannel("A").point(lambda value: value * alpha // 255)
                    icon_image.putalpha(image_alpha)
                image_w, image_h = icon_image.size
                x = item["x"] - left
                y = item["y"] - top
                anchor = item.get("anchor", "mm")
                if anchor == "lt":
                    paste_x, paste_y = int(x), int(y)
                elif anchor == "lm":
                    paste_x, paste_y = int(x), int(y - image_h / 2)
                else:
                    paste_x, paste_y = int(x - image_w / 2), int(y - image_h / 2)
                image.alpha_composite(icon_image, dest=(paste_x, paste_y))

        self._update_layered_window(left, top, image)

    def _font(self, size):
        if size in self.font_cache:
            return self.font_cache[size]
        fonts_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
        font_path = os.path.join(fonts_dir, "msyhbd.ttc")
        if not os.path.exists(font_path):
            font_path = os.path.join(fonts_dir, "msyh.ttc")
        try:
            font = ImageFont.truetype(font_path, size)
        except Exception:
            font = ImageFont.load_default()
        self.font_cache[size] = font
        return font

    @staticmethod
    def _rgba(hex_color, alpha):
        hex_color = hex_color.lstrip("#")
        return (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
            max(0, min(255, int(alpha))),
        )

    def _update_layered_window(self, left, top, image):
        image = image.convert("RGBA")
        width, height = image.size
        image = self._premultiply_alpha(image)
        bgra = image.tobytes("raw", "BGRA")

        hdc_screen = self.user32.GetDC(None)
        hdc_mem = self.gdi32.CreateCompatibleDC(hdc_screen)
        bits = ctypes.c_void_p()

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = self.BI_RGB

        hbitmap = self.gdi32.CreateDIBSection(
            hdc_screen,
            ctypes.byref(bmi),
            self.DIB_RGB_COLORS,
            ctypes.byref(bits),
            None,
            0,
        )
        if not hbitmap:
            self.gdi32.DeleteDC(hdc_mem)
            self.user32.ReleaseDC(None, hdc_screen)
            raise ctypes.WinError()

        ctypes.memmove(bits, bgra, len(bgra))
        old_bitmap = self.gdi32.SelectObject(hdc_mem, hbitmap)

        dst = POINT(int(left), int(top))
        size = SIZE(width, height)
        src = POINT(0, 0)
        blend = BLENDFUNCTION(self.AC_SRC_OVER, 0, 255, self.AC_SRC_ALPHA)

        self.user32.UpdateLayeredWindow(
            self.hwnd,
            hdc_screen,
            ctypes.byref(dst),
            ctypes.byref(size),
            hdc_mem,
            ctypes.byref(src),
            0,
            ctypes.byref(blend),
            self.ULW_ALPHA,
        )
        self.user32.ShowWindow(self.hwnd, self.SW_SHOWNOACTIVATE)
        self.visible = True

        self.gdi32.SelectObject(hdc_mem, old_bitmap)
        self.gdi32.DeleteObject(hbitmap)
        self.gdi32.DeleteDC(hdc_mem)
        self.user32.ReleaseDC(None, hdc_screen)

    @staticmethod
    def _premultiply_alpha(image):
        r, g, b, a = image.split()
        r = ImageChops.multiply(r, a)
        g = ImageChops.multiply(g, a)
        b = ImageChops.multiply(b, a)
        return Image.merge("RGBA", (r, g, b, a))
